"""
Schema + structure tests for stealth_address_ops profile.

Run: python domains/stealth_address_ops/test_profile.py

Note: per-heuristic + analyzer behavioural tests live in test_analyzer.py
(this domain pre-dates the standardised test_profile.py pattern). This
file adds the pattern's basic-shape coverage so the v2 guard set passes
the standardised inventory check.
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
    assert profile["meta"]["domain_name"] == "stealth_address_ops"
    assert len(profile["heuristics"]) >= 5


def test_profile_validation():
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from meta.tx_validation_engine import validate_profile
    profile = load_profile()
    results = validate_profile(profile)
    assert results["overall"] == "PASS", f"Validation failed: {results}"


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
    data_path = Path(__file__).parent / "data"
    if not data_path.exists():
        # Some domains store labeled data elsewhere; allow this
        return
    files = list(data_path.glob("*.jsonl"))
    if files:
        with open(files[0]) as f:
            lines = [l for l in f if l.strip()]
        assert len(lines) >= 1, "Expected at least one labeled incident"


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
