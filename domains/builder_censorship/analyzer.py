"""
Builder/Relay Censorship Analyzer — profile-based pre-submission CR risk.

Loads builder_censorship/profile.json and evaluates a transaction's submission
path against 5 heuristics (H1-H5) covering censoring relays, OFAC interaction,
L2 forced-inclusion availability, builder monoculture, and the compound
no-circumvention case.

This is a DEMO / preliminary implementation. Production version would:
- Pull current censoring-relay registry from a maintained source
- Pull live OFAC SDN address list (with cache)
- Read live builder share via mevboost.org / relayscan.io API
- Read L2 forced-inclusion status from a tracked registry

Usage:
    python analyzer.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


CENSORING_RELAYS = {
    "bloxroute_regulated",
    "bloxroute-regulated",
    "manifold",
    "eden_compliance",
}

NON_CENSORING_RELAYS = {
    "flashbots",
    "ultrasound",
    "agnostic-relay",
    "agnostic",
    "aestus",
}

L2_FORCED_INCLUSION_AVAILABLE = {
    "ethereum": True,
    "arbitrum": True,
    "optimism": True,
    "base": True,
    "scroll": True,
    "linea": False,
    "zksync": True,
}


@dataclass
class BuilderCensorshipTx:
    """A transaction whose submission path is being audited."""
    tx_hash: str
    user_address: str
    to_address: str
    selected_relays: list[str] = field(default_factory=list)
    has_private_mempool_configured: bool = False
    destination_chain: str = "ethereum"
    interacts_with_sanctioned_addresses: list[str] = field(default_factory=list)
    recent_block_builder_count: int = 20  # unique builders in last 100 blocks
    dominant_builder_share: float = 0.20  # fraction by top builder
    wallet_exposes_l1_inbox_path: bool = False
    mev_boost_enabled: bool = True


@dataclass
class RiskAlert:
    heuristic_id: str
    heuristic_name: str
    severity: str
    confidence: float
    signal: str
    recommendation: str
    skill: Optional[str] = None
    action: Optional[str] = None  # block | warn | inform


@dataclass
class AnalysisResult:
    tx: BuilderCensorshipTx
    alerts: list[RiskAlert] = field(default_factory=list)
    overall_risk: str = "low"
    should_block: bool = False


def load_profile(path: str | Path) -> dict:
    with open(path) as f:
        return json.load(f)


def _is_censoring(relay: str) -> bool:
    return relay.lower() in CENSORING_RELAYS


def check_h1_censoring_relay_route(tx: BuilderCensorshipTx, profile: dict) -> list[RiskAlert]:
    if not tx.selected_relays:
        return []

    censoring = [r for r in tx.selected_relays if _is_censoring(r)]
    if not censoring:
        return []

    h = profile["heuristics"]["H1_censoring_relay_route"]
    all_censoring = len(censoring) == len(tx.selected_relays)

    if all_censoring:
        return [
            RiskAlert(
                heuristic_id="H1",
                heuristic_name=h["name"],
                severity="high",
                confidence=0.98,
                signal=f"All {len(tx.selected_relays)} selected relays are censoring: {', '.join(tx.selected_relays)}",
                recommendation="Add at least one non-censoring relay (Flashbots, Ultrasound, Agnostic) to wallet config.",
                skill="relay_diversity_audit",
                action="warn",
            )
        ]

    return [
        RiskAlert(
            heuristic_id="H1",
            heuristic_name=h["name"],
            severity="medium",
            confidence=0.95,
            signal=f"{len(censoring)} of {len(tx.selected_relays)} selected relays are censoring: {', '.join(censoring)}",
            recommendation="Verify the non-censoring relays in your set are reachable; consider removing censoring relays.",
            skill="relay_diversity_audit",
            action="inform",
        )
    ]


def check_h2_sanctioned_address(tx: BuilderCensorshipTx, profile: dict) -> list[RiskAlert]:
    if not tx.interacts_with_sanctioned_addresses:
        return []

    h = profile["heuristics"]["H2_sanctioned_address_interaction"]
    addrs = ", ".join(tx.interacts_with_sanctioned_addresses[:3])
    return [
        RiskAlert(
            heuristic_id="H2",
            heuristic_name=h["name"],
            severity="critical",
            confidence=0.95,
            signal=f"Transaction interacts with OFAC SDN address(es): {addrs}",
            recommendation="Route through non-censoring relay or private mempool. Review jurisdictional exposure separately.",
            skill="private_mempool_routing",
            action="warn",
        )
    ]


def check_h3_no_forced_inclusion(tx: BuilderCensorshipTx, profile: dict) -> list[RiskAlert]:
    chain = tx.destination_chain.lower()
    if chain == "ethereum":
        return []

    h = profile["heuristics"]["H3_l2_centralized_sequencer_no_forced_inclusion"]
    has_path = L2_FORCED_INCLUSION_AVAILABLE.get(chain, False)

    if not has_path:
        return [
            RiskAlert(
                heuristic_id="H3",
                heuristic_name=h["name"],
                severity="high",
                confidence=0.85,
                signal=f"Destination L2 '{chain}' has no production forced-inclusion path; sole inclusion path is the centralized sequencer.",
                recommendation="For sensitive transactions, prefer L2s with active forced-inclusion (Arbitrum, Optimism, Base, Scroll) until {chain} ships sequencer decentralization.",
                skill="l1_inbox_submission",
                action="warn",
            )
        ]

    if not tx.wallet_exposes_l1_inbox_path:
        return [
            RiskAlert(
                heuristic_id="H3",
                heuristic_name=h["name"],
                severity="medium",
                confidence=0.80,
                signal=f"L2 '{chain}' supports forced-inclusion but the wallet does not expose the L1-inbox path.",
                recommendation="Ensure wallet/UI surfaces the L1-inbox forced-inclusion path so the user has an escape hatch if censored.",
                skill="l1_inbox_submission",
                action="inform",
            )
        ]
    return []


def check_h4_builder_monoculture(tx: BuilderCensorshipTx, profile: dict) -> list[RiskAlert]:
    h = profile["heuristics"]["H4_builder_monoculture"]
    alerts: list[RiskAlert] = []

    if tx.recent_block_builder_count < 10:
        alerts.append(
            RiskAlert(
                heuristic_id="H4",
                heuristic_name=h["name"],
                severity="medium",
                confidence=0.75,
                signal=f"Only {tx.recent_block_builder_count} unique builders in recent 100 blocks (<10 threshold)",
                recommendation="For non-urgent txs, wait for builder set to broaden; subscribe to a builder-diversity dashboard.",
                skill="builder_diversity_dashboard",
                action="inform",
            )
        )

    if tx.dominant_builder_share > 0.40:
        alerts.append(
            RiskAlert(
                heuristic_id="H4",
                heuristic_name=h["name"],
                severity="medium",
                confidence=0.80,
                signal=f"Top builder produced {tx.dominant_builder_share:.0%} of recent blocks (>40% threshold)",
                recommendation="Watch builder share; censorship surface is concentrated at the dominant builder's policy.",
                skill="builder_diversity_dashboard",
                action="inform",
            )
        )

    return alerts


def check_h5_compound_no_path(tx: BuilderCensorshipTx, profile: dict) -> list[RiskAlert]:
    h = profile["heuristics"]["H5_no_circumvention_path"]

    all_relays_censoring = (
        bool(tx.selected_relays)
        and all(_is_censoring(r) for r in tx.selected_relays)
    )
    has_sanctioned = bool(tx.interacts_with_sanctioned_addresses)
    no_l2_remedy = (
        tx.destination_chain.lower() != "ethereum"
        and not L2_FORCED_INCLUSION_AVAILABLE.get(tx.destination_chain.lower(), False)
    )

    if all_relays_censoring and not tx.has_private_mempool_configured and (
        has_sanctioned or no_l2_remedy
    ):
        return [
            RiskAlert(
                heuristic_id="H5",
                heuristic_name=h["name"],
                severity="critical",
                confidence=0.95,
                signal="No available submission path will include this transaction: all relays censoring, no private mempool, and either sanctioned-address interaction or no L2 forced-inclusion remedy.",
                recommendation="STOP. Reconfigure relays or enable private mempool before submitting. Otherwise the transaction will silently fail.",
                skill="relay_diversity_audit",
                action="block",
            )
        ]
    return []


_CHECKS = [
    check_h1_censoring_relay_route,
    check_h2_sanctioned_address,
    check_h3_no_forced_inclusion,
    check_h4_builder_monoculture,
    check_h5_compound_no_path,
]


def analyze_transaction(tx: BuilderCensorshipTx, profile: dict) -> AnalysisResult:
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


# ---------------------------------------------------------------------------
# Local self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    profile_path = Path(__file__).parent / "profile.json"
    profile = load_profile(profile_path)

    # Worst-case scenario: all relays censoring, sanctioned address, no L2 remedy
    bad = BuilderCensorshipTx(
        tx_hash="0xtest1",
        user_address="0xUser",
        to_address="0xSanctionedRouter",
        selected_relays=["bloxroute_regulated", "manifold"],
        has_private_mempool_configured=False,
        destination_chain="ethereum",
        interacts_with_sanctioned_addresses=["0xSanctionedRouter"],
        recent_block_builder_count=6,
        dominant_builder_share=0.55,
        wallet_exposes_l1_inbox_path=False,
    )
    print("=== Worst-case ===")
    res = analyze_transaction(bad, profile)
    print(f"overall={res.overall_risk} block={res.should_block} alerts={len(res.alerts)}")
    for a in res.alerts:
        print(f"  [{a.severity}] {a.heuristic_id}: {a.signal[:80]}")

    # Healthy scenario: diverse relays, clean tx
    good = BuilderCensorshipTx(
        tx_hash="0xtest2",
        user_address="0xUser",
        to_address="0xCleanContract",
        selected_relays=["flashbots", "ultrasound", "agnostic"],
        has_private_mempool_configured=True,
        destination_chain="ethereum",
        interacts_with_sanctioned_addresses=[],
        recent_block_builder_count=22,
        dominant_builder_share=0.25,
    )
    print("\n=== Healthy ===")
    res = analyze_transaction(good, profile)
    print(f"overall={res.overall_risk} block={res.should_block} alerts={len(res.alerts)}")
