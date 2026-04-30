"""
Validation engine for transaction risk profiles.

Adapted from e_AI's 13-property validation engine. Checks profile quality
with traffic-light verdicts (PASS / MARGINAL / FAIL).

Transaction profile properties:
  Functional (F1-F5):
    1. Heuristic coverage: all known heuristics have detection signals
    2. Recommendation coverage: every heuristic has at least one actionable recommendation
    3. Skill completeness: every referenced skill is defined with parameters
    4. Confidence calibration: signal confidences are distributed, not all 0.95
    5. Benchmark coverage: every heuristic has a benchmark scenario

  Security (S1-S3):
    6. Adversary model completeness: capabilities and limitations defined
    7. Severity consistency: critical heuristics have high-confidence signals
    8. Fundamental limitations documented: heuristics with irreducible constraints noted

  Quality (Q1-Q3):
    9.  Vocabulary depth: descriptions are specific, not generic
    10. Template coverage: output templates exist for all output types
    11. Profile balance: heuristics are balanced in depth (no stub entries)
"""

from __future__ import annotations

import json
from pathlib import Path


def validate_profile(profile: dict) -> dict:
    """Run all validation checks. Returns traffic-light report."""
    results = {}

    results["F1_heuristic_coverage"] = _check_heuristic_coverage(profile)
    results["F2_recommendation_coverage"] = _check_recommendation_coverage(profile)
    results["F3_skill_completeness"] = _check_skill_completeness(profile)
    results["F4_confidence_calibration"] = _check_confidence_calibration(profile)
    results["F5_benchmark_coverage"] = _check_benchmark_coverage(profile)
    results["S1_adversary_model"] = _check_adversary_model(profile)
    results["S2_severity_consistency"] = _check_severity_consistency(profile)
    results["S3_fundamental_limitations"] = _check_fundamental_limitations(profile)
    results["Q1_vocabulary_depth"] = _check_vocabulary_depth(profile)
    results["Q2_template_coverage"] = _check_template_coverage(profile)
    results["Q3_profile_balance"] = _check_profile_balance(profile)

    # Overall verdict
    verdicts = [r["verdict"] for r in results.values()]
    if any(v == "FAIL" for v in verdicts):
        results["overall"] = "FAIL"
    elif any(v == "MARGINAL" for v in verdicts):
        results["overall"] = "MARGINAL"
    else:
        results["overall"] = "PASS"

    return results


def print_report(results: dict):
    """Print a human-readable validation report."""
    print("=" * 60)
    print("Transaction Profile Validation Report")
    print("=" * 60)
    for key, val in results.items():
        if key == "overall":
            continue
        verdict = val["verdict"]
        icon = {"PASS": "+", "MARGINAL": "~", "FAIL": "!"}[verdict]
        print(f"  [{icon}] {key}: {verdict}")
        if val.get("detail"):
            print(f"      {val['detail']}")
    print("-" * 60)
    print(f"  Overall: {results['overall']}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Functional checks
# ---------------------------------------------------------------------------

def _check_heuristic_coverage(profile: dict) -> dict:
    """F1: All heuristics have detection signals with data requirements."""
    heuristics = profile.get("heuristics", {})
    total = len(heuristics)
    covered = 0
    missing = []

    for hname, h in heuristics.items():
        signals = h.get("detection", {}).get("signals", [])
        if signals and all(s.get("data_needed") for s in signals):
            covered += 1
        else:
            missing.append(hname)

    rate = covered / max(total, 1)
    if rate >= 1.0:
        verdict = "PASS"
    elif rate >= 0.8:
        verdict = "MARGINAL"
    else:
        verdict = "FAIL"

    return {"verdict": verdict, "covered": covered, "total": total,
            "detail": f"{covered}/{total} heuristics fully covered" +
                      (f". Missing: {missing}" if missing else "")}


def _check_recommendation_coverage(profile: dict) -> dict:
    """F2: Every heuristic has at least one recommendation with effectiveness > 0."""
    heuristics = profile.get("heuristics", {})
    total = len(heuristics)
    covered = 0

    for hname, h in heuristics.items():
        recs = h.get("recommendations", [])
        if recs and any(r.get("effectiveness", 0) > 0 for r in recs):
            covered += 1

    rate = covered / max(total, 1)
    verdict = "PASS" if rate >= 1.0 else ("MARGINAL" if rate >= 0.8 else "FAIL")
    return {"verdict": verdict, "detail": f"{covered}/{total} heuristics have actionable recommendations"}


def _check_skill_completeness(profile: dict) -> dict:
    """F3: Every referenced skill has a definition with parameters."""
    skills = profile.get("skills", {})
    referenced = set()
    for h in profile.get("heuristics", {}).values():
        for rec in h.get("recommendations", []):
            s = rec.get("skill_required")
            if s:
                referenced.add(s)

    defined = set(skills.keys())
    missing = referenced - defined
    no_params = [s for s, v in skills.items() if not v.get("parameters")]

    if not missing and not no_params:
        verdict = "PASS"
    elif not missing:
        verdict = "MARGINAL"
    else:
        verdict = "FAIL"

    detail = f"{len(defined)} skills defined, {len(referenced)} referenced"
    if missing:
        detail += f". Missing: {missing}"
    if no_params:
        detail += f". No params: {no_params}"
    return {"verdict": verdict, "detail": detail}


def _check_confidence_calibration(profile: dict) -> dict:
    """F4: Signal confidences are distributed, not all the same value."""
    confidences = []
    for h in profile.get("heuristics", {}).values():
        for s in h.get("detection", {}).get("signals", []):
            confidences.append(s.get("confidence", 0))

    if not confidences:
        return {"verdict": "FAIL", "detail": "No confidence scores found"}

    unique = len(set(confidences))
    if unique >= 4:
        verdict = "PASS"
    elif unique >= 2:
        verdict = "MARGINAL"
    else:
        verdict = "FAIL"

    return {"verdict": verdict, "detail": f"{unique} unique confidence values across {len(confidences)} signals"}


def _check_benchmark_coverage(profile: dict) -> dict:
    """F5: Every heuristic has a benchmark scenario."""
    heuristics = profile.get("heuristics", {})
    total = len(heuristics)
    covered = sum(1 for h in heuristics.values() if h.get("benchmark_scenario"))

    rate = covered / max(total, 1)
    verdict = "PASS" if rate >= 1.0 else ("MARGINAL" if rate >= 0.8 else "FAIL")
    return {"verdict": verdict, "detail": f"{covered}/{total} heuristics have benchmark scenarios"}


# ---------------------------------------------------------------------------
# Security checks
# ---------------------------------------------------------------------------

def _check_adversary_model(profile: dict) -> dict:
    """S1: Adversary model has both capabilities and limitations."""
    adv = profile.get("risk_domain", {}).get("adversary_model", {})
    caps = adv.get("capabilities", [])
    lims = adv.get("limitations", [])

    if caps and lims and len(caps) >= 3:
        verdict = "PASS"
    elif caps and lims:
        verdict = "MARGINAL"
    else:
        verdict = "FAIL"

    return {"verdict": verdict, "detail": f"{len(caps)} capabilities, {len(lims)} limitations"}


def _check_severity_consistency(profile: dict) -> dict:
    """S2: Critical heuristics have at least one high-confidence signal (>0.8)."""
    issues = []
    for hname, h in profile.get("heuristics", {}).items():
        if h.get("severity") == "critical":
            signals = h.get("detection", {}).get("signals", [])
            max_conf = max((s.get("confidence", 0) for s in signals), default=0)
            if max_conf < 0.8:
                issues.append(f"{hname} (max confidence: {max_conf})")

    if not issues:
        verdict = "PASS"
    else:
        verdict = "FAIL"

    return {"verdict": verdict, "detail": f"Issues: {issues}" if issues else "All critical heuristics have high-confidence signals"}


def _check_fundamental_limitations(profile: dict) -> dict:
    """S3: Heuristics that can't be fully mitigated document this."""
    documented = 0
    total_critical = 0
    for h in profile.get("heuristics", {}).values():
        if h.get("severity") in ("critical", "high"):
            total_critical += 1
            if h.get("fundamental_limitation"):
                documented += 1

    if total_critical == 0:
        return {"verdict": "PASS", "detail": "No critical/high heuristics"}

    rate = documented / total_critical
    verdict = "PASS" if rate >= 0.5 else ("MARGINAL" if rate >= 0.25 else "FAIL")
    return {"verdict": verdict, "detail": f"{documented}/{total_critical} critical/high heuristics document limitations"}


# ---------------------------------------------------------------------------
# Quality checks
# ---------------------------------------------------------------------------

def _check_vocabulary_depth(profile: dict) -> dict:
    """Q1: Descriptions are specific (>20 chars) not generic stubs."""
    short_descs = []
    for hname, h in profile.get("heuristics", {}).items():
        desc = h.get("description", "")
        if len(desc) < 20:
            short_descs.append(hname)

    if not short_descs:
        verdict = "PASS"
    elif len(short_descs) <= 1:
        verdict = "MARGINAL"
    else:
        verdict = "FAIL"

    return {"verdict": verdict, "detail": f"Short descriptions: {short_descs}" if short_descs else "All descriptions are substantive"}


def _check_template_coverage(profile: dict) -> dict:
    """Q2: Output templates exist for risk_assessment, summary, skill_suggestion."""
    templates = profile.get("templates", {})
    expected = {"risk_assessment", "summary", "skill_suggestion"}
    present = set(templates.keys()) & expected
    missing = expected - present

    if not missing:
        verdict = "PASS"
    elif len(missing) == 1:
        verdict = "MARGINAL"
    else:
        verdict = "FAIL"

    return {"verdict": verdict, "detail": f"Templates: {present}" + (f". Missing: {missing}" if missing else "")}


def _check_profile_balance(profile: dict) -> dict:
    """Q3: Heuristics are balanced in depth (signals per heuristic)."""
    signal_counts = []
    for h in profile.get("heuristics", {}).values():
        signals = h.get("detection", {}).get("signals", [])
        signal_counts.append(len(signals))

    if not signal_counts:
        return {"verdict": "FAIL", "detail": "No heuristics"}

    min_s = min(signal_counts)
    max_s = max(signal_counts)

    if max_s <= 2 * min_s + 1:
        verdict = "PASS"
    elif max_s <= 3 * min_s + 1:
        verdict = "MARGINAL"
    else:
        verdict = "FAIL"

    return {"verdict": verdict, "detail": f"Signals per heuristic: min={min_s}, max={max_s}"}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m meta.validation_engine <profile.json>")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        profile = json.load(f)

    results = validate_profile(profile)
    print_report(results)
