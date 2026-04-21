"""
Pattern generator — Phase 2a of the meta-framework pipeline.

Given the analysis from Phase 1, uses a local LLM to generate:
  - Regex sanitizer patterns for each category of sensitive spans
  - False positive word lists
  - Entity name lists with generic replacements
  - Normalization config

Output: the sensitive_patterns and normalization sections of a DomainProfile.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict

from llm_backend import call_llm
from meta.prompts import PATTERN_GENERATION, ENTITY_EXTRACTION


def _extract_json(text: str) -> dict | list | None:
    """Extract first JSON object/array from LLM output."""
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


def _validate_regex(pattern: str) -> bool:
    """Check if a regex pattern compiles without error."""
    try:
        re.compile(pattern)
        return True
    except re.error:
        return False


# ---------------------------------------------------------------------------
# Span grouping
# ---------------------------------------------------------------------------

def _group_spans_by_category(span_results: list[dict]) -> dict[str, list[str]]:
    """Group extracted sensitive spans by category.

    Returns: {category: [span1, span2, ...]}
    """
    groups: dict[str, list[str]] = defaultdict(list)
    for entry in span_results:
        for span_info in entry.get("spans", []):
            cat = span_info.get("category", "unknown")
            text = span_info.get("span", "")
            if text:
                groups[cat].append(text)
    return dict(groups)


# ---------------------------------------------------------------------------
# Pattern generation via LLM
# ---------------------------------------------------------------------------

def generate_patterns(
    span_results: list[dict],
    progress: bool = True,
) -> dict:
    """Generate regex patterns from observed sensitive spans.

    Returns the sensitive_patterns section of a DomainProfile.
    """
    if progress:
        print("  Generating sanitizer patterns...")

    grouped = _group_spans_by_category(span_results)
    if progress:
        print(f"  Found {len(grouped)} span categories: {list(grouped.keys())}")
        for cat, spans in grouped.items():
            print(f"    {cat}: {len(spans)} examples")

    # Ask LLM to generate patterns for each category
    all_patterns = []
    for cat, spans in sorted(grouped.items()):
        if progress:
            print(f"  Generating patterns for '{cat}'...")

        # Deduplicate and sample
        unique_spans = sorted(set(spans))[:50]
        span_block = "\n".join(f'  "{s}"' for s in unique_spans)

        resp = call_llm(
            prompt=f"Category: {cat}\n\nExamples of sensitive spans:\n{span_block}",
            system=PATTERN_GENERATION,
            max_tokens=2048,
        )
        parsed = _extract_json(resp)
        if isinstance(parsed, dict):
            for pat_group in parsed.get("patterns", []):
                if isinstance(pat_group, dict):
                    all_patterns.append(pat_group)

    # Separate into icase vs csense patterns
    amount_patterns_icase = []
    amount_patterns_csense = []
    address_patterns = []
    other_structural = []

    for pat_group in all_patterns:
        category = pat_group.get("category", "unknown")
        flags = pat_group.get("flags", "IGNORECASE")
        patterns = pat_group.get("patterns", [])

        # Validate each pattern
        valid = [p for p in patterns if isinstance(p, str) and _validate_regex(p)]
        invalid = [p for p in patterns if isinstance(p, str) and not _validate_regex(p)]
        if invalid and progress:
            print(f"    [warn] {len(invalid)} invalid regex patterns dropped for '{category}'")

        if category in ("amount", "quantity", "number", "currency"):
            if flags == "IGNORECASE":
                amount_patterns_icase.extend(valid)
            else:
                amount_patterns_csense.extend(valid)
        elif category in ("identifier", "address", "credential", "account"):
            address_patterns.extend(valid)
        else:
            other_structural.extend(valid)

    # Build the sensitive_patterns dict
    # Start with core patterns, add domain-agnostic defaults
    sensitive_patterns: dict = {
        "components": {},
        "amount_patterns_icase": amount_patterns_icase,
        "amount_patterns_csense": amount_patterns_csense,
        "amount_known_token_pattern": "",  # will be filled if applicable
        "false_positive_words": [],
        "address_patterns": address_patterns,
        "ens_pattern": "",
        "percent_pattern": r'\b\d+(?:\.\d+)?%\b',  # universal default
        "hf_pattern": "",
        "leverage_pattern": "",
        "number_words": [
            "hundred", "thousand", "million", "billion", "trillion",
            "half a million", "quarter million",
            "six-figure", "seven-figure", "eight-figure",
            "double", "triple", "quadruple",
        ],
        "number_word_patterns": [],
        "cardinal_token_pattern": "",
        "cardinal_known_token": "",
        "worded_percent_pattern": "",
        "worded_decimal_pattern": "",
        "worded_fraction_token": "",
        "worded_decimal_token": "",
        "emotional_words": [
            "worried", "anxious", "urgent", "emergency", "scared",
            "nervous", "panicking", "desperate", "afraid", "concerned about",
        ],
        "timing_patterns": [
            r'\b(?:by|on|before|after|next)\s+(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b',
            r'\b(?:within|in)\s+\d+\s+(?:hours?|days?|weeks?|months?)\b',
            r'\bright now\b', r'\bimmediately\b', r'\bASAP\b',
            r'\btoday\b', r'\btomorrow\b', r'\byesterday\b',
        ],
        "directional_verbs": {},
        "qualitative_words": [],
        "entity_names": [],
    }

    return sensitive_patterns


# ---------------------------------------------------------------------------
# Entity extraction
# ---------------------------------------------------------------------------

def generate_entity_list(
    queries: list[dict],
    subdomains: dict,
    progress: bool = True,
) -> list[str]:
    """Extract entity names from queries for the genericizer.

    Returns: list of entity names sorted longest-first.
    """
    if progress:
        print("  Extracting entity names...")

    # Use queries + ontology protocol lists
    query_block = "\n".join(f"- {q['text']}" for q in queries[:80])

    resp = call_llm(
        prompt=f"Domain queries:\n{query_block}",
        system=ENTITY_EXTRACTION,
        max_tokens=2048,
    )
    parsed = _extract_json(resp)

    entities = []
    generic_refs_map = {}  # entity → generic_ref
    if isinstance(parsed, dict):
        for ent in parsed.get("entities", []):
            if isinstance(ent, dict):
                name = ent.get("name", "")
                if name:
                    entities.append(name)
                    generic_refs_map[name] = ent.get("generic_ref", "")
            elif isinstance(ent, str):
                entities.append(ent)

    # Also collect from ontology
    for sd_data in subdomains.values():
        for proto in sd_data.get("protocols", []):
            if proto not in entities:
                entities.append(proto)

    # Sort longest-first for greedy matching
    entities = sorted(set(entities), key=len, reverse=True)

    if progress:
        print(f"  Found {len(entities)} entities")

    return entities


# ---------------------------------------------------------------------------
# False positive detection
# ---------------------------------------------------------------------------

def generate_false_positives(
    queries: list[dict],
    subdomains: dict,
    progress: bool = True,
) -> list[str]:
    """Identify common words that might be false positives for amount patterns.

    Returns: sorted list of false-positive words.
    """
    if progress:
        print("  Identifying false positive words...")

    # Collect acronyms and version strings from the domain
    fp_words = set()

    # Common universal false positives
    fp_words.update([
        'V2', 'V3', 'V4', 'V5',
        'API', 'SDK', 'CLI', 'GPU', 'CPU', 'RAM',
        'FAQ', 'IDE',
        'APIs', 'SDKs', 'GPUs', 'CPUs',
        'Hz', 'MB', 'GB', 'TB', 'KB',
    ])

    # Extract uppercase words from non-sensitive queries that look like tokens
    # but are actually domain terminology
    for q in queries:
        if q.get("label") != "sensitive":
            words = q["text"].split()
            for w in words:
                # Short uppercase words (2-5 chars) are likely acronyms
                if 2 <= len(w) <= 5 and w.isupper() and w.isalpha():
                    fp_words.add(w)
                    if not w.endswith('s'):
                        fp_words.add(w + 's')

    return sorted(fp_words)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def generate_all_patterns(
    analysis: dict,
    queries: list[dict],
    subdomains: dict,
    progress: bool = True,
) -> tuple[dict, dict]:
    """Run the full Phase 2a pattern generation pipeline.

    Returns: (sensitive_patterns, normalization)
    """
    print("Phase 2a: Generating patterns")

    span_results = analysis.get("span_results", [])

    # Generate regex patterns
    sensitive_patterns = generate_patterns(span_results, progress=progress)

    # Generate entity list
    entities = generate_entity_list(queries, subdomains, progress=progress)
    sensitive_patterns["entity_names"] = entities

    # Generate false positive list
    fp_words = generate_false_positives(queries, subdomains, progress=progress)
    sensitive_patterns["false_positive_words"] = fp_words

    # Default normalization config
    normalization = {
        "currency_symbols": ["€", "£", "¥", "₹", "₩", "₿"],
        "hyphenated_cardinals": [
            "twenty", "thirty", "forty", "fifty",
            "sixty", "seventy", "eighty", "ninety",
        ],
    }

    print(f"  Generated {len(sensitive_patterns['amount_patterns_icase'])} icase patterns, "
          f"{len(sensitive_patterns['amount_patterns_csense'])} csense patterns, "
          f"{len(entities)} entities, {len(fp_words)} false-positive words")

    return sensitive_patterns, normalization
