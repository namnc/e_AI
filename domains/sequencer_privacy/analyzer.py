"""
Sequencer Privacy Analyzer — profile-based L2 sequencer trust analysis.

Loads sequencer_privacy/profile.json and evaluates an L2 transaction
submission scenario against 5 heuristics (H1-H5): centralized sequencer,
sequencer censorship, sequencer MEV extraction, shared-sequencer linkage,
pre-confirmation privacy leak.

This guard is largely informational today: the actionable mitigation is
mostly "wait for encrypted-mempool / decentralized-sequencer rollouts".
The analyzer surfaces the trust posture so users can make informed
routing decisions, not block transactions.

Production deployment must wire SEQUENCER_REGISTRY against L2Beat's
live data and per-L2 governance disclosures.

Usage:
    python analyzer.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# Per-L2 sequencer trust posture. Conservative as of 2026; production must
# reconcile against L2Beat's stage / sequencer-status table on a cadence.
SEQUENCER_REGISTRY: dict[str, dict] = {
    "ethereum": {
        "operator": "ethereum_validator_set",
        "model": "decentralized",
        "encrypted_mempool_shipped": False,
        "shared_sequencer": False,
        "force_inclusion_path": True,
        "fair_ordering": False,
    },
    "arbitrum": {
        "operator": "Offchain Labs",
        "model": "centralized",
        "encrypted_mempool_shipped": False,
        "shared_sequencer": False,
        "force_inclusion_path": True,
        "fair_ordering": False,
    },
    "optimism": {
        "operator": "OP Labs",
        "model": "centralized",
        "encrypted_mempool_shipped": False,
        "shared_sequencer": False,
        "force_inclusion_path": True,
        "fair_ordering": False,
    },
    "base": {
        "operator": "Coinbase",
        "model": "centralized",
        "encrypted_mempool_shipped": False,
        "shared_sequencer": False,
        "force_inclusion_path": True,
        "fair_ordering": False,
    },
    "zksync": {
        "operator": "Matter Labs",
        "model": "centralized",
        "encrypted_mempool_shipped": False,
        "shared_sequencer": False,
        "force_inclusion_path": True,
        "fair_ordering": False,
    },
    "scroll": {
        "operator": "Scroll Foundation",
        "model": "centralized",
        "encrypted_mempool_shipped": False,
        "shared_sequencer": False,
        "force_inclusion_path": True,
        "fair_ordering": False,
    },
    "linea": {
        "operator": "ConsenSys",
        "model": "centralized",
        "encrypted_mempool_shipped": False,
        "shared_sequencer": False,
        "force_inclusion_path": False,
        "fair_ordering": False,
    },
    "starknet": {
        "operator": "StarkWare",
        "model": "centralized",
        "encrypted_mempool_shipped": False,
        "shared_sequencer": False,
        "force_inclusion_path": False,
        "fair_ordering": False,
    },
    "espresso": {
        "operator": "Espresso Systems",
        "model": "shared_sequencer",
        "encrypted_mempool_shipped": False,
        "shared_sequencer": True,
        "force_inclusion_path": True,
        "fair_ordering": True,
    },
    "astria": {
        "operator": "Astria",
        "model": "shared_sequencer",
        "encrypted_mempool_shipped": False,
        "shared_sequencer": True,
        "force_inclusion_path": True,
        "fair_ordering": True,
    },
}


@dataclass
class SequencerSubmission:
    """An L2 transaction submission scenario being analyzed."""
    user_address: str
    l2_chain: str
    submitted_tx_id: str = ""
    tx_value_usd: float = 0.0
    tx_kind: str = "transfer"  # transfer | swap | privacy_pool_deposit | bridge | other
    is_high_value: bool = False
    is_privacy_relevant: bool = False

    # Per-submission overrides (optional; falls back to registry)
    sequencer_model_override: Optional[str] = None
    sequencer_operator_override: Optional[str] = None

    # Censorship observation
    tx_submitted_at: int = 0
    expected_inclusion_by: int = 0
    actually_included: bool = True
    valid_gas_and_nonce: bool = True
    user_flagged_as_sanctioned: bool = False
    consecutive_exclusions: int = 0

    # MEV
    sequencer_mev_extracted_usd_30d: float = 0.0
    sequencer_share_of_l2_mev_pct: float = 0.0  # 0.0 - 1.0

    # Shared sequencer
    shared_sequencer_other_rollups: list[str] = field(default_factory=list)

    # Preconfirmation
    preconfirmation_published_before_batch: bool = False
    preconfirmation_window_seconds: int = 0
    preconfirmation_publicly_readable: bool = True


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
    submission: SequencerSubmission
    alerts: list[RiskAlert] = field(default_factory=list)
    overall_risk: str = "low"
    should_block: bool = False


def load_profile(path: str | Path) -> dict:
    with open(path) as f:
        return json.load(f)


def _registry_entry(chain: str) -> dict:
    return SEQUENCER_REGISTRY.get(chain.lower(), {
        "operator": "unknown",
        "model": "unknown",
        "encrypted_mempool_shipped": False,
        "shared_sequencer": False,
        "force_inclusion_path": False,
        "fair_ordering": False,
    })


def check_h1_centralized_sequencer(s: SequencerSubmission, profile: dict) -> list[RiskAlert]:
    entry = _registry_entry(s.l2_chain)
    model = s.sequencer_model_override or entry["model"]
    operator = s.sequencer_operator_override or entry["operator"]

    if model == "decentralized":
        return []

    h = profile["heuristics"]["H1_centralized_sequencer"]
    severity = "high" if s.is_privacy_relevant else "medium"

    return [
        RiskAlert(
            heuristic_id="H1",
            heuristic_name=h["name"],
            severity=severity,
            confidence=0.95,
            signal=(
                f"L2 '{s.l2_chain}' runs a {model} sequencer ({operator}); "
                f"encrypted_mempool={'YES' if entry['encrypted_mempool_shipped'] else 'NO'}."
            ),
            recommendation=(
                "Treat sequencer as a trusted observer. For privacy-sensitive txs, "
                "wait for encrypted mempool / decentralized sequencer rollout, or use forced L1 inclusion."
            ),
            skill="decentralization_checker",
            action="warn" if s.is_privacy_relevant else "inform",
        )
    ]


def check_h2_sequencer_censorship(s: SequencerSubmission, profile: dict) -> list[RiskAlert]:
    h = profile["heuristics"]["H2_sequencer_censorship"]
    alerts: list[RiskAlert] = []

    if (
        not s.actually_included
        and s.valid_gas_and_nonce
        and s.expected_inclusion_by > 0
        and s.tx_submitted_at > 0
        and s.tx_submitted_at <= s.expected_inclusion_by
    ):
        confidence = 0.95 if s.user_flagged_as_sanctioned else 0.75
        alerts.append(
            RiskAlert(
                heuristic_id="H2",
                heuristic_name=h["name"],
                severity=h["severity"],
                confidence=confidence,
                signal=(
                    "Tx not included by expected window despite valid gas and nonce"
                    + (" (user flagged as sanctioned)." if s.user_flagged_as_sanctioned else ".")
                ),
                recommendation="Use L1 forced-inclusion path if available; record incident.",
                skill="inclusion_timer",
                action="warn",
            )
        )

    if s.consecutive_exclusions >= 3:
        alerts.append(
            RiskAlert(
                heuristic_id="H2",
                heuristic_name=h["name"],
                severity="critical",
                confidence=0.90,
                signal=f"Sender excluded from {s.consecutive_exclusions} consecutive batches; persistent censorship.",
                recommendation="BLOCK further L2 submissions; route via L1 forced inclusion.",
                skill="inclusion_timer",
                action="block",
            )
        )

    return alerts


def check_h3_sequencer_mev(s: SequencerSubmission, profile: dict) -> list[RiskAlert]:
    if s.sequencer_share_of_l2_mev_pct <= 0.30 and s.sequencer_mev_extracted_usd_30d <= 0:
        return []

    h = profile["heuristics"]["H3_sequencer_mev"]
    return [
        RiskAlert(
            heuristic_id="H3",
            heuristic_name=h["name"],
            severity=h["severity"],
            confidence=0.80,
            signal=(
                f"Sequencer extracted ${s.sequencer_mev_extracted_usd_30d:,.0f} MEV in 30d "
                f"({s.sequencer_share_of_l2_mev_pct:.0%} of L2 MEV)."
            ),
            recommendation=(
                "Use private order flow (MEV Blocker / app-level commit-reveal) on L2 if available; "
                "prefer L2s with FCFS or fair-ordering guarantees."
            ),
            skill="sequencer_monitor",
            action="warn",
        )
    ]


def check_h4_shared_sequencer_linkage(s: SequencerSubmission, profile: dict) -> list[RiskAlert]:
    entry = _registry_entry(s.l2_chain)
    is_shared = entry["shared_sequencer"] or len(s.shared_sequencer_other_rollups) > 1
    if not is_shared:
        return []

    h = profile["heuristics"]["H4_shared_sequencer_linkage"]
    others = s.shared_sequencer_other_rollups or [s.l2_chain]
    return [
        RiskAlert(
            heuristic_id="H4",
            heuristic_name=h["name"],
            severity=h["severity"],
            confidence=0.80,
            signal=(
                f"Shared sequencer also operates on {others}; cross-rollup activity is correlatable."
            ),
            recommendation="Avoid mirroring identity across rollups served by the same shared sequencer; add timing jitter.",
            skill="decentralization_checker",
            action="warn",
        )
    ]


def check_h5_preconfirmation_privacy(s: SequencerSubmission, profile: dict) -> list[RiskAlert]:
    if not s.preconfirmation_published_before_batch:
        return []

    h = profile["heuristics"]["H5_preconfirmation_privacy"]
    severity = h["severity"] if s.preconfirmation_publicly_readable else "medium"
    return [
        RiskAlert(
            heuristic_id="H5",
            heuristic_name=h["name"],
            severity=severity,
            confidence=0.85,
            signal=(
                f"Preconfirmation window of {s.preconfirmation_window_seconds}s leaks tx content "
                f"before batch posting"
                + (" (public API)." if s.preconfirmation_publicly_readable else " (gated API).")
            ),
            recommendation="For sensitive actions, prefer L2s with commit-reveal or wait for encrypted mempool.",
            skill="inclusion_timer",
            action="inform",
        )
    ]


_CHECKS = [
    check_h1_centralized_sequencer,
    check_h2_sequencer_censorship,
    check_h3_sequencer_mev,
    check_h4_shared_sequencer_linkage,
    check_h5_preconfirmation_privacy,
]


def analyze_submission(submission: SequencerSubmission, profile: dict) -> AnalysisResult:
    alerts: list[RiskAlert] = []
    for chk in _CHECKS:
        alerts.extend(chk(submission, profile))

    severity_rank = {"low": 1, "medium": 2, "high": 3, "critical": 4}
    overall = "low"
    block = False
    for a in alerts:
        if severity_rank.get(a.severity, 0) > severity_rank.get(overall, 0):
            overall = a.severity
        if a.action == "block":
            block = True

    return AnalysisResult(submission=submission, alerts=alerts, overall_risk=overall, should_block=block)


# ---------------------------------------------------------------------------
# Local self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    profile_path = Path(__file__).parent / "profile.json"
    profile = load_profile(profile_path)

    bad = SequencerSubmission(
        user_address="0xUserSequencer",
        l2_chain="arbitrum",
        submitted_tx_id="0xSeqSubmit01",
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
    print("=== Worst-case ===")
    res = analyze_submission(bad, profile)
    print(f"overall={res.overall_risk} block={res.should_block} alerts={len(res.alerts)}")
    for a in res.alerts:
        print(f"  [{a.severity}] {a.heuristic_id}: {a.signal[:80]}")

    good = SequencerSubmission(
        user_address="0xUserClean",
        l2_chain="ethereum",
        tx_kind="transfer",
        is_privacy_relevant=False,
        actually_included=True,
        valid_gas_and_nonce=True,
        sequencer_share_of_l2_mev_pct=0.0,
        sequencer_mev_extracted_usd_30d=0.0,
        preconfirmation_published_before_batch=False,
    )
    print("\n=== Healthy ===")
    res = analyze_submission(good, profile)
    print(f"overall={res.overall_risk} block={res.should_block} alerts={len(res.alerts)}")
