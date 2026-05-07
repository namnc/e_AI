"""
cross_domain_density.py

Per-domain density matrix: how many `signals` each heuristic carries, plus
totals and averages per domain. Surfaces under- and over-specified heuristics.

For each domain's `profile.json`, walks `heuristics.<H*>.detection.signals`.
A `signal` here is each item in the list — usually a string or dict pointing
to a measurable on-chain / RPC property the heuristic looks for.

Usage:
    python3 scripts/cross_domain_density.py            # text matrix
    python3 scripts/cross_domain_density.py --json     # machine-readable
    python3 scripts/cross_domain_density.py --csv      # CSV for spreadsheets
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOMAINS = ROOT / "domains"


def signal_count(heuristic: dict) -> int:
    det = heuristic.get("detection")
    if not isinstance(det, dict):
        return 0
    sig = det.get("signals")
    if not isinstance(sig, list):
        return 0
    return len(sig)


def collect() -> list[dict]:
    """Returns list of {domain, heuristics: {hid: {name, signals}}}."""
    out = []
    for d in sorted(DOMAINS.iterdir()):
        if not d.is_dir():
            continue
        prof = d / "profile.json"
        if not prof.exists():
            continue
        try:
            data = json.loads(prof.read_text())
        except Exception as e:
            print(f"  [warn] {d.name}: {e}", file=sys.stderr)
            continue
        heur = data.get("heuristics") or {}
        if not isinstance(heur, dict):
            continue
        h_out = {}
        for hkey, hval in heur.items():
            if not isinstance(hval, dict):
                continue
            hid = hval.get("id", hkey)
            h_out[hid] = {
                "key": hkey,
                "name": hval.get("name", ""),
                "signals": signal_count(hval),
            }
        out.append({"domain": d.name, "heuristics": h_out})
    return out


def render_text(rows: list[dict]) -> str:
    buf = io.StringIO()
    print("Cross-domain density matrix", file=buf)
    print("=" * 78, file=buf)
    print(f"{'Domain':<26} {'#H':>4} {'tot':>5} {'min':>4} {'avg':>5} {'max':>4}", file=buf)
    print("-" * 78, file=buf)
    grand_h = 0
    grand_sig = 0
    for r in rows:
        h = r["heuristics"]
        sigs = [v["signals"] for v in h.values()]
        n_h = len(sigs)
        tot = sum(sigs)
        mn = min(sigs) if sigs else 0
        mx = max(sigs) if sigs else 0
        avg = tot / n_h if n_h else 0
        grand_h += n_h
        grand_sig += tot
        print(f"{r['domain']:<26} {n_h:>4} {tot:>5} {mn:>4} {avg:>5.1f} {mx:>4}", file=buf)
    print("-" * 78, file=buf)
    avg_global = grand_sig / grand_h if grand_h else 0
    print(f"{'TOTAL':<26} {grand_h:>4} {grand_sig:>5} {'':>4} {avg_global:>5.1f}", file=buf)
    print("=" * 78, file=buf)
    print(file=buf)

    print("Per-heuristic detail (signals per heuristic):", file=buf)
    for r in rows:
        h = r["heuristics"]
        if not h:
            print(f"  [{r['domain']}]: (no heuristics)", file=buf)
            continue
        cells = [f"{hid}={v['signals']}" for hid, v in sorted(h.items())]
        print(f"  [{r['domain']}]: " + ", ".join(cells), file=buf)

    print(file=buf)
    print("Outliers (signals == 0 or >= 8):", file=buf)
    found = False
    for r in rows:
        for hid, v in sorted(r["heuristics"].items()):
            if v["signals"] == 0 or v["signals"] >= 8:
                tag = "EMPTY" if v["signals"] == 0 else "DENSE"
                print(f"  [{tag}] {r['domain']}/{hid}: {v['signals']} ({v['name']})", file=buf)
                found = True
    if not found:
        print("  (none)", file=buf)

    return buf.getvalue()


def render_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["domain", "heuristic_id", "heuristic_name", "signal_count"])
    for r in rows:
        for hid, v in sorted(r["heuristics"].items()):
            w.writerow([r["domain"], hid, v["name"], v["signals"]])
    return buf.getvalue()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--csv", action="store_true", help="CSV output")
    args = parser.parse_args()

    rows = collect()
    if args.json:
        print(json.dumps(rows, indent=2))
    elif args.csv:
        sys.stdout.write(render_csv(rows))
    else:
        sys.stdout.write(render_text(rows))


if __name__ == "__main__":
    main()
