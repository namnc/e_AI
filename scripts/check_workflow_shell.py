#!/usr/bin/env python3
"""
Workflow shell-syntax check.

Codex Phase 4 review #1 caught an orphan `else/fi` in
.github/workflows/tests.yml that yaml.safe_load happily accepted but
`bash -n` rejected. The Kohaku CI step would have failed silently in
real CI.

This script extracts every `run:` block from the workflow and runs
`bash -n` on it. Exit non-zero on any syntax error.

Usage:
    python3 scripts/check_workflow_shell.py [workflow_path]

Wired as a CI step in v2-domain-tests.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def extract_run_blocks(workflow_path: Path) -> list[tuple[str, str, str, int]]:
    """Return list of (job, step_name, run_block, source_line). Use a
    minimal YAML walk — we don't want a hard dep on PyYAML in CI."""
    try:
        import yaml  # type: ignore
    except ImportError:
        # Best effort regex extraction; sufficient for this use case.
        return _extract_via_regex(workflow_path)

    text = workflow_path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)

    out: list[tuple[str, str, str, int]] = []
    for job_name, job in (data.get("jobs") or {}).items():
        for step in job.get("steps", []) or []:
            run = step.get("run")
            if not run or not isinstance(run, str):
                continue
            name = step.get("name", "(unnamed)")
            out.append((job_name, name, run, 0))
    return out


def _extract_via_regex(path: Path) -> list[tuple[str, str, str, int]]:
    """PyYAML-free fallback. Codex Phase 5 review #7: the prior version
    only caught `run: |` block-style, missing all single-line
    `run: <cmd>` invocations. tests.yml had 26 `run:` entries but the
    fallback found 8. This version walks the workflow line-by-line and
    extracts both forms.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=False)
    out: list[tuple[str, str, str, int]] = []
    last_name = "(unnamed)"
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()
        # Track step name so each run-block has a label.
        m_name = re.match(r"-\s*name:\s*(.+?)\s*$", stripped)
        if m_name:
            last_name = m_name.group(1).strip().strip('"\'')
            i += 1
            continue

        # `run: |` (block scalar)
        m_block = re.match(r"run:\s*\|[+-]?\s*$", stripped)
        if m_block:
            block_indent = len(line) - len(stripped)
            i += 1
            block_lines: list[str] = []
            while i < len(lines):
                cur = lines[i]
                # Allow blank lines within block
                if not cur.strip():
                    block_lines.append("")
                    i += 1
                    continue
                cur_indent = len(cur) - len(cur.lstrip())
                if cur_indent <= block_indent:
                    break
                block_lines.append(cur)
                i += 1
            # Dedent to common minimum (excluding blanks).
            non_blank = [l for l in block_lines if l.strip()]
            if non_blank:
                common = min(len(l) - len(l.lstrip()) for l in non_blank)
                run = "\n".join(l[common:] if l.strip() else "" for l in block_lines)
                out.append(("?", last_name, run, 0))
            continue

        # Single-line `run: <cmd>` (anything that isn't `|`)
        m_inline = re.match(r"run:\s+(\S.*)$", stripped)
        if m_inline:
            cmd = m_inline.group(1).strip()
            # Strip surrounding quotes if YAML scalar was quoted.
            if (cmd.startswith('"') and cmd.endswith('"')) or (cmd.startswith("'") and cmd.endswith("'")):
                cmd = cmd[1:-1]
            out.append(("?", last_name, cmd, 0))
            i += 1
            continue

        i += 1
    return out


def _count_workflow_run_lines(path: Path) -> int:
    """Count `run:` lines in the workflow for invariant assertion. Both
    inline and block-style are counted (excludes commented lines and
    `run:` appearing inside string scalars, by approximation)."""
    text = path.read_text(encoding="utf-8")
    n = 0
    for line in text.splitlines():
        s = line.lstrip()
        if s.startswith("#"):
            continue
        if re.match(r"run:\s*", s):
            n += 1
    return n


def check(workflow_path: Path) -> int:
    blocks = extract_run_blocks(workflow_path)
    if not blocks:
        print(f"WARN: no run: blocks found in {workflow_path}", file=sys.stderr)
        return 1

    # Phase 6E: assert extractor coverage matches the workflow's actual
    # run: count. If the regex fallback misses inline run: lines (the
    # Phase 5 review #7 bug), this fails loudly rather than passing
    # quietly with partial coverage.
    expected = _count_workflow_run_lines(workflow_path)
    if len(blocks) < expected:
        print(
            f"FAIL: extractor found {len(blocks)} run-block(s) but workflow has "
            f"{expected} run: line(s). Inline run: commands likely missed.",
            file=sys.stderr,
        )
        return 1

    failures = 0
    for job, name, run, _ in blocks:
        with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as f:
            f.write(run)
            tmp = f.name
        try:
            r = subprocess.run(["bash", "-n", tmp], capture_output=True, text=True)
            if r.returncode != 0:
                print(f"FAIL [{job}] {name}: {r.stderr.strip()}", file=sys.stderr)
                failures += 1
        finally:
            os.unlink(tmp)
    if failures:
        print(f"\n{failures} workflow run-block(s) failed bash -n.", file=sys.stderr)
        return 1
    print(
        f"OK: {len(blocks)} run-block(s) (block + inline) parse cleanly via bash -n. "
        f"Coverage matches workflow's {expected} run: line(s)."
    )
    return 0


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        Path(__file__).resolve().parent.parent / ".github" / "workflows" / "tests.yml"
    )
    sys.exit(check(target))
