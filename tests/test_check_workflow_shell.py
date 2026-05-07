"""
Tests for scripts/check_workflow_shell.py.

Codex Phase 5 review #7 / Phase 6E: the regex fallback used to extract
only `run: |` block-style commands, missing single-line `run: <cmd>`.
This pinned the extractor to find 8 blocks while the workflow had 26
`run:` entries — failing silently. Phase 6E rewrote the fallback to
walk the YAML line-by-line and count both forms, then assert coverage
matches the workflow's actual `run:` count.

These tests pin both behaviors:
  - PyYAML-free regex fallback finds inline + block run: forms
  - Coverage assertion fails when extraction is incomplete
"""
from __future__ import annotations

import sys
import textwrap
import tempfile
import unittest
from pathlib import Path

# Importable from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.check_workflow_shell import _extract_via_regex, _count_workflow_run_lines


def _write(tmpdir: Path, name: str, body: str) -> Path:
    p = tmpdir / name
    p.write_text(body)
    return p


class TestRegexFallback(unittest.TestCase):
    """Fallback extractor (when PyYAML is absent) must find both block and
    inline run: forms. Phase 5 review #7 caught silent under-coverage."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def test_block_style_run_extracted(self):
        wf = _write(self.tmpdir, "wf.yml", textwrap.dedent("""\
            jobs:
              build:
                runs-on: ubuntu-latest
                steps:
                  - name: Block step
                    run: |
                      echo hello
                      echo world
        """))
        blocks = _extract_via_regex(wf)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0][1], "Block step")
        self.assertIn("echo hello", blocks[0][2])
        self.assertIn("echo world", blocks[0][2])

    def test_inline_run_extracted(self):
        """Phase 5 review #7: inline run was missed. Phase 6E fixes it."""
        wf = _write(self.tmpdir, "wf.yml", textwrap.dedent("""\
            jobs:
              build:
                runs-on: ubuntu-latest
                steps:
                  - name: Inline step
                    run: python3 test_one.py
                  - name: Another inline
                    run: bash -n run_all.sh
        """))
        blocks = _extract_via_regex(wf)
        self.assertEqual(len(blocks), 2,
                         "inline run: commands must be extracted (Phase 6E)")
        bodies = [b[2] for b in blocks]
        self.assertIn("python3 test_one.py", bodies)
        self.assertIn("bash -n run_all.sh", bodies)

    def test_mixed_block_and_inline(self):
        wf = _write(self.tmpdir, "wf.yml", textwrap.dedent("""\
            jobs:
              build:
                steps:
                  - name: Block A
                    run: |
                      echo block-a
                  - name: Inline B
                    run: echo inline-b
                  - name: Block C
                    run: |
                      if true; then
                        echo c
                      fi
                  - name: Inline D
                    run: pip install foo
        """))
        blocks = _extract_via_regex(wf)
        self.assertEqual(len(blocks), 4)
        names = [b[1] for b in blocks]
        self.assertEqual(names, ["Block A", "Inline B", "Block C", "Inline D"])

    def test_quoted_inline_command_unquoted(self):
        wf = _write(self.tmpdir, "wf.yml", textwrap.dedent("""\
            jobs:
              build:
                steps:
                  - name: Quoted
                    run: "echo quoted"
                  - name: Single-quoted
                    run: 'echo sq'
        """))
        blocks = _extract_via_regex(wf)
        self.assertEqual(len(blocks), 2)
        bodies = [b[2] for b in blocks]
        self.assertIn("echo quoted", bodies)
        self.assertIn("echo sq", bodies)

    def test_dedent_preserves_logic(self):
        wf = _write(self.tmpdir, "wf.yml", textwrap.dedent("""\
            jobs:
              build:
                steps:
                  - name: Indented block
                    run: |
                      for x in a b c; do
                        echo $x
                      done
        """))
        blocks = _extract_via_regex(wf)
        body = blocks[0][2]
        # The for-loop body must be properly dedented; the inner `echo`
        # must stay nested relative to `for`/`done`.
        self.assertIn("for x in a b c; do\n  echo $x\ndone", body)


class TestCoverageInvariant(unittest.TestCase):
    """The check() function asserts extractor coverage matches the count of
    raw `run:` lines. Pin that with a synthetic workflow."""

    def test_count_workflow_run_lines_matches_extraction(self):
        tmpdir = Path(tempfile.mkdtemp())
        wf = _write(tmpdir, "wf.yml", textwrap.dedent("""\
            jobs:
              build:
                steps:
                  - name: One
                    run: echo 1
                  - name: Two
                    run: |
                      echo 2
                  - name: Three
                    run: echo 3
                  - name: Comment-out
                    # run: echo not-counted
                    run: echo 4
        """))
        n_run = _count_workflow_run_lines(wf)
        n_extract = len(_extract_via_regex(wf))
        self.assertEqual(n_run, n_extract,
                         "extractor coverage must match raw `run:` count")
        self.assertEqual(n_run, 4)


if __name__ == "__main__":
    unittest.main()
