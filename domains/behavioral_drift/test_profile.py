"""
Auto-generated tests for behavioral_drift domain.

Run: python domains/behavioral_drift/test_profile.py
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
    assert profile["meta"]["domain_name"] == "behavioral_drift"
    assert len(profile["heuristics"]) == 5


def test_profile_validation():
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from meta.tx_validation_engine import validate_profile
    profile = load_profile()
    results = validate_profile(profile)
    assert results["overall"] == "PASS", f"Validation failed: {results}"


def test_h1_structure():
    """Test H1: Portfolio concentration"""
    profile = load_profile()
    h = profile["heuristics"]["H1_portfolio_concentration"]
    assert h["severity"] == "high"
    assert len(h["detection"]["signals"]) >= 3
    assert len(h["recommendations"]) >= 2
    for s in h["detection"]["signals"]:
        assert 0 <= s["confidence"] <= 1
        assert s.get("data_needed"), f"Signal {s['name']} missing data_needed"
    for r in h["recommendations"]:
        assert 0 <= r["effectiveness"] <= 1


def test_h2_structure():
    """Test H2: Leverage creep"""
    profile = load_profile()
    h = profile["heuristics"]["H2_leverage_creep"]
    assert h["severity"] == "critical"
    assert len(h["detection"]["signals"]) >= 3
    assert len(h["recommendations"]) >= 2
    for s in h["detection"]["signals"]:
        assert 0 <= s["confidence"] <= 1
        assert s.get("data_needed"), f"Signal {s['name']} missing data_needed"
    for r in h["recommendations"]:
        assert 0 <= r["effectiveness"] <= 1


def test_h3_structure():
    """Test H3: Approval accumulation"""
    profile = load_profile()
    h = profile["heuristics"]["H3_approval_accumulation"]
    assert h["severity"] == "critical"
    assert len(h["detection"]["signals"]) >= 3
    assert len(h["recommendations"]) >= 2
    for s in h["detection"]["signals"]:
        assert 0 <= s["confidence"] <= 1
        assert s.get("data_needed"), f"Signal {s['name']} missing data_needed"
    for r in h["recommendations"]:
        assert 0 <= r["effectiveness"] <= 1


def test_h4_structure():
    """Test H4: Gas spending trend"""
    profile = load_profile()
    h = profile["heuristics"]["H4_gas_spending_trend"]
    assert h["severity"] == "medium"
    assert len(h["detection"]["signals"]) >= 3
    assert len(h["recommendations"]) >= 2
    for s in h["detection"]["signals"]:
        assert 0 <= s["confidence"] <= 1
        assert s.get("data_needed"), f"Signal {s['name']} missing data_needed"
    for r in h["recommendations"]:
        assert 0 <= r["effectiveness"] <= 1


def test_h5_structure():
    """Test H5: Interaction pattern rigidity"""
    profile = load_profile()
    h = profile["heuristics"]["H5_interaction_pattern_rigidity"]
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
    """Rule-based analyzer fires alerts on a maximally drifty wallet snapshot."""
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from domains.behavioral_drift.analyzer import BehavioralSnapshot, analyze_snapshot
    profile = load_profile()
    bad = BehavioralSnapshot(
        user_address="0xUser",
        weeks_observed=12,
        top_protocol="morpho",
        portfolio_share_in_top_protocol_weekly=[0.30, 0.40, 0.55, 0.70, 0.82] + [0.82] * 7,
        chain_count_active=1,
        leverage_ratio_weekly=[1.0, 1.3, 1.7, 2.0, 2.5] + [2.9] * 7,
        collateral_value_weekly_usd=[400000] * 12,
        aggregate_health_factor=1.05,
        open_unlimited_approvals=47,
        approvals_added_last_30d=18,
        approvals_revoked_last_30d=0,
        stale_approvals_count=12,
        approvals_to_known_vulnerable=2,
        gas_spent_weekly_usd=[100, 150, 200, 300, 400] + [500] * 7,
        avg_gas_to_value_ratio=0.08,
        interaction_pattern_signature="weekday_09:30_UTC_loop",
        pattern_repeat_rate_pct_last_60d=0.86,
        temporal_variance_hours=0.5,
    )
    res = analyze_snapshot(bad, profile)
    assert res.alerts, "Worst-case scenario produced no alerts"
    assert res.should_block, "Worst-case scenario should block"
    assert res.overall_risk == "critical"


def test_analyzer_healthy_clean():
    """Rule-based analyzer is silent on a stable wallet snapshot."""
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from domains.behavioral_drift.analyzer import BehavioralSnapshot, analyze_snapshot
    profile = load_profile()
    good = BehavioralSnapshot(
        user_address="0xUser",
        weeks_observed=12,
        top_protocol="aave",
        portfolio_share_in_top_protocol_weekly=[0.20, 0.22, 0.21, 0.23, 0.20, 0.22, 0.21, 0.20, 0.22, 0.21, 0.23, 0.22],
        chain_count_active=3,
        leverage_ratio_weekly=[1.10, 1.12, 1.10, 1.11, 1.10, 1.12, 1.11, 1.10, 1.12, 1.10, 1.11, 1.10],
        collateral_value_weekly_usd=[100000] * 12,
        aggregate_health_factor=3.5,
        open_unlimited_approvals=4,
        approvals_added_last_30d=1,
        approvals_revoked_last_30d=2,
        stale_approvals_count=0,
        approvals_to_known_vulnerable=0,
        gas_spent_weekly_usd=[80, 90, 85, 88, 92, 87, 90, 85, 88, 90, 92, 88],
        avg_gas_to_value_ratio=0.01,
        interaction_pattern_signature="varied",
        pattern_repeat_rate_pct_last_60d=0.20,
        temporal_variance_hours=8.0,
    )
    res = analyze_snapshot(good, profile)
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
