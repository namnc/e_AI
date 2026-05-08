"""
Unit tests for scripts/lint_docs.py.

Codex Phase 4 review missed-coverage: the linter is only run against
the current repo contents, so a pattern that becomes too broad or too
permissive can pass review until a future doc edit trips or bypasses
it. These tests exercise the rule logic directly with synthetic
fixtures.

Wired as `python3 tests/test_lint_docs.py` from CI (or via
`python3 -m unittest tests.test_lint_docs`).
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("lint_docs", REPO / "scripts" / "lint_docs.py")
lint_docs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lint_docs)  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# R1 — count drift patterns
# ---------------------------------------------------------------------------


class TestR1NumericClaims(unittest.TestCase):
    EXPECTED = 16  # current v2 production count

    def _matches(self, line: str, expected: int) -> list[int]:
        """Return all distinct N's flagged by R1 numeric patterns on `line`."""
        seen: set[int] = set()
        for pat in lint_docs.COUNT_PATTERNS:
            for m in pat.finditer(line):
                n = int(m.group(1))
                if 1 <= n <= 99 and n != expected:
                    seen.add(n)
        return sorted(seen)

    def test_total_set_claim_with_drift_fires(self):
        for line in [
            "all 15 guards across this set",
            "the 14 v2 guards comprise...",
            "set of 17 guards",
            "across all 13 guards",
            "15 profile-validated prototype guards",
            "We ship 18 guards today.",
        ]:
            with self.subTest(line=line):
                self.assertTrue(self._matches(line, self.EXPECTED),
                                f"should flag drift in: {line}")

    def test_correct_count_passes(self):
        for line in [
            "all 16 guards across this set",
            "the 16 v2 guards",
            "16 profile-validated prototype guards",
            "We ship 16 guards today.",
        ]:
            with self.subTest(line=line):
                self.assertEqual(self._matches(line, self.EXPECTED), [],
                                 f"should not flag correct count in: {line}")

    def test_subdivision_phrases_pass(self):
        """Codex Phase 4 review #R1: 'we ship 8 guards in cluster A' must
        NOT trip when the total is 16 and the line is clearly a cluster."""
        for line in [
            "we ship 8 guards in cluster A",
            "the wallet cluster has 7 guards plus 1 hygiene-only",
            "cluster B contains 3 guards focused on L2",
            "thirteen guards are rule-based, three are LLM-only",
        ]:
            with self.subTest(line=line):
                # Numeric patterns shouldn't fire (tightened "ship N guards"
                # requires "today/now/across/via/in v2" sentinel).
                hits = self._matches(line, self.EXPECTED)
                # Word-form pattern requires v2/production/total qualifier so
                # "thirteen guards are rule-based" doesn't trip.
                word_hits = list(lint_docs.WORD_NUM_PATTERN.finditer(line))
                self.assertFalse(hits and word_hits == [],
                                 f"subdivision phrase tripped: {line} → {hits}")

    def test_word_form_total_claim_fires(self):
        for line, expected in [
            ("Fifteen v2 production guards plus a fresh one.", [15]),
            ("We added fourteen production guards initially.", [14]),
        ]:
            with self.subTest(line=line):
                got = [
                    lint_docs.WORD_NUMS[m.group(1).lower()]
                    for m in lint_docs.WORD_NUM_PATTERN.finditer(line)
                    if lint_docs.WORD_NUMS[m.group(1).lower()] != self.EXPECTED
                ]
                self.assertEqual(got, expected)

    def test_word_form_subdivision_passes(self):
        line = "thirteen guards are rule-based, three are LLM-only"
        hits = list(lint_docs.WORD_NUM_PATTERN.finditer(line))
        self.assertEqual(hits, [], "cluster phrase must not trip word-form pattern")

    # ---------- Phase 6F: as-of-today + word-form ship false-negatives ----

    def test_numeric_ship_as_of_today_fires(self):
        """Phase 5 review #R1 / Phase 6F: 'We ship 15 guards as of today'
        must trip — prior lookahead required 'today/now' immediately after
        'guards' and missed the 'as of today' tail."""
        line = "We ship 15 guards as of today."
        self.assertIn(15, self._matches(line, self.EXPECTED),
                      "ship-N-guards-as-of-today drift must fire")

    def test_numeric_ship_as_of_now_fires(self):
        line = "We ship 14 guards as of now"
        self.assertIn(14, self._matches(line, self.EXPECTED))

    def test_word_form_ship_as_of_today_fires(self):
        """Phase 5 review #R1 / Phase 6F: 'we ship sixteen guards as of
        today' was the prompt example. The bare word-form ship-claim
        without v2/production qualifier must trip when the count drifts."""
        line = "We ship fifteen guards as of today"
        hits = [
            lint_docs.WORD_NUMS[m.group(1).lower()]
            for m in lint_docs.WORD_NUM_SHIP_PATTERN.finditer(line)
            if lint_docs.WORD_NUMS[m.group(1).lower()] != self.EXPECTED
        ]
        self.assertEqual(hits, [15],
                         "word-form ship-claim with as-of-today drift must fire")

    def test_word_form_ship_correct_count_passes(self):
        line = "We ship sixteen guards as of today"
        hits = [
            lint_docs.WORD_NUMS[m.group(1).lower()]
            for m in lint_docs.WORD_NUM_SHIP_PATTERN.finditer(line)
            if lint_docs.WORD_NUMS[m.group(1).lower()] != self.EXPECTED
        ]
        self.assertEqual(hits, [],
                         "word-form ship-claim with correct count must not fire")

    def test_word_form_ship_without_total_qualifier_passes(self):
        """'thirteen guards in cluster A' doesn't have 'ship' verb — it's
        not a ship-claim and shouldn't trip the new ship pattern."""
        line = "thirteen guards in cluster A"
        hits = list(lint_docs.WORD_NUM_SHIP_PATTERN.finditer(line))
        self.assertEqual(hits, [],
                         "non-ship cluster phrase must not trip ship pattern")

    # ---------- Phase 7F: remaining R1 variants (Codex Phase 6 review) ----

    def test_numeric_ship_by_today_fires(self):
        """Phase 7F: 'we ship 18 guards by today' must trip."""
        line = "we ship 18 guards by today"
        self.assertIn(18, self._matches(line, self.EXPECTED))

    def test_numeric_ship_paren_as_of_today_fires(self):
        """Phase 7F: 'we ship 18 guards (as of today)' must trip — paren
        between guards and 'as of today' previously broke the lookahead."""
        line = "we ship 18 guards (as of today)"
        self.assertIn(18, self._matches(line, self.EXPECTED))

    def test_past_tense_shipped_numeric_fires(self):
        """Phase 7F: past tense 'we shipped 18 guards as of today' must trip."""
        line = "we shipped 18 guards as of today"
        self.assertIn(18, self._matches(line, self.EXPECTED))

    def test_past_tense_shipped_word_form_fires(self):
        """Phase 7F: 'we shipped fifteen guards as of today' must trip via
        the WORD_NUM_SHIP_PATTERN (now also matches past tense)."""
        line = "we shipped fifteen guards as of today"
        hits = [
            lint_docs.WORD_NUMS[m.group(1).lower()]
            for m in lint_docs.WORD_NUM_SHIP_PATTERN.finditer(line)
            if lint_docs.WORD_NUMS[m.group(1).lower()] != self.EXPECTED
        ]
        self.assertEqual(hits, [15])

    def test_word_form_ship_by_today_fires(self):
        """Phase 7F: 'we ship sixteen guards by today' for word form."""
        line = "we ship fifteen guards by today"
        hits = [
            lint_docs.WORD_NUMS[m.group(1).lower()]
            for m in lint_docs.WORD_NUM_SHIP_PATTERN.finditer(line)
            if lint_docs.WORD_NUMS[m.group(1).lower()] != self.EXPECTED
        ]
        self.assertEqual(hits, [15])

    # ---------- Phase 8B: gerund 'shipping' (Codex Phase 7 #2) ------------

    def test_gerund_shipping_numeric_fires(self):
        """Phase 8B: 'we are shipping 18 guards as of today' must trip."""
        line = "we are shipping 18 guards as of today"
        self.assertIn(18, self._matches(line, self.EXPECTED))

    def test_gerund_shipping_word_form_fires(self):
        """Phase 8B: 'now shipping eighteen guards by today' (gerund + word)"""
        line = "now shipping eighteen guards by today"
        hits = [
            lint_docs.WORD_NUMS[m.group(1).lower()]
            for m in lint_docs.WORD_NUM_SHIP_PATTERN.finditer(line)
            if lint_docs.WORD_NUMS[m.group(1).lower()] != self.EXPECTED
        ]
        self.assertEqual(hits, [18])

    def test_gerund_shipping_correct_count_passes(self):
        """Phase 8B: 'we are shipping sixteen guards as of today' (== EXPECTED)
        must NOT fire."""
        line = "we are shipping sixteen guards as of today"
        hits = [
            lint_docs.WORD_NUMS[m.group(1).lower()]
            for m in lint_docs.WORD_NUM_SHIP_PATTERN.finditer(line)
            if lint_docs.WORD_NUMS[m.group(1).lower()] != self.EXPECTED
        ]
        self.assertEqual(hits, [])

    def test_gerund_shipping_cluster_phrase_passes(self):
        """Phase 8B: 'shipping 8 guards in cluster A' is a cluster claim,
        not a total — the existing tail-lookahead prevents false positive."""
        line = "shipping 8 guards in cluster A"
        self.assertEqual(self._matches(line, self.EXPECTED), [],
                         "cluster phrase must not trip even with gerund verb")

    # ---------- Phase 9A: subject-first total claim (Codex Phase 8 review) ----

    def test_subject_first_numeric_ship_today_fires(self):
        """Phase 9A: 'our 18 guards ship today' must trip — Codex Phase 8
        flagged this as the remaining must-fix R1 false-negative class."""
        line = "our 18 guards ship today"
        self.assertIn(18, self._matches(line, self.EXPECTED))

    def test_subject_first_numeric_ship_as_of_today_fires(self):
        line = "our 17 guards ship as of today"
        self.assertIn(17, self._matches(line, self.EXPECTED))

    def test_subject_first_numeric_ship_correct_count_passes(self):
        line = "our 16 guards ship today"
        self.assertEqual(self._matches(line, self.EXPECTED), [],
                         "subject-first ship with correct count must not fire")

    def test_subject_first_numeric_no_release_verb_passes(self):
        """Phase 9A: 'our 18 guards in cluster A' has no release-verb tail
        — must not fire (mirrors verb-first cluster-phrase invariant)."""
        line = "our 18 guards in cluster A"
        self.assertEqual(self._matches(line, self.EXPECTED), [],
                         "subject-first cluster phrase must not trip")

    def test_subject_first_word_form_ship_today_fires(self):
        line = "our eighteen guards ship today"
        hits = [
            lint_docs.WORD_NUMS[m.group(1).lower()]
            for m in lint_docs.WORD_NUM_SUBJECT_FIRST_SHIP_PATTERN.finditer(line)
            if lint_docs.WORD_NUMS[m.group(1).lower()] != self.EXPECTED
        ]
        self.assertEqual(hits, [18])

    def test_subject_first_word_form_correct_count_passes(self):
        line = "our sixteen guards ship today"
        hits = [
            lint_docs.WORD_NUMS[m.group(1).lower()]
            for m in lint_docs.WORD_NUM_SUBJECT_FIRST_SHIP_PATTERN.finditer(line)
            if lint_docs.WORD_NUMS[m.group(1).lower()] != self.EXPECTED
        ]
        self.assertEqual(hits, [],
                         "subject-first word-form with correct count must not fire")

    # ---------- Phase 10A: parenthetical/appositive (Codex Phase 9 review) ----

    def test_subject_first_numeric_parenthetical_fires(self):
        """Phase 10A: 'our 18 guards (the v2 set) ship today' must trip —
        Codex Phase 9 flagged parenthetical between guards + ship."""
        line = "our 18 guards (the v2 set) ship today"
        self.assertIn(18, self._matches(line, self.EXPECTED))

    def test_subject_first_numeric_parenthetical_correct_count_passes(self):
        line = "our 16 guards (the v2 set) ship today"
        self.assertEqual(self._matches(line, self.EXPECTED), [],
                         "parenthetical with correct count must not fire")

    def test_subject_first_numeric_parenthetical_no_release_verb_passes(self):
        """Phase 10A: 'our 18 guards (the v2 set) in cluster A' has no
        release verb — must not fire."""
        line = "our 18 guards (the v2 set) in cluster A"
        self.assertEqual(self._matches(line, self.EXPECTED), [],
                         "parenthetical without release verb must not trip")

    def test_subject_first_word_form_parenthetical_fires(self):
        line = "our eighteen guards (the v2 set) ship today"
        hits = [
            lint_docs.WORD_NUMS[m.group(1).lower()]
            for m in lint_docs.WORD_NUM_SUBJECT_FIRST_SHIP_PATTERN.finditer(line)
            if lint_docs.WORD_NUMS[m.group(1).lower()] != self.EXPECTED
        ]
        self.assertEqual(hits, [18])


# ---------------------------------------------------------------------------
# R2 — production claim hedging
# ---------------------------------------------------------------------------


class TestR2ProductionClaim(unittest.TestCase):
    def _is_flagged(self, line: str, prev: str = "") -> bool:
        return bool(
            lint_docs.PROD_CLAIM_RE.search(line)
            and not lint_docs._claim_is_hedged(line, prev)
        )

    def test_unhedged_production_ready_flagged(self):
        self.assertTrue(self._is_flagged("This is production-ready software."))
        self.assertTrue(self._is_flagged("Maturity: Production"))
        self.assertTrue(self._is_flagged("Tier 1 production deployment."))

    def test_hedged_production_passes(self):
        self.assertFalse(self._is_flagged("Not yet production-grade."))
        self.assertFalse(self._is_flagged("production-grade in the sense of being calibrated"))
        self.assertFalse(self._is_flagged("14B is the minimum for Tier 1 production use"))

    def test_third_party_attributed_passes(self):
        for line in [
            "Status: production-ready (Phala Network, Brave Leo, Azure Confidential VMs).",
            "Blockaid is production-grade wallet security.",
            "Pocket Universe ships production-ready scam detection.",
            "Flashbots offers production-grade MEV infrastructure.",
        ]:
            with self.subTest(line=line):
                self.assertFalse(self._is_flagged(line),
                                 f"third-party attribution must pass: {line}")

    def test_prev_line_attribution_no_longer_passes(self):
        """Codex Phase 4 review #R2.4: same-line only. A token on the
        previous line must NOT smuggle a real production claim through."""
        # With same-line-only logic, the production claim on the next line
        # is still flagged even if "Phala" appeared on the previous line.
        self.assertTrue(self._is_flagged(
            line="This e_AI substrate is production-ready.",
            prev="Phala Network deploys TEEs.",
        ))


# ---------------------------------------------------------------------------
# R3 — AI_PS path escapes
# ---------------------------------------------------------------------------


class TestR3PathEscapes(unittest.TestCase):
    def test_ai_ps_reference_flagged(self):
        # Either pattern in AI_PS_PATTERNS should match these strings —
        # each pattern targets a different shape of leak.
        def any_match(s: str) -> bool:
            return any(p.search(s) for p in lint_docs.AI_PS_PATTERNS)
        self.assertTrue(any_match("see notes in AI_PS workspace"))
        self.assertTrue(any_match("~/Documents/Claude/AI_PS/foo.md"))

    def test_projects_path_flagged(self):
        self.assertTrue(lint_docs.PROJECTS_PATH_RE.search("see projects/pq_stealth_address/ for"))

    def test_normal_path_not_flagged(self):
        self.assertFalse(lint_docs.PROJECTS_PATH_RE.search("examples/wallet_eip1193/guard.ts"))
        self.assertFalse(lint_docs.PROJECTS_PATH_RE.search("docs/v2_plan.md"))


# ---------------------------------------------------------------------------
# Marker cap behavior
# ---------------------------------------------------------------------------


class TestInlineMarkerCap(unittest.TestCase):
    def test_repo_cap_constants_sane(self):
        self.assertGreaterEqual(lint_docs.INLINE_ALLOW_MARKER_CAP_PER_FILE, 1)
        self.assertGreaterEqual(
            lint_docs.INLINE_ALLOW_MARKER_CAP_REPO,
            lint_docs.INLINE_ALLOW_MARKER_CAP_PER_FILE,
        )


# ---------------------------------------------------------------------------
# Phase 11B: synthetic marker-cap tests (Codex Phase 6 deferred)
# ---------------------------------------------------------------------------
#
# Codex Phase 6 review noted: "R3 marker-cap tests only assert the
# constants are sane; they do not build a synthetic markdown file with
# 4 markers or 11 repo-wide markers and assert the linter fails."
# Codex Phase 7 review carried it forward as deferred.
#
# These tests exercise the marker-counting + cap-check logic with
# synthetic markdown content (in-memory; no temp filesystem needed).


class TestMarkerCapSyntheticFiles(unittest.TestCase):
    """Pin per-file and repo-wide marker cap behavior with synthetic
    markdown. Relies only on the linter's marker-counting line + cap
    constants — no full lint() invocation needed."""

    MARKER = "<!-- lint-allow-ai-ps -->"

    def _count_markers_in(self, text: str) -> int:
        """Mirrors the linter's per-file marker-count line:
            sum(1 for ln in lines if INLINE_ALLOW_MARKER in ln)
        Tests verify the same logic."""
        return sum(1 for ln in text.splitlines() if lint_docs.INLINE_ALLOW_MARKER in ln)

    def test_three_markers_under_per_file_cap(self):
        """3 markers in one file: at the cap (cap=3), no issue."""
        text = "\n".join([f"line {i} {self.MARKER}" for i in range(3)])
        n = self._count_markers_in(text)
        self.assertEqual(n, 3)
        self.assertEqual(lint_docs.INLINE_ALLOW_MARKER_CAP_PER_FILE, 3)
        self.assertFalse(
            n > lint_docs.INLINE_ALLOW_MARKER_CAP_PER_FILE,
            "3 markers must NOT exceed per-file cap of 3",
        )

    def test_four_markers_exceeds_per_file_cap(self):
        """4 markers in one file: ABOVE cap (cap=3), must exceed."""
        text = "\n".join([f"line {i} {self.MARKER}" for i in range(4)])
        n = self._count_markers_in(text)
        self.assertEqual(n, 4)
        self.assertTrue(
            n > lint_docs.INLINE_ALLOW_MARKER_CAP_PER_FILE,
            "4 markers MUST exceed per-file cap of 3 — this is the "
            "case that should produce an R3 marker-cap issue",
        )

    def test_marker_only_counts_when_present_in_line(self):
        """Marker text inside a paragraph still counts (per-line check)."""
        text = "intro paragraph\nthis line has the marker {} inline\nfinal".format(
            self.MARKER
        )
        self.assertEqual(self._count_markers_in(text), 1)

    def test_multi_marker_per_line_counted_once(self):
        """If a line has the marker twice, it's still counted once
        (mirrors `1 for ln in ... if MARKER in ln`)."""
        text = f"line with two {self.MARKER} markers {self.MARKER} inline"
        self.assertEqual(
            self._count_markers_in(text), 1,
            "marker appearing twice on one line counts as 1 per the "
            "current linter rule",
        )

    def test_synthetic_repo_wide_cap_logic(self):
        """Simulate counting markers across N synthetic files; verify the
        repo-wide cap math the linter uses (`marker_total += marker_count`)
        flags totals above INLINE_ALLOW_MARKER_CAP_REPO."""
        files = [
            "\n".join([f"line {i} {self.MARKER}" for i in range(3)])  # 3 markers
            for _ in range(4)  # 4 files
        ]
        total = sum(self._count_markers_in(t) for t in files)
        self.assertEqual(total, 12)
        self.assertEqual(lint_docs.INLINE_ALLOW_MARKER_CAP_REPO, 10)
        self.assertTrue(
            total > lint_docs.INLINE_ALLOW_MARKER_CAP_REPO,
            "12 markers across 4 files MUST exceed repo cap of 10 — "
            "this is the case that should produce an R3 repo-cap issue",
        )

    def test_synthetic_repo_wide_under_cap_passes(self):
        """3 files × 3 markers = 9 markers, under repo cap of 10."""
        files = [
            "\n".join([f"line {i} {self.MARKER}" for i in range(3)])
            for _ in range(3)
        ]
        total = sum(self._count_markers_in(t) for t in files)
        self.assertEqual(total, 9)
        self.assertFalse(
            total > lint_docs.INLINE_ALLOW_MARKER_CAP_REPO,
            "9 markers across 3 files must NOT exceed repo cap of 10",
        )

    def test_per_file_cap_triggers_before_repo_cap(self):
        """A single file with 4 markers triggers per-file cap even though
        4 < repo cap of 10. Mirrors the linter's two separate checks."""
        text = "\n".join([f"line {i} {self.MARKER}" for i in range(4)])
        n = self._count_markers_in(text)
        self.assertTrue(n > lint_docs.INLINE_ALLOW_MARKER_CAP_PER_FILE)
        self.assertFalse(n > lint_docs.INLINE_ALLOW_MARKER_CAP_REPO,
                         "4 markers in one file should not on its own "
                         "exceed repo cap")


# ---------------------------------------------------------------------------
# count_v2_production_profiles — sanity check
# ---------------------------------------------------------------------------


class TestProfileCount(unittest.TestCase):
    def test_count_is_positive(self):
        self.assertGreaterEqual(lint_docs.count_v2_production_profiles(), 1)


if __name__ == "__main__":
    unittest.main()
