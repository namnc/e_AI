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
    text = path.read_text(encoding="utf-8")
    out: list[tuple[str, str, str, int]] = []
    pattern = re.compile(r"^\s*-\s*name:\s*(.+)\s*\n(?:\s*#.*\n)*\s*run:\s*\|\s*\n((?:\s{8,}.*\n?)+)", re.M)
    for m in pattern.finditer(text):
        name = m.group(1).strip()
        run = m.group(2)
        # Dedent — strip leading whitespace common to all lines.
        lines = run.splitlines()
        if lines:
            indent = min(len(l) - len(l.lstrip()) for l in lines if l.strip())
            run = "\n".join(l[indent:] for l in lines)
        out.append(("?", name, run, m.start()))
    return out


def check(workflow_path: Path) -> int:
    blocks = extract_run_blocks(workflow_path)
    if not blocks:
        print(f"WARN: no run: blocks found in {workflow_path}", file=sys.stderr)
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
    print(f"OK: {len(blocks)} run-block(s) parse cleanly via bash -n.")
    return 0


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        Path(__file__).resolve().parent.parent / ".github" / "workflows" / "tests.yml"
    )
    sys.exit(check(target))
