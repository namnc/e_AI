"""
Behavioral Drift Analyzer — profile-based long-term wallet behavior risk.

Loads behavioral_drift/profile.json and evaluates a multi-week behavioral
snapshot against 5 heuristics (H1-H5): portfolio concentration, leverage
creep, approval accumulation, gas spending trend, interaction pattern
rigidity.

This is a DEMO / preliminary implementation. Production deployment must
wire the snapshot fields from on-chain RPC + indexer (DeFi positions,
approval events, transaction timestamps) over a >=90-day window.

Usage:
    python analyzer.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


CONCENTRATION_DOMINANCE_THRESHOLD = 0.50
CONCENTRATION_DRIFT_DELTA = 0.10
LEVERAGE_INCREASE_FACTOR = 1.5
LEVERAGE_HEALTH_FACTOR_ALERT = 1.3
UNLIMITED_APPROVALS_THRESHOLD = 10
GAS_GROWTH_FACTOR = 2.0
PATTERN_REPEAT_THRESHOLD = 0.70


@dataclass
class BehavioralSnapshot:
    """Multi-week wallet behavioral snapshot for drift analysis."""
    user_address: str
    weeks_observed: int

    # H1: portfolio concentration
    top_protocol: str = ""
    portfolio_share_in_top_protocol_weekly: list[float] = field(default_factory=list)
    chain_count_active: int = 1

    # H2: leverage creep
    leverage_ratio_weekly: list[float] = field(default_factory=list)
    collateral_value_weekly_usd: list[float] = field(default_factory=list)
    aggregate_health_factor: float = 5.0
    lending_protocol_count: int = 0

    # H3: approval accumulation
    open_unlimited_approvals: int = 0
    approvals_added_last_30d: int = 0
    approvals_revoked_last_30d: int = 0
    stale_approvals_count: int = 0  # contracts not interacted with in 90+ days
    approvals_to_known_vulnerable: int = 0

    # H4: gas spending
    gas_spent_weekly_usd: list[float] = field(default_factory=list)
    avg_gas_to_value_ratio: float = 0.0  # gas as fraction of tx value

    # H5: interaction pattern rigidity
    interaction_pattern_signature: str = ""
    pattern_repeat_rate_pct_last_60d: float = 0.0
    temporal_variance_hours: float = 24.0  # std-dev of tx hour-of-day

    current_timestamp: int = 0


@dataclass
class RiskAlert:
    heuristic_id: str
    heuristic_name: str
    severity: str
    confidence: float
    signal: str
    recommendation: str
    skill: Optional[str] = None
    action: Optional[str] = None


@dataclass
class AnalysisResult:
    snapshot: BehavioralSnapshot
    alerts: list[RiskAlert] = field(default_factory=list)
    overall_risk: str = "low"
    should_block: bool = False


def load_profile(path: str | Path) -> dict:
    with open(path) as f:
        return json.load(f)


def check_h1_portfolio_concentration(s: BehavioralSnapshot, profile: dict) -> list[RiskAlert]:
    series = s.portfolio_share_in_top_protocol_weekly
    if len(series) < 2:
        return []

    h = profile["heuristics"]["H1_portfolio_concentration"]
    alerts: list[RiskAlert] = []

    current = series[-1]
    delta = current - series[0]

    if current > CONCENTRATION_DOMINANCE_THRESHOLD and delta > CONCENTRATION_DRIFT_DELTA:
        alerts.append(
            RiskAlert(
                heuristic_id="H1",
                heuristic_name=h["name"],
                severity=h["severity"],
                confidence=0.85,
                signal=(
                    f"Concentration in {s.top_protocol or 'top protocol'} drifted "
                    f"{series[0]:.0%} -> {current:.0%} over {len(series)} weeks "
                    f"(+{delta:.0%} above {CONCENTRATION_DOMINANCE_THRESHOLD:.0%} threshold)."
                ),
                recommendation="Diversify across protocols; cap single-protocol exposure at <30%.",
                skill="portfolio_tracker",
                action="warn",
            )
        )

    if s.chain_count_active <= 1 and current > CONCENTRATION_DOMINANCE_THRESHOLD:
        alerts.append(
            RiskAlert(
                heuristic_id="H1",
                heuristic_name=h["name"],
                severity="medium",
                confidence=0.70,
                signal=f"Entire portfolio on a single chain with {current:.0%} in one protocol.",
                recommendation="Consider cross-chain diversification to reduce correlated risk.",
                skill="portfolio_tracker",
                action="inform",
            )
        )

    return alerts


def check_h2_leverage_creep(s: BehavioralSnapshot, profile: dict) -> list[RiskAlert]:
    lev = s.leverage_ratio_weekly
    if len(lev) < 2:
        return []

    h = profile["heuristics"]["H2_leverage_creep"]
    alerts: list[RiskAlert] = []

    growing = lev[-1] > lev[0] * LEVERAGE_INCREASE_FACTOR
    coll = s.collateral_value_weekly_usd
    coll_flat = bool(coll) and len(coll) >= 2 and coll[-1] < coll[0] * 1.10

    if growing and coll_flat:
        alerts.append(
            RiskAlert(
                heuristic_id="H2",
                heuristic_name=h["name"],
                severity=h["severity"],
                confidence=0.90,
                signal=(
                    f"Leverage drifted {lev[0]:.2f}x -> {lev[-1]:.2f}x over {len(lev)} weeks "
                    f"with collateral roughly flat (${coll[0]:,.0f} -> ${coll[-1]:,.0f})."
                ),
                recommendation="Reduce borrow position; recheck health-factor sensitivity to a 30% collateral price drop.",
                skill="leverage_monitor",
                action="warn",
            )
        )

    if s.aggregate_health_factor < LEVERAGE_HEALTH_FACTOR_ALERT:
        alerts.append(
            RiskAlert(
                heuristic_id="H2",
                heuristic_name=h["name"],
                severity="critical",
                confidence=0.95,
                signal=f"Aggregate health factor {s.aggregate_health_factor:.2f} < {LEVERAGE_HEALTH_FACTOR_ALERT}.",
                recommendation="BLOCK new borrows; deleverage now to avoid liquidation in normal volatility.",
                skill="leverage_monitor",
                action="block",
            )
        )

    return alerts


def check_h3_approval_accumulation(s: BehavioralSnapshot, profile: dict) -> list[RiskAlert]:
    h = profile["heuristics"]["H3_approval_accumulation"]
    alerts: list[RiskAlert] = []

    if s.approvals_to_known_vulnerable > 0:
        alerts.append(
            RiskAlert(
                heuristic_id="H3",
                heuristic_name=h["name"],
                severity="critical",
                confidence=0.95,
                signal=f"{s.approvals_to_known_vulnerable} outstanding approval(s) to contracts in vulnerability database.",
                recommendation="REVOKE immediately; tokens are exposed to a known exploit vector.",
                skill="approval_auditor",
                action="block",
            )
        )

    if s.open_unlimited_approvals > UNLIMITED_APPROVALS_THRESHOLD and s.approvals_revoked_last_30d == 0:
        alerts.append(
            RiskAlert(
                heuristic_id="H3",
                heuristic_name=h["name"],
                severity=h["severity"],
                confidence=0.85,
                signal=(
                    f"{s.open_unlimited_approvals} unlimited approvals with zero revocations in 30d "
                    f"({s.approvals_added_last_30d} added)."
                ),
                recommendation="Run revoke.cash audit; revoke unused approvals; prefer exact-amount approvals.",
                skill="approval_auditor",
                action="warn",
            )
        )

    if s.stale_approvals_count > 0:
        alerts.append(
            RiskAlert(
                heuristic_id="H3",
                heuristic_name=h["name"],
                severity="medium",
                confidence=0.80,
                signal=f"{s.stale_approvals_count} approvals to contracts not used in 90+ days.",
                recommendation="Revoke stale approvals; each is an unnecessary attack surface.",
                skill="approval_auditor",
                action="inform",
            )
        )

    return alerts


def check_h4_gas_spending_trend(s: BehavioralSnapshot, profile: dict) -> list[RiskAlert]:
    gas = s.gas_spent_weekly_usd
    if len(gas) < 4:
        return []

    h = profile["heuristics"]["H4_gas_spending_trend"]
    alerts: list[RiskAlert] = []

    if gas[-1] > gas[0] * GAS_GROWTH_FACTOR:
        alerts.append(
            RiskAlert(
                heuristic_id="H4",
                heuristic_name=h["name"],
                severity=h["severity"],
                confidence=0.65,
                signal=f"Weekly gas spend grew ${gas[0]:.0f} -> ${gas[-1]:.0f} over {len(gas)} weeks.",
                recommendation="Audit recent strategies for gas waste; consider batching or migrating to L2.",
                action="inform",
            )
        )

    if s.avg_gas_to_value_ratio > 0.05:
        alerts.append(
            RiskAlert(
                heuristic_id="H4",
                heuristic_name=h["name"],
                severity="medium",
                confidence=0.75,
                signal=f"Average gas-to-value ratio {s.avg_gas_to_value_ratio:.1%} > 5%.",
                recommendation="Batch operations; switch low-value transfers to L2.",
                action="inform",
            )
        )

    return alerts


def check_h5_pattern_rigidity(s: BehavioralSnapshot, profile: dict) -> list[RiskAlert]:
    h = profile["heuristics"]["H5_interaction_pattern_rigidity"]
    alerts: list[RiskAlert] = []

    if s.pattern_repeat_rate_pct_last_60d > PATTERN_REPEAT_THRESHOLD:
        alerts.append(
            RiskAlert(
                heuristic_id="H5",
                heuristic_name=h["name"],
                severity=h["severity"],
                confidence=0.85,
                signal=(
                    f"Pattern '{s.interaction_pattern_signature}' repeats at "
                    f"{s.pattern_repeat_rate_pct_last_60d:.0%} of opportunities (>{PATTERN_REPEAT_THRESHOLD:.0%} threshold)."
                ),
                recommendation="Add timing/order jitter (1-6 hour random delay); occasionally reorder non-dependent ops.",
                action="inform",
            )
        )

    if s.temporal_variance_hours < 1.0 and s.weeks_observed >= 4:
        alerts.append(
            RiskAlert(
                heuristic_id="H5",
                heuristic_name=h["name"],
                severity="medium",
                confidence=0.75,
                signal=f"Transaction time-of-day variance {s.temporal_variance_hours:.1f}h (very rigid daily schedule).",
                recommendation="Randomize transaction timing to break temporal fingerprint.",
                action="inform",
            )
        )

    return alerts


_CHECKS = [
    check_h1_portfolio_concentration,
    check_h2_leverage_creep,
    check_h3_approval_accumulation,
    check_h4_gas_spending_trend,
    check_h5_pattern_rigidity,
]


def analyze_snapshot(snapshot: BehavioralSnapshot, profile: dict) -> AnalysisResult:
    alerts: list[RiskAlert] = []
    for chk in _CHECKS:
        alerts.extend(chk(snapshot, profile))

    severity_rank = {"low": 1, "medium": 2, "high": 3, "critical": 4}
    overall = "low"
    block = False
    for a in alerts:
        if severity_rank.get(a.severity, 0) > severity_rank.get(overall, 0):
            overall = a.severity
        if a.action == "block":
            block = True

    return AnalysisResult(snapshot=snapshot, alerts=alerts, overall_risk=overall, should_block=block)


# ---------------------------------------------------------------------------
# Local self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    profile_path = Path(__file__).parent / "profile.json"
    profile = load_profile(profile_path)

    bad = BehavioralSnapshot(
        user_address="0xUserDrifter",
        weeks_observed=12,
        top_protocol="morpho",
        portfolio_share_in_top_protocol_weekly=[0.30, 0.34, 0.39, 0.45, 0.50, 0.55, 0.60, 0.66, 0.71, 0.74, 0.78, 0.82],
        chain_count_active=1,
        leverage_ratio_weekly=[1.10, 1.15, 1.22, 1.30, 1.40, 1.55, 1.70, 1.90, 2.10, 2.35, 2.60, 2.90],
        collateral_value_weekly_usd=[400000, 405000, 408000, 410000, 412000, 414000, 415000, 416000, 416500, 417000, 417500, 418000],
        aggregate_health_factor=1.10,
        lending_protocol_count=2,
        open_unlimited_approvals=47,
        approvals_added_last_30d=18,
        approvals_revoked_last_30d=0,
        stale_approvals_count=12,
        approvals_to_known_vulnerable=2,
        gas_spent_weekly_usd=[120, 135, 158, 184, 210, 245, 285, 330, 380, 440, 510, 590],
        avg_gas_to_value_ratio=0.08,
        interaction_pattern_signature="weekday_09:30_UTC_aave_borrow_to_uniswap_swap_to_curve_lp",
        pattern_repeat_rate_pct_last_60d=0.86,
        temporal_variance_hours=0.5,
    )
    print("=== Worst-case ===")
    res = analyze_snapshot(bad, profile)
    print(f"overall={res.overall_risk} block={res.should_block} alerts={len(res.alerts)}")
    for a in res.alerts:
        print(f"  [{a.severity}] {a.heuristic_id}: {a.signal[:80]}")

    good = BehavioralSnapshot(
        user_address="0xUserStable",
        weeks_observed=12,
        top_protocol="aave",
        portfolio_share_in_top_protocol_weekly=[0.20, 0.22, 0.21, 0.23, 0.20, 0.22, 0.21, 0.20, 0.22, 0.21, 0.23, 0.22],
        chain_count_active=3,
        leverage_ratio_weekly=[1.10, 1.12, 1.10, 1.11, 1.10, 1.12, 1.11, 1.10, 1.12, 1.10, 1.11, 1.10],
        collateral_value_weekly_usd=[100000] * 12,
        aggregate_health_factor=3.5,
        lending_protocol_count=1,
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
    print("\n=== Healthy ===")
    res = analyze_snapshot(good, profile)
    print(f"overall={res.overall_risk} block={res.should_block} alerts={len(res.alerts)}")
