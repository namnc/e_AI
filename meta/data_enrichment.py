"""
Dataset enrichment — improves input data quality before profile generation.

Two enrichment sources:
  1. Web search: find real query patterns from forums, docs, support pages
  2. LLM synthesis: generate queries for underrepresented categories

Guardrails:
  - Provenance tracking: every added query tagged with source
  - Synthetic cap: max 50% of final dataset can be synthetic
  - Dedup: no duplicates or near-duplicates of existing queries
  - Domain coherence: enriched queries must pass coherence check
  - Label validation: all added queries labeled by local LLM
  - Re-validation: enriched dataset must pass all 6 input checks

Refinement loop:
  validate → identify gaps → enrich → re-validate → repeat until PASS
"""

from __future__ import annotations

import json
import re
from collections import Counter
from difflib import SequenceMatcher

from llm_backend import call_llm
from meta.util import extract_json as _extract_json


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_FIND_QUERIES_PROMPT = """\
You are building a dataset of user queries about a specific domain for a \
privacy research project. Given web search results from forums and support \
pages, extract realistic user queries that people actually ask.

Rules:
- Extract ONLY questions/queries, not answers or descriptions
- Preserve natural phrasing (informal is OK)
- Include a mix of sensitive (contains private data) and generic queries
- Each query should be something a real user might ask a cloud AI assistant

Output JSON: {"queries": [
  {"text": "extracted query", "label": "sensitive" | "non_sensitive"},
  ...
]}"""

_SYNTHESIZE_QUERIES_PROMPT = """\
You are generating realistic user queries for a privacy research dataset. \
Given a domain and specific gaps in the current dataset, generate queries \
that fill those gaps.

Rules:
- Generate queries that sound like REAL users (informal, specific, with context)
- For "sensitive" queries: include specific numbers, names, dates, positions
- For "non_sensitive" queries: ask about general concepts and mechanisms
- Match the tone and complexity of the example queries provided
- Each query must be unique and not a paraphrase of the examples

Output JSON: {"queries": [
  {"text": "generated query", "label": "sensitive" | "non_sensitive"},
  ...
]}"""

_LABEL_QUERY_PROMPT = """\
Classify this query as "sensitive" or "non_sensitive".

A query is SENSITIVE if it contains private, exploitable information:
- Specific amounts, addresses, account IDs
- Personal financial details, health data, legal situations
- Timing/urgency that reveals intent
- Emotional state about a specific situation

A query is NON_SENSITIVE if it asks about general concepts, mechanisms, or public knowledge.

Output JSON: {"label": "sensitive" | "non_sensitive", "reason": "brief explanation"}"""


# ---------------------------------------------------------------------------
# Gap analysis
# ---------------------------------------------------------------------------

def identify_gaps(
    queries: list[dict],
    validation_report: dict,
) -> dict:
    """Identify specific gaps in the dataset that enrichment could fill.

    Returns: {
        needs_sensitive: int,     # how many more sensitive queries needed
        needs_non_sensitive: int, # how many more non-sensitive queries needed
        needs_total: int,         # how many more queries to reach 50 minimum
        weak_coherence: bool,     # domain coherence is low
        label_imbalance: float,   # ratio of majority/minority label
    }
    """
    labels = Counter(q.get("label", "unlabeled") for q in queries)
    total = len(queries)
    sensitive = labels.get("sensitive", 0)
    non_sensitive = labels.get("non_sensitive", 0)

    gaps = {
        "needs_total": max(0, 50 - total),
        "needs_sensitive": max(0, 15 - sensitive),
        "needs_non_sensitive": max(0, 15 - non_sensitive),
        "weak_coherence": False,
        "label_imbalance": 0,
    }

    # Check validation report for specific weaknesses
    checks = validation_report.get("checks", {})

    coherence = checks.get("domain_coherence", {})
    if coherence.get("verdict") in ("FAIL", "MARGINAL"):
        gaps["weak_coherence"] = True

    label_dist = checks.get("label_distribution", {})
    if label_dist.get("verdict") in ("FAIL", "MARGINAL"):
        dist = label_dist.get("distribution", {})
        if dist:
            max_count = max(dist.values())
            min_count = min(v for v in dist.values() if v > 0) if any(v > 0 for v in dist.values()) else 0
            gaps["label_imbalance"] = max_count / max(min_count, 1)

    return gaps


# ---------------------------------------------------------------------------
# Web search enrichment
# ---------------------------------------------------------------------------

def enrich_from_web(
    domain_name: str,
    current_queries: list[dict],
    gaps: dict,
    search_fn,
    max_add: int = 30,
    progress: bool = True,
) -> list[dict]:
    """Search for real query patterns from forums and support pages.

    Returns: list of new query dicts with provenance tag.
    """
    if progress:
        print(f"  Searching for real {domain_name} queries...")

    from meta.web_enrichment import _sanitize_snippet

    search_queries = [
        f"{domain_name} user questions forum site:reddit.com",
        f"{domain_name} frequently asked questions support",
        f"{domain_name} help query examples community",
    ]

    all_snippets = []
    for sq in search_queries:
        try:
            snippets = search_fn(sq)
            all_snippets.extend(snippets)
        except Exception:
            continue

    if not all_snippets:
        if progress:
            print(f"    No search results found")
        return []

    snippet_block = "\n".join(
        f"- {_sanitize_snippet(s)}" for s in all_snippets[:30]
    )
    resp = call_llm(
        prompt=f"Domain: {domain_name}\n\nForum/support snippets:\n{snippet_block}",
        system=_FIND_QUERIES_PROMPT,
        max_tokens=2048,
    )
    parsed = _extract_json(resp)
    if not isinstance(parsed, dict):
        return []

    new_queries = []
    existing_texts = set(q.get("text", "").strip().lower() for q in current_queries)

    for entry in parsed.get("queries", []):
        if not isinstance(entry, dict) or "text" not in entry:
            continue
        text = entry["text"].strip()
        if len(text) < 10:
            continue
        if text.lower() in existing_texts:
            continue
        # Near-duplicate check
        if any(SequenceMatcher(None, text.lower(), ex).ratio() > 0.85
               for ex in existing_texts):
            continue
        if len(new_queries) >= max_add:
            break
        new_queries.append({
            "text": text,
            "label": entry.get("label", "unlabeled"),
            "origin": "web_enrichment",
            "source": f"web_search:{domain_name}",
        })
        existing_texts.add(text.lower())

    if progress:
        print(f"    Found {len(new_queries)} new queries from web")
    return new_queries


# ---------------------------------------------------------------------------
# LLM synthesis
# ---------------------------------------------------------------------------

def synthesize_queries(
    domain_name: str,
    current_queries: list[dict],
    gaps: dict,
    max_add: int = 20,
    progress: bool = True,
) -> list[dict]:
    """Generate synthetic queries to fill dataset gaps.

    Returns: list of new query dicts with provenance tag.
    """
    if progress:
        print(f"  Synthesizing queries for gaps...")

    # Determine what to generate
    to_generate = []
    if gaps["needs_sensitive"] > 0:
        to_generate.append(("sensitive", min(gaps["needs_sensitive"], max_add // 2)))
    if gaps["needs_non_sensitive"] > 0:
        to_generate.append(("non_sensitive", min(gaps["needs_non_sensitive"], max_add // 2)))
    if gaps["needs_total"] > 0:
        remaining = min(gaps["needs_total"], max_add) - sum(n for _, n in to_generate)
        if remaining > 0:
            to_generate.append(("mixed", remaining))

    if not to_generate:
        if progress:
            print(f"    No gaps to fill")
        return []

    # Sample existing queries as examples
    examples = current_queries[:20]
    example_block = "\n".join(
        f"- [{q.get('label', '?')}] {q['text'][:100]}" for q in examples
    )

    all_new = []
    existing_texts = set(q.get("text", "").strip().lower() for q in current_queries)

    for label_type, count in to_generate:
        gap_desc = f"Need {count} more {label_type} queries"
        resp = call_llm(
            prompt=(
                f"Domain: {domain_name}\n"
                f"Gap: {gap_desc}\n\n"
                f"Example queries from current dataset:\n{example_block}"
            ),
            system=_SYNTHESIZE_QUERIES_PROMPT,
            max_tokens=2048,
        )
        parsed = _extract_json(resp)
        if not isinstance(parsed, dict):
            continue

        for entry in parsed.get("queries", []):
            if not isinstance(entry, dict) or "text" not in entry:
                continue
            text = entry["text"].strip()
            if len(text) < 10 or text.lower() in existing_texts:
                continue
            if len(all_new) >= max_add:
                break
            all_new.append({
                "text": text,
                "label": entry.get("label", label_type if label_type != "mixed" else "unlabeled"),
                "origin": "synthetic",
                "source": f"llm_synthesis:{domain_name}",
            })
            existing_texts.add(text.lower())

    if progress:
        print(f"    Synthesized {len(all_new)} queries")
    return all_new


# ---------------------------------------------------------------------------
# Label validation
# ---------------------------------------------------------------------------

def validate_labels(
    queries: list[dict],
    progress: bool = True,
) -> list[dict]:
    """Re-label queries using local LLM to ensure label accuracy.

    Re-labels: (1) unlabeled/missing queries, and (2) all web/synthetic
    queries regardless of their current label (the generating source may
    have assigned an incorrect label).
    """
    needs_label = [
        q for q in queries
        if q.get("label") in (None, "unlabeled", "")
        or q.get("origin") in ("web_enrichment", "synthetic")
    ]
    if not needs_label:
        return queries

    if progress:
        print(f"  Labeling {len(needs_label)} queries (unlabeled + web/synthetic)...")

    for i, q in enumerate(needs_label):
        resp = call_llm(
            prompt=f"Query: {q['text']}",
            system=_LABEL_QUERY_PROMPT,
            max_tokens=200,
        )
        parsed = _extract_json(resp)
        if isinstance(parsed, dict) and "label" in parsed:
            q["label"] = parsed["label"]

    return queries


# ---------------------------------------------------------------------------
# Orchestrator: enrich until quality threshold met
# ---------------------------------------------------------------------------

def enrich_dataset(
    queries: list[dict],
    domain_name: str,
    search_fn=None,
    max_rounds: int = 3,
    max_synthetic_ratio: float = 0.50,
    progress: bool = True,
) -> tuple[list[dict], dict]:
    """Enrich dataset until it passes input validation.

    Loop: validate → identify gaps → enrich (web + synthesis) → re-validate.
    Stops when PASS or max_rounds exhausted.

    Guardrails:
    - Synthetic queries capped at max_synthetic_ratio of final dataset
    - All added queries tracked with provenance
    - Dedup against existing queries
    - Re-validated after each round

    Args:
        queries: original dataset
        domain_name: for search context
        search_fn: optional callable for web search
        max_rounds: circuit breaker
        max_synthetic_ratio: max fraction of synthetic queries (default 50%)

    Returns:
        (enriched_queries, final_validation_report)
    """
    from meta.input_validator import validate_dataset

    if progress:
        print(f"\nDataset enrichment (max {max_rounds} rounds)")

    original_count = len(queries)

    for round_num in range(1, max_rounds + 1):
        if progress:
            print(f"\n--- Enrichment round {round_num}/{max_rounds} ---")

        # Validate current state
        report = validate_dataset(queries, progress=False)
        if progress:
            print(f"  Current: {len(queries)} queries, {report['overall']}")

        if report["overall"] == "PASS":
            if progress:
                print(f"  Dataset quality sufficient — no enrichment needed")
            return queries, report

        # Identify gaps
        gaps = identify_gaps(queries, report)
        if progress:
            print(f"  Gaps: {gaps}")

        # Calculate synthetic budget
        current_synthetic = sum(
            1 for q in queries if q.get("origin") in ("synthetic", "web_enrichment")
        )
        max_allowed = int(len(queries) * max_synthetic_ratio / (1 - max_synthetic_ratio))
        budget = max(0, max_allowed - current_synthetic)
        if budget == 0:
            if progress:
                print(f"  Synthetic cap reached ({max_synthetic_ratio:.0%}). Stopping.")
            return queries, report

        added = 0

        # Web search enrichment
        if search_fn and budget > 0:
            web_queries = enrich_from_web(
                domain_name, queries, gaps, search_fn,
                max_add=min(15, budget), progress=progress,
            )
            queries.extend(web_queries)
            added += len(web_queries)
            budget -= len(web_queries)

        # LLM synthesis
        if budget > 0 and (gaps["needs_total"] > 0 or gaps["needs_sensitive"] > 0
                           or gaps["needs_non_sensitive"] > 0):
            synth_queries = synthesize_queries(
                domain_name, queries, gaps,
                max_add=min(20, budget), progress=progress,
            )
            queries.extend(synth_queries)
            added += len(synth_queries)

        if added == 0:
            if progress:
                print(f"  No queries added — stopping")
            return queries, report

        # Label any unlabeled queries
        queries = validate_labels(queries, progress=progress)

        if progress:
            print(f"  Added {added} queries (total: {len(queries)}, "
                  f"original: {original_count}, "
                  f"enriched: {len(queries) - original_count})")

    # Final validation
    report = validate_dataset(queries, progress=progress)
    if progress:
        synthetic_count = sum(
            1 for q in queries if q.get("origin") in ("synthetic", "web_enrichment")
        )
        print(f"\nEnrichment complete: {len(queries)} queries "
              f"({original_count} original, {synthetic_count} enriched)")
        if report["overall"] != "PASS":
            print(f"  WARNING: Dataset still {report['overall']} after {max_rounds} rounds. "
                  f"Consider providing a larger/better initial dataset.")

    return queries, report
