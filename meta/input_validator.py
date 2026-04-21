"""
Input dataset validator — pre-flight checks before profile generation.

Validates the JSONL dataset is suitable for quality profile generation.
Runs before any LLM calls, catching garbage inputs early and saving time.

Checks:
  1. Minimum query count (>=20 for basic, >=50 recommended)
  2. Label distribution (not all same label, has sensitive+non_sensitive)
  3. Language quality (queries are questions, not gibberish)
  4. Domain coherence (queries are related, not random topics)
  5. Duplicate detection (no excessive repetition)
  6. Schema compliance (required fields present)
"""

from __future__ import annotations

import re
from collections import Counter


def validate_dataset(queries: list[dict], progress: bool = True) -> dict:
    """Run all pre-flight checks on the dataset.

    Args:
        queries: list of dicts loaded from JSONL, each must have 'text' field

    Returns: {
        checks: {name: {verdict, ...}},
        overall: "PASS" | "MARGINAL" | "FAIL",
        reason: str,
    }
    """
    checks = {}

    checks["query_count"] = _check_query_count(queries)
    checks["schema"] = _check_schema(queries)
    checks["label_distribution"] = _check_label_distribution(queries)
    checks["language_quality"] = _check_language_quality(queries)
    checks["duplicates"] = _check_duplicates(queries)
    checks["domain_coherence"] = _check_domain_coherence(queries)

    verdicts = [c.get("verdict", "SKIP") for c in checks.values()]
    fail_count = sum(1 for v in verdicts if v == "FAIL")
    marginal_count = sum(1 for v in verdicts if v == "MARGINAL")

    if fail_count > 0:
        failed = [name for name, c in checks.items() if c.get("verdict") == "FAIL"]
        overall = "FAIL"
        reason = f"{fail_count} checks failed: {failed}"
    elif marginal_count > 1:
        overall = "MARGINAL"
        reason = f"{marginal_count} checks marginal"
    else:
        overall = "PASS"
        reason = "Dataset suitable for profile generation"

    if progress:
        print(f"Input validation: {overall}")
        for name, check in checks.items():
            v = check.get("verdict", "SKIP")
            detail = check.get("detail", "")
            symbol = {"PASS": "+", "MARGINAL": "~", "FAIL": "!"}
            print(f"  [{symbol.get(v, '?')}] {name}: {v} {detail}")
        if overall == "FAIL":
            print(f"  REJECTED: {reason}")
            print(f"  Fix the dataset and re-run.")

    return {"checks": checks, "overall": overall, "reason": reason}


# ---------------------------------------------------------------------------
# Check 1: Query count
# ---------------------------------------------------------------------------

def _check_query_count(queries: list[dict]) -> dict:
    n = len(queries)
    if n >= 50:
        return {"verdict": "PASS", "count": n, "detail": f"({n} queries)"}
    elif n >= 20:
        return {"verdict": "MARGINAL", "count": n,
                "detail": f"({n} queries — 50+ recommended)"}
    else:
        return {"verdict": "FAIL", "count": n,
                "detail": f"({n} queries — minimum 20 required)"}


# ---------------------------------------------------------------------------
# Check 2: Schema compliance
# ---------------------------------------------------------------------------

def _check_schema(queries: list[dict]) -> dict:
    missing_text = sum(1 for q in queries if "text" not in q)
    missing_label = sum(1 for q in queries if "label" not in q)
    empty_text = sum(1 for q in queries if not q.get("text", "").strip())

    issues = []
    if missing_text > 0:
        issues.append(f"{missing_text} entries missing 'text'")
    if empty_text > 0:
        issues.append(f"{empty_text} entries with empty text")
    if missing_label > 0:
        issues.append(f"{missing_label} entries missing 'label'")

    if missing_text > 0 or empty_text > len(queries) * 0.1:
        return {"verdict": "FAIL", "issues": issues,
                "detail": f"({'; '.join(issues)})"}
    elif missing_label > len(queries) * 0.5:
        return {"verdict": "MARGINAL", "issues": issues,
                "detail": f"({'; '.join(issues)})"}
    else:
        return {"verdict": "PASS", "issues": issues,
                "detail": "" if not issues else f"({'; '.join(issues)})"}


# ---------------------------------------------------------------------------
# Check 3: Label distribution
# ---------------------------------------------------------------------------

def _check_label_distribution(queries: list[dict]) -> dict:
    labels = Counter(q.get("label", "unlabeled") for q in queries)
    total = len(queries)

    has_sensitive = labels.get("sensitive", 0) > 0
    has_non_sensitive = labels.get("non_sensitive", 0) > 0
    unlabeled_pct = labels.get("unlabeled", 0) / max(total, 1)

    # Check for dominant single label
    most_common_label, most_common_count = labels.most_common(1)[0]
    dominance = most_common_count / max(total, 1)

    if not has_sensitive:
        return {"verdict": "FAIL", "distribution": dict(labels),
                "detail": "(no 'sensitive' queries — cannot validate sanitizer)"}
    elif not has_non_sensitive:
        return {"verdict": "MARGINAL", "distribution": dict(labels),
                "detail": "(no 'non_sensitive' queries — cannot check false positives)"}
    elif dominance > 0.90:
        return {"verdict": "MARGINAL", "distribution": dict(labels),
                "detail": f"({dominance:.0%} queries are '{most_common_label}' — imbalanced)"}
    elif unlabeled_pct > 0.50:
        return {"verdict": "MARGINAL", "distribution": dict(labels),
                "detail": f"({unlabeled_pct:.0%} unlabeled)"}
    else:
        return {"verdict": "PASS", "distribution": dict(labels), "detail": ""}


# ---------------------------------------------------------------------------
# Check 4: Language quality
# ---------------------------------------------------------------------------

def _check_language_quality(queries: list[dict]) -> dict:
    total = len(queries)
    if total == 0:
        return {"verdict": "FAIL", "detail": "(no queries)"}

    too_short = 0       # < 10 chars
    too_long = 0        # > 2000 chars
    not_question = 0    # no question mark and doesn't start with question word
    low_alpha = 0       # < 50% alphabetic characters (gibberish)

    question_words = {"what", "how", "why", "when", "where", "which", "can",
                      "does", "should", "would", "could", "is", "are", "do",
                      "will", "if", "my", "i"}

    for q in queries:
        text = q.get("text", "")
        if len(text) < 10:
            too_short += 1
        if len(text) > 2000:
            too_long += 1

        # Check if it's question-like
        has_qmark = "?" in text
        first_word = text.split()[0].lower() if text.split() else ""
        is_question_like = has_qmark or first_word in question_words
        if not is_question_like:
            not_question += 1

        # Check for gibberish (low alphabetic ratio)
        alpha_count = sum(1 for c in text if c.isalpha())
        if len(text) > 0 and alpha_count / len(text) < 0.5:
            low_alpha += 1

    issues = []
    if too_short > 0:
        issues.append(f"{too_short} too short (<10 chars)")
    if too_long > 0:
        issues.append(f"{too_long} too long (>2000 chars)")
    if not_question > total * 0.5:
        issues.append(f"{not_question}/{total} not question-like")
    if low_alpha > 0:
        issues.append(f"{low_alpha} low-quality/gibberish")

    bad_pct = (too_short + low_alpha) / max(total, 1)

    if bad_pct > 0.20:
        return {"verdict": "FAIL", "issues": issues,
                "detail": f"({'; '.join(issues)})"}
    elif bad_pct > 0.05 or not_question > total * 0.5:
        return {"verdict": "MARGINAL", "issues": issues,
                "detail": f"({'; '.join(issues)})" if issues else ""}
    else:
        return {"verdict": "PASS", "issues": issues, "detail": ""}


# ---------------------------------------------------------------------------
# Check 5: Duplicate detection
# ---------------------------------------------------------------------------

def _check_duplicates(queries: list[dict]) -> dict:
    texts = [q.get("text", "").strip().lower() for q in queries]
    total = len(texts)
    unique = len(set(texts))
    dup_count = total - unique
    dup_pct = dup_count / max(total, 1)

    # Find most repeated
    counts = Counter(texts)
    most_common = counts.most_common(1)
    max_repeats = most_common[0][1] if most_common else 0

    if dup_pct > 0.20:
        return {"verdict": "FAIL", "duplicates": dup_count,
                "max_repeats": max_repeats,
                "detail": f"({dup_count} duplicates, {dup_pct:.0%} of dataset)"}
    elif dup_pct > 0.05:
        return {"verdict": "MARGINAL", "duplicates": dup_count,
                "max_repeats": max_repeats,
                "detail": f"({dup_count} duplicates)"}
    else:
        return {"verdict": "PASS", "duplicates": dup_count,
                "max_repeats": max_repeats, "detail": ""}


# ---------------------------------------------------------------------------
# Check 6: Domain coherence
# ---------------------------------------------------------------------------

def _check_domain_coherence(queries: list[dict]) -> dict:
    """Check that queries are from a coherent domain, not random topics.

    Uses vocabulary overlap as a proxy: queries from the same domain share
    significant vocabulary. Random queries have low pairwise overlap.
    """
    if len(queries) < 10:
        return {"verdict": "SKIP", "detail": "(too few queries to assess)"}

    # Build word sets for each query (stop words removed)
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "can", "shall", "to", "of", "in", "for",
        "on", "with", "at", "by", "from", "as", "into", "through", "during",
        "before", "after", "above", "below", "between", "and", "but", "or",
        "not", "no", "so", "if", "then", "than", "too", "very", "just",
        "about", "up", "out", "how", "what", "when", "where", "which", "who",
        "why", "this", "that", "these", "those", "it", "its", "my", "your",
        "his", "her", "our", "their", "i", "you", "he", "she", "we", "they",
    }

    word_sets = []
    for q in queries[:100]:
        words = set(
            w.lower() for w in re.findall(r'\b[a-zA-Z]{3,}\b', q.get("text", ""))
            if w.lower() not in stop_words
        )
        word_sets.append(words)

    # Measure: what fraction of words appear in >= 5% of queries?
    all_words: Counter = Counter()
    for ws in word_sets:
        for w in ws:
            all_words[w] += 1

    threshold = max(len(word_sets) * 0.05, 2)
    shared_words = sum(1 for w, c in all_words.items() if c >= threshold)
    total_unique = len(all_words)

    coherence = shared_words / max(total_unique, 1)

    if coherence >= 0.10:
        return {"verdict": "PASS", "coherence": round(coherence, 4),
                "shared_words": shared_words,
                "detail": f"({coherence:.0%} vocabulary coherence)"}
    elif coherence >= 0.05:
        return {"verdict": "MARGINAL", "coherence": round(coherence, 4),
                "shared_words": shared_words,
                "detail": f"({coherence:.0%} vocabulary coherence — queries may be too diverse)"}
    else:
        return {"verdict": "FAIL", "coherence": round(coherence, 4),
                "shared_words": shared_words,
                "detail": f"({coherence:.0%} vocabulary coherence — queries appear unrelated)"}
