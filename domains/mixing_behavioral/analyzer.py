"""
Mixing Behavioral Analyzer — pre-withdrawal post-mixer linkability detection.

Profile-driven runtime check matching Tutela-class heuristics on the
pre-withdrawal moment. Production inputs come from chain-data integrations
(pool deposit history, address cluster maps, gas stats, defi-interaction
prediction); the analyzer trusts the caller to wire them.

Usage:
    python analyzer.py
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class MixerWithdrawal:
    """A pre-withdrawal moment from a privacy mixer / pool."""
    tx_hash: str
    user_address: str
    withdrawal_address: str
    pool_id: str
    pool_denomination: str  # e.g., "1.0 ETH" for fixed-denom; "variable" for Privacy Pools
    deposit_timestamp: int  # unix seconds
    withdrawal_timestamp: int  # unix seconds (planned)
    pool_deposit_count_in_24h_window: int  # unique depositors in pool over deposit-time ± 12h
    pool_concurrent_deposits_in_window: int  # depositors active during dwell window

    # H2 amount-fingerprinting inputs
    deposit_amount: float = 0.0  # native unit (ETH for ETH pools)
    pool_amount_distribution: list[float] = field(default_factory=list)  # other amounts in pool over window
    is_variable_denom_pool: bool = False  # True for Railgun / Privacy Pools

    # H3 multi-denomination linkage
    user_recent_deposits_across_pools: list[dict] = field(default_factory=list)  # [{pool, amount, timestamp}]
    user_recent_withdrawals_across_pools: list[dict] = field(default_factory=list)

    # H4 cross-protocol linkage
    withdrawal_address_prior_defi_interactions: int = 0  # count over 90d
    expected_post_withdrawal_action: Optional[str] = None  # "defi_swap" | "bridge" | "hold" | None
    expected_post_withdrawal_delay_blocks: int = 0
    withdrawal_address_known_cluster_match: bool = False  # behavioral-profile match against known cluster

    # H5 mixer-specific metadata
    selected_relayer: Optional[str] = None
    relayer_market_share_pct: float = 100.0  # what fraction of pool withdrawals this relayer handles
    withdrawal_address_prior_mixer_uses: int = 0
    withdrawal_tx_gas_price_gwei: float = 0.0
    block_gas_median_gwei: float = 0.0
    block_gas_stddev_gwei: float = 0.0

    # H1 behavioral pattern
    user_prior_dwell_times_seconds: list[int] = field(default_factory=list)  # past dwell times across mixing ops


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
    tx: MixerWithdrawal
    alerts: list[RiskAlert] = field(default_factory=list)
    overall_risk: str = "low"
    should_block: bool = False


def load_profile(path: str | Path) -> dict:
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# H1 — Timing correlation
# ---------------------------------------------------------------------------

def check_h1_timing_correlation(tx: MixerWithdrawal, profile: dict) -> list[RiskAlert]:
    h = profile["heuristics"]["H1_timing_correlation"]
    alerts: list[RiskAlert] = []
    dwell_seconds = max(0, tx.withdrawal_timestamp - tx.deposit_timestamp)
    dwell_hours = dwell_seconds / 3600.0

    # short_dwell_time: <1h with <50 concurrent
    if dwell_hours < 1 and tx.pool_concurrent_deposits_in_window < 50:
        alerts.append(
            RiskAlert(
                heuristic_id="H1",
                heuristic_name=h["name"],
                severity="critical",
                confidence=0.9,
                signal=f"Dwell {dwell_hours:.2f}h with only {tx.pool_concurrent_deposits_in_window} concurrent deposits — anonymity set narrows to a handful",
                recommendation="Wait until pool has more concurrent deposits or extend dwell time substantially.",
                skill="dwell_time_extension",
                action="warn",
            )
        )
    elif dwell_hours < 6 and tx.pool_concurrent_deposits_in_window < 200:
        # medium_dwell_time
        alerts.append(
            RiskAlert(
                heuristic_id="H1",
                heuristic_name=h["name"],
                severity="medium",
                confidence=0.65,
                signal=f"Dwell {dwell_hours:.1f}h with {tx.pool_concurrent_deposits_in_window} concurrent deposits — moderate timing-correlation risk",
                recommendation="Consider extending dwell time toward 24h+ or wait for pool to grow.",
                skill="dwell_time_extension",
                action="inform",
            )
        )

    # consistent_dwell_pattern: behavioral fingerprint
    if len(tx.user_prior_dwell_times_seconds) >= 3:
        dwells_h = [d / 3600.0 for d in tx.user_prior_dwell_times_seconds]
        mean = statistics.mean(dwells_h)
        try:
            stddev = statistics.stdev(dwells_h)
        except statistics.StatisticsError:
            stddev = 0.0
        # Tight spread (low CV) means consistent dwell — fingerprint
        if mean > 0 and stddev / mean < 0.20 and abs(dwell_hours - mean) < stddev * 1.5:
            alerts.append(
                RiskAlert(
                    heuristic_id="H1",
                    heuristic_name=h["name"],
                    severity="medium",
                    confidence=0.8,
                    signal=f"Dwell-time pattern is consistent across {len(dwells_h)} prior ops (mean {mean:.1f}h, stddev {stddev:.1f}h) — behavioral fingerprint",
                    recommendation="Vary dwell time substantially across mixing operations to avoid pattern-fingerprint.",
                    skill="dwell_pattern_randomization",
                    action="inform",
                )
            )
    return alerts


# ---------------------------------------------------------------------------
# H2 — Amount fingerprinting
# ---------------------------------------------------------------------------

def check_h2_amount_fingerprinting(tx: MixerWithdrawal, profile: dict) -> list[RiskAlert]:
    h = profile["heuristics"]["H2_amount_fingerprinting"]
    alerts: list[RiskAlert] = []

    # unique_amount_in_pool: variable-pool with <3 matches in 24h
    if tx.is_variable_denom_pool and tx.pool_amount_distribution:
        matches = sum(
            1
            for a in tx.pool_amount_distribution
            if abs(a - tx.deposit_amount) < tx.deposit_amount * 0.001
        )
        if matches < 3:
            alerts.append(
                RiskAlert(
                    heuristic_id="H2",
                    heuristic_name=h["name"],
                    severity="high",
                    confidence=0.9,
                    signal=f"Deposit amount {tx.deposit_amount} has only {matches} matches in pool — uniquely-identifying",
                    recommendation="Round deposit to a common pool denomination, or split into common-amount tranches.",
                    skill="amount_normalization",
                    action="warn",
                )
            )

    # precise_non_round_amount: >4 decimal places
    s = f"{tx.deposit_amount:.10f}".rstrip("0").rstrip(".")
    if "." in s:
        decimals = len(s.split(".")[1])
        if decimals > 4:
            alerts.append(
                RiskAlert(
                    heuristic_id="H2",
                    heuristic_name=h["name"],
                    severity="medium",
                    confidence=0.55,
                    signal=f"Deposit amount has {decimals} decimal places — statistically unique even in active pools",
                    recommendation="Round deposit to a standard denomination (0.1, 1.0, 10.0).",
                    skill="amount_normalization",
                    action="inform",
                )
            )

    # total_amount_fingerprint: cross-pool denomination sum
    if tx.user_recent_deposits_across_pools:
        recent_amounts = sorted(
            d.get("amount", 0.0) for d in tx.user_recent_deposits_across_pools
        )
        if len(recent_amounts) >= 2:
            # Distinctive multi-denomination combination?
            # Soft heuristic: if >=3 distinct denominations within a 7-day window, the
            # combination is likely unique.
            distinct = len({round(a, 4) for a in recent_amounts})
            if distinct >= 3:
                alerts.append(
                    RiskAlert(
                        heuristic_id="H2",
                        heuristic_name=h["name"],
                        severity="medium",
                        confidence=0.75,
                        signal=f"User has deposited {distinct} distinct denominations recently — combined value may be uniquely-identifying",
                        recommendation="Stick to one or two pool denominations across a session; avoid multi-denomination combinations.",
                        skill="amount_normalization",
                        action="inform",
                    )
                )
    return alerts


# ---------------------------------------------------------------------------
# H3 — Multi-denomination linkage
# ---------------------------------------------------------------------------

def check_h3_multi_denomination_linkage(tx: MixerWithdrawal, profile: dict) -> list[RiskAlert]:
    h = profile["heuristics"]["H3_multi_denomination_linkage"]
    alerts: list[RiskAlert] = []

    deps = tx.user_recent_deposits_across_pools
    wds = tx.user_recent_withdrawals_across_pools
    if len(deps) < 2:
        return alerts

    # correlated_multi_pool_deposits: multiple pools, short window
    timestamps = [d.get("timestamp", 0) for d in deps]
    if timestamps:
        span = max(timestamps) - min(timestamps)
        if span < 86400 and len({d.get("pool") for d in deps}) >= 2:  # within 24h, multiple pools
            alerts.append(
                RiskAlert(
                    heuristic_id="H3",
                    heuristic_name=h["name"],
                    severity="high",
                    confidence=0.85,
                    signal=f"User deposited across {len({d.get('pool') for d in deps})} pools within {span//3600}h — multi-pool correlation visible",
                    recommendation="Space cross-pool deposits over multiple days; avoid same-day multi-pool patterns.",
                    skill="cross_pool_temporal_spread",
                    action="warn",
                )
            )

    # denomination_sum_fingerprint: deposit-sum matches withdrawal-sum within window
    if deps and wds:
        total_dep = sum(d.get("amount", 0.0) for d in deps)
        total_wd = sum(w.get("amount", 0.0) for w in wds)
        if total_dep > 0 and abs(total_dep - total_wd) / total_dep < 0.05:
            alerts.append(
                RiskAlert(
                    heuristic_id="H3",
                    heuristic_name=h["name"],
                    severity="high",
                    confidence=0.7,
                    signal=f"Deposit total ({total_dep:.4f}) matches withdrawal total ({total_wd:.4f}) within 5% — value fingerprint",
                    recommendation="Maintain a residual balance in the mixer; do not withdraw the exact deposited amount.",
                    skill="value_residual_strategy",
                    action="warn",
                )
            )

    return alerts


# ---------------------------------------------------------------------------
# H4 — Cross-protocol linkage
# ---------------------------------------------------------------------------

def check_h4_cross_protocol_linkage(tx: MixerWithdrawal, profile: dict) -> list[RiskAlert]:
    h = profile["heuristics"]["H4_cross_protocol_linkage"]
    alerts: list[RiskAlert] = []

    # immediate_defi_interaction: planned within 2 blocks
    if tx.expected_post_withdrawal_action in ("defi_swap", "lend", "borrow"):
        if tx.expected_post_withdrawal_delay_blocks <= 2:
            alerts.append(
                RiskAlert(
                    heuristic_id="H4",
                    heuristic_name=h["name"],
                    severity="critical",
                    confidence=0.85,
                    signal=f"Planned {tx.expected_post_withdrawal_action} within {tx.expected_post_withdrawal_delay_blocks} blocks of withdrawal — immediate-defi-interaction fingerprint",
                    recommendation="Wait at least 24h after withdrawal before any DeFi interaction; consider a fresh address for the post-mixer activity.",
                    skill="post_withdrawal_delay",
                    action="warn",
                )
            )

    # behavioral_continuity: known-cluster behavioral match
    if tx.withdrawal_address_known_cluster_match:
        alerts.append(
            RiskAlert(
                heuristic_id="H4",
                heuristic_name=h["name"],
                severity="critical",
                confidence=0.8,
                signal="Withdrawal address's prior pattern matches a known address-cluster's behavioral profile",
                recommendation="Use a fresh withdrawal address with no prior cluster-linkable behavior.",
                skill="address_freshness",
                action="block",
            )
        )

    # bridge_after_mixer: bridge interaction within 1h
    if tx.expected_post_withdrawal_action == "bridge":
        if tx.expected_post_withdrawal_delay_blocks * 12 < 3600:  # <1h assuming 12s blocks
            alerts.append(
                RiskAlert(
                    heuristic_id="H4",
                    heuristic_name=h["name"],
                    severity="high",
                    confidence=0.75,
                    signal=f"Planned bridge within {tx.expected_post_withdrawal_delay_blocks} blocks (~{tx.expected_post_withdrawal_delay_blocks*12//60}min) of withdrawal — cross-chain correlation opportunity",
                    recommendation="Delay bridging by 24h+; consider routing through an additional anonymizing layer before bridging.",
                    skill="post_withdrawal_delay",
                    action="warn",
                )
            )
    return alerts


# ---------------------------------------------------------------------------
# H5 — Mixer-specific metadata
# ---------------------------------------------------------------------------

def check_h5_mixer_specific_metadata(tx: MixerWithdrawal, profile: dict) -> list[RiskAlert]:
    h = profile["heuristics"]["H5_mixer_specific_metadata"]
    alerts: list[RiskAlert] = []

    # relayer_fingerprint: <5% market share
    if tx.selected_relayer and tx.relayer_market_share_pct < 5.0:
        alerts.append(
            RiskAlert(
                heuristic_id="H5",
                heuristic_name=h["name"],
                severity="medium",
                confidence=0.7,
                signal=f"Selected relayer '{tx.selected_relayer}' handles {tx.relayer_market_share_pct:.1f}% of pool withdrawals — narrow anonymity group",
                recommendation="Use a relayer with majority market share, or rotate relayers across mixing operations.",
                skill="relayer_diversification",
                action="inform",
            )
        )

    # withdrawal_address_reuse: same address used for prior mixing operations
    if tx.withdrawal_address_prior_mixer_uses >= 1:
        alerts.append(
            RiskAlert(
                heuristic_id="H5",
                heuristic_name=h["name"],
                severity="high",
                confidence=0.9,
                signal=f"Withdrawal address has been used as destination for {tx.withdrawal_address_prior_mixer_uses} prior mixing operation(s)",
                recommendation="Use a fresh, never-used address as withdrawal destination.",
                skill="address_freshness",
                action="warn",
            )
        )

    # gas_pattern_fingerprint: > 2 stddev from block median
    if tx.block_gas_stddev_gwei > 0:
        z = (tx.withdrawal_tx_gas_price_gwei - tx.block_gas_median_gwei) / tx.block_gas_stddev_gwei
        if abs(z) > 2:
            alerts.append(
                RiskAlert(
                    heuristic_id="H5",
                    heuristic_name=h["name"],
                    severity="medium",
                    confidence=0.65,
                    signal=f"Withdrawal gas price {tx.withdrawal_tx_gas_price_gwei:.2f} gwei is {z:+.1f}σ from block median ({tx.block_gas_median_gwei:.2f} gwei)",
                    recommendation="Use the block median gas price (or relayer-default) to avoid gas-price fingerprinting.",
                    skill="gas_price_normalization",
                    action="inform",
                )
            )
    return alerts


_CHECKS = [
    check_h1_timing_correlation,
    check_h2_amount_fingerprinting,
    check_h3_multi_denomination_linkage,
    check_h4_cross_protocol_linkage,
    check_h5_mixer_specific_metadata,
]


def analyze_withdrawal(tx: MixerWithdrawal, profile: dict) -> AnalysisResult:
    alerts: list[RiskAlert] = []
    for chk in _CHECKS:
        alerts.extend(chk(tx, profile))

    severity_rank = {"low": 1, "medium": 2, "high": 3, "critical": 4}
    overall = "low"
    block = False
    for a in alerts:
        if severity_rank.get(a.severity, 0) > severity_rank.get(overall, 0):
            overall = a.severity
        if a.action == "block":
            block = True

    return AnalysisResult(tx=tx, alerts=alerts, overall_risk=overall, should_block=block)


if __name__ == "__main__":
    profile_path = Path(__file__).parent / "profile.json"
    profile = load_profile(profile_path)

    bad = MixerWithdrawal(
        tx_hash="0xtest1",
        user_address="0xUser",
        withdrawal_address="0xPriorReusedAddr",
        pool_id="tornado-eth-1.0",
        pool_denomination="1.0 ETH",
        deposit_timestamp=1735000000,
        withdrawal_timestamp=1735000000 + 30 * 60,  # 30 min dwell
        pool_deposit_count_in_24h_window=10,
        pool_concurrent_deposits_in_window=12,
        deposit_amount=1.234567,
        is_variable_denom_pool=True,
        pool_amount_distribution=[1.0, 1.0, 1.0, 0.5, 0.5],  # only 0 matches → unique
        user_recent_deposits_across_pools=[
            {"pool": "pool-A", "amount": 1.0, "timestamp": 1734996400},
            {"pool": "pool-B", "amount": 0.5, "timestamp": 1734997000},
            {"pool": "pool-C", "amount": 0.234567, "timestamp": 1734998000},
        ],
        user_recent_withdrawals_across_pools=[
            {"pool": "pool-A", "amount": 1.0, "timestamp": 1735000400},
            {"pool": "pool-B", "amount": 0.5, "timestamp": 1735000600},
            {"pool": "pool-C", "amount": 0.234567, "timestamp": 1735001000},
        ],
        expected_post_withdrawal_action="defi_swap",
        expected_post_withdrawal_delay_blocks=1,
        withdrawal_address_known_cluster_match=True,
        selected_relayer="rare_relayer",
        relayer_market_share_pct=2.5,
        withdrawal_address_prior_mixer_uses=2,
        withdrawal_tx_gas_price_gwei=120.0,
        block_gas_median_gwei=20.0,
        block_gas_stddev_gwei=5.0,
        user_prior_dwell_times_seconds=[1800, 1850, 1820],  # consistent ~30min
    )

    print("=== Worst-case ===")
    res = analyze_withdrawal(bad, profile)
    print(f"overall={res.overall_risk} block={res.should_block} alerts={len(res.alerts)}")
    for a in res.alerts:
        print(f"  [{a.severity}] {a.heuristic_id}: {a.signal[:90]}")

    good = MixerWithdrawal(
        tx_hash="0xtest2",
        user_address="0xUser",
        withdrawal_address="0xFreshAddr",
        pool_id="tornado-eth-1.0",
        pool_denomination="1.0 ETH",
        deposit_timestamp=1735000000,
        withdrawal_timestamp=1735000000 + 7 * 24 * 3600,  # 7-day dwell
        pool_deposit_count_in_24h_window=400,
        pool_concurrent_deposits_in_window=350,
        deposit_amount=1.0,
        is_variable_denom_pool=False,
        expected_post_withdrawal_action=None,
        withdrawal_address_known_cluster_match=False,
        selected_relayer="majority_relayer",
        relayer_market_share_pct=45.0,
        withdrawal_address_prior_mixer_uses=0,
        withdrawal_tx_gas_price_gwei=20.0,
        block_gas_median_gwei=20.0,
        block_gas_stddev_gwei=5.0,
    )
    print("\n=== Healthy ===")
    res = analyze_withdrawal(good, profile)
    print(f"overall={res.overall_risk} block={res.should_block} alerts={len(res.alerts)}")
