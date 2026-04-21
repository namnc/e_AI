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


def _extract_json(text: str) -> dict | None:
    start = text.find('{')
    if start == -1:
        return None
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
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


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
            # Shouldn't happen, but guard against it
            if progress:
                print(f"  No false negatives to repair")
            return profile, result

        # Repair
        repairs = repair_patterns(result["false_negatives"], progress=progress)

        if not repairs:
            if progress:
                print(f"  LLM could not generate valid repairs. Stopping.")
            return profile, result

        # Apply repairs
        profile = apply_repairs(profile, repairs)
        if progress:
            print(f"  Applied {len(repairs)} repairs to profile")

    # Final validation after all rounds
    if progress:
        print(f"\n--- Final validation ---")
    result = check_sanitizer_completeness(profile, span_results)
    if progress:
        fn_count = len(result.get("false_negatives", []))
        print(f"  Sanitizer: {result['passed']}/{result['total']} "
              f"({result['verdict']}), {fn_count} false negatives remaining")

    return profile, result
