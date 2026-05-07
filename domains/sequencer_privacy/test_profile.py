"""
Auto-generated tests for sequencer_privacy domain.

Run: python domains/sequencer_privacy/test_profile.py
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
    assert profile["meta"]["domain_name"] == "sequencer_privacy"
    assert len(profile["heuristics"]) == 5


def test_profile_validation():
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from meta.tx_validation_engine import validate_profile
    profile = load_profile()
    results = validate_profile(profile)
    assert results["overall"] == "PASS", f"Validation failed: {results}"


def test_h1_structure():
    """Test H1: Centralized sequencer"""
    profile = load_profile()
    h = profile["heuristics"]["H1_centralized_sequencer"]
    assert h["severity"] == "high"
    assert len(h["detection"]["signals"]) >= 3
    assert len(h["recommendations"]) >= 2
    for s in h["detection"]["signals"]:
        assert 0 <= s["confidence"] <= 1
        assert s.get("data_needed"), f"Signal {s['name']} missing data_needed"
    for r in h["recommendations"]:
        assert 0 <= r["effectiveness"] <= 1


def test_h2_structure():
    """Test H2: Sequencer censorship"""
    profile = load_profile()
    h = profile["heuristics"]["H2_sequencer_censorship"]
    assert h["severity"] == "critical"
    assert len(h["detection"]["signals"]) >= 3
    assert len(h["recommendations"]) >= 2
    for s in h["detection"]["signals"]:
        assert 0 <= s["confidence"] <= 1
        assert s.get("data_needed"), f"Signal {s['name']} missing data_needed"
    for r in h["recommendations"]:
        assert 0 <= r["effectiveness"] <= 1


def test_h3_structure():
    """Test H3: Sequencer MEV extraction"""
    profile = load_profile()
    h = profile["heuristics"]["H3_sequencer_mev"]
    assert h["severity"] == "high"
    assert len(h["detection"]["signals"]) >= 2
    assert len(h["recommendations"]) >= 2
    for s in h["detection"]["signals"]:
        assert 0 <= s["confidence"] <= 1
        assert s.get("data_needed"), f"Signal {s['name']} missing data_needed"
    for r in h["recommendations"]:
        assert 0 <= r["effectiveness"] <= 1


def test_h4_structure():
    """Test H4: Shared sequencer linkage"""
    profile = load_profile()
    h = profile["heuristics"]["H4_shared_sequencer_linkage"]
    assert h["severity"] == "high"
    assert len(h["detection"]["signals"]) >= 3
    assert len(h["recommendations"]) >= 2
    for s in h["detection"]["signals"]:
        assert 0 <= s["confidence"] <= 1
        assert s.get("data_needed"), f"Signal {s['name']} missing data_needed"
    for r in h["recommendations"]:
        assert 0 <= r["effectiveness"] <= 1


def test_h5_structure():
    """Test H5: Pre-confirmation privacy leak"""
    profile = load_profile()
    h = profile["heuristics"]["H5_preconfirmation_privacy"]
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
    """Rule-based analyzer fires alerts on a maximally adversarial sequencer scenario."""
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from domains.sequencer_privacy.analyzer import SequencerSubmission, analyze_submission
    profile = load_profile()
    bad = SequencerSubmission(
        user_address="0xUser",
        l2_chain="arbitrum",
        tx_value_usd=18000.0,
        tx_kind="privacy_pool_deposit",
        is_high_value=True,
        is_privacy_relevant=True,
        tx_submitted_at=1735776000,
        expected_inclusion_by=1735776300,
        actually_included=False,
        valid_gas_and_nonce=True,
        user_flagged_as_sanctioned=True,
        consecutive_exclusions=4,
        sequencer_mev_extracted_usd_30d=1_250_000.0,
        sequencer_share_of_l2_mev_pct=0.78,
        shared_sequencer_other_rollups=["arbitrum", "optimism", "base"],
        preconfirmation_published_before_batch=True,
        preconfirmation_window_seconds=30,
        preconfirmation_publicly_readable=True,
    )
    res = analyze_submission(bad, profile)
    assert res.alerts, "Worst-case scenario produced no alerts"
    assert res.should_block, "Worst-case scenario should block"
    assert res.overall_risk == "critical"


def test_analyzer_healthy_clean():
    """Rule-based analyzer is silent on a clean L1-routed submission."""
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from domains.sequencer_privacy.analyzer import SequencerSubmission, analyze_submission
    profile = load_profile()
    good = SequencerSubmission(
        user_address="0xUser",
        l2_chain="ethereum",
        tx_kind="transfer",
        is_privacy_relevant=False,
        actually_included=True,
        valid_gas_and_nonce=True,
        sequencer_share_of_l2_mev_pct=0.0,
        sequencer_mev_extracted_usd_30d=0.0,
        preconfirmation_published_before_batch=False,
    )
    res = analyze_submission(good, profile)
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
