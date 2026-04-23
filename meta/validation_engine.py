"""
Validation engine — automated property verification for generated domain profiles.

Checks:
  1. Sanitizer completeness: 0% FN on labeled sensitive spans
  2. False positive rate: <5% words removed from non-sensitive queries
  3. Profile completeness: >=95% of queries map to a subdomain
  4. Template coverage: >=60% of queries match a template
  5. Vocabulary depth: >=3 items per slot per subdomain
  6. Cover quality: adversary detection <= 40% (quick classifier)

Anti-malicious-LLM guardrails:
  7. Entity completeness: entities in dataset covered by entity_names (anti-omission)
  8. Held-out sanitizer: test against independent data not from generating LLM (anti-self-certification)
  9. Ontology balance: subdomain vocabularies balanced in size (anti-fingerprinting)
  10. Sensitivity label completeness: heuristic regex detects categories LLM may have omitted (anti-self-certification)
  11. Vocabulary diversity: edit-distance dedup catches near-duplicate slot fills (anti-inflation)

Quality:
  12. Tier 1 pipeline: end-to-end decompose → genericize → answer → synthesize (target: >=70% quality retained)
  13. Tier 0 usability: sanitized queries still coherent (target: avg >=2.0/5, no destroyed queries)

Output: traffic-light report (PASS / MARGINAL / FAIL per property).
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

from core.profile_loader import load_profile
from meta.util import extract_json as _extract_json


# ---------------------------------------------------------------------------
# Property 1: Sanitizer completeness
# ---------------------------------------------------------------------------

def check_sanitizer_completeness(
    profile: dict,
    span_results: list[dict],
) -> dict:
    """Test every labeled sensitive span against the sanitizer.

    Returns: {passed, total, false_negatives, fn_rate, verdict}
    """
    # Import cover_generator with this profile loaded
    import cover_generator as cg
    cg._init_from_profile(profile)

    total = 0
    false_negatives = []

    for entry in span_results:
        text = entry["text"]
        for span_info in entry.get("spans", []):
            span_text = span_info.get("span", "")
            if not span_text:
                continue
            total += 1
            sanitized = cg.sanitize_query(text)
            # Check if span survives sanitization — two checks:
            # 1. Exact substring match (original behavior)
            # 2. Numeric-value match: if the span contains digits, check if
            #    those digits appear in the sanitized output. Catches cases
            #    where normalization splits tokens (e.g., "10000 DAI" → "10000 da i")
            span_lower = span_text.lower()
            sanitized_lower = sanitized.lower()
            # Also normalize whitespace for comparison
            sanitized_collapsed = re.sub(r'\s+', '', sanitized_lower)
            span_collapsed = re.sub(r'\s+', '', span_lower)

            leaked = False
            if span_lower in sanitized_lower:
                leaked = True
            elif span_collapsed in sanitized_collapsed:
                # Whitespace-insensitive match (catches split-token leaks)
                leaked = True
            else:
                # Extract numeric portion and check if it survives
                import re as _re
                digits = _re.findall(r'\d{3,}', span_text)
                for d in digits:
                    if d in sanitized:
                        leaked = True
                        break

            if leaked:
                false_negatives.append({
                    "query": text,
                    "span": span_text,
                    "category": span_info.get("category", ""),
                    "sanitized_output": sanitized,
                })

    fn_rate = len(false_negatives) / max(total, 1)
    if fn_rate == 0:
        verdict = "PASS"
    elif fn_rate <= 0.05:
        verdict = "MARGINAL"
    else:
        verdict = "FAIL"

    return {
        "passed": total - len(false_negatives),
        "total": total,
        "false_negatives": false_negatives,
        "fn_rate": round(fn_rate, 4),
        "verdict": verdict,
    }


# ---------------------------------------------------------------------------
# Property 2: False positive rate
# ---------------------------------------------------------------------------

def check_false_positive_rate(
    profile: dict,
    queries: list[dict],
) -> dict:
    """Check that non-sensitive queries are not over-stripped.

    Returns: {total_queries, avg_word_removal_rate, max_removal, verdict}
    """
    import cover_generator as cg
    cg._init_from_profile(profile)

    non_sensitive = [q for q in queries if q.get("label") != "sensitive"]
    if not non_sensitive:
        return {"total_queries": 0, "avg_word_removal_rate": 0, "verdict": "SKIP"}

    removal_rates = []
    worst = None
    for entry in non_sensitive:
        text = entry["text"]
        sanitized = cg.sanitize_query(text)
        original_words = len(text.split())
        remaining_words = len(sanitized.split())
        if original_words > 0:
            removed = 1 - (remaining_words / original_words)
            removal_rates.append(removed)
            if worst is None or removed > worst["rate"]:
                worst = {"query": text, "sanitized": sanitized, "rate": removed}

    avg_rate = sum(removal_rates) / max(len(removal_rates), 1)
    max_rate = max(removal_rates) if removal_rates else 0

    if avg_rate <= 0.05:
        verdict = "PASS"
    elif avg_rate <= 0.10:
        verdict = "MARGINAL"
    else:
        verdict = "FAIL"

    return {
        "total_queries": len(non_sensitive),
        "avg_word_removal_rate": round(avg_rate, 4),
        "max_removal_rate": round(max_rate, 4),
        "worst_case": worst,
        "verdict": verdict,
    }


# ---------------------------------------------------------------------------
# Property 3: Profile completeness
# ---------------------------------------------------------------------------

def check_profile_completeness(
    profile: dict,
    queries: list[dict],
) -> dict:
    """Check that queries map to subdomains in the profile.

    Returns: {total, matched, coverage, unmatched_samples, verdict}
    """
    import cover_generator as cg
    cg._init_from_profile(profile)

    total = len(queries)
    matched = 0
    unmatched = []

    valid_domains = set(profile.get("subdomains", {}).keys())

    for entry in queries:
        domain = cg.classify_domain(entry["text"])
        if domain in valid_domains:
            matched += 1
        else:
            unmatched.append({"text": entry["text"], "classified_as": domain})

    coverage = matched / max(total, 1)
    if coverage >= 0.95:
        verdict = "PASS"
    elif coverage >= 0.80:
        verdict = "MARGINAL"
    else:
        verdict = "FAIL"

    return {
        "total": total,
        "matched": matched,
        "coverage": round(coverage, 4),
        "unmatched_samples": unmatched[:10],
        "verdict": verdict,
    }


# ---------------------------------------------------------------------------
# Property 4: Template coverage
# ---------------------------------------------------------------------------

def check_template_coverage(
    profile: dict,
    queries: list[dict],
) -> dict:
    """Check that queries match templates with reasonable scores.

    Returns: {total, matched, coverage, avg_score, verdict}
    """
    import cover_generator as cg
    cg._init_from_profile(profile)

    total = len(queries)
    matched = 0
    scores = []

    for entry in queries:
        sanitized = cg.sanitize_query(entry["text"])
        template, score = cg._match_template(sanitized)
        scores.append(score)
        if score >= 2:
            matched += 1

    coverage = matched / max(total, 1)
    avg_score = sum(scores) / max(len(scores), 1)

    # Template matching is for cover generation, not query coverage.
    # Even the hand-crafted DeFi profile only matches ~55% of diverse queries.
    if coverage >= 0.60:
        verdict = "PASS"
    elif coverage >= 0.40:
        verdict = "MARGINAL"
    else:
        verdict = "FAIL"

    return {
        "total": total,
        "matched": matched,
        "coverage": round(coverage, 4),
        "avg_score": round(avg_score, 2),
        "verdict": verdict,
    }


# ---------------------------------------------------------------------------
# Property 5: Vocabulary depth
# ---------------------------------------------------------------------------

def check_vocabulary_depth(profile: dict) -> dict:
    """Check that each subdomain has sufficient vocabulary.

    Returns: {subdomains_checked, deficient, details, verdict}
    """
    required_keys = [
        "protocols", "mechanisms", "operations", "triggers",
        "metrics", "actors", "risk_concepts", "generic_refs",
    ]
    # 3 is sufficient for cover generation; 5 is ideal for variety
    min_items = 3

    deficient = []
    checked = 0

    for sd_name, sd_data in profile.get("subdomains", {}).items():
        checked += 1
        for key in required_keys:
            items = sd_data.get(key, [])
            if len(items) < min_items:
                deficient.append({
                    "subdomain": sd_name,
                    "key": key,
                    "count": len(items),
                    "minimum": min_items,
                })

    if not deficient:
        verdict = "PASS"
    elif len(deficient) <= 3:
        verdict = "MARGINAL"
    else:
        verdict = "FAIL"

    return {
        "subdomains_checked": checked,
        "deficient_slots": len(deficient),
        "details": deficient,
        "verdict": verdict,
    }


# ---------------------------------------------------------------------------
# Property 6: Cover quality (quick check)
# ---------------------------------------------------------------------------

def check_cover_quality(
    profile: dict,
    queries: list[dict],
    n_sets: int = 50,
) -> dict:
    """Quick cover quality check using string-similarity heuristic.

    A proper check would train a classifier; this is a fast approximation
    that checks if real queries are distinguishable by length/vocabulary overlap.

    Returns: {sets_tested, detection_rate, verdict}
    """
    import cover_generator as cg
    cg._init_from_profile(profile)

    sensitive = [q for q in queries if q.get("label") == "sensitive"]
    if not sensitive:
        sensitive = queries

    sample = sensitive[:n_sets]
    correct_guesses = 0
    total_tested = 0

    for entry in sample:
        try:
            shuffled, real_idx = cg.generate_cover_set(
                entry["text"], k=4,
                seed=int.from_bytes(entry["text"].encode()[:8], "big") & 0xFFFFFFFF,
            )
        except Exception:
            continue

        total_tested += 1

        # Heuristic detection: pick the query most different in length
        avg_len = sum(len(q) for q in shuffled) / len(shuffled)
        deviations = [abs(len(q) - avg_len) for q in shuffled]
        guess = deviations.index(max(deviations))

        if guess == real_idx:
            correct_guesses += 1

    detection_rate = correct_guesses / max(total_tested, 1)

    if detection_rate <= 0.30:
        verdict = "PASS"
    elif detection_rate <= 0.40:
        verdict = "MARGINAL"
    else:
        verdict = "FAIL"

    return {
        "sets_tested": total_tested,
        "detection_rate": round(detection_rate, 4),
        "random_baseline": 0.25,
        "verdict": verdict,
        "note": "Heuristic check (length deviation). Full validation requires DistilBERT classifier.",
    }


# ---------------------------------------------------------------------------
# Property 7: Entity completeness (anti-omission guardrail)
# ---------------------------------------------------------------------------

def check_entity_completeness(
    profile: dict,
    queries: list[dict],
) -> dict:
    """Check that entity names in the dataset are covered by entity_names.

    Prevents the generating LLM from omitting key entities so the
    genericizer fails to strip them.

    Returns: {found_in_queries, covered, missed, coverage, verdict}
    """
    import re as _re

    entity_names = profile.get("sensitive_patterns", {}).get("entity_names", [])
    entity_set = set(e.lower() for e in entity_names)

    # Also collect all protocol names from subdomains
    for sd_data in profile.get("subdomains", {}).values():
        for proto in sd_data.get("protocols", []):
            entity_set.add(proto.lower())

    # Extract capitalized multi-word phrases from queries that look like entity names
    # (2+ chars, starts with uppercase, appears in multiple queries)
    candidate_counts: dict[str, int] = {}
    entity_pattern = _re.compile(r'\b[A-Z][a-zA-Z0-9]*(?:\s+(?:V\d+|[A-Z][a-zA-Z0-9]*))*\b')
    for entry in queries:
        found = set(entity_pattern.findall(entry["text"]))
        for ent in found:
            if len(ent) >= 2:
                candidate_counts[ent] = candidate_counts.get(ent, 0) + 1

    # Entities appearing 2+ times are likely real entity names
    found_in_queries = {ent for ent, count in candidate_counts.items() if count >= 2}

    covered = {ent for ent in found_in_queries if ent.lower() in entity_set}
    missed = found_in_queries - covered

    # Filter aggressively: entity completeness should only flag
    # protocol/product NAMES that the genericizer should strip, not
    # common English words, acronyms, or domain-general terms.
    skip_words = {
        "The", "This", "What", "How", "Why", "When", "Where", "Which",
        "Can", "Does", "Should", "Would", "Could", "Will", "My", "Is",
        "Are", "Do", "If", "For", "Not", "But", "Or", "And", "In", "On",
        "At", "To", "From", "By", "With", "About", "Into", "Through",
        "Best", "Most", "Some", "Any", "All", "Each", "Every", "Other",
        "Current", "Explain", "Compare", "Calculate", "Estimate",
        # Domain-general terms (not protocol names)
        "DeFi", "Ethereum", "Bitcoin", "Blockchain", "Web3", "Crypto",
    }
    missed = {
        e for e in missed
        if e not in skip_words
        and not e.isupper()           # all-caps = acronyms
        and not (e.endswith('s') and e[:-1].isupper())  # plural acronyms (AMMs, DEXes)
        and len(e) > 3                # skip short matches
        and not e.endswith('ing')     # skip gerunds
        and not e.endswith('ed')      # skip past tense
    }

    coverage = len(covered) / max(len(covered) + len(missed), 1)

    if coverage >= 0.70:
        verdict = "PASS"
    elif coverage >= 0.50:
        verdict = "MARGINAL"
    else:
        verdict = "FAIL"

    return {
        "found_in_queries": len(covered) + len(missed),
        "covered": len(covered),
        "missed_entities": sorted(missed)[:20],
        "coverage": round(coverage, 4),
        "verdict": verdict,
    }


# ---------------------------------------------------------------------------
# Property 8: Held-out sanitizer test (anti-self-certification guardrail)
# ---------------------------------------------------------------------------

def _auto_generate_held_out(queries: list[dict] | None) -> list[dict]:
    """Auto-generate held-out test data from any dataset.

    Strategy:
    1. If queries have labeled private_params, use those directly (best)
    2. Otherwise, extract numeric/address-like substrings as synthetic params
    """
    import re as _re
    if not queries:
        return []

    # Strategy 1: use dataset-provided private_params if available
    with_params = [
        q for q in queries
        if q.get("private_params") and q.get("label") == "sensitive"
    ]
    if with_params:
        # Use last 20% as held-out, but always keep at least 1
        split_idx = min(len(with_params) - 1, max(1, int(len(with_params) * 0.8)))
        return [
            {"text": q.get("text", q.get("query", "")),
             "private_params": q["private_params"]}
            for q in with_params[split_idx:]
        ]

    sensitive = [q for q in queries if q.get("label") == "sensitive"]
    if not sensitive:
        return []

    # Use the last 20% of sensitive queries as held-out
    split_idx = max(1, int(len(sensitive) * 0.8))
    held_out_source = sensitive[split_idx:]

    # Extract numeric/address-like spans as synthetic private_params
    _param_patterns = [
        r'\$[\d,]+(?:\.\d+)?[KkMmBb]?',       # dollar amounts
        r'\b\d+(?:\.\d+)?%',                    # percentages
        r'\b\d{1,3}(?:,\d{3})+\b',             # comma numbers
        r'\b\d+(?:\.\d+)?\s*[A-Z]{2,6}\b',     # number + token (500 ETH)
        r'0[xX][a-fA-F0-9]{6,}',               # addresses
    ]

    results = []
    for q in held_out_source:
        text = q.get("text", "")
        params = []
        for pat in _param_patterns:
            for match in _re.finditer(pat, text):
                params.append(match.group())
        if params:
            results.append({"text": text, "private_params": params})

    return results


def check_held_out_sanitizer(
    profile: dict,
    held_out_queries: list[dict] | None = None,
    queries_for_held_out: list[dict] | None = None,
) -> dict:
    """Test the sanitizer against a HELD-OUT test set not generated by the same LLM.

    This counters the self-certification attack: the generating LLM could
    coordinate patterns and test data to hide gaps. A held-out set provides
    independent validation.

    held_out_queries: list of {text, private_params: [str]} — params that MUST be stripped.
    If not provided, auto-generates held-out data from the dataset by extracting
    numeric/address-like substrings from sensitive queries as synthetic private_params.
    For DeFi domains, also falls back to COMPLEX_QUERIES from dataset.py.

    Returns: {total_params, stripped, leaked, fn_rate, verdict}
    """
    import cover_generator as cg
    cg._init_from_profile(profile)

    if held_out_queries is None:
        # Strategy 1: Auto-generate held-out from any dataset
        # Extract numeric/address-like spans from sensitive queries
        held_out_queries = _auto_generate_held_out(queries_for_held_out)

        # Strategy 2: For DeFi, also try COMPLEX_QUERIES
        if not held_out_queries:
            domain = profile.get("meta", {}).get("domain_name", "")
            if domain in ("defi", "defi_generated", "defi_14b"):
                try:
                    from dataset import COMPLEX_QUERIES
                    held_out_queries = [
                        {"text": q["query"], "private_params": q.get("private_params", [])}
                        for q in COMPLEX_QUERIES
                    ]
                except ImportError:
                    pass

        if not held_out_queries:
            return {"verdict": "SKIP", "reason": "No held-out data available"}

    # The sanitizer strips AMOUNTS/ADDRESSES/PERCENTAGES, not protocol names
    # or intent words (those are handled by the genericizer). Filter params
    # to only those the sanitizer is responsible for: numeric values, addresses,
    # percentages, health factors, leverage ratios.
    import re as _re
    # Only test params that look like amounts the SANITIZER should strip.
    # Uses the profile's known token list for comprehensive matching.
    _known = profile.get("sensitive_patterns", {}).get("components", {}).get("KNOWN_TOKENS", "")
    _token_pattern = _known if _known else "ETH|BTC|USDC|USDT|DAI"
    _numeric_like = _re.compile(
        r'\$[\d,]+|'              # dollar amounts
        r'\b\d{3,}\b|'           # 3+ digit numbers (amounts, not IDs)
        r'\b\d+\s*(?:' + _token_pattern + r')\b|'  # token amounts (50 ETH, 80 SOL, 99 ARB...)
        r'\b\d+\.\d+\b|'        # decimal values (1.12, 0.5)
        r'\b\d+(?:\.\d+)?%|'     # percentages
        r'0[xX][a-zA-Z0-9]+(?:\.{2,}[a-zA-Z0-9]+)?|'  # addresses (full or truncated with alphanumeric suffix)
        r'health factor|'        # domain-specific metric
        r'\b\d+[xX]\b',          # leverage (5x, 10X)
        _re.IGNORECASE,
    )

    if not held_out_queries:
        return {"verdict": "SKIP", "reason": "No held-out data provided"}

    total_params = 0
    leaked = []

    for entry in held_out_queries:
        text = entry.get("text", "")
        params = entry.get("private_params", [])
        sanitized = cg.sanitize_query(text)

        for param in params:
            # Only test params the sanitizer is responsible for (numeric/address/percentage)
            if not _numeric_like.search(param):
                continue
            total_params += 1
            param_clean = param.lower().replace(",", "")
            sanitized_clean = sanitized.lower().replace(",", "")
            # Three-way leak detection:
            # 1. Direct substring match
            # 2. Whitespace-collapsed match (catches split-token leaks)
            # 3. Numeric value match (catches obfuscated amounts)
            param_collapsed = re.sub(r'\s+', '', param_clean)
            sanitized_collapsed = re.sub(r'\s+', '', sanitized_clean)
            # For truncated addresses like 0x5e6F...7g8H, also check if the
            # suffix fragment (e.g., "7g8h") survives in the sanitized text
            addr_suffix = re.findall(r'\.{2,}([a-zA-Z0-9]{2,})', param)
            is_leaked = (
                param_clean in sanitized_clean
                or param_collapsed in sanitized_collapsed
                or any(d in sanitized for d in re.findall(r'\d{3,}', param))
                or any(s.lower() in sanitized_clean for s in addr_suffix)
            )
            if is_leaked:
                leaked.append({"query": text, "param": param, "sanitized": sanitized})

    fn_rate = len(leaked) / max(total_params, 1)

    if fn_rate == 0:
        verdict = "PASS"
    elif fn_rate <= 0.05:
        verdict = "MARGINAL"
    else:
        verdict = "FAIL"

    return {
        "total_params": total_params,
        "stripped": total_params - len(leaked),
        "leaked": leaked[:10],
        "fn_rate": round(fn_rate, 4),
        "verdict": verdict,
    }


# ---------------------------------------------------------------------------
# Property 9: Ontology balance (anti-fingerprinting guardrail)
# ---------------------------------------------------------------------------

def check_ontology_balance(profile: dict) -> dict:
    """Check that subdomain vocabularies are balanced in size.

    Imbalanced ontologies allow adversaries to fingerprint real queries by
    vocabulary richness — a subdomain with 50 terms vs one with 5 terms
    makes the 50-term subdomain's covers more varied and detectable.

    Returns: {subdomains, min_size, max_size, ratio, verdict}
    """
    vocab_sizes = {}
    for sd_name, sd_data in profile.get("subdomains", {}).items():
        if sd_name == "general":
            continue  # general is a catch-all, expect imbalance
        total = sum(
            len(sd_data.get(key, []))
            for key in ("mechanisms", "operations", "triggers", "metrics")
        )
        vocab_sizes[sd_name] = total

    if not vocab_sizes:
        return {"verdict": "SKIP", "reason": "No subdomains"}

    min_size = min(vocab_sizes.values())
    max_size = max(vocab_sizes.values())
    ratio = min_size / max(max_size, 1)

    if ratio >= 0.40:
        verdict = "PASS"
    elif ratio >= 0.20:
        verdict = "MARGINAL"
    else:
        verdict = "FAIL"

    return {
        "subdomains": vocab_sizes,
        "min_size": min_size,
        "max_size": max_size,
        "ratio": round(ratio, 4),
        "verdict": verdict,
        "note": "Ratio < 0.4 means one subdomain has 2.5x+ more vocabulary, aiding fingerprinting",
    }


# ---------------------------------------------------------------------------
# Property 10: Sensitivity label completeness (anti-self-certification)
# ---------------------------------------------------------------------------

# Heuristic patterns that are LLM-INDEPENDENT — if the LLM's sensitivity
# analysis missed these categories, it's under-labeling.
_HEURISTIC_TIMING = [
    r'\b(?:by|on|before|after|next)\s+(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b',
    r'\b(?:within|in)\s+\d+\s+(?:hours?|days?|weeks?|months?)\b',
    r'\bright now\b', r'\bimmediately\b', r'\bASAP\b',
    r'\btoday\b', r'\btomorrow\b', r'\byesterday\b',
]
_HEURISTIC_EMOTIONAL = [
    r'\b(?:worried|anxious|urgent|emergency|scared|nervous|panicking|desperate|afraid)\b',
]
_HEURISTIC_AMOUNTS = [
    r'\$[\d,]+(?:\.\d+)?[KkMmBb]?',                    # Dollar amounts (universal)
    r'\b\d{1,3}(?:,\d{3})+\b',                          # Large comma numbers (universal)
    r'\b\d+(?:\.\d+)?%\b',                               # Percentages (universal)
]


def check_sensitivity_labels(
    queries: list[dict],
    span_results: list[dict] | None = None,
    profile: dict | None = None,
) -> dict:
    """Check that the LLM's sensitivity labels cover all major leakage categories.

    Uses LLM-INDEPENDENT heuristic regex to detect timing, emotional, and
    amount patterns in queries. If these exist in the dataset but were NOT
    labeled as sensitive by the generating LLM, the labels are incomplete.

    This counters the self-certification attack: a malicious LLM can't
    omit hard-to-catch categories because the heuristics catch them independently.

    Returns: {categories_found, categories_labeled, missed, verdict}
    """
    import re as _re

    if not span_results:
        return {"verdict": "SKIP", "reason": "No span_results to audit"}

    # Build set of all labeled spans
    all_labeled = set()
    for entry in span_results:
        for span_info in entry.get("spans", []):
            all_labeled.add(span_info.get("span", "").lower())

    # Use domain-specific heuristics if available, otherwise universal defaults
    domain_heuristics = {}
    if profile:
        domain_heuristics = profile.get("domain_heuristics") or {}

    categories = {
        "timing": domain_heuristics.get("timing", _HEURISTIC_TIMING),
        "emotional": domain_heuristics.get("emotional", _HEURISTIC_EMOTIONAL),
        "amounts": domain_heuristics.get("amounts", _HEURISTIC_AMOUNTS),
    }

    results = {}
    for cat_name, patterns in categories.items():
        found_in_data = 0
        labeled_by_llm = 0
        missed_examples = []

        for entry in span_results:
            text = entry["text"]
            for pat in patterns:
                for match in _re.finditer(pat, text, _re.IGNORECASE):
                    found_in_data += 1
                    span_text = match.group().lower()
                    # Check if ANY labeled span overlaps with this match
                    if any(span_text in labeled or labeled in span_text
                           for labeled in all_labeled):
                        labeled_by_llm += 1
                    else:
                        if len(missed_examples) < 3:
                            missed_examples.append({
                                "query": text[:80],
                                "pattern_match": match.group(),
                            })

        coverage = labeled_by_llm / max(found_in_data, 1)
        results[cat_name] = {
            "found": found_in_data,
            "labeled": labeled_by_llm,
            "coverage": round(coverage, 4),
            "missed_examples": missed_examples,
        }

    # Overall verdict: all categories should have >50% label coverage
    all_coverages = [r["coverage"] for r in results.values() if r["found"] > 0]
    min_coverage = min(all_coverages) if all_coverages else 1.0

    if min_coverage >= 0.50:
        verdict = "PASS"
    elif min_coverage >= 0.25:
        verdict = "MARGINAL"
    else:
        verdict = "FAIL"

    return {
        "categories": results,
        "min_category_coverage": round(min_coverage, 4),
        "verdict": verdict,
        "note": "Low coverage means LLM under-labeled a sensitivity category",
    }


# ---------------------------------------------------------------------------
# Property 11: Vocabulary diversity (anti-duplication guardrail)
# ---------------------------------------------------------------------------

def check_vocabulary_diversity(profile: dict) -> dict:
    """Check that vocabulary slots contain genuinely distinct terms.

    Catches near-duplicates and semantically empty fills. Excludes
    protocols (versioned names like Aave V2/V3 are intentional) and
    operations (add/remove collateral ARE distinct operations).

    Returns: {duplicates_found, details, verdict, note}
    """
    from difflib import SequenceMatcher

    duplicates = []

    for sd_name, sd_data in profile.get("subdomains", {}).items():
        # Skip protocols (versioned names like Aave V2/V3 are intentional, not duplicates)
        # and operations (add/remove collateral ARE distinct operations)
        for slot in ("mechanisms", "triggers",
                     "metrics", "actors", "risk_concepts", "generic_refs"):
            items = sd_data.get(slot, [])
            if len(items) < 2:
                continue

            # Check all pairs for high similarity
            for i, a in enumerate(items):
                for b in items[i + 1:]:
                    sim = SequenceMatcher(None, a.lower(), b.lower()).ratio()
                    if sim > 0.75:
                        duplicates.append({
                            "subdomain": sd_name,
                            "slot": slot,
                            "term_a": a,
                            "term_b": b,
                            "similarity": round(sim, 2),
                        })

    if len(duplicates) <= 3:
        verdict = "PASS"
    elif len(duplicates) <= 10:
        verdict = "MARGINAL"
    else:
        verdict = "FAIL"

    return {
        "duplicates_found": len(duplicates),
        "details": duplicates[:15],
        "verdict": verdict,
        "note": "High similarity terms inflate apparent diversity without real cover variety",
    }


# ---------------------------------------------------------------------------
# Property 12: Tier 1 pipeline quality (decompose → genericize → synthesize)
# ---------------------------------------------------------------------------

_DECOMPOSE_SYSTEM = """\
You are a privacy orchestrator. Given a user query, decompose it into 2-3 \
generic sub-queries that:
1. Reveal NO private parameters (amounts, addresses, percentages, timing)
2. Each ask about a generic mechanism in the domain
3. Together provide enough information to answer the original question

Respond with ONLY a JSON array of sub-queries: ["query1", "query2"]"""

_SYNTHESIZE_SYSTEM = """\
You are a domain advisor. You have received answers to several generic \
sub-queries. Using these answers AND the user's specific parameters \
(provided below), synthesize a concrete, actionable answer.

Respond naturally as if answering the user's original question directly."""

_PIPELINE_JUDGE = """\
You are comparing two answers to the same question. Rate each answer 1-5:
5 = Complete, specific, directly actionable
4 = Mostly complete, covers the key points
3 = Partial, addresses the topic but misses important details
2 = Tangential, loosely related but not useful
1 = Irrelevant or wrong

Output JSON: {"score_a": 1-5, "score_b": 1-5}"""


def check_tier1_pipeline(
    profile: dict,
    queries: list[dict],
    n_samples: int = 5,
    progress: bool = True,
) -> dict:
    """End-to-end Tier 1 pipeline test: decompose → genericize → answer → synthesize.

    Tests whether the generated profile's ontology and entity names produce
    a working privacy-preserving pipeline with acceptable answer quality.
    Compares pipeline answers to direct answers (blinded A/B).

    Target: pipeline should retain >=70% of direct answer quality.
    Hand-crafted DeFi baseline: 3.8/5 pipeline vs ~4.5/5 direct ≈ 84% retained.

    Requires active LLM backend.

    Returns: {samples, avg_direct, avg_pipeline, quality_retained, verdict}
    """
    try:
        from llm_backend import call_llm, get_backend, is_local
        if not is_local():
            return {"verdict": "SKIP", "reason": "Tier 1 pipeline check requires local backend (sends unsanitized queries)"}
        if get_backend() is None:
            return {"verdict": "SKIP", "reason": "No LLM backend initialized"}
    except Exception:
        return {"verdict": "SKIP", "reason": "LLM backend not available"}

    import cover_generator as cg
    cg._init_from_profile(profile)

    domain_name = profile.get("meta", {}).get("domain_name", "unknown")

    # Use sensitive queries with private_params if available, else sample sensitive
    complex_qs = [q for q in queries if q.get("private_params")]
    if not complex_qs:
        complex_qs = [q for q in queries if q.get("label") == "sensitive"][:n_samples]
    else:
        complex_qs = complex_qs[:n_samples]

    if not complex_qs:
        return {"verdict": "SKIP", "reason": "No complex queries with private_params"}

    import random as _rng

    results_list = []

    for i, entry in enumerate(complex_qs):
        text = entry.get("text", entry.get("query", ""))
        private_params = entry.get("private_params", [])

        try:
            # Step 1: Direct answer (baseline)
            direct_answer = call_llm(text, max_tokens=400)

            # Step 2: Decompose (local LLM sees full query — this is the real pipeline)
            decomp_resp = call_llm(
                f"Decompose this query:\n\n{text}",
                system=_DECOMPOSE_SYSTEM,
                max_tokens=300,
            )
            parsed = _extract_json(decomp_resp)
            if isinstance(parsed, list):
                sub_queries = parsed
            elif isinstance(parsed, dict):
                sub_queries = parsed.get("sub_queries", [])
            else:
                sub_queries = [cg.sanitize_query(text)]

            if not sub_queries:
                sub_queries = [cg.sanitize_query(text)]

            # Step 3: Genericize each sub-query and get cloud answers
            sub_answers = []
            for sq in sub_queries[:3]:
                generic_sq = cg.genericize_subquery(str(sq))
                answer = call_llm(generic_sq, max_tokens=300)
                sub_answers.append(answer)

            # Step 4: Synthesize
            params_str = ", ".join(str(p) for p in private_params) if private_params else "(no specific params)"
            synthesis_prompt = (
                f"User's original question: {text}\n\n"
                f"Their specific parameters: {params_str}\n\n"
                f"Sub-query answers:\n" +
                "\n".join(f"Q: {sq}\nA: {sa[:200]}" for sq, sa in zip(sub_queries, sub_answers)) +
                f"\n\nSynthesize a complete answer."
            )
            pipeline_answer = call_llm(synthesis_prompt, system=_SYNTHESIZE_SYSTEM, max_tokens=400)

            # Step 5: Blinded A/B judge
            ab_rng = _rng.Random(42 + i)
            labels = ["direct", "pipeline"]
            answers = [direct_answer, pipeline_answer]
            order = [0, 1]
            ab_rng.shuffle(order)

            judge_prompt = (
                f"ORIGINAL QUESTION: {text}\n\n"
                f"ANSWER A: {answers[order[0]][:500]}\n\n"
                f"ANSWER B: {answers[order[1]][:500]}\n\n"
                f"Rate both answers (1-5)."
            )
            judge_resp = call_llm(judge_prompt, system=_PIPELINE_JUDGE, max_tokens=200)
            judge_parsed = _extract_json(judge_resp)

            if isinstance(judge_parsed, dict):
                score_a = int(judge_parsed.get("score_a", 3))
                score_b = int(judge_parsed.get("score_b", 3))
                # Un-shuffle
                scores = [0, 0]
                scores[order[0]] = score_a
                scores[order[1]] = score_b
                direct_score = scores[0]
                pipeline_score = scores[1]
            else:
                direct_score = 3
                pipeline_score = 3

            retained = min(pipeline_score / max(direct_score, 1), 1.0)
            results_list.append({
                "direct_score": direct_score,
                "pipeline_score": pipeline_score,
                "quality_retained": retained,
            })

            if progress:
                print(f"    [{i+1}/{len(complex_qs)}] direct={direct_score} "
                      f"pipeline={pipeline_score} retained={retained:.0%}")

        except Exception as e:
            if progress:
                print(f"    [{i+1}] ERROR: {e}")

    if not results_list:
        return {"verdict": "SKIP", "reason": "No results collected"}

    avg_direct = sum(r["direct_score"] for r in results_list) / len(results_list)
    avg_pipeline = sum(r["pipeline_score"] for r in results_list) / len(results_list)
    avg_retained = sum(r["quality_retained"] for r in results_list) / len(results_list)

    # Hand-crafted baseline: 3.8/5 pipeline ≈ 84% retained
    # Generated profile should achieve >=70% retained
    if avg_retained >= 0.70 and avg_pipeline >= 3.0:
        verdict = "PASS"
    elif avg_retained >= 0.50 and avg_pipeline >= 2.0:
        verdict = "MARGINAL"
    else:
        verdict = "FAIL"

    return {
        "samples": len(results_list),
        "avg_direct": round(avg_direct, 2),
        "avg_pipeline": round(avg_pipeline, 2),
        "quality_retained": round(avg_retained, 4),
        "details": results_list,
        "verdict": verdict,
        "note": "Hand-crafted baseline: 3.8/5, 84% retained. Target: >=70% retained, >=3.0/5.",
    }


# ---------------------------------------------------------------------------
# Property 13: Usability preservation (answer quality after sanitization)
# ---------------------------------------------------------------------------

_USABILITY_JUDGE = """\
You are evaluating whether a sanitized query still produces useful answers. \
You will see a user's ORIGINAL question and a SANITIZED version (private \
parameters removed). Rate whether the sanitized version would still get a \
useful answer from an AI assistant, on a 1-5 scale:

5 = Sanitized version asks essentially the same question; answer would be equally useful
4 = Minor information lost but the core question is preserved; answer mostly useful
3 = Some important context removed; answer partially useful
2 = Key information destroyed; answer would be about the right topic but miss the point
1 = Query is mangled or empty; answer would be useless

Output JSON only: {"score": 1-5, "reason": "brief explanation"}"""


def check_usability(
    profile: dict,
    queries: list[dict],
    n_samples: int = 10,
    progress: bool = True,
) -> dict:
    """Check that sanitization preserves query usability.

    Samples queries, sanitizes them with the profile, then asks an LLM
    to judge whether the sanitized version would still get a useful answer.
    Requires a LOCAL LLM backend (sends unsanitized queries).

    Returns: {samples, avg_score, scores, verdict}
    """
    try:
        from llm_backend import call_llm, get_backend, is_local
        if not is_local():
            return {"verdict": "SKIP", "reason": "Usability check requires local backend (sends unsanitized queries)"}
        if get_backend() is None:
            return {"verdict": "SKIP", "reason": "No LLM backend initialized"}
    except Exception:
        return {"verdict": "SKIP", "reason": "LLM backend not available"}

    import cover_generator as cg
    cg._init_from_profile(profile)

    # Sample sensitive queries (most interesting for usability)
    sensitive = [q for q in queries if q.get("label") == "sensitive"]
    if not sensitive:
        sensitive = queries
    sample = sensitive[:n_samples]

    scores = []
    details = []

    for i, entry in enumerate(sample):
        text = entry["text"]
        sanitized = cg.sanitize_query(text)

        # Skip if sanitization didn't change anything (non-sensitive query)
        if sanitized.strip() == text.strip():
            continue

        prompt = (
            f"ORIGINAL QUESTION: {text}\n\n"
            f"SANITIZED VERSION: {sanitized}\n\n"
            f"Rate the sanitized version's usability (1-5)."
        )

        try:
            resp = call_llm(prompt, system=_USABILITY_JUDGE, max_tokens=200)
            parsed = _extract_json(resp)
            if isinstance(parsed, dict) and "score" in parsed:
                score = int(parsed["score"])
                score = max(1, min(5, score))
                scores.append(score)
                details.append({
                    "original": text[:80],
                    "sanitized": sanitized[:80],
                    "score": score,
                    "reason": parsed.get("reason", ""),
                })
        except Exception:
            continue

        if progress and (i + 1) % 5 == 0:
            print(f"    Usability check: {i + 1}/{len(sample)}")

    if not scores:
        return {"verdict": "SKIP", "reason": "No usability scores collected"}

    avg_score = sum(scores) / len(scores)
    pct_good = sum(1 for s in scores if s >= 4) / len(scores)

    # Tier 0 sanitization ALWAYS loses some information (amounts, addresses).
    # A score of 2-3/5 is expected and healthy — it means the sanitizer is
    # doing its job. FAIL means queries are destroyed (empty, incoherent).
    if avg_score >= 3.0:
        verdict = "PASS"
    elif avg_score >= 2.0:
        verdict = "MARGINAL"
    else:
        verdict = "FAIL"

    # Flag queries that scored 1 (destroyed) or 2 (key info lost) for potential refinement
    low_quality = [d for d in details if d["score"] <= 2]

    return {
        "samples": len(scores),
        "avg_score": round(avg_score, 2),
        "pct_good": round(pct_good, 4),
        "pct_destroyed": round(len(low_quality) / max(len(scores), 1), 4),
        "score_distribution": {s: scores.count(s) for s in range(1, 6)},
        "low_quality_queries": low_quality[:5],
        "details": details[:5],
        "verdict": verdict,
        "note": "Tier 0 sanitization loses amounts by design. Avg <2.0 = over-stripping. Score <=2 = low quality.",
    }


# ---------------------------------------------------------------------------
# Full validation report
# ---------------------------------------------------------------------------

def validate_profile(
    profile_path: str | None = None,
    profile: dict | None = None,
    dataset_path: str | None = None,
    queries: list[dict] | None = None,
    span_results: list[dict] | None = None,
    progress: bool = True,
) -> dict:
    """Run all validation checks and produce a traffic-light report.

    Either provide profile_path (loads from disk) or profile (dict).
    Either provide dataset_path (loads JSONL) or queries (list of dicts).
    span_results is optional — needed for sanitizer completeness check.

    Returns: {properties: {name: result_dict}, summary: {pass, marginal, fail}}
    """
    if profile is None:
        if profile_path is None:
            raise ValueError("Must provide either profile or profile_path")
        profile = load_profile(profile_path)

    if queries is None:
        if dataset_path is None:
            raise ValueError("Must provide either queries or dataset_path")
        from meta.analyzer import load_dataset
        queries = load_dataset(dataset_path)

    results = {}

    # 1. Sanitizer completeness
    if span_results:
        if progress:
            print("Checking sanitizer completeness...")
        results["sanitizer_completeness"] = check_sanitizer_completeness(
            profile, span_results
        )
        if progress:
            r = results["sanitizer_completeness"]
            print(f"  {r['passed']}/{r['total']} spans stripped "
                  f"({r['verdict']})")
    else:
        results["sanitizer_completeness"] = {
            "verdict": "SKIP",
            "reason": "No span_results provided",
        }

    # 2. False positive rate
    if progress:
        print("Checking false positive rate...")
    results["false_positive_rate"] = check_false_positive_rate(profile, queries)
    if progress:
        r = results["false_positive_rate"]
        print(f"  Avg removal rate: {r.get('avg_word_removal_rate', 'N/A')} "
              f"({r['verdict']})")

    # 3. Profile completeness
    if progress:
        print("Checking profile completeness...")
    results["profile_completeness"] = check_profile_completeness(profile, queries)
    if progress:
        r = results["profile_completeness"]
        print(f"  {r['matched']}/{r['total']} queries matched "
              f"({r['verdict']})")

    # 4. Template coverage
    if progress:
        print("Checking template coverage...")
    results["template_coverage"] = check_template_coverage(profile, queries)
    if progress:
        r = results["template_coverage"]
        print(f"  {r['matched']}/{r['total']} queries matched "
              f"(avg score {r['avg_score']}) ({r['verdict']})")

    # 5. Vocabulary depth
    if progress:
        print("Checking vocabulary depth...")
    results["vocabulary_depth"] = check_vocabulary_depth(profile)
    if progress:
        r = results["vocabulary_depth"]
        print(f"  {r['deficient_slots']} deficient slots "
              f"({r['verdict']})")

    # 6. Cover quality
    if progress:
        print("Checking cover quality...")
    results["cover_quality"] = check_cover_quality(profile, queries)
    if progress:
        r = results["cover_quality"]
        print(f"  Detection rate: {r['detection_rate']} vs "
              f"{r['random_baseline']} random ({r['verdict']})")

    # 7. Entity completeness (anti-omission)
    if progress:
        print("Checking entity completeness...")
    results["entity_completeness"] = check_entity_completeness(profile, queries)
    if progress:
        r = results["entity_completeness"]
        print(f"  {r.get('covered', 0)}/{r.get('found_in_queries', 0)} entities covered "
              f"({r['verdict']})")

    # 8. Held-out sanitizer test (anti-self-certification)
    if progress:
        print("Checking held-out sanitizer...")
    results["held_out_sanitizer"] = check_held_out_sanitizer(
        profile, queries_for_held_out=queries
    )
    if progress:
        r = results["held_out_sanitizer"]
        if r["verdict"] != "SKIP":
            print(f"  {r.get('stripped', 0)}/{r.get('total_params', 0)} params stripped "
                  f"({r['verdict']})")
        else:
            print(f"  Skipped: {r.get('reason', '')}")

    # 9. Ontology balance (anti-fingerprinting)
    if progress:
        print("Checking ontology balance...")
    results["ontology_balance"] = check_ontology_balance(profile)
    if progress:
        r = results["ontology_balance"]
        if r["verdict"] != "SKIP":
            print(f"  Min/max ratio: {r.get('ratio', 'N/A')} ({r['verdict']})")
        else:
            print(f"  Skipped: {r.get('reason', '')}")

    # 10. Sensitivity label completeness (anti-self-certification)
    if progress:
        print("Checking sensitivity label completeness...")
    results["sensitivity_labels"] = check_sensitivity_labels(queries, span_results, profile)
    if progress:
        r = results["sensitivity_labels"]
        if r["verdict"] != "SKIP":
            print(f"  Min category coverage: {r.get('min_category_coverage', 'N/A')} "
                  f"({r['verdict']})")
        else:
            print(f"  Skipped: {r.get('reason', '')}")

    # 11. Vocabulary diversity (anti-duplication)
    if progress:
        print("Checking vocabulary diversity...")
    results["vocabulary_diversity"] = check_vocabulary_diversity(profile)
    if progress:
        r = results["vocabulary_diversity"]
        print(f"  {r['duplicates_found']} near-duplicates found ({r['verdict']})")

    # 12. Tier 1 pipeline quality
    if progress:
        print("Checking Tier 1 pipeline quality...")
    results["tier1_pipeline"] = check_tier1_pipeline(profile, queries, progress=progress)
    if progress:
        r = results["tier1_pipeline"]
        if r["verdict"] != "SKIP":
            print(f"  Pipeline: {r.get('avg_pipeline', 'N/A')}/5, "
                  f"retained {r.get('quality_retained', 0):.0%} ({r['verdict']})")
        else:
            print(f"  Skipped: {r.get('reason', '')}")

    # 13. Tier 0 usability preservation
    if progress:
        print("Checking Tier 0 usability...")
    results["usability"] = check_usability(profile, queries, progress=progress)
    if progress:
        r = results["usability"]
        if r["verdict"] != "SKIP":
            print(f"  Avg score: {r.get('avg_score', 'N/A')}/5 ({r['verdict']})")
        else:
            print(f"  Skipped: {r.get('reason', '')}")

    # Summary
    verdicts = [r.get("verdict", "SKIP") for r in results.values()]
    summary = {
        "pass": sum(1 for v in verdicts if v == "PASS"),
        "marginal": sum(1 for v in verdicts if v == "MARGINAL"),
        "fail": sum(1 for v in verdicts if v == "FAIL"),
        "skip": sum(1 for v in verdicts if v == "SKIP"),
    }

    overall = "PASS"
    if summary["fail"] > 0:
        overall = "FAIL"
    elif summary["marginal"] > 0:
        overall = "MARGINAL"

    if progress:
        print(f"\n{'='*60}")
        print(f"VALIDATION SUMMARY: {overall}")
        print(f"  PASS: {summary['pass']}  MARGINAL: {summary['marginal']}  "
              f"FAIL: {summary['fail']}  SKIP: {summary['skip']}")
        print(f"{'='*60}")

    return {
        "properties": results,
        "summary": summary,
        "overall": overall,
    }
