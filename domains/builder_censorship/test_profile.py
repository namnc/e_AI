"""
Auto-generated tests for builder_censorship domain.

Run: python domains/builder_censorship/test_profile.py
"""

import json
import sys
from pathlib import Path

PROFILE_PATH = Path(__file__).parent / "profile.json"


def load_profile():
    with open(PROFILE_PATH) as f:
        return json.load(f)


def test_profile_loads():
    profile = load_profile()
    assert profile["meta"]["domain_name"] == "builder_censorship"
    assert len(profile["heuristics"]) == 5


def test_profile_validation():
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from meta.tx_validation_engine import validate_profile
    profile = load_profile()
    results = validate_profile(profile)
    assert results["overall"] == "PASS", f"Validation failed: {results}"


def test_heuristic_ids_unique():
    profile = load_profile()
    ids = [h["id"] for h in profile["heuristics"].values()]
    assert len(set(ids)) == len(ids), f"Duplicate heuristic ids: {ids}"


def test_h1_structure():
    """H1: censoring relay route"""
    profile = load_profile()
    h = profile["heuristics"]["H1_censoring_relay_route"]
    assert h["severity"] == "high"
    assert len(h["detection"]["signals"]) >= 2
    assert len(h["recommendations"]) >= 2


def test_h2_structure():
    """H2: sanctioned address interaction"""
    profile = load_profile()
    h = profile["heuristics"]["H2_sanctioned_address_interaction"]
    assert h["severity"] == "critical"
    assert len(h["detection"]["signals"]) >= 2


def test_h3_structure():
    """H3: L2 forced-inclusion missing"""
    profile = load_profile()
    h = profile["heuristics"]["H3_l2_centralized_sequencer_no_forced_inclusion"]
    assert h["severity"] == "high"


def test_h4_structure():
    """H4: builder monoculture"""
    profile = load_profile()
    h = profile["heuristics"]["H4_builder_monoculture"]
    assert h["severity"] == "medium"


def test_h5_structure():
    """H5: compound no-circumvention path"""
    profile = load_profile()
    h = profile["heuristics"]["H5_no_circumvention_path"]
    assert h["severity"] == "high"
    assert h["detection"]["type"] == "compound"


def test_recommendations_well_formed():
    profile = load_profile()
    for h in profile["heuristics"].values():
        for r in h["recommendations"]:
            assert "action" in r
            assert "description" in r
            assert "effectiveness" in r
            assert 0 <= r["effectiveness"] <= 1


def test_skills_complete():
    profile = load_profile()
    skills = set(profile.get("skills", {}).keys())
    referenced = set()
    for h in profile["heuristics"].values():
        for r in h.get("recommendations", []):
            s = r.get("skill_required")
            if s:
                referenced.add(s)
    missing = referenced - skills
    assert not missing, f"Missing skills: {missing}"


def test_templates():
    profile = load_profile()
    templates = profile.get("templates", {})
    for key in ["risk_assessment", "summary", "skill_suggestion"]:
        assert key in templates, f"Missing template: {key}"


def test_labeled_data_exists():
    data_path = Path(__file__).parent / "data" / "labeled_incidents.jsonl"
    assert data_path.exists(), "No labeled data file"
    with open(data_path) as f:
        lines = [l for l in f if l.strip()]
    assert len(lines) >= 5, f"Only {len(lines)} incidents"


if __name__ == "__main__":
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for test in tests:
        try:
            test()
            print(f"  PASS  {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {test.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed out of {passed + failed}")
    sys.exit(1 if failed else 0)
