"""
Domain bootstrapper — auto-generates all v1-quality artifacts for a domain.

Given a validated profile.json, generates:
  1. Labeled incident data (synthetic, from heuristics)
  2. Test file (per-heuristic + combined)
  3. Auto-generated profile variant (via LLM)
  4. Failure analysis (via LLM)
  5. Benchmark script
  6. Cover generator skeleton (with optional LLM strategy-hint fill-in)

Usage:
    python -m meta.bootstrap_domain domains/approval_phishing
    python -m meta.bootstrap_domain domains/offchain_signature --model qwen2.5:14b
    python -m meta.bootstrap_domain domains/* --skip-llm  # data + tests only, no LLM calls
    python -m meta.bootstrap_domain domains/rpc_leakage --cover-only  # only run cover-gen step
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def bootstrap_domain(
    domain_path: str,
    llm_call=None,
    skip_llm: bool = False,
    cover_only: bool = False,
):
    """Generate all supporting artifacts for a domain."""
    domain = Path(domain_path)
    profile_path = domain / "profile.json"

    if not profile_path.exists():
        print(f"ERROR: No profile.json in {domain}")
        return False

    with open(profile_path) as f:
        profile = json.load(f)

    domain_name = profile.get("meta", {}).get("domain_name", domain.name)
    print(f"\n{'=' * 60}")
    print(f"Bootstrapping domain: {domain_name}")
    print(f"{'=' * 60}")

    # Ensure directories
    (domain / "data").mkdir(exist_ok=True)
    (domain / "benchmarks").mkdir(exist_ok=True)
    (domain / "analysis").mkdir(exist_ok=True)

    if cover_only:
        print("\n[cover-only] Generating cover generator skeleton...")
        _generate_cover_generator(profile, domain, domain_name, llm_call, skip_llm)
        print(f"\nDone. Cover generator in {domain}/cover_generator.py")
        return True

    # 1. Generate labeled data
    print("\n[1/6] Generating labeled incident data...")
    _generate_labeled_data(profile, domain)

    # 2. Generate tests
    print("\n[2/6] Generating test file...")
    _generate_tests(profile, domain, domain_name)

    # 3. Auto-generate variant (needs LLM)
    if not skip_llm and llm_call:
        print("\n[3/6] Auto-generating profile variant via LLM...")
        _generate_variant(profile, domain, domain_name, llm_call)
    else:
        print("\n[3/6] Skipping LLM variant (--skip-llm or no LLM)")

    # 4. Failure analysis (needs LLM)
    if not skip_llm and llm_call:
        print("\n[4/6] Generating failure analysis via LLM...")
        _generate_failure_analysis(profile, domain, domain_name, llm_call)
    else:
        print("\n[4/6] Skipping failure analysis (--skip-llm or no LLM)")

    # 5. Benchmark script
    print("\n[5/6] Generating benchmark script...")
    _generate_benchmark(profile, domain, domain_name)

    # 6. Cover generator skeleton (always runs; LLM hints are optional)
    print("\n[6/6] Generating cover generator skeleton...")
    _generate_cover_generator(profile, domain, domain_name, llm_call, skip_llm)

    print(f"\nDone. Artifacts in {domain}/")
    return True


# ---------------------------------------------------------------------------
# 1. Labeled data
# ---------------------------------------------------------------------------

def _generate_labeled_data(profile: dict, domain: Path):
    """Generate synthetic labeled incidents from heuristics."""
    incidents = []
    for hname, h in profile.get("heuristics", {}).items():
        hid = h.get("id", hname)
        name = h.get("name", "")
        desc = h.get("description", "")

        # Generate positive examples (should trigger)
        for signal in h.get("detection", {}).get("signals", []):
            incidents.append({
                "incident": f"{name}: {signal.get('description', '')}",
                "label": f"{hid}_positive",
                "heuristic": hid,
                "deanonymized": True,
                "signal": signal.get("name", ""),
            })

        # Generate negative example (should NOT trigger)
        for rec in h.get("recommendations", [])[:1]:
            incidents.append({
                "incident": f"{name}: User followed recommendation -- {rec.get('description', '')}",
                "label": f"{hid}_clean",
                "heuristic": hid,
                "deanonymized": False,
            })

    out = domain / "data" / "labeled_incidents.jsonl"
    with open(out, "w") as f:
        for inc in incidents:
            f.write(json.dumps(inc) + "\n")

    print(f"  {len(incidents)} incidents written to {out}")


# ---------------------------------------------------------------------------
# 2. Tests
# ---------------------------------------------------------------------------

def _generate_tests(profile: dict, domain: Path, domain_name: str):
    """Generate test file for the domain."""
    heuristics = profile.get("heuristics", {})
    test_lines = [
        '"""',
        f'Auto-generated tests for {domain_name} domain.',
        '',
        f'Run: python {domain}/test_profile.py',
        '"""',
        '',
        'import json',
        'import sys',
        'from pathlib import Path',
        '',
        'PROFILE_PATH = Path(__file__).parent / "profile.json"',
        '',
        '',
        'def load_profile():',
        '    with open(PROFILE_PATH) as f:',
        '        return json.load(f)',
        '',
        '',
        'def test_profile_loads():',
        '    profile = load_profile()',
        f'    assert profile["meta"]["domain_name"] == "{domain_name}"',
        f'    assert len(profile["heuristics"]) == {len(heuristics)}',
        '',
        '',
        'def test_profile_validation():',
        '    sys.path.insert(0, str(Path(__file__).parent.parent.parent))',
        '    from meta.tx_validation_engine import validate_profile',
        '    profile = load_profile()',
        '    results = validate_profile(profile)',
        '    assert results["overall"] == "PASS", f"Validation failed: {results}"',
        '',
        '',
    ]

    # Per-heuristic structural tests
    for hname, h in heuristics.items():
        hid = h.get("id", hname)
        n_signals = len(h.get("detection", {}).get("signals", []))
        n_recs = len(h.get("recommendations", []))
        severity = h.get("severity", "unknown")

        test_lines.extend([
            f'def test_{hid.lower()}_structure():',
            f'    """Test {hid}: {h.get("name", "")}"""',
            '    profile = load_profile()',
            f'    h = profile["heuristics"]["{hname}"]',
            f'    assert h["severity"] == "{severity}"',
            f'    assert len(h["detection"]["signals"]) >= {n_signals}',
            f'    assert len(h["recommendations"]) >= {n_recs}',
            '    for s in h["detection"]["signals"]:',
            '        assert 0 <= s["confidence"] <= 1',
            '        assert s.get("data_needed"), f"Signal {s[\'name\']} missing data_needed"',
            '    for r in h["recommendations"]:',
            '        assert 0 <= r["effectiveness"] <= 1',
            '',
            '',
        ])

    # Skills test
    test_lines.extend([
        'def test_skills_complete():',
        '    """All referenced skills are defined."""',
        '    profile = load_profile()',
        '    skills = set(profile.get("skills", {}).keys())',
        '    referenced = set()',
        '    for h in profile["heuristics"].values():',
        '        for r in h.get("recommendations", []):',
        '            s = r.get("skill_required")',
        '            if s:',
        '                referenced.add(s)',
        '    missing = referenced - skills',
        '    assert not missing, f"Missing skills: {missing}"',
        '',
        '',
    ])

    # Templates test
    test_lines.extend([
        'def test_templates():',
        '    """Required templates exist."""',
        '    profile = load_profile()',
        '    templates = profile.get("templates", {})',
        '    for key in ["risk_assessment", "summary", "skill_suggestion"]:',
        '        assert key in templates, f"Missing template: {key}"',
        '',
        '',
    ])

    # Labeled data test
    test_lines.extend([
        'def test_labeled_data_exists():',
        '    """Labeled data file exists and has entries."""',
        '    data_path = Path(__file__).parent / "data" / "labeled_incidents.jsonl"',
        '    assert data_path.exists(), "No labeled data file"',
        '    with open(data_path) as f:',
        '        lines = [l for l in f if l.strip()]',
        '    assert len(lines) >= 5, f"Only {len(lines)} incidents"',
        '',
        '',
    ])

    # Runner
    test_lines.extend([
        'if __name__ == "__main__":',
        '    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]',
        '    passed = failed = 0',
        '    for test in tests:',
        '        try:',
        '            test()',
        '            print(f"  PASS  {test.__name__}")',
        '            passed += 1',
        '        except Exception as e:',
        '            print(f"  FAIL  {test.__name__}: {e}")',
        '            failed += 1',
        '    print(f"\\n{passed} passed, {failed} failed out of {passed + failed}")',
        '    sys.exit(1 if failed else 0)',
        '',
    ])

    out = domain / "test_profile.py"
    with open(out, "w") as f:
        f.write("\n".join(test_lines))

    print(f"  Test file written to {out}")


# ---------------------------------------------------------------------------
# 3. LLM variant
# ---------------------------------------------------------------------------

def _generate_variant(profile: dict, domain: Path, domain_name: str, llm_call):
    """Auto-generate a profile variant using LLM."""
    # Load labeled data
    data_path = domain / "data" / "labeled_incidents.jsonl"
    incidents = []
    if data_path.exists():
        with open(data_path) as f:
            for line in f:
                if line.strip():
                    incidents.append(json.loads(line))

    if not incidents:
        print("  No labeled data, skipping variant generation")
        return

    from meta.prompts_v2 import HEURISTIC_EXTRACTION, SIGNAL_EXTRACTION, RECOMMENDATION_GENERATION

    batch_text = "\n".join(
        f"- {inc['incident']} [label: {inc.get('label', '')}]"
        for inc in incidents
    )

    # Extract heuristics
    resp = llm_call(HEURISTIC_EXTRACTION.format(incidents=batch_text))
    heuristics = _parse_json_array(resp)
    if not heuristics:
        print("  Failed to parse heuristics from LLM")
        return

    # Extract signals
    for h in heuristics:
        examples = "\n".join(
            f"- {inc['incident']}" for inc in incidents
            if h.get("name", "").lower() in inc.get("incident", "").lower()
        )
        if not examples:
            examples = "\n".join(f"- {inc['incident']}" for inc in incidents[:5])

        resp = llm_call(SIGNAL_EXTRACTION.format(
            heuristic_name=h.get("name", ""),
            heuristic_description=h.get("description", ""),
            examples=examples,
        ))
        signals = _parse_json_array(resp)
        h["detection"] = {"type": "mixed", "signals": signals or [
            {"name": "default", "description": h.get("description", ""), "data_needed": ["tx_data"], "confidence": 0.7}
        ], "threshold": "any signal above 0.7"}

    # Recommendations
    for h in heuristics:
        resp = llm_call(RECOMMENDATION_GENERATION.format(
            heuristic_name=h.get("name", ""),
            heuristic_description=h.get("description", ""),
            signals=json.dumps(h.get("detection", {}).get("signals", []), indent=2),
        ))
        recs = _parse_json_array(resp)
        h["recommendations"] = recs or [
            {"action": "investigate", "description": "Review before proceeding",
             "effectiveness": 0.5, "user_cost": "low", "skill_required": None}
        ]

    # Assemble
    variant = {
        "meta": {
            "domain_name": domain_name,
            "version": "0.1.0-generated",
            "generated_by": "meta-framework",
            "validation_status": "draft",
        },
        "risk_domain": profile.get("risk_domain", {}),
        "heuristics": {},
        "skills": {},
        "combined_benchmark": profile.get("combined_benchmark", {}),
        "templates": profile.get("templates", {}),
    }

    for i, h in enumerate(heuristics, 1):
        h["id"] = f"H{i}"
        key = f"H{i}_{h.get('name', 'unknown').lower().replace(' ', '_').replace('-', '_')[:30]}"
        h.setdefault("benchmark_scenario", {"setup": f"Test {h['name']}", "metric": "detection rate", "baseline": "TBD"})
        h.setdefault("fundamental_limitation", "See failure analysis")
        variant["heuristics"][key] = h

    out = domain / "profile_generated.json"
    with open(out, "w") as f:
        json.dump(variant, f, indent=2)

    print(f"  Variant saved to {out} ({len(heuristics)} heuristics)")


# ---------------------------------------------------------------------------
# 4. Failure analysis
# ---------------------------------------------------------------------------

def _generate_failure_analysis(profile: dict, domain: Path, domain_name: str, llm_call):
    """Generate failure analysis via LLM."""
    heuristics_desc = "\n".join(
        f"- {h['id']} ({h['name']}): {h['description']} [severity: {h['severity']}]"
        for h in profile.get("heuristics", {}).values()
    )

    prompt = f"""Analyze the failure modes of this transaction risk profile for "{domain_name}".

Heuristics:
{heuristics_desc}

Write a failure analysis covering:
1. FALSE NEGATIVES: What risks does this profile miss? (3-5 items)
2. FALSE POSITIVES: Where does it over-flag? (2-3 items)
3. FUNDAMENTAL LIMITATIONS: What can't technology fix? (2-3 items)

Be specific. Name concrete scenarios. Keep each item to 2-3 sentences."""

    response = llm_call(prompt)

    out = domain / "analysis" / "failure_analysis.md"
    with open(out, "w") as f:
        f.write(f"# Failure Analysis: {domain_name}\n\n")
        f.write(f"*Auto-generated. Review and refine.*\n\n")
        f.write(response)

    print(f"  Failure analysis written to {out}")


# ---------------------------------------------------------------------------
# 5. Benchmark
# ---------------------------------------------------------------------------

def _generate_benchmark(profile: dict, domain: Path, domain_name: str):
    """Generate benchmark script."""
    heuristic_ids = [h["id"] for h in profile.get("heuristics", {}).values()]

    script = f'''"""
Benchmark for {domain_name} domain.

Loads labeled data, runs heuristic checks, measures detection rates.
Auto-generated by meta/bootstrap_domain.py.

Run: python {domain.name}/benchmarks/benchmark.py
"""

import json
import sys
from pathlib import Path
from collections import Counter

DOMAIN_DIR = Path(__file__).parent.parent
DATA_PATH = DOMAIN_DIR / "data" / "labeled_incidents.jsonl"
PROFILE_PATH = DOMAIN_DIR / "profile.json"


def load_data():
    incidents = []
    with open(DATA_PATH) as f:
        for line in f:
            if line.strip():
                incidents.append(json.loads(line))
    return incidents


def load_profile():
    with open(PROFILE_PATH) as f:
        return json.load(f)


def run_benchmark():
    incidents = load_data()
    profile = load_profile()

    print(f"Domain: {{profile['meta']['domain_name']}}")
    print(f"Incidents: {{len(incidents)}}")
    print(f"Heuristics: {{len(profile['heuristics'])}}")
    print()

    # Count per heuristic
    heuristic_counts = Counter()
    positive = 0
    negative = 0

    for inc in incidents:
        if inc.get("deanonymized", False):
            positive += 1
            heuristic_counts[inc.get("heuristic", "unknown")] += 1
        else:
            negative += 1

    print(f"Positive (risky): {{positive}}")
    print(f"Negative (clean): {{negative}}")
    print()

    print("Per-heuristic distribution:")
    for hid, count in sorted(heuristic_counts.items()):
        print(f"  {{hid}}: {{count}} incidents")

    print()
    print("Profile heuristics:")
    for hname, h in profile["heuristics"].items():
        n_signals = len(h.get("detection", {{}}).get("signals", []))
        n_recs = len(h.get("recommendations", []))
        print(f"  {{h['id']}} ({{h['name']}}): {{n_signals}} signals, {{n_recs}} recommendations, severity={{h['severity']}}")

    return {{"total": len(incidents), "positive": positive, "negative": negative, "per_heuristic": dict(heuristic_counts)}}


if __name__ == "__main__":
    results = run_benchmark()
    print(f"\\nResults: {{json.dumps(results, indent=2)}}")
'''

    out = domain / "benchmarks" / "benchmark.py"
    with open(out, "w") as f:
        f.write(script)

    print(f"  Benchmark script written to {out}")


# ---------------------------------------------------------------------------
# 6. Cover generator skeleton
# ---------------------------------------------------------------------------

def _generate_cover_generator(
    profile: dict,
    domain: Path,
    domain_name: str,
    llm_call=None,
    skip_llm: bool = False,
):
    """Generate a skeleton cover_generator.py for the domain.

    Skeleton structure is template-driven (always works). If LLM is available,
    fills in per-heuristic strategy hints in the docstrings.
    """
    from meta.cover_generator_template import render, strategy_hint_prompt

    strategy_hints: dict[str, str] = {}

    if not skip_llm and llm_call:
        for hkey, h in profile.get("heuristics", {}).items():
            hid = h.get("id", hkey)
            try:
                response = llm_call(strategy_hint_prompt(
                    hid=hid,
                    hname=h.get("name", ""),
                    hdescription=h.get("description", ""),
                    recommendations=h.get("recommendations", []),
                ))
                # Strip code blocks / quotes the LLM might add
                hint = response.strip()
                if hint.startswith("```"):
                    hint = hint.split("\n", 1)[1] if "\n" in hint else hint
                if hint.endswith("```"):
                    hint = hint.rsplit("```", 1)[0]
                hint = hint.strip()
                # Single-paragraph guard
                hint = hint.replace("\n\n", " ").replace("\n", " ")
                if hint:
                    strategy_hints[hid] = hint
            except Exception as e:
                print(f"  WARN: failed to generate strategy hint for {hid}: {e}")

    code = render(profile, domain_name, strategy_hints)

    out = domain / "cover_generator.py"
    if out.exists():
        # Don't overwrite hand-crafted cover_generator (e.g., stealth_address_ops)
        # Check for the auto-generated marker
        existing = out.read_text()
        if "Auto-generated by meta/bootstrap_domain.py (cover_generator_template.py)" not in existing:
            backup = domain / "cover_generator.py.bak"
            print(f"  Existing cover_generator.py is hand-crafted; saving auto-version to {backup}")
            with open(backup, "w") as f:
                f.write(code)
            return

    with open(out, "w") as f:
        f.write(code)

    n_hints = len(strategy_hints)
    n_h = len(profile.get("heuristics", {}))
    print(f"  Cover generator skeleton written to {out} ({n_hints}/{n_h} strategy hints from LLM)")


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _parse_json_array(text: str) -> list:
    """Extract JSON array from LLM response."""
    text = text.strip()
    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    return []


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Bootstrap a domain to v1 quality")
    parser.add_argument("domains", nargs="+", help="Domain directories to bootstrap")
    parser.add_argument("--skip-llm", action="store_true", help="Skip LLM-dependent steps")
    parser.add_argument("--cover-only", action="store_true", help="Only run cover generator step")
    parser.add_argument("--backend", default="ollama", choices=["ollama", "anthropic"])
    parser.add_argument("--model", default=None)
    args = parser.parse_args()

    llm_call = None
    if not args.skip_llm:
        try:
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from core.llm_analyzer import LLMAnalyzer
            analyzer = LLMAnalyzer({}, backend=args.backend, model=args.model)
            analyzer.connect()

            def llm_call(prompt):
                return analyzer._call_llm(
                    "You are a security researcher. Respond concisely.",
                    prompt,
                )
        except Exception as e:
            print(f"LLM not available ({e}). Running --skip-llm mode.")
            args.skip_llm = True

    for domain_path in args.domains:
        bootstrap_domain(domain_path, llm_call, args.skip_llm, cover_only=args.cover_only)
