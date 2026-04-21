"""
Refinement loop — iterates between validation and LLM-based pattern repair.

When the validation engine reports false negatives (sensitive spans that survive
sanitization), this module feeds the missed spans back to the local LLM to
generate better regex patterns. Iterates until validation passes or max rounds.

Usage:
    from meta.refiner import refine_profile
    profile, report = refine_profile(profile, queries, span_results, max_rounds=3)
"""

from __future__ import annotations

import json
import re

from llm_backend import call_llm
from meta.validation_engine import check_sanitizer_completeness
from meta.util import extract_json as _extract_json


# ---------------------------------------------------------------------------
# LLM prompt for pattern repair
# ---------------------------------------------------------------------------

REPAIR_PROMPT = """\
You are a regex engineer fixing a privacy sanitizer. The sanitizer FAILED to \
strip certain sensitive spans from user queries. For each missed span, write \
a regex pattern that would catch it and similar variants.

Rules:
- Output valid Python re module regex syntax
- Patterns should be general enough to catch variants (different numbers, \
  different names) but specific enough to avoid false positives
- Include the flags: "IGNORECASE" or "CASESENSITIVE"
- For each pattern, explain what class of sensitive data it catches

Output JSON:
{
  "repairs": [
    {
      "pattern": "regex string",
      "flags": "IGNORECASE",
      "catches": "description of what this catches",
      "test_cases": ["example1 that should match", "example2"]
    }
  ]
}"""


def _validate_regex(pattern: str) -> bool:
    try:
        re.compile(pattern)
        return True
    except re.error:
        return False


# ---------------------------------------------------------------------------
# Core repair function
# ---------------------------------------------------------------------------

def repair_patterns(
    false_negatives: list[dict],
    progress: bool = True,
) -> list[dict]:
    """Given false negatives from validation, generate repair patterns via LLM.

    Args:
        false_negatives: list of {query, span, category, sanitized_output}

    Returns:
        list of {pattern, flags} dicts ready to add to the profile.
    """
    if not false_negatives:
        return []

    if progress:
        print(f"  Repairing {len(false_negatives)} false negatives...")

    # Group by category for context
    by_category: dict[str, list[dict]] = {}
    for fn in false_negatives:
        cat = fn.get("category", "unknown")
        by_category.setdefault(cat, []).append(fn)

    # Build the prompt with all missed spans
    lines = []
    for cat, fns in sorted(by_category.items()):
        lines.append(f"\nCategory: {cat}")
        for fn in fns[:15]:  # cap per category
            lines.append(f'  Missed span: "{fn["span"]}"')
            lines.append(f'  In query: "{fn["query"]}"')
            lines.append(f'  After sanitization: "{fn["sanitized_output"]}"')
            lines.append("")

    missed_block = "\n".join(lines)

    resp = call_llm(
        prompt=f"Missed sensitive spans:\n{missed_block}",
        system=REPAIR_PROMPT,
        max_tokens=2048,
    )

    parsed = _extract_json(resp)
    repairs = []
    if isinstance(parsed, dict):
        for repair in parsed.get("repairs", []):
            if not isinstance(repair, dict):
                continue
            pattern = repair.get("pattern", "")
            if not pattern or not _validate_regex(pattern):
                if progress and pattern:
                    print(f"    [warn] Invalid repair pattern: {pattern!r}")
                continue
            flags = repair.get("flags", "IGNORECASE")
            repairs.append({"pattern": pattern, "flags": flags})

    if progress:
        print(f"  Generated {len(repairs)} repair patterns")

    return repairs


def apply_repairs(profile: dict, repairs: list[dict]) -> dict:
    """Add repair patterns to the profile's sensitive_patterns section.

    Returns the modified profile (mutated in place).
    """
    sp = profile.setdefault("sensitive_patterns", {})

    for repair in repairs:
        flags = repair.get("flags", "IGNORECASE")
        pattern = repair["pattern"]

        if flags == "IGNORECASE":
            icase = sp.setdefault("amount_patterns_icase", [])
            if pattern not in icase:
                icase.append(pattern)
        else:
            csense = sp.setdefault("amount_patterns_csense", [])
            if pattern not in csense:
                csense.append(pattern)

    return profile


# ---------------------------------------------------------------------------
# Refinement loop
# ---------------------------------------------------------------------------

def refine_profile(
    profile: dict,
    queries: list[dict],
    span_results: list[dict],
    max_rounds: int = 3,
    progress: bool = True,
) -> tuple[dict, dict]:
    """Iterate: validate → repair → validate until PASS or max_rounds.

    Circuit breaker: if no improvement between rounds, stops early and
    reports what failed. This prevents wasting LLM calls on repairs
    that don't help.

    Args:
        profile: the generated DomainProfile dict
        queries: the original dataset
        span_results: sensitivity analysis results with labeled spans
        max_rounds: maximum repair iterations
        progress: print progress

    Returns:
        (refined_profile, final_validation_result)
    """
    if progress:
        print(f"\nRefinement loop (max {max_rounds} rounds)")

    prev_fn_count = None

    for round_num in range(1, max_rounds + 1):
        if progress:
            print(f"\n--- Round {round_num}/{max_rounds} ---")

        # Validate
        result = check_sanitizer_completeness(profile, span_results)
        fn_count = len(result.get("false_negatives", []))

        if progress:
            print(f"  Sanitizer: {result['passed']}/{result['total']} "
                  f"({result['verdict']}), {fn_count} false negatives")

        if result["verdict"] == "PASS":
            if progress:
                print(f"  PASS — no refinement needed")
            return profile, result

        if fn_count == 0:
            if progress:
                print(f"  No false negatives to repair")
            return profile, result

        # Circuit breaker: no improvement or regression from last round
        if prev_fn_count is not None:
            if fn_count > prev_fn_count:
                # Regression — repairs made things worse
                if progress:
                    print(f"  REGRESSION ({prev_fn_count} -> {fn_count}). Stopping.")
                result["stalled"] = True
                result["escalation"] = f"Regression: {prev_fn_count} -> {fn_count} FN."
                return profile, result
            elif fn_count == prev_fn_count:
                # Stall — no improvement
                if progress:
                    print(f"  No improvement ({fn_count} FN). Stopping.")
                result["stalled"] = True
                result["escalation"] = f"Stalled at {fn_count} FN."
                return profile, result
        prev_fn_count = fn_count

        # Repair
        repairs = repair_patterns(result["false_negatives"], progress=progress)

        if not repairs:
            if progress:
                print(f"  LLM could not generate valid repairs. Stopping.")
            result["stalled"] = True
            result["escalation"] = "LLM failed to generate valid repair patterns."
            return profile, result

        # Apply repairs
        profile = apply_repairs(profile, repairs)
        if progress:
            print(f"  Applied {len(repairs)} repairs to profile")

    # Final validation after all rounds
    if progress:
        print(f"\n--- Final validation ---")
    result = check_sanitizer_completeness(profile, span_results)
    fn_count = len(result.get("false_negatives", []))
    if progress:
        print(f"  Sanitizer: {result['passed']}/{result['total']} "
              f"({result['verdict']}), {fn_count} false negatives remaining")
    if result["verdict"] != "PASS":
        result["stalled"] = True
        result["escalation"] = (
            f"Exhausted {max_rounds} rounds with {fn_count} false negatives remaining. "
            f"Recommend: larger model, more training data, or manual pattern crafting."
        )

    return profile, result


# ---------------------------------------------------------------------------
# Usability refinement
# ---------------------------------------------------------------------------

USABILITY_REPAIR_PROMPT = """\
You are a regex engineer improving a privacy sanitizer's USABILITY. The \
sanitizer is stripping too much from certain queries, destroying their meaning. \
For each destroyed query, identify which words are being incorrectly removed \
and suggest false-positive exception words that should be PRESERVED.

Rules:
- Only suggest words that are NOT sensitive (not amounts, addresses, or private data)
- Suggest domain terminology, protocol names, or technical terms that happen to match amount patterns
- Output words that should be added to the false_positive_words list

Output JSON:
{
  "false_positive_additions": ["word1", "word2"],
  "reasoning": "why these words should be preserved"
}"""


def refine_usability(
    profile: dict,
    queries: list[dict],
    max_rounds: int = 2,
    progress: bool = True,
) -> tuple[dict, dict]:
    """Iterate: check usability → add false-positive exceptions → re-check.

    When the sanitizer destroys queries (score 1), this identifies
    over-broad patterns and adds false-positive exceptions to preserve
    domain terminology.

    Returns:
        (refined_profile, final_usability_result)
    """
    from meta.validation_engine import check_usability

    if progress:
        print(f"\nUsability refinement (max {max_rounds} rounds)")

    for round_num in range(1, max_rounds + 1):
        if progress:
            print(f"\n--- Usability round {round_num}/{max_rounds} ---")

        result = check_usability(profile, queries, n_samples=10, progress=progress)

        if progress:
            print(f"  Usability: {result.get('avg_score', 'N/A')}/5 ({result['verdict']})")

        if result["verdict"] == "SKIP":
            return profile, result

        # Refine queries that scored 1 (destroyed) or 2 (key info lost)
        bad_queries = [d for d in result.get("details", []) if d["score"] <= 2]
        if not bad_queries:
            # Also check legacy key for backwards compatibility
            bad_queries = result.get("low_quality_queries", [])
        if not bad_queries:
            if progress:
                print(f"  No low-quality queries — usability acceptable")
            return profile, result

        if progress:
            print(f"  {len(bad_queries)} low-quality queries (score<=2) — attempting repair")

        # Ask LLM to identify over-stripping
        examples = "\n".join(
            f"  Original: {d['original']}\n  Sanitized: {d['sanitized']}\n"
            for d in bad_queries[:5]
        )
        resp = call_llm(
            prompt=f"Destroyed queries:\n{examples}",
            system=USABILITY_REPAIR_PROMPT,
            max_tokens=1024,
        )
        parsed = _extract_json(resp)
        if not isinstance(parsed, dict):
            if progress:
                print(f"  LLM could not suggest repairs")
            return profile, result

        # Apply false-positive additions
        fp_additions = parsed.get("false_positive_additions", [])
        sp = profile.setdefault("sensitive_patterns", {})
        existing_fp = set(sp.get("false_positive_words", []))
        added = 0
        for word in fp_additions:
            if isinstance(word, str) and word not in existing_fp:
                sp.setdefault("false_positive_words", []).append(word)
                existing_fp.add(word)
                added += 1

        if progress:
            print(f"  Added {added} false-positive exceptions: {fp_additions[:5]}")

        if added == 0:
            if progress:
                print(f"  No new exceptions — stopping")
            return profile, result

    # Final check
    result = check_usability(profile, queries, n_samples=10, progress=progress)
    if progress:
        print(f"  Final usability: {result.get('avg_score', 'N/A')}/5 ({result['verdict']})")
    if result.get("verdict") == "FAIL":
        result["stalled"] = True
        result["escalation"] = (
            f"Usability refinement exhausted {max_rounds} rounds. "
            f"Score: {result.get('avg_score', 'N/A')}/5. "
            f"Recommend: review patterns for over-stripping, or use Tier 1 pipeline."
        )
    return profile, result
