"""
e_AI v2 L2 Background Monitor

Continuous monitoring for L2-specific privacy risks.
Not per-action — runs periodically to check pool sizes,
sequencer behavior, and batch linkage.

For L2 access method: l2_anonymity_set, l2_bridge_linkage.

Usage:
    from examples.l2_monitor.guard import L2Monitor

    monitor = L2Monitor(rpc_url="https://arb1.arbitrum.io/rpc")
    monitor.check_anonymity_set(pool_address="0x...", user_amount=1.0)
    monitor.check_sequencer_centralization()
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Alert:
    profile: str
    heuristic: str
    severity: str
    confidence: float
    signal: str
    recommendation: str


@dataclass
class MonitorResult:
    timestamp: int
    chain: str
    alerts: list[Alert] = field(default_factory=list)
    pool_size: Optional[int] = None
    sequencer_info: Optional[dict] = None


class L2Monitor:
    """Monitors L2 privacy conditions."""

    def __init__(self, chain: str = "arbitrum", rpc_url: str = ""):
        self.chain = chain
        self.rpc_url = rpc_url
        self.history: list[MonitorResult] = []

    def check_anonymity_set(
        self,
        pool_deposits_24h: int,
        user_amount_bucket: str = "1.0 ETH",
        matching_deposits: int = 0,
    ) -> MonitorResult:
        """Check if the L2 privacy pool has sufficient anonymity set.

        Args:
            pool_deposits_24h: Total deposits in last 24h
            user_amount_bucket: User's amount range
            matching_deposits: Deposits matching user's amount in 24h
        """
        result = MonitorResult(
            timestamp=int(time.time()),
            chain=self.chain,
            pool_size=pool_deposits_24h,
        )

        # H1: Thin pool
        if pool_deposits_24h < 20:
            result.alerts.append(Alert(
                profile="l2_anonymity_set",
                heuristic="H1",
                severity="critical",
                confidence=0.9,
                signal=f"Only {pool_deposits_24h} deposits on {self.chain} in 24h — anonymity set dangerously small",
                recommendation=f"Wait for more activity, or use L1 where the pool has more users",
            ))

        if matching_deposits < 5:
            result.alerts.append(Alert(
                profile="l2_anonymity_set",
                heuristic="H1",
                severity="high",
                confidence=0.85,
                signal=f"Only {matching_deposits} deposits matching {user_amount_bucket} in 24h on {self.chain}",
                recommendation="Adjust amount to match a more popular bucket, or wait for more matching deposits",
            ))

        # H4: L2-specific timing
        block_times = {"arbitrum": 0.25, "optimism": 2.0, "base": 2.0, "ethereum": 12.0}
        bt = block_times.get(self.chain, 2.0)
        if bt < 3.0:
            result.alerts.append(Alert(
                profile="l2_anonymity_set",
                heuristic="H4",
                severity="medium",
                confidence=0.7,
                signal=f"{self.chain} block time is {bt}s — timing correlation is {12.0/bt:.0f}x tighter than L1",
                recommendation=f"Increase delay between deposit and spend proportionally ({int(6 * 12.0/bt)}-{int(24 * 12.0/bt)}h equivalent L1 delay)",
            ))

        self.history.append(result)
        return result

    def check_sequencer_centralization(
        self,
        sequencer_operator: str = "unknown",
        is_centralized: bool = True,
        forced_inclusion_available: bool = True,
    ) -> MonitorResult:
        """Check sequencer centralization risk."""
        result = MonitorResult(
            timestamp=int(time.time()),
            chain=self.chain,
            sequencer_info={"operator": sequencer_operator, "centralized": is_centralized},
        )

        # H2: Sequencer visibility
        if is_centralized:
            result.alerts.append(Alert(
                profile="l2_anonymity_set",
                heuristic="H2",
                severity="critical",
                confidence=0.95,
                signal=f"{self.chain} sequencer ({sequencer_operator}) sees all transactions before batch posting",
                recommendation="Sequencer knows your transaction before it's public. Consider using private submission or L1 for sensitive transactions.",
            ))

        # H3: Forced inclusion
        if forced_inclusion_available:
            result.alerts.append(Alert(
                profile="l2_anonymity_set",
                heuristic="H3",
                severity="high",
                confidence=0.8,
                signal="Forced inclusion via L1 reveals your L2 transaction to L1 observers",
                recommendation="Only use forced inclusion if sequencer is censoring. Otherwise submit normally.",
            ))

        self.history.append(result)
        return result

    def daily_report(self) -> str:
        """Generate daily L2 privacy report."""
        if not self.history:
            return f"No monitoring data for {self.chain}."

        total_alerts = sum(len(r.alerts) for r in self.history)
        critical = sum(1 for r in self.history for a in r.alerts if a.severity == "critical")
        pool_sizes = [r.pool_size for r in self.history if r.pool_size is not None]
        avg_pool = sum(pool_sizes) / len(pool_sizes) if pool_sizes else 0

        return (
            f"L2 Monitor Daily Report — {self.chain}\n"
            f"  Checks: {len(self.history)}\n"
            f"  Alerts: {total_alerts} ({critical} critical)\n"
            f"  Avg pool size: {avg_pool:.0f} deposits/24h\n"
        )


# --- Demo ---

def demo():
    print("=" * 60)
    print("e_AI v2 L2 Background Monitor Demo")
    print("=" * 60)

    # Arbitrum monitor
    arb = L2Monitor(chain="arbitrum")

    print("\n--- Check 1: Thin pool on Arbitrum ---")
    result = arb.check_anonymity_set(
        pool_deposits_24h=8,
        user_amount_bucket="1.0 ETH",
        matching_deposits=2,
    )
    for a in result.alerts:
        print(f"  [{a.heuristic}] {a.severity}: {a.signal}")
        print(f"    → {a.recommendation}")

    print("\n--- Check 2: Sequencer centralization ---")
    result = arb.check_sequencer_centralization(
        sequencer_operator="Offchain Labs",
        is_centralized=True,
    )
    for a in result.alerts:
        print(f"  [{a.heuristic}] {a.severity}: {a.signal}")
        print(f"    → {a.recommendation}")

    # Optimism for comparison
    op = L2Monitor(chain="optimism")
    print("\n--- Check 3: Optimism pool ---")
    result = op.check_anonymity_set(
        pool_deposits_24h=45,
        user_amount_bucket="1.0 ETH",
        matching_deposits=12,
    )
    for a in result.alerts:
        print(f"  [{a.heuristic}] {a.severity}: {a.signal}")
        print(f"    → {a.recommendation}")

    if not result.alerts:
        print("  ✅ No alerts — pool size sufficient")

    # Reports
    print(f"\n{arb.daily_report()}")
    print(op.daily_report())


if __name__ == "__main__":
    demo()
