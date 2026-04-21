"""
Feedback loop — uses validation results from previous runs to improve future generation.

Two types of feedback:
  1. Same-domain: previous run of the same domain informs the next run
  2. Cross-domain: ALL previous runs inform generation for any domain
     (e.g., DeFi 7B/14B results improve medical profile generation)

After each generation + validation run, diagnostic data is saved. On the next run,
this module loads ALL diagnostics and adjusts the generation prompts to address
previously identified weaknesses.

Acceptance thresholds:
  - ACCEPTED: 0 FAIL, <=2 MARGINAL, usability >= 2.0/5
  - NEEDS_WORK: 0 FAIL, >2 MARGINAL
  - REJECTED: any FAIL
"""

from __future__ import annotations

import json
import os
from pathlib import Path


# ---------------------------------------------------------------------------
# Acceptance thresholds
# ---------------------------------------------------------------------------

def assess_acceptance(validation_report: dict) -> dict:
    """Determine if a profile meets acceptance thresholds.

    Returns: {
        status: "ACCEPTED" | "NEEDS_WORK" | "REJECTED",
        reason: str,
        fail_checks: [...],
        marginal_checks: [...],
    }
    """
    properties = validation_report.get("properties", {})
    summary = validation_report.get("summary", {})

    fail_checks = [
        name for name, result in properties.items()
        if result.get("verdict") == "FAIL"
    ]
    marginal_checks = [
        name for name, result in properties.items()
        if result.get("verdict") == "MARGINAL"
    ]

    # Check usability specifically
    usability = properties.get("usability", {})
    usability_score = usability.get("avg_score", 5.0)
    usability_verdict = usability.get("verdict", "SKIP")

    if fail_checks:
        status = "REJECTED"
        reason = f"{len(fail_checks)} checks FAIL: {fail_checks}"
    elif len(marginal_checks) > 2:
        status = "NEEDS_WORK"
        reason = f"{len(marginal_checks)} checks MARGINAL (max 2 allowed): {marginal_checks}"
    elif usability_verdict == "FAIL":
        status = "REJECTED"
        reason = f"Usability too low: {usability_score}/5"
    else:
        status = "ACCEPTED"
        reason = f"{summary.get('pass', 0)} PASS, {len(marginal_checks)} MARGINAL"

    return {
        "status": status,
        "reason": reason,
        "fail_checks": fail_checks,
        "marginal_checks": marginal_checks,
        "usability_score": usability_score,
    }


# ---------------------------------------------------------------------------
# Diagnostic storage
# ---------------------------------------------------------------------------

_FEEDBACK_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "domains", "_feedback",
)


def save_diagnostics(
    domain_name: str,
    validation_report: dict,
    generation_meta: dict | None = None,
):
    """Save validation diagnostics for future feedback.

    Stored in domains/_feedback/<domain>_latest.json.
    """
    os.makedirs(_FEEDBACK_DIR, exist_ok=True)
    path = os.path.join(_FEEDBACK_DIR, f"{domain_name}_latest.json")

    diagnostics = {
        "domain": domain_name,
        "acceptance": assess_acceptance(validation_report),
        "summary": validation_report.get("summary", {}),
        "properties": {},
    }

    # Extract actionable diagnostics from each check
    for name, result in validation_report.get("properties", {}).items():
        diag = {"verdict": result.get("verdict", "SKIP")}

        if name == "sensitivity_labels":
            diag["weak_categories"] = [
                cat for cat, data in result.get("categories", {}).items()
                if data.get("coverage", 1.0) < 0.5
            ]
        elif name == "vocabulary_diversity":
            diag["duplicate_count"] = result.get("duplicates_found", 0)
        elif name == "entity_completeness":
            diag["missed_entities"] = result.get("missed_entities", [])[:10]
        elif name == "usability":
            diag["avg_score"] = result.get("avg_score", 0)
            diag["destroyed"] = len(result.get("low_quality_queries", []))
        elif name == "ontology_balance":
            diag["ratio"] = result.get("ratio", 0)
            diag["subdomains"] = result.get("subdomains", {})

        diagnostics["properties"][name] = diag

    if generation_meta:
        diagnostics["generation"] = generation_meta

    with open(path, "w") as f:
        json.dump(diagnostics, f, indent=2)

    return path


def load_diagnostics(domain_name: str) -> dict | None:
    """Load previous diagnostics for a domain. Returns None if not found."""
    path = os.path.join(_FEEDBACK_DIR, f"{domain_name}_latest.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def load_all_diagnostics() -> list[dict]:
    """Load diagnostics from ALL previous runs across all domains.

    Used for cross-domain learning: patterns that failed in DeFi
    generation (e.g., taxonomy consolidation) inform medical generation.
    """
    if not os.path.exists(_FEEDBACK_DIR):
        return []
    results = []
    for fname in sorted(os.listdir(_FEEDBACK_DIR)):
        if fname.endswith("_latest.json"):
            path = os.path.join(_FEEDBACK_DIR, fname)
            try:
                with open(path) as f:
                    results.append(json.load(f))
            except (json.JSONDecodeError, OSError):
                continue
    return results


def aggregate_cross_domain_learnings(all_diagnostics: list[dict]) -> dict:
    """Aggregate learnings from all previous runs into universal adjustments.

    Identifies patterns that recur ACROSS domains — these indicate
    framework-level issues, not domain-specific ones.

    Returns adjustments dict compatible with apply_adjustments_to_prompt().
    """
    if not all_diagnostics:
        return {}

    adjustments = {}

    # Only count an issue as "recurring" if it appears across DIFFERENT domains
    domain_cat_pairs = set()
    for diag in all_diagnostics:
        domain = diag.get("domain", "unknown")
        props = diag.get("properties", {})
        sens = props.get("sensitivity_labels", {})
        for cat in sens.get("weak_categories", []):
            domain_cat_pairs.add((domain, cat))

    # Count categories that are weak in 2+ DIFFERENT domains
    from collections import Counter
    cat_domain_counts = Counter()
    for domain, cat in domain_cat_pairs:
        cat_domain_counts[cat] += 1
    recurring_weak = [cat for cat, count in cat_domain_counts.items() if count >= 2]
    if recurring_weak:
        adjustments["sensitivity_emphasis"] = recurring_weak

    # If vocabulary diversity failed in 2+ runs, add dedup warning
    dedup_fails = sum(
        1 for d in all_diagnostics
        if d.get("properties", {}).get("vocabulary_diversity", {}).get("duplicate_count", 0) > 5
    )
    if dedup_fails >= 2:
        adjustments["dedup_warning"] = True

    # If usability was low across runs, add note
    usability_scores = [
        d.get("properties", {}).get("usability", {}).get("avg_score", 5)
        for d in all_diagnostics
        if d.get("properties", {}).get("usability", {}).get("avg_score") is not None
    ]
    if usability_scores and sum(usability_scores) / len(usability_scores) < 2.5:
        adjustments["usability_note"] = (
            "Previous runs had low usability across domains. "
            "Generate specific, narrow patterns — avoid broad patterns that strip domain terms."
        )

    # Collect all missed entities across runs for awareness
    all_missed = []
    for diag in all_diagnostics:
        props = diag.get("properties", {})
        entity = props.get("entity_completeness", {})
        all_missed.extend(entity.get("missed_entities", []))
    if len(set(all_missed)) > 5:
        adjustments["entity_awareness"] = (
            f"Previous runs missed {len(set(all_missed))} entities across domains. "
            f"Be thorough in entity extraction."
        )

    return adjustments


# ---------------------------------------------------------------------------
# Prompt adjustment based on feedback
# ---------------------------------------------------------------------------

def get_prompt_adjustments(domain_name: str) -> dict:
    """Load previous diagnostics and generate prompt adjustments.

    Merges two sources:
    1. Same-domain feedback (previous run of this domain)
    2. Cross-domain feedback (aggregate learnings from ALL previous runs)

    Returns a dict of adjustments to apply to generation prompts:
    {
        "sensitivity_emphasis": ["timing", "emotional"],
        "dedup_warning": True,
        "entity_hints": ["Tornado Cash", "Flashbots Protect"],
        "usability_note": "...",
    }
    """
    # Start with cross-domain learnings (framework-level)
    all_diag = load_all_diagnostics()
    adjustments = aggregate_cross_domain_learnings(all_diag)

    # Layer same-domain feedback on top (more specific)
    diag = load_diagnostics(domain_name)
    if diag is None:
        return adjustments

    # If sensitivity labels had weak categories, emphasize them
    sens = diag.get("properties", {}).get("sensitivity_labels", {})
    weak_cats = sens.get("weak_categories", [])
    if weak_cats:
        adjustments["sensitivity_emphasis"] = weak_cats

    # If vocabulary had duplicates, add warning
    vocab = diag.get("properties", {}).get("vocabulary_diversity", {})
    if vocab.get("duplicate_count", 0) > 5:
        adjustments["dedup_warning"] = True

    # If entities were missed, provide hints
    entity = diag.get("properties", {}).get("entity_completeness", {})
    missed = entity.get("missed_entities", [])
    if missed:
        adjustments["entity_hints"] = missed[:10]

    # If usability was low, add note
    usability = diag.get("properties", {}).get("usability", {})
    if usability.get("avg_score", 5) < 2.5:
        adjustments["usability_note"] = (
            "Previous run had low usability. "
            "Ensure patterns are specific enough to not strip domain terminology."
        )

    # If ontology was imbalanced, add note
    balance = diag.get("properties", {}).get("ontology_balance", {})
    if balance.get("ratio", 1) < 0.3:
        adjustments["balance_note"] = (
            "Previous run had imbalanced vocabulary. "
            "Ensure all subdomains have similar vocabulary depth."
        )

    return adjustments


def apply_adjustments_to_prompt(base_prompt: str, adjustments: dict) -> str:
    """Append feedback-based adjustments to a generation prompt.

    Non-invasive: adds a "FEEDBACK FROM PREVIOUS RUN" section at the end.
    """
    if not adjustments:
        return base_prompt

    lines = ["\n\nFEEDBACK FROM PREVIOUS RUN (address these issues):"]

    if "sensitivity_emphasis" in adjustments and adjustments["sensitivity_emphasis"]:
        cats = ", ".join(str(c) for c in adjustments["sensitivity_emphasis"])
        lines.append(f"- Pay special attention to these sensitivity categories: {cats}")

    if adjustments.get("dedup_warning"):
        lines.append(
            "- Avoid near-duplicate vocabulary (e.g., 'staking assets' and 'unstaking assets' "
            "are similar — use genuinely distinct terms)"
        )

    if "entity_hints" in adjustments and adjustments["entity_hints"]:
        hints = ", ".join(str(h) for h in adjustments["entity_hints"][:5])
        lines.append(f"- These entities were missed last time — include them: {hints}")

    if "usability_note" in adjustments:
        lines.append(f"- {adjustments['usability_note']}")

    if "balance_note" in adjustments:
        lines.append(f"- {adjustments['balance_note']}")

    if "entity_awareness" in adjustments:
        lines.append(f"- {adjustments['entity_awareness']}")

    return base_prompt + "\n".join(lines)
