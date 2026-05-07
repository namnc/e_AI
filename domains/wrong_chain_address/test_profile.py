"""
Auto-generated tests for wrong_chain_address domain.

Run: python domains/wrong_chain_address/test_profile.py
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
    assert profile["meta"]["domain_name"] == "wrong_chain_address"
    assert len(profile["heuristics"]) == 5


def test_profile_validation():
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from meta.tx_validation_engine import validate_profile
    profile = load_profile()
    results = validate_profile(profile)
    assert results["overall"] == "PASS", f"Validation failed: {results}"


def test_h1_structure():
    """Test H1: Address has no activity on target chain"""
    profile = load_profile()
    h = profile["heuristics"]["H1_no_activity_on_target_chain"]
    assert h["severity"] == "high"
    assert len(h["detection"]["signals"]) >= 3
    assert len(h["recommendations"]) >= 2
    for s in h["detection"]["signals"]:
        assert 0 <= s["confidence"] <= 1
        assert s.get("data_needed"), f"Signal {s['name']} missing data_needed"
    for r in h["recommendations"]:
        assert 0 <= r["effectiveness"] <= 1


def test_h2_structure():
    """Test H2: Contract address cannot receive tokens"""
    profile = load_profile()
    h = profile["heuristics"]["H2_contract_cannot_receive"]
    assert h["severity"] == "critical"
    assert len(h["detection"]["signals"]) >= 2
    assert len(h["recommendations"]) >= 2
    for s in h["detection"]["signals"]:
        assert 0 <= s["confidence"] <= 1
        assert s.get("data_needed"), f"Signal {s['name']} missing data_needed"
    for r in h["recommendations"]:
        assert 0 <= r["effectiveness"] <= 1


def test_h3_structure():
    """Test H3: Address poisoning"""
    profile = load_profile()
    h = profile["heuristics"]["H3_address_poisoning"]
    assert h["severity"] == "critical"
    assert len(h["detection"]["signals"]) >= 3
    assert len(h["recommendations"]) >= 2
    for s in h["detection"]["signals"]:
        assert 0 <= s["confidence"] <= 1
        assert s.get("data_needed"), f"Signal {s['name']} missing data_needed"
    for r in h["recommendations"]:
        assert 0 <= r["effectiveness"] <= 1


def test_h4_structure():
    """Test H4: Chain ID mismatch"""
    profile = load_profile()
    h = profile["heuristics"]["H4_chain_id_mismatch"]
    assert h["severity"] == "critical"
    assert len(h["detection"]["signals"]) >= 2
    assert len(h["recommendations"]) >= 2
    for s in h["detection"]["signals"]:
        assert 0 <= s["confidence"] <= 1
        assert s.get("data_needed"), f"Signal {s['name']} missing data_needed"
    for r in h["recommendations"]:
        assert 0 <= r["effectiveness"] <= 1


def test_h5_structure():
    """Test H5: Deprecated contract"""
    profile = load_profile()
    h = profile["heuristics"]["H5_deprecated_contract"]
    assert h["severity"] == "high"
    assert len(h["detection"]["signals"]) >= 3
    assert len(h["recommendations"]) >= 2
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


def test_analyzer_worst_case_fires():
    """Rule-based analyzer fires alerts on a maximally bad transfer."""
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from domains.wrong_chain_address.analyzer import TransferIntent, analyze_transfer
    profile = load_profile()
    bad = TransferIntent(
        tx_hash="0xtest_bad",
        user_address="0xUser",
        recipient_address="0xRecipient00000000000000000000000Lookalike",
        intended_target_chain_id=137,
        intended_target_chain_name="polygon",
        signing_chain_id=1,
        recipient_tx_count_on_target_chain=0,
        recipient_tx_count_on_other_chains={"ethereum": 1284},
        recipient_is_contract=True,
        recipient_implements_receive=False,
        recipient_implements_erc20_receiver=False,
        recipient_lookalike_in_history="0xRecipient00000000000000000000000Original",
        recipient_address_distance="prefix+suffix match",
        recent_dust_from_lookalike=True,
        recipient_paused=True,
        recipient_migrated_to="0xNewVersion",
        recipient_last_activity_age_days=900,
    )
    res = analyze_transfer(bad, profile)
    assert res.alerts, "Worst-case scenario produced no alerts"
    assert res.should_block, "Worst-case scenario should block"
    assert res.overall_risk in ("high", "critical")


def test_analyzer_healthy_clean():
    """Rule-based analyzer is silent on a clean transfer."""
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from domains.wrong_chain_address.analyzer import TransferIntent, analyze_transfer
    profile = load_profile()
    good = TransferIntent(
        tx_hash="0xtest_good",
        user_address="0xUser",
        recipient_address="0x71C7656EC7ab88b098defB751B7401B5f6d8976F",
        intended_target_chain_id=1,
        intended_target_chain_name="ethereum",
        signing_chain_id=1,
        recipient_tx_count_on_target_chain=420,
        recipient_tx_count_on_other_chains={},
        recipient_is_contract=False,
    )
    res = analyze_transfer(good, profile)
    assert not res.alerts, f"Healthy scenario produced alerts: {[a.heuristic_id for a in res.alerts]}"
    assert not res.should_block


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
