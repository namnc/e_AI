"""
Auto-generated tests for governance_proposal domain.

Run: python domains/governance_proposal/test_profile.py
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
    assert profile["meta"]["domain_name"] == "governance_proposal"
    assert len(profile["heuristics"]) == 5


def test_profile_validation():
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from meta.tx_validation_engine import validate_profile
    profile = load_profile()
    results = validate_profile(profile)
    assert results["overall"] == "PASS", f"Validation failed: {results}"


def test_h1_structure():
    """Test H1: Treasury drain"""
    profile = load_profile()
    h = profile["heuristics"]["H1_treasury_drain"]
    assert h["severity"] == "critical"
    assert len(h["detection"]["signals"]) >= 3
    assert len(h["recommendations"]) >= 3
    for s in h["detection"]["signals"]:
        assert 0 <= s["confidence"] <= 1
        assert s.get("data_needed"), f"Signal {s['name']} missing data_needed"
    for r in h["recommendations"]:
        assert 0 <= r["effectiveness"] <= 1


def test_h2_structure():
    """Test H2: Parameter manipulation"""
    profile = load_profile()
    h = profile["heuristics"]["H2_parameter_manipulation"]
    assert h["severity"] == "high"
    assert len(h["detection"]["signals"]) >= 3
    assert len(h["recommendations"]) >= 3
    for s in h["detection"]["signals"]:
        assert 0 <= s["confidence"] <= 1
        assert s.get("data_needed"), f"Signal {s['name']} missing data_needed"
    for r in h["recommendations"]:
        assert 0 <= r["effectiveness"] <= 1


def test_h3_structure():
    """Test H3: Proxy upgrade to unverified code"""
    profile = load_profile()
    h = profile["heuristics"]["H3_proxy_upgrade"]
    assert h["severity"] == "critical"
    assert len(h["detection"]["signals"]) >= 4
    assert len(h["recommendations"]) >= 3
    for s in h["detection"]["signals"]:
        assert 0 <= s["confidence"] <= 1
        assert s.get("data_needed"), f"Signal {s['name']} missing data_needed"
    for r in h["recommendations"]:
        assert 0 <= r["effectiveness"] <= 1


def test_h4_structure():
    """Test H4: Timelocked bypass"""
    profile = load_profile()
    h = profile["heuristics"]["H4_timelock_bypass"]
    assert h["severity"] == "critical"
    assert len(h["detection"]["signals"]) >= 3
    assert len(h["recommendations"]) >= 3
    for s in h["detection"]["signals"]:
        assert 0 <= s["confidence"] <= 1
        assert s.get("data_needed"), f"Signal {s['name']} missing data_needed"
    for r in h["recommendations"]:
        assert 0 <= r["effectiveness"] <= 1


def test_h5_structure():
    """Test H5: Voter concentration"""
    profile = load_profile()
    h = profile["heuristics"]["H5_voter_concentration"]
    assert h["severity"] == "high"
    assert len(h["detection"]["signals"]) >= 3
    assert len(h["recommendations"]) >= 3
    for s in h["detection"]["signals"]:
        assert 0 <= s["confidence"] <= 1
        assert s.get("data_needed"), f"Signal {s['name']} missing data_needed"
    for r in h["recommendations"]:
        assert 0 <= r["effectiveness"] <= 1


def test_skills_complete():
    """All referenced skills are defined."""
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
    """Required templates exist."""
    profile = load_profile()
    templates = profile.get("templates", {})
    for key in ["risk_assessment", "summary", "skill_suggestion"]:
        assert key in templates, f"Missing template: {key}"


def test_labeled_data_exists():
    """Labeled data file exists and has entries."""
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
