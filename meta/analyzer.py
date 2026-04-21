"""
Domain analyzer — Phase 1 of the meta-framework pipeline.

Given a JSONL dataset, uses a local LLM to:
  1. Extract sensitive spans from each query
  2. Cluster queries into subdomains
  3. Extract vocabulary for each subdomain
  4. Extract question templates

Output: a partial DomainProfile dict (meta, subdomains, templates, sensitive spans).
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from llm_backend import call_llm
from meta.prompts import (
    SENSITIVITY_EXTRACTION,
    SUBDOMAIN_CLASSIFICATION,
    SUBDOMAIN_CONSOLIDATION,
    VOCABULARY_EXTRACTION,
    TEMPLATE_EXTRACTION,
)


def _extract_json(text: str) -> dict | list | None:
    """Extract the first JSON object or array from LLM output."""
    for start_char, end_char in [('{', '}'), ('[', ']')]:
        start = text.find(start_char)
        if start == -1:
            continue
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == '\\':
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == start_char:
                depth += 1
            elif ch == end_char:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break
    return None


def load_dataset(path: str) -> list[dict]:
    """Load a JSONL dataset. Each line must have at least 'text' field."""
    queries = []
    with open(path) as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                print(f"  [warn] Skipping malformed line {line_num}", file=sys.stderr)
                continue
            if "text" not in entry:
                print(f"  [warn] Line {line_num} missing 'text' field", file=sys.stderr)
                continue
            queries.append(entry)
    return queries


# ---------------------------------------------------------------------------
# Step 1: Sensitivity extraction
# ---------------------------------------------------------------------------

def extract_sensitive_spans(queries: list[dict], progress: bool = True) -> list[dict]:
    """For each query, identify sensitive spans via LLM.

    Returns list of dicts: {text, label, spans: [{span, category, reason}]}
    """
    results = []
    total = len(queries)
    for i, entry in enumerate(queries):
        if progress and (i + 1) % 10 == 0:
            print(f"  Sensitivity extraction: {i + 1}/{total}")
        text = entry["text"]
        resp = call_llm(
            prompt=f"Query: {text}",
            system=SENSITIVITY_EXTRACTION,
            max_tokens=1024,
        )
        parsed = _extract_json(resp)
        spans = parsed.get("spans", []) if isinstance(parsed, dict) else []
        results.append({
            "text": text,
            "label": entry.get("label", "unknown"),
            "spans": spans,
        })
    return results


# ---------------------------------------------------------------------------
# Step 2: Subdomain clustering
# ---------------------------------------------------------------------------

def cluster_subdomains(queries: list[dict], progress: bool = True) -> dict:
    """Classify queries into subdomains, then consolidate taxonomy.

    Returns: {
        "taxonomy": {original_label: consolidated_label},
        "assignments": [{text, subdomain}],
        "distribution": {subdomain: count},
    }
    """
    # Step 2a: classify each query
    raw_labels = []
    total = len(queries)
    for i, entry in enumerate(queries):
        if progress and (i + 1) % 10 == 0:
            print(f"  Subdomain classification: {i + 1}/{total}")
        text = entry["text"]
        resp = call_llm(
            prompt=f"Query: {text}",
            system=SUBDOMAIN_CLASSIFICATION,
            max_tokens=256,
        )
        parsed = _extract_json(resp)
        label = parsed.get("subdomain", "general") if isinstance(parsed, dict) else "general"
        raw_labels.append({"text": text, "raw_label": label})

    # Step 2b: consolidate taxonomy
    unique_labels = sorted(set(r["raw_label"] for r in raw_labels))
    if len(unique_labels) <= 8:
        # Already a clean taxonomy
        taxonomy = {l: l for l in unique_labels}
        descriptions = {}
    else:
        label_counts = Counter(r["raw_label"] for r in raw_labels)
        label_summary = ", ".join(f'"{l}" ({c})' for l, c in label_counts.most_common())
        resp = call_llm(
            prompt=f"Labels with counts: {label_summary}",
            system=SUBDOMAIN_CONSOLIDATION,
            max_tokens=1024,
        )
        parsed = _extract_json(resp)
        if isinstance(parsed, dict):
            taxonomy = parsed.get("taxonomy", {l: l for l in unique_labels})
            descriptions = parsed.get("subdomain_descriptions", {})
        else:
            taxonomy = {l: l for l in unique_labels}
            descriptions = {}

    # Apply taxonomy
    assignments = []
    distribution = Counter()
    for r in raw_labels:
        consolidated = taxonomy.get(r["raw_label"], r["raw_label"])
        assignments.append({"text": r["text"], "subdomain": consolidated})
        distribution[consolidated] += 1

    return {
        "taxonomy": taxonomy,
        "descriptions": descriptions,
        "assignments": assignments,
        "distribution": dict(distribution),
    }


# ---------------------------------------------------------------------------
# Step 3: Vocabulary extraction
# ---------------------------------------------------------------------------

def extract_vocabulary(
    assignments: list[dict],
    distribution: dict[str, int],
    progress: bool = True,
) -> dict[str, dict]:
    """Extract vocabulary for each subdomain via LLM.

    Returns: {subdomain: {entities: [...], mechanisms: [...], ...}}
    """
    # Group queries by subdomain
    by_subdomain: dict[str, list[str]] = defaultdict(list)
    for a in assignments:
        by_subdomain[a["subdomain"]].append(a["text"])

    subdomains = {}
    total = len(by_subdomain)
    for idx, (subdomain, queries) in enumerate(sorted(by_subdomain.items())):
        if progress:
            print(f"  Vocabulary extraction: {subdomain} ({idx + 1}/{total})")

        # Sample up to 30 queries for context
        sample = queries[:30]
        query_block = "\n".join(f"- {q}" for q in sample)

        resp = call_llm(
            prompt=f"Subdomain: {subdomain}\n\nExample queries:\n{query_block}",
            system=VOCABULARY_EXTRACTION,
            max_tokens=2048,
        )
        parsed = _extract_json(resp)
        if isinstance(parsed, dict):
            onto = {}
            for key in ["entities", "mechanisms", "operations", "triggers",
                        "metrics", "actors", "risk_concepts", "generic_refs"]:
                onto[key] = parsed.get(key, [])
            # Ensure minimum vocabulary depth
            for key, items in onto.items():
                if len(items) < 3:
                    print(f"    [warn] {subdomain}.{key} has only {len(items)} items")
        else:
            onto = {k: [] for k in ["entities", "mechanisms", "operations",
                                     "triggers", "metrics", "actors",
                                     "risk_concepts", "generic_refs"]}

        # Use ontology key "protocols" for backward compatibility
        onto["protocols"] = onto.pop("entities", [])

        # Compute frequency
        total_queries = sum(distribution.values())
        freq = distribution.get(subdomain, 0) / max(total_queries, 1)
        onto["_frequency"] = round(freq, 4)

        subdomains[subdomain] = onto

    return subdomains


# ---------------------------------------------------------------------------
# Step 4: Template extraction
# ---------------------------------------------------------------------------

def extract_templates(queries: list[dict], progress: bool = True) -> list[str]:
    """Extract question templates from the dataset via LLM.

    Returns: list of template strings with {SLOT} placeholders.
    """
    if progress:
        print("  Template extraction...")

    # Sample diverse queries
    sample = queries[:50]
    query_block = "\n".join(f"- {q['text']}" for q in sample)

    resp = call_llm(
        prompt=f"Example queries:\n{query_block}",
        system=TEMPLATE_EXTRACTION,
        max_tokens=2048,
    )
    parsed = _extract_json(resp)
    templates = []
    if isinstance(parsed, dict):
        templates = parsed.get("templates", [])
    elif isinstance(parsed, list):
        templates = parsed

    # Validate templates have slots
    valid = []
    for t in templates:
        if isinstance(t, str) and "{" in t and t.strip().endswith("?"):
            valid.append(t)
        else:
            print(f"    [warn] Dropping invalid template: {t!r}")

    if len(valid) < 10:
        print(f"    [warn] Only {len(valid)} valid templates (target: 15-25)")

    return valid


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def analyze_dataset(
    dataset_path: str,
    domain_name: str,
    progress: bool = True,
) -> dict:
    """Run the full Phase 1 analysis pipeline.

    Returns a partial profile dict with:
      - meta
      - subdomains (with vocabulary)
      - templates
      - _analysis (raw analysis data for Phase 2)
    """
    print(f"Phase 1: Analyzing dataset ({dataset_path})")
    queries = load_dataset(dataset_path)
    print(f"  Loaded {len(queries)} queries")

    if len(queries) < 20:
        print(f"  [warn] Very small dataset ({len(queries)} queries). "
              f"Results will be thin. Recommend 200+.")

    # Step 1: sensitivity extraction
    print("\nStep 1: Extracting sensitive spans...")
    span_results = extract_sensitive_spans(queries, progress=progress)

    # Step 2: subdomain clustering
    print("\nStep 2: Clustering subdomains...")
    cluster_results = cluster_subdomains(queries, progress=progress)
    print(f"  Found {len(cluster_results['distribution'])} subdomains: "
          f"{cluster_results['distribution']}")

    # Step 3: vocabulary extraction
    print("\nStep 3: Extracting vocabulary per subdomain...")
    subdomains = extract_vocabulary(
        cluster_results["assignments"],
        cluster_results["distribution"],
        progress=progress,
    )

    # Step 4: template extraction
    print("\nStep 4: Extracting templates...")
    templates = extract_templates(queries, progress=progress)
    print(f"  Extracted {len(templates)} templates")

    # Build domain distribution and top domains
    total_q = sum(cluster_results["distribution"].values())
    domain_distribution = {
        sd: round(count / max(total_q, 1), 2)
        for sd, count in sorted(
            cluster_results["distribution"].items(),
            key=lambda x: -x[1],
        )
    }
    # Top domains: those covering >= 10% of queries (up to 6)
    top_domains = [
        sd for sd, freq in domain_distribution.items()
        if freq >= 0.10
    ][:6]
    if len(top_domains) < 2:
        top_domains = list(domain_distribution.keys())[:4]

    # Clean subdomains: remove internal _frequency key
    for sd_data in subdomains.values():
        sd_data.pop("_frequency", None)

    profile = {
        "meta": {
            "domain_name": domain_name,
            "version": "0.1.0",
            "generated_by": "meta/analyzer.py",
            "validation_status": "draft",
        },
        "domain_distribution": domain_distribution,
        "top_domains": top_domains,
        "subdomains": subdomains,
        "templates": templates,
        # Raw analysis data for Phase 2 (not persisted in final profile)
        "_analysis": {
            "span_results": span_results,
            "cluster_results": cluster_results,
        },
    }

    print(f"\nPhase 1 complete. Profile draft has "
          f"{len(subdomains)} subdomains, {len(templates)} templates.")
    return profile
