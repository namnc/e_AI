"""
Stealth Address Ops Analyzer — demonstrates profile-based transaction risk analysis.

Loads stealth_address_ops.json profile and evaluates transactions against the
6 deanonymization heuristics from arxiv 2308.01703.

This is a DEMO / preliminary implementation. Production version would:
- Integrate with LLM for natural language recommendations
- Read real on-chain data via RPC
- Execute skills (paymaster, timing delay, etc.)
- Track user history for behavioral pattern detection

Usage:
    python analyzer.py                     # run example scenarios
    python analyzer.py --benchmark         # run full benchmark simulation
"""

from __future__ import annotations

import json
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class SteathTx:
    """A stealth address transaction to analyze."""
    deposit_address: str
    withdrawal_address: str
    stealth_address: str
    amount_eth: float
    deposit_timestamp: int      # unix seconds
    spend_timestamp: int        # unix seconds
    gas_price_gwei: float
    gas_funding_source: str     # "paymaster" | "self" | "relay" | address
    is_self_send: bool = False
    address_cluster: set[str] = field(default_factory=set)


@dataclass
class RiskAlert:
    """A risk flagged by the analyzer."""
    heuristic_id: str
    heuristic_name: str
    severity: str
    confidence: float
    signal: str
    recommendation: str
    skill: Optional[str] = None


@dataclass
class AnalysisResult:
    """Complete analysis of a transaction."""
    tx: SteathTx
    alerts: list[RiskAlert] = field(default_factory=list)
    overall_risk: str = "low"  # low | medium | high | critical
    deanonymized: bool = False


# ---------------------------------------------------------------------------
# Profile loader
# ---------------------------------------------------------------------------

def load_profile(path: str | Path) -> dict:
    """Load a domain profile JSON."""
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Heuristic checks
# ---------------------------------------------------------------------------

def check_h1_same_entity(tx: SteathTx, profile: dict) -> list[RiskAlert]:
    """H1: Same-entity withdrawal — sender and receiver in same cluster."""
    alerts = []
    h = profile["heuristics"]["H1_same_entity_withdrawal"]

    if tx.withdrawal_address in tx.address_cluster:
        alerts.append(RiskAlert(
            heuristic_id="H1",
            heuristic_name=h["name"],
            severity=h["severity"],
            confidence=0.95,
            signal="Withdrawal address is in sender's address cluster",
            recommendation=h["recommendations"][0]["description"],
        ))
    return alerts


def check_h2_gas_fingerprint(
    tx: SteathTx,
    profile: dict,
    block_median_gas: float = 30.0,
    block_std_gas: float = 5.0,
) -> list[RiskAlert]:
    """H2: Gas price fingerprinting."""
    alerts = []
    h = profile["heuristics"]["H2_gas_price_fingerprinting"]

    z_score = abs(tx.gas_price_gwei - block_median_gas) / max(block_std_gas, 0.1)
    if z_score > 2.0:
        alerts.append(RiskAlert(
            heuristic_id="H2",
            heuristic_name=h["name"],
            severity=h["severity"],
            confidence=min(0.5 + z_score * 0.1, 0.95),
            signal=f"Gas price {tx.gas_price_gwei:.1f} gwei is {z_score:.1f} std devs from block median ({block_median_gas:.1f})",
            recommendation=h["recommendations"][0]["description"],
            skill="gas_randomizer",
        ))
    return alerts


def check_h3_timing(tx: SteathTx, profile: dict) -> list[RiskAlert]:
    """H3: Timing correlation — short dwell time between deposit and spend."""
    alerts = []
    h = profile["heuristics"]["H3_timing_correlation"]

    dwell_hours = (tx.spend_timestamp - tx.deposit_timestamp) / 3600
    if dwell_hours < 1:
        alerts.append(RiskAlert(
            heuristic_id="H3",
            heuristic_name=h["name"],
            severity="critical",
            confidence=0.90,
            signal=f"Spend occurred {dwell_hours:.1f}h after deposit (< 1h threshold)",
            recommendation=h["recommendations"][0]["description"],
            skill="timing_delay",
        ))
    elif dwell_hours < 6:
        alerts.append(RiskAlert(
            heuristic_id="H3",
            heuristic_name=h["name"],
            severity="high",
            confidence=0.60,
            signal=f"Spend occurred {dwell_hours:.1f}h after deposit (< 6h threshold)",
            recommendation=h["recommendations"][0]["description"],
            skill="timing_delay",
        ))
    return alerts


def check_h4_funding(tx: SteathTx, profile: dict) -> list[RiskAlert]:
    """H4: Funding linkability — stealth address gas funded from known address."""
    alerts = []
    h = profile["heuristics"]["H4_funding_linkability"]

    if tx.gas_funding_source not in ("paymaster", "relay"):
        confidence = 0.95 if tx.gas_funding_source != "fresh" else 0.30
        alerts.append(RiskAlert(
            heuristic_id="H4",
            heuristic_name=h["name"],
            severity=h["severity"],
            confidence=confidence,
            signal=f"Stealth address gas funded from {tx.gas_funding_source}",
            recommendation=h["recommendations"][0]["description"],
            skill="paymaster",
        ))
    return alerts


def check_h5_self_send(tx: SteathTx, profile: dict) -> list[RiskAlert]:
    """H5: Self-transfer detection."""
    alerts = []
    h = profile["heuristics"]["H5_self_transfer"]

    if tx.is_self_send:
        alerts.append(RiskAlert(
            heuristic_id="H5",
            heuristic_name=h["name"],
            severity="critical",
            confidence=1.0,
            signal="Self-transfer detected: sender is the stealth address owner",
            recommendation=h["recommendations"][0]["description"],
        ))
    return alerts


def check_h6_unique_amount(
    tx: SteathTx,
    profile: dict,
    deposit_pool_amounts: list[float] | None = None,
) -> list[RiskAlert]:
    """H6: Unique amounts — non-standard amounts narrow anonymity set."""
    alerts = []
    h = profile["heuristics"]["H6_unique_amounts"]

    # Check if amount is a round denomination
    standard_denoms = profile["skills"]["amount_normalizer"]["parameters"]["denominations_eth"]
    is_round = tx.amount_eth in standard_denoms

    if not is_round:
        # Check pool uniqueness if pool data available
        if deposit_pool_amounts:
            matches = sum(1 for a in deposit_pool_amounts if abs(a - tx.amount_eth) < 0.001)
            if matches <= 1:
                confidence = 0.95
                signal = f"Amount {tx.amount_eth} ETH is unique in deposit pool (no other matching deposits)"
            elif matches < 5:
                confidence = 0.70
                signal = f"Amount {tx.amount_eth} ETH has only {matches} matches in deposit pool"
            else:
                return alerts  # enough cover
        else:
            confidence = 0.50
            signal = f"Amount {tx.amount_eth} ETH is not a standard denomination"

        nearest = min(standard_denoms, key=lambda d: abs(d - tx.amount_eth))
        alerts.append(RiskAlert(
            heuristic_id="H6",
            heuristic_name=h["name"],
            severity=h["severity"],
            confidence=confidence,
            signal=signal,
            recommendation=f"Round to {nearest} ETH ({h['recommendations'][0]['description']})",
            skill="amount_normalizer",
        ))
    return alerts


# ---------------------------------------------------------------------------
# Main analyzer
# ---------------------------------------------------------------------------

def analyze_transaction(
    tx: SteathTx,
    profile: dict,
    deposit_pool_amounts: list[float] | None = None,
    block_median_gas: float = 30.0,
    block_std_gas: float = 5.0,
) -> AnalysisResult:
    """Run all 6 heuristic checks against a transaction."""
    result = AnalysisResult(tx=tx)

    checks = [
        check_h1_same_entity(tx, profile),
        check_h2_gas_fingerprint(tx, profile, block_median_gas, block_std_gas),
        check_h3_timing(tx, profile),
        check_h4_funding(tx, profile),
        check_h5_self_send(tx, profile),
        check_h6_unique_amount(tx, profile, deposit_pool_amounts),
    ]

    for alerts in checks:
        result.alerts.extend(alerts)

    # Determine overall risk level
    if any(a.severity == "critical" and a.confidence > 0.8 for a in result.alerts):
        result.overall_risk = "critical"
        result.deanonymized = True
    elif any(a.severity == "critical" for a in result.alerts):
        result.overall_risk = "high"
    elif any(a.severity == "high" for a in result.alerts):
        result.overall_risk = "medium"
    elif result.alerts:
        result.overall_risk = "low"

    return result


def format_result(result: AnalysisResult) -> str:
    """Format analysis result for display."""
    lines = [
        f"--- Risk Assessment: {result.overall_risk.upper()} ---",
        f"Amount: {result.tx.amount_eth} ETH",
        f"Dwell time: {(result.tx.spend_timestamp - result.tx.deposit_timestamp)/3600:.1f}h",
        f"Gas funding: {result.tx.gas_funding_source}",
        f"Alerts: {len(result.alerts)}",
    ]
    if result.deanonymized:
        lines.append("*** LIKELY DEANONYMIZED ***")

    for alert in result.alerts:
        lines.append(f"\n  [{alert.heuristic_id}] {alert.heuristic_name} (confidence: {alert.confidence:.0%})")
        lines.append(f"    Signal: {alert.signal}")
        lines.append(f"    Action: {alert.recommendation}")
        if alert.skill:
            lines.append(f"    Skill: {alert.skill}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Benchmark simulation
# ---------------------------------------------------------------------------

def generate_synthetic_dataset(n: int = 100, seed: int = 42) -> list[SteathTx]:
    """Generate synthetic stealth address transactions for benchmarking.

    Distribution modeled after Umbra usage patterns (approximate):
    - 30% use same-cluster withdrawal addresses
    - 60% spend within 6 hours
    - 70% fund gas from known address
    - 5% self-sends
    - 40% use non-standard amounts
    """
    rng = random.Random(seed)
    txs = []

    for i in range(n):
        deposit_addr = f"0x{'d' * 38}{i:02x}"
        is_same_cluster = rng.random() < 0.30
        withdrawal_addr = f"0x{'w' * 38}{i:02x}"
        stealth_addr = f"0x{'s' * 38}{i:02x}"

        cluster = {deposit_addr}
        if is_same_cluster:
            cluster.add(withdrawal_addr)

        # Timing: 60% within 6h, 25% within 1h
        dwell_draw = rng.random()
        if dwell_draw < 0.25:
            dwell_secs = rng.randint(60, 3600)
        elif dwell_draw < 0.60:
            dwell_secs = rng.randint(3600, 21600)
        else:
            dwell_secs = rng.randint(21600, 172800)

        deposit_ts = 1700000000 + rng.randint(0, 86400 * 30)
        spend_ts = deposit_ts + dwell_secs

        # Amount: 40% non-standard
        standard_amounts = [0.1, 0.5, 1.0, 5.0, 10.0]
        if rng.random() < 0.40:
            amount = round(rng.uniform(0.01, 50.0), rng.randint(2, 6))
        else:
            amount = rng.choice(standard_amounts)

        # Gas funding: 70% from known address
        funding_draw = rng.random()
        if funding_draw < 0.15:
            gas_source = "paymaster"
        elif funding_draw < 0.30:
            gas_source = "relay"
        else:
            gas_source = f"0x{'f' * 38}{i:02x}"

        # Gas price: 80% normal, 20% outlier
        if rng.random() < 0.80:
            gas_price = rng.gauss(30.0, 3.0)
        else:
            gas_price = rng.gauss(30.0, 15.0)

        is_self = rng.random() < 0.05

        txs.append(SteathTx(
            deposit_address=deposit_addr,
            withdrawal_address=withdrawal_addr,
            stealth_address=stealth_addr,
            amount_eth=amount,
            deposit_timestamp=deposit_ts,
            spend_timestamp=spend_ts,
            gas_price_gwei=max(1.0, gas_price),
            gas_funding_source=gas_source,
            is_self_send=is_self,
            address_cluster=cluster,
        ))

    return txs


def run_benchmark(profile: dict, n: int = 1000) -> dict:
    """Run benchmark: measure deanonymization rate before/after recommendations."""
    txs = generate_synthetic_dataset(n)
    all_amounts = [tx.amount_eth for tx in txs]

    # Analyze all transactions
    results = [analyze_transaction(tx, profile, all_amounts) for tx in txs]

    # Count deanonymized
    deanon_count = sum(1 for r in results if r.deanonymized)
    deanon_rate = deanon_count / len(results)

    # Per-heuristic breakdown
    heuristic_counts: dict[str, int] = {}
    for r in results:
        for a in r.alerts:
            heuristic_counts[a.heuristic_id] = heuristic_counts.get(a.heuristic_id, 0) + 1

    # Simulate "after recommendations" (apply all mitigations)
    mitigated_txs = []
    for tx in txs:
        mtx = SteathTx(
            deposit_address=tx.deposit_address,
            withdrawal_address=tx.withdrawal_address,
            stealth_address=tx.stealth_address,
            amount_eth=min(
                profile["skills"]["amount_normalizer"]["parameters"]["denominations_eth"],
                key=lambda d: abs(d - tx.amount_eth),
            ),
            deposit_timestamp=tx.deposit_timestamp,
            spend_timestamp=tx.deposit_timestamp + random.randint(21600, 86400),  # 6-24h delay
            gas_price_gwei=random.gauss(30.0, 3.0),  # randomized
            gas_funding_source="paymaster",  # always paymaster
            is_self_send=False,  # blocked
            address_cluster=set(),  # fresh address, no cluster
        )
        mitigated_txs.append(mtx)

    mitigated_results = [analyze_transaction(tx, profile, all_amounts) for tx in mitigated_txs]
    mitigated_deanon = sum(1 for r in mitigated_results if r.deanonymized)
    mitigated_rate = mitigated_deanon / len(mitigated_results)

    return {
        "n_transactions": n,
        "baseline": {
            "deanonymized": deanon_count,
            "deanon_rate": f"{deanon_rate:.1%}",
            "per_heuristic": heuristic_counts,
        },
        "mitigated": {
            "deanonymized": mitigated_deanon,
            "deanon_rate": f"{mitigated_rate:.1%}",
        },
        "improvement": f"{deanon_rate:.1%} -> {mitigated_rate:.1%}",
    }


# ---------------------------------------------------------------------------
# Example scenarios
# ---------------------------------------------------------------------------

def run_examples(profile: dict):
    """Run illustrative example scenarios."""
    examples = [
        ("Good practice: paymaster + delayed + round amount", SteathTx(
            deposit_address="0xaaaa",
            withdrawal_address="0xbbbb",
            stealth_address="0xcccc",
            amount_eth=1.0,
            deposit_timestamp=1700000000,
            spend_timestamp=1700000000 + 43200,  # 12h later
            gas_price_gwei=30.5,
            gas_funding_source="paymaster",
            address_cluster={"0xaaaa"},
        )),
        ("Bad practice: immediate spend, unique amount, self-funded gas", SteathTx(
            deposit_address="0xaaaa",
            withdrawal_address="0xbbbb",
            stealth_address="0xcccc",
            amount_eth=3.847,
            deposit_timestamp=1700000000,
            spend_timestamp=1700000000 + 600,  # 10 min later
            gas_price_gwei=45.0,
            gas_funding_source="0xaaaa",
            address_cluster={"0xaaaa"},
        )),
        ("Self-send (worst case)", SteathTx(
            deposit_address="0xaaaa",
            withdrawal_address="0xaaaa",
            stealth_address="0xcccc",
            amount_eth=5.0,
            deposit_timestamp=1700000000,
            spend_timestamp=1700000000 + 7200,
            gas_price_gwei=30.0,
            gas_funding_source="paymaster",
            is_self_send=True,
            address_cluster={"0xaaaa"},
        )),
        ("Cluster linkage: withdrawal address in sender's cluster", SteathTx(
            deposit_address="0xaaaa",
            withdrawal_address="0xbbbb",
            stealth_address="0xcccc",
            amount_eth=10.0,
            deposit_timestamp=1700000000,
            spend_timestamp=1700000000 + 86400,  # 24h
            gas_price_gwei=29.0,
            gas_funding_source="paymaster",
            address_cluster={"0xaaaa", "0xbbbb", "0xdddd"},
        )),
    ]

    for name, tx in examples:
        print(f"\n{'='*60}")
        print(f"Scenario: {name}")
        print(f"{'='*60}")
        result = analyze_transaction(tx, profile)
        print(format_result(result))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    profile_path = Path(__file__).parent.parent / "profiles" / "stealth_address_ops.json"
    profile = load_profile(profile_path)

    if "--benchmark" in sys.argv:
        print("Running benchmark simulation (1000 synthetic transactions)...")
        results = run_benchmark(profile)
        print(json.dumps(results, indent=2))
    else:
        print(f"Stealth Address Ops Analyzer v{profile['meta']['version']}")
        print(f"Profile: {profile['meta']['domain_name']}")
        print(f"Source: {profile['meta']['source_paper']}")
        print(f"Baseline deanon rate: {profile['meta']['baseline_deanon_rate']:.1%}")
        print(f"Target: <{profile['meta']['target_deanon_rate']:.0%}")
        run_examples(profile)


if __name__ == "__main__":
    main()
