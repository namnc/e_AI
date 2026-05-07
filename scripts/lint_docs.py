#!/usr/bin/env python3
"""
Documentation drift linter for e_AI v2.

Checks (per Codex 2026-05-07 + Phase 3 reviews):

  R1. Profile-count drift. Every claim of the form "N guards", "N profiles",
      "N production profiles", "N production domains", "N v2 guards", or the
      word forms ("fifteen guards", "sixteen guards", "seventeen guards")
      must equal the actual number of v2 production profile.json files
      under domains/ (excluding _template, _feedback, and defi_* variants
      which are Part 3 R&D, not v2). Counting profile.json (not directories)
      mirrors what CI's validation loop iterates over (Phase 3 review #R1.2).

  R2. Production-vs-prototype wording. Any claim containing "production-grade",
      "production-ready", "Maturity: Production", or "Tier 1 production"
      must either be (a) hedged ("not yet", "not production",
      "in the sense of"), or (b) attributed to a third party (TEE / Phala /
      Brave / Azure / Intel / AMD / Confidential / Blockaid / Pocket Universe /
      Flashbots / Rabby / Scam Sniffer / Semaphore / Railgun).

  R3. AI_PS path escape. References to AI_PS-only paths
      (projects/<aips_project>/, "AI_PS", ~/Documents/Claude/AI_PS) must not
      appear in user-facing docs. Internal-state docs that won't be
      published can opt out per-file via INTERNAL_DOCS_ALLOWLIST. Single
      lines can opt out via the inline marker `<!-- lint-allow-ai-ps -->`
      anywhere on the line.

Scope: scans every *.md file in the repo except in node_modules/, dist/,
.git/. (Phase 3 review #R3.5 — examples/ READMEs, prior_art docs, analysis
markdown were missed by the prior glob.)

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

# Internal docs where AI_PS path references are tolerated wholesale (these
# files are workflow state, not published artifacts). Phase 3 review #R3.6
# trimmed publication_checklist.md off this list — it's published-facing
# even though it audits the state of the publish.
INTERNAL_DOCS_ALLOWLIST = {
    "docs/domain_status.md",
    "docs/v2_plan.md",
    "docs/v1_README_archive.md",
}

# Inline marker — place on any line to allow that single line to mention
# AI_PS / projects/ paths even outside the per-file allowlist. Useful for
# meta-references like "no AI_PS escapes" in publication checklist.
INLINE_ALLOW_MARKER = "<!-- lint-allow-ai-ps -->"

# Skip these directory roots when walking for *.md files.
SKIP_DIR_NAMES = {"node_modules", "dist", ".git", "__pycache__", "build"}

# Files lint applies to: every *.md in the repo, minus skipped roots.
def _doc_files() -> list[Path]:
    out: list[Path] = []
    for p in REPO.rglob("*.md"):
        if any(part in SKIP_DIR_NAMES for part in p.parts):
            continue
        if p.name == "CHANGELOG.md":
            continue
        out.append(p)
    return sorted(out)


def count_v2_production_profiles() -> int:
    """Count profile.json files (not directories) so the linter and CI
    validation loop agree on what counts (Phase 3 review #R1.2)."""
    n = 0
    for prof in DOMAINS_DIR.glob("*/profile.json"):
        name = prof.parent.name
        if name in SKIP_DOMAINS:
            continue
        if any(name == prefix or name.startswith(prefix + "_") for prefix in SKIP_PREFIXES):
            continue
        n += 1
    return n


# ---------------------------------------------------------------------------
# R1 patterns — TOTAL-set claims only; cluster/subdivision counts pass.
# ---------------------------------------------------------------------------

COUNT_PATTERNS = [
    re.compile(r"\ball\s+(\d{1,3})\s+(?:profile-validated\s+)?(?:prototype\s+)?guards?\b", re.I),
    re.compile(r"\bthe\s+(\d{1,3})\s+(?:profile-validated\s+)?(?:prototype\s+)?(?:v2\s+)?guards?\b", re.I),
    re.compile(r"\bset\s+of\s+(\d{1,3})\s+guards?\b", re.I),
    re.compile(r"\bacross\s+all\s+(\d{1,3})\s+guards?\b", re.I),
    re.compile(r"\b(\d{1,3})\s+profile-validated\s+(?:prototype\s+)?guards?\b", re.I),
    re.compile(r"\b(\d{1,3})\s+production\s+profiles?\b", re.I),
    re.compile(r"\b(\d{1,3})\s+production\s+domains?\b", re.I),
    re.compile(r"\b(\d{1,3})\s+v2\s+(?:production\s+)?(?:tx-analysis\s+)?guards?\b", re.I),
    re.compile(r"\bship\s+(\d{1,3})\s+guards?\b", re.I),
]

# Word-form numerals → integer. Phase 3 review #R1.1 noted that
# "Fifteen v2 production guards" passed silently. Limited to the band
# we plausibly hit in this repo.
WORD_NUMS: dict[str, int] = {
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
}
WORD_NUM_PATTERN = re.compile(
    r"\b(" + "|".join(WORD_NUMS.keys()) + r")\s+(?:v2\s+)?(?:production\s+)?guards?\b",
    re.I,
)

PROD_CLAIM_RE = re.compile(
    r"(?:\bproduction[- ](?:ready|grade)\b"
    r"|\bMaturity:\s*Production\b"
    r"|\bTier\s+1\s+production\b)",
    re.I,
)

HEDGE_TOKENS = (
    "not yet", "not production", "isn't production", "is not production",
    "in the sense of", "not (yet)", "n/a", "varies",
    # "minimum for tier 1 production" is a calibration claim, not a
    # production-ready claim. Same shape: "X is the minimum required for".
    "minimum for", "minimum required", "required for",
)

# Third-party allowlist — if any of these names appears on the same or
# previous line, treat the production claim as attributed (not e_AI's own).
THIRD_PARTY_TOKENS = (
    # TEE / hardware
    "phala", "brave leo", "azure", "confidential vm", "intel sgx",
    "intel tdx", "amd sev", "tee ", "tees", "(phala", "(brave",
    "(azure", "(intel", "(amd", "confidential computing",
    # Privacy / wallet ecosystem (Phase 3 review #R2.4)
    "blockaid", "pocket universe", "flashbots", "rabby", "scam sniffer",
    "semaphore", "railgun", "umbra", "privacy pools", "metamask",
    "kohaku", "0xbow", "rotki", "tornado",
)

# R3: AI_PS path escape.
AI_PS_PATTERNS = [
    re.compile(r"\bAI[_-]PS\b"),
    re.compile(r"~/Documents/Claude/AI[_-]PS"),
]
# Match `projects/<name>/` references. e_AI itself doesn't have a top-level
# projects/ dir (verified by grep), so any such reference is an AI_PS leak.
PROJECTS_PATH_RE = re.compile(r"projects/[a-z][a-z0-9_]+/")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _claim_is_hedged(line: str, prev_line: str) -> bool:
    haystack = (line + "\n" + prev_line).lower()
    return any(tok in haystack for tok in (HEDGE_TOKENS + THIRD_PARTY_TOKENS))


def _is_internal_doc(rel_path: str) -> bool:
    return rel_path in INTERNAL_DOCS_ALLOWLIST


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def lint() -> int:
    expected = count_v2_production_profiles()
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

            # R1: numeric count drift
            seen_ns: set[int] = set()
            for pat in COUNT_PATTERNS:
                for m in pat.finditer(line):
                    n = int(m.group(1))
                    if not (1 <= n <= 99 and n != expected):
                        continue
                    if n in seen_ns:
                        continue
                    seen_ns.add(n)
                    issues.append(
                        f"{rel}:{line_no}: R1 count drift — claims '{m.group(0)}' "
                        f"but actual v2 production profiles = {expected}"
                    )

            # R1 word-form numerals
            for m in WORD_NUM_PATTERN.finditer(line):
                n = WORD_NUMS[m.group(1).lower()]
                if n != expected:
                    issues.append(
                        f"{rel}:{line_no}: R1 word-form count drift — claims "
                        f"'{m.group(0)}' but actual v2 production profiles = {expected}"
                    )

            # R2: production claim must be hedged or attributed
            if PROD_CLAIM_RE.search(line):
                if not _claim_is_hedged(line, prev):
                    issues.append(
                        f"{rel}:{line_no}: R2 unhedged production claim — "
                        f"'{line.strip()[:120]}'"
                    )

            # R3: AI_PS path escape — skip internal-allowlisted files; per-line
            # opt-out via INLINE_ALLOW_MARKER.
            if _is_internal_doc(rel):
                continue
            if INLINE_ALLOW_MARKER in line:
                continue
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
            f"\n{len(issues)} issue(s). v2 production profile count = {expected}.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: docs clean. v2 production profile count = {expected}.")
    return 0


if __name__ == "__main__":
    sys.exit(lint())
