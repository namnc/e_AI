"""
behavioral_drift demo — runs the rule-based + LLM analyzers on a sample 12-week snapshot.

Run:
    python examples/per_domain/behavioral_drift/demo.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from core.llm_analyzer import LLMAnalyzer
from domains.behavioral_drift.analyzer import (
    BehavioralSnapshot,
    analyze_snapshot,
    load_profile,
)


HERE = Path(__file__).parent
PROFILE_PATH = REPO_ROOT / "domains" / "behavioral_drift" / "profile.json"
SAMPLE_PATH = HERE / "sample_tx.json"


def build_snapshot() -> BehavioralSnapshot:
    raw = json.loads(SAMPLE_PATH.read_text())
    return BehavioralSnapshot(
        user_address=raw["user_address"],
        weeks_observed=raw["weeks_observed"],
        top_protocol=raw.get("top_protocol", ""),
        portfolio_share_in_top_protocol_weekly=raw.get("portfolio_share_in_top_protocol_weekly", []),
        chain_count_active=raw.get("chain_count_active", 1),
        leverage_ratio_weekly=raw.get("leverage_ratio_weekly", []),
        collateral_value_weekly_usd=raw.get("collateral_value_weekly_usd", []),
        aggregate_health_factor=raw.get("aggregate_health_factor", 5.0),
        lending_protocol_count=raw.get("lending_protocol_count", 0),
        open_unlimited_approvals=raw.get("open_unlimited_approvals", 0),
        approvals_added_last_30d=raw.get("approvals_added_last_30d", 0),
        approvals_revoked_last_30d=raw.get("approvals_revoked_last_30d", 0),
        stale_approvals_count=raw.get("stale_approvals_count", 0),
        approvals_to_known_vulnerable=raw.get("approvals_to_known_vulnerable", 0),
        gas_spent_weekly_usd=raw.get("gas_spent_weekly_usd", []),
        avg_gas_to_value_ratio=raw.get("avg_gas_to_value_ratio", 0.0),
        interaction_pattern_signature=raw.get("interaction_pattern_signature", ""),
        pattern_repeat_rate_pct_last_60d=raw.get("pattern_repeat_rate_pct_last_60d", 0.0),
        temporal_variance_hours=raw.get("temporal_variance_hours", 24.0),
        current_timestamp=raw.get("current_timestamp", 0),
    )


def print_result(result, llm_result):
    s = result.snapshot
    print("=" * 70)
    print("behavioral_drift — multi-week behavioral risk")
    print("=" * 70)
    print(f"User: {s.user_address}")
    print(f"Weeks observed: {s.weeks_observed}")
    if s.portfolio_share_in_top_protocol_weekly:
        series = s.portfolio_share_in_top_protocol_weekly
        print(f"Concentration ({s.top_protocol}): {series[0]:.0%} -> {series[-1]:.0%}")
    if s.leverage_ratio_weekly:
        lev = s.leverage_ratio_weekly
        print(f"Leverage: {lev[0]:.2f}x -> {lev[-1]:.2f}x; health={s.aggregate_health_factor:.2f}")
    print(f"Approvals: {s.open_unlimited_approvals} open ({s.approvals_to_known_vulnerable} vulnerable)")
    print()
    print(f"OVERALL RISK: {result.overall_risk.upper()}")
    print(f"SHOULD BLOCK: {result.should_block}")
    print(f"ALERTS: {len(result.alerts)}")
    print()
    for a in result.alerts:
        print(f"  [{a.severity.upper():8s}] {a.heuristic_id} {a.heuristic_name} "
              f"(confidence {a.confidence:.2f})")
        print(f"    signal: {a.signal}")
        print(f"    recommend: {a.recommendation}")
        if a.action:
            print(f"    action: {a.action}")
        print()
    print("-" * 70)
    print("LLM behavioral analysis")
    print("-" * 70)
    if llm_result.get("degraded_mode"):
        print(f"[degraded] {llm_result.get('degraded_reason')}")
        print(f"Synthesized result: {llm_result.get('explanation')}")
    else:
        print(f"Risk: {llm_result.get('risk_level')}")
        print(f"Explanation: {llm_result.get('explanation')}")
        if llm_result.get("recommendations"):
            print("Recommendations:")
            for r in llm_result["recommendations"]:
                print(f"  - {r}")


def main():
    profile = load_profile(PROFILE_PATH)
    snapshot = build_snapshot()
    result = analyze_snapshot(snapshot, profile)

    rule_alerts_dicts = [
        {
            "heuristic_id": a.heuristic_id,
            "severity": a.severity,
            "signal": a.signal,
            "recommendation": a.recommendation,
        }
        for a in result.alerts
    ]
    llm = LLMAnalyzer(profile, backend="ollama", model="qwen2.5:7b")
    llm.connect()
    llm_result = llm.analyze(
        tx={
            "weeks": snapshot.weeks_observed,
            "top_protocol": snapshot.top_protocol,
            "concentration_now": (snapshot.portfolio_share_in_top_protocol_weekly or [None])[-1],
            "leverage_now": (snapshot.leverage_ratio_weekly or [None])[-1],
            "open_approvals": snapshot.open_unlimited_approvals,
            "pattern_rate": snapshot.pattern_repeat_rate_pct_last_60d,
        },
        rule_based_alerts=rule_alerts_dicts,
    )

    print_result(result, llm_result)


if __name__ == "__main__":
    main()
