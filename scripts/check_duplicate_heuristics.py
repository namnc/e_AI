"""
check_duplicate_heuristics.py

Scan every `domains/*/profile.json` and surface heuristics that look duplicated
across domains. Two layers:

1. Exact-key duplicates: same heuristic key (e.g., "H1_unlimited_approval")
   appearing in >1 domain. Treated as a real bug — fails CI.
2. Name overlap: distinct heuristic keys but identical (or near-identical)
   `name` fields. Treated as ADVISORY by default (different domains may
   legitimately analyze the same concept under different keys, e.g.
   'Timing correlation' in mixing_behavioral H1 and stealth_address_ops H3).

Soft heuristic for "near-identical": case-folded normalized name match.

Usage:
    python3 scripts/check_duplicate_heuristics.py            # text output
    python3 scripts/check_duplicate_heuristics.py --json     # machine-readable
    python3 scripts/check_duplicate_heuristics.py --strict   # name-overlap fails CI too

Exit code (Phase 6 + Phase 7G clarification):
  - 0 if exact-key clean (default; name-overlap is advisory)
  - 1 if exact-key duplicates exist (always)
  - 1 if --strict AND any name-overlap exists
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOMAINS = ROOT / "domains"


def normalize_name(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s


def collect() -> dict:
    """Returns {key_or_normname: [(domain, heuristic_id, name)]}."""
    by_key: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    by_name: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
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
        for hkey, hval in heur.items():
            if not isinstance(hval, dict):
                continue
            hid = hval.get("id", "")
            hname = hval.get("name", "")
            by_key[hkey].append((d.name, hid, hname))
            if hname:
                by_name[normalize_name(hname)].append((d.name, hid, hname))
    return {"by_key": by_key, "by_name": by_name}


def duplicates(d: dict) -> dict:
    """Filter to only multi-domain hits (across distinct domain names)."""
    out_key = {
        k: v for k, v in d["by_key"].items()
        if len({t[0] for t in v}) > 1
    }
    out_name = {
        k: v for k, v in d["by_name"].items()
        if len({t[0] for t in v}) > 1
    }
    return {"by_key": out_key, "by_name": out_name}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--strict", action="store_true",
                        help="treat name-overlap as a CI failure too "
                             "(default: only exact-key duplicates fail)")
    args = parser.parse_args()

    raw = collect()
    dups = duplicates(raw)

    if args.json:
        print(json.dumps({
            "exact_key_duplicates": dups["by_key"],
            "name_overlap_duplicates": dups["by_name"],
        }, indent=2))
        # Only EXACT-key duplicates fail CI. Name overlap is advisory —
        # two domains may legitimately analyze the same concept under
        # different heuristic IDs (e.g., "Timing correlation" exists in
        # mixing_behavioral H1 and stealth_address_ops H3). Use --strict
        # to fail on name overlap too.
        rc = 1 if dups["by_key"] else (1 if (args.strict and dups["by_name"]) else 0)
        sys.exit(rc)

    n_dom = sum(1 for d in DOMAINS.iterdir() if d.is_dir() and (d / "profile.json").exists())
    print(f"Scanned {n_dom} domain profiles.")
    print()

    if not dups["by_key"] and not dups["by_name"]:
        print("OK: no duplicate heuristics across domains.")
        sys.exit(0)

    if dups["by_key"]:
        print("Exact-key duplicates (same heuristic key in >1 domain):")
        for k, hits in sorted(dups["by_key"].items()):
            print(f"  {k}")
            for dom, hid, hname in hits:
                print(f"    - {dom}: {hid} \"{hname}\"")
        print()

    if dups["by_name"]:
        print("Name-overlap (different keys, same/near name) — ADVISORY:")
        for nm, hits in sorted(dups["by_name"].items()):
            domains_seen = sorted({t[0] for t in hits})
            if len(domains_seen) <= 1:
                continue
            print(f"  '{hits[0][2]}'")
            for dom, hid, hname in hits:
                print(f"    - {dom}: {hid}")
        print()

    # Exact-key duplicates fail CI (real bug). Name-overlap is advisory.
    # --strict promotes name-overlap to a CI failure too.
    if dups["by_key"]:
        sys.exit(1)
    if args.strict and dups["by_name"]:
        sys.exit(1)
    print("OK (exact-key clean; name-overlaps are advisory)")
    sys.exit(0)


if __name__ == "__main__":
    main()
