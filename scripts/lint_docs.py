#!/usr/bin/env python3
"""
Documentation drift linter for e_AI v2.

Checks (per Codex 2026-05-07 review):

  R1. Profile-count drift. Every claim of the form "N guards", "N profiles",
      "N production profiles", "N production domains" must equal the actual
      number of v2 production domains under domains/ (excluding _template,
      _feedback, and defi_* variants which are Part 3 R&D, not v2).

  R2. Production-vs-prototype wording. Any claim containing "production-grade"
      or "production-ready" must either be (a) hedged ("not yet", "not
      production", "in the sense of"), or (b) attributed to a third party
      (TEE/Phala/Brave/Azure/Intel/AMD/Confidential).

  R3. AI_PS path escape. References to AI_PS-only paths
      (projects/<aips_project>/, "AI_PS", ~/Documents/Claude/AI_PS) must not
      appear in user-facing docs (README, ethresearch_*, companion_*). They
      are allowed in internal-state docs (docs/domain_status.md,
      docs/publication_checklist.md, docs/v2_plan.md, docs/v1_README_archive.md)
      because those are not published.

Exit code: 0 if clean, 1 if any drift detected.

Wired as `python3 scripts/lint_docs.py` from CI.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DOMAINS_DIR = REPO / "domains"

# Domains that are NOT v2 production guards.
SKIP_DOMAINS = {"_template", "_feedback"}
SKIP_PREFIXES = ("defi",)  # defi, defi_*, defi_14b etc. — Part 3 variants

# Internal docs where AI_PS path references are tolerated.
INTERNAL_DOCS_ALLOWLIST = {
    "docs/domain_status.md",
    "docs/publication_checklist.md",
    "docs/v2_plan.md",
    "docs/v1_README_archive.md",
}

# Files lint applies to (relative to REPO).
def _doc_files() -> list[Path]:
    files = []
    for p in REPO.glob("*.md"):
        if p.name == "CHANGELOG.md":
            continue
        files.append(p)
    files.extend((REPO / "docs").glob("*.md"))
    files.extend((REPO / "domains").glob("*/README.md"))
    return sorted(files)


def count_v2_production_domains() -> int:
    n = 0
    for child in DOMAINS_DIR.iterdir():
        if not child.is_dir():
            continue
        name = child.name
        if name in SKIP_DOMAINS:
            continue
        if any(name == prefix or name.startswith(prefix + "_") for prefix in SKIP_PREFIXES):
            continue
        n += 1
    return n


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

# R1: only fire on TOTAL-set claims, not cluster/subdivision counts.
# Conservative patterns that strongly imply "N is the total guard count":
#   "all 16 guards", "the 16 guards", "set of 16 guards", "full set of 16",
#   "across all 16 guards", "16 profile-validated prototype guards",
#   "16 production profiles", "16 production domains".
COUNT_PATTERNS = [
    re.compile(r"\ball\s+(\d{1,3})\s+(?:profile-validated\s+)?(?:prototype\s+)?guards?\b", re.I),
    re.compile(r"\bthe\s+(\d{1,3})\s+(?:profile-validated\s+)?(?:prototype\s+)?guards?\b", re.I),
    re.compile(r"\bset\s+of\s+(\d{1,3})\s+guards?\b", re.I),
    re.compile(r"\bacross\s+all\s+(\d{1,3})\s+guards?\b", re.I),
    re.compile(r"\b(\d{1,3})\s+profile-validated\s+(?:prototype\s+)?guards?\b", re.I),
    re.compile(r"\b(\d{1,3})\s+production\s+profiles?\b", re.I),
    re.compile(r"\b(\d{1,3})\s+production\s+domains?\b", re.I),
]
# Reserved for future false-positive token list (not currently used after
# tightening COUNT_PATTERNS to total-only forms).
COUNT_FALSE_POSITIVE_TOKENS: tuple[str, ...] = ()

PROD_CLAIM_RE = re.compile(r"\bproduction[- ](?:ready|grade)\b", re.I)
HEDGE_TOKENS = (
    "not yet", "not production", "isn't production", "is not production",
    "in the sense of",
)
THIRD_PARTY_TOKENS = (
    "phala", "brave leo", "azure", "confidential vm", "intel sgx", "intel tdx",
    "amd sev", "tee ", "tees", "(phala", "(brave", "(azure", "(intel", "(amd",
    "confidential computing",
)

# R3: AI_PS path escape.
AI_PS_PATTERNS = [
    re.compile(r"\bAI[_-]PS\b"),
    re.compile(r"~/Documents/Claude/AI[_-]PS"),
]
# Match `projects/<name>/` references where <name> is NOT one of e_AI's own
# subprojects. e_AI itself doesn't have a top-level projects/ dir, so any
# such reference is an AI_PS leak.
PROJECTS_PATH_RE = re.compile(r"projects/[a-z][a-z0-9_]+/")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _line_excludes_false_positive(line: str) -> bool:
    line_lc = line.lower()
    return not any(tok in line_lc for tok in COUNT_FALSE_POSITIVE_TOKENS)


def _claim_is_hedged(line: str, prev_line: str) -> bool:
    line_lc = line.lower()
    prev_lc = prev_line.lower()
    for tok in HEDGE_TOKENS + THIRD_PARTY_TOKENS:
        if tok in line_lc or tok in prev_lc:
            return True
    return False


def _is_internal_doc(rel_path: str) -> bool:
    return rel_path in INTERNAL_DOCS_ALLOWLIST


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def lint() -> int:
    expected_count = count_v2_production_domains()
    issues: list[str] = []

    files = _doc_files()
    if not files:
        print("ERROR: no doc files found — repo layout changed?", file=sys.stderr)
        return 1

    for f in files:
        rel = str(f.relative_to(REPO))
        try:
            text = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        lines = text.splitlines()

        for i, line in enumerate(lines):
            line_no = i + 1
            prev = lines[i - 1] if i > 0 else ""

            # R1: count drift (dedup per (line_no, n) — multiple patterns may
            # overlap on the same span, e.g. "across all 17 guards" matches
            # both \bacross\s+all\s+ and the embedded \ball\s+ pattern).
            if _line_excludes_false_positive(line):
                seen_ns: set[int] = set()
                for pat in COUNT_PATTERNS:
                    for m in pat.finditer(line):
                        n = int(m.group(1))
                        if not (1 <= n <= 99 and n != expected_count):
                            continue
                        if n in seen_ns:
                            continue
                        seen_ns.add(n)
                        issues.append(
                            f"{rel}:{line_no}: R1 count drift — claims '{m.group(0)}' "
                            f"but actual v2 production domains = {expected_count}"
                        )

            # R2: production claim must be hedged or third-party
            if PROD_CLAIM_RE.search(line):
                if not _claim_is_hedged(line, prev):
                    issues.append(
                        f"{rel}:{line_no}: R2 unhedged production claim — "
                        f"'{line.strip()[:120]}'"
                    )

            # R3: AI_PS path escape (skip internal-only docs)
            if not _is_internal_doc(rel):
                for pat in AI_PS_PATTERNS:
                    if pat.search(line):
                        issues.append(
                            f"{rel}:{line_no}: R3 AI_PS reference leaked — "
                            f"'{line.strip()[:120]}'"
                        )
                if PROJECTS_PATH_RE.search(line):
                    issues.append(
                        f"{rel}:{line_no}: R3 projects/ path leaked — "
                        f"'{line.strip()[:120]}'"
                    )

    if issues:
        print("Documentation drift detected:", file=sys.stderr)
        for issue in issues:
            print(f"  {issue}", file=sys.stderr)
        print(
            f"\n{len(issues)} issue(s). v2 production domain count = {expected_count}.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: docs clean. v2 production domain count = {expected_count}.")
    return 0


if __name__ == "__main__":
    sys.exit(lint())
