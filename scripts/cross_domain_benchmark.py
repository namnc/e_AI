"""
Cross-domain benchmark runner.

Runs `python analyzer.py --benchmark` for every domain that has an analyzer.py,
parses the JSON output, and tabulates TPR/FPR per domain.

Usage:
    python scripts/cross_domain_benchmark.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DOMAINS = ROOT / "domains"
TIMEOUT_SECS = 60


def find_analyzer_domains() -> list[Path]:
    out = []
    for d in sorted(DOMAINS.iterdir()):
        if not d.is_dir():
            continue
        if (d / "analyzer.py").exists():
            out.append(d)
    return out


def run_benchmark(domain: Path) -> dict:
    """Return parsed benchmark dict, or {'error': ...} on failure."""
    try:
        result = subprocess.run(
            ["python3", str(domain / "analyzer.py"), "--benchmark"],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECS,
            cwd=ROOT,
        )
    except subprocess.TimeoutExpired:
        return {"error": "timeout"}
    except Exception as e:
        return {"error": f"exception: {e}"}

    if result.returncode != 0:
        return {"error": f"exit {result.returncode}: {result.stderr.strip()[:200]}"}

    # Find first {...} block in stdout (analyzers print json after a header line)
    text = result.stdout
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return {"error": "no json in output"}
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError as e:
        return {"error": f"json parse: {e}"}


def fmt_pct(s) -> str:
    if isinstance(s, str):
        return s
    if isinstance(s, (int, float)):
        return f"{s:.1%}" if 0 <= s <= 1 else str(s)
    return "n/a"


def main():
    domains = find_analyzer_domains()
    print(f"Running benchmarks for {len(domains)} domains...")
    print()

    rows = []
    for d in domains:
        name = d.name
        print(f"  [{name}] running...", end="", flush=True)
        result = run_benchmark(d)
        print(" done." if "error" not in result else f" ERROR: {result['error']}")
        rows.append((name, result))

    # Tabulate
    print()
    print("=" * 78)
    print(f"{'Domain':<24} {'TPR':>8} {'FPR':>8} {'TP':>5} {'FP':>5} {'FN':>5} {'Total':>7}")
    print("-" * 78)
    for name, r in rows:
        if "error" in r:
            print(f"{name:<24} {'ERR':>8} {'ERR':>8}    -     -     -      -")
            continue
        tpr = r.get("true_positive_rate", "")
        fpr = r.get("false_positive_rate", "")
        tp = r.get("true_positive", "-")
        fp = r.get("false_positive", "-")
        fn = r.get("false_negative", "-")
        total = (
            r.get("n_transactions") or r.get("n_proposals") or r.get("n_portfolios")
            or r.get("n_sequences") or r.get("n_actions") or r.get("n_sessions")
            or r.get("n_requests") or r.get("n_accounts") or "-"
        )
        print(f"{name:<24} {tpr:>8} {fpr:>8} {tp!s:>5} {fp!s:>5} {fn!s:>5} {total!s:>7}")
    print("=" * 78)
    print()

    # Per-heuristic counts where available
    print("Per-heuristic alert distribution (per domain):")
    for name, r in rows:
        if "error" in r:
            continue
        per_h = r.get("per_heuristic_alert_count") or r.get("per_heuristic")
        if per_h:
            top = sorted(per_h.items(), key=lambda kv: -kv[1])[:5]
            print(f"  {name:<24}: " + ", ".join(f"{k}={v}" for k, v in top))


if __name__ == "__main__":
    main()
