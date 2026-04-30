"""
Governance Proposal Analyzer — profile-based malicious proposal detection.

Loads governance_proposal/profile.json and evaluates DAO proposals against 5
heuristics (H1-H5) covering treasury drain, parameter manipulation, proxy
upgrade to unverified code, timelock bypass, and voter concentration.

This is a DEMO / preliminary implementation. Production would:
- Decode proposal calldata via Tally / Boardroom APIs or proposal_decoder skill
- Query treasury balance via on-chain RPC (token balances at the DAO multisig)
- Verify implementation contracts via Etherscan / Sourcify
- Pull historical parameter values from event logs

Usage:
    python analyzer.py                     # run example scenarios
    python analyzer.py --benchmark         # run benchmark
"""

from __future__ import annotations

import json
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TREASURY_DRAIN_RATIO = 0.10            # H1: >10% treasury outflow
RECIPIENT_NEW_TX_THRESHOLD = 5         # H1: <5 prior txs = new recipient
RECENT_DEPLOY_HOURS = 48               # H3: <48h since deployment
PARAMETER_STDDEV_THRESHOLD = 2.0       # H2: 2 sigma outlier
TIMELOCK_MIN_HOURS = 48                # H4: typical minimum
QUORUM_DOMINANCE_THRESHOLD = 0.40      # H5: single voter >40% of quorum


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class TreasuryTransfer:
    recipient: str
    token: str
    amount_wei: int
    value_usd: float


@dataclass
class ParameterChange:
    param_name: str
    old_value: float
    new_value: float
    historical_mean: float = 0.0
    historical_std: float = 0.0


@dataclass
class ProxyUpgrade:
    proxy_address: str
    old_implementation: str
    new_implementation: str
    new_implementation_verified: bool = False
    new_implementation_deployed_timestamp: int = 0
    bytecode_diff_size: int = 0
    has_selfdestruct: bool = False
    has_unrestricted_delegatecall: bool = False


@dataclass
class GovernanceProposal:
    """A DAO proposal to analyze."""
    proposal_id: str
    dao_name: str
    proposer_address: str
    proposed_at: int
    voting_ends_at: int

    # H1 treasury
    treasury_balance_usd: float = 0.0
    transfers: list[TreasuryTransfer] = field(default_factory=list)
    recipient_tx_counts: dict[str, int] = field(default_factory=dict)
    recipient_labels: dict[str, str] = field(default_factory=dict)  # {address: "multisig" | "grant" | ""}

    # H2 parameters
    parameter_changes: list[ParameterChange] = field(default_factory=list)
    oracle_replacements: list[dict] = field(default_factory=list)  # [{old, new, new_verified}]
    parameter_dependency_compounds: list[str] = field(default_factory=list)  # text descriptions

    # H3 proxy upgrade
    proxy_upgrades: list[ProxyUpgrade] = field(default_factory=list)

    # H4 timelock
    current_timelock_hours: float = 48.0
    proposed_timelock_hours: float = 48.0
    minimum_timelock_hours: float = 24.0

    # H5 voter concentration
    top_voter_share: float = 0.0       # 0.0-1.0, share of yes votes from largest voter
    top_voter_address: str = ""
    quorum_share: float = 0.5          # share needed for quorum

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
    proposal: GovernanceProposal
    alerts: list[RiskAlert] = field(default_factory=list)
    overall_risk: str = "low"
    should_block: bool = False


# ---------------------------------------------------------------------------
# Profile loader
# ---------------------------------------------------------------------------

def load_profile(path: str | Path) -> dict:
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Heuristic checks
# ---------------------------------------------------------------------------

def check_h1_treasury_drain(p: GovernanceProposal, profile: dict) -> list[RiskAlert]:
    """H1: Treasury drain — >10% outflow to new/unknown recipient, possibly multi-asset sweep."""
    alerts: list[RiskAlert] = []
    h = profile["heuristics"]["H1_treasury_drain"]

    if not p.transfers or p.treasury_balance_usd <= 0:
        return alerts

    total_outflow = sum(t.value_usd for t in p.transfers)
    outflow_ratio = total_outflow / max(p.treasury_balance_usd, 1.0)
    is_large = outflow_ratio > TREASURY_DRAIN_RATIO

    # multi-asset sweep: 3+ different tokens in single proposal
    unique_tokens = {t.token for t in p.transfers}
    is_sweep = len(unique_tokens) >= 3

    # Unknown recipient: any transfer to address with <5 prior txs and no label
    unknown_recipients: list[str] = []
    for t in p.transfers:
        tx_count = p.recipient_tx_counts.get(t.recipient, 0)
        label = p.recipient_labels.get(t.recipient, "")
        if tx_count < RECIPIENT_NEW_TX_THRESHOLD and not label:
            unknown_recipients.append(t.recipient)

    if is_large and unknown_recipients:
        alerts.append(RiskAlert(
            heuristic_id="H1",
            heuristic_name=h["name"],
            severity="critical",
            confidence=0.90,
            signal=(
                f"Proposal moves ${total_outflow:,.0f} ({outflow_ratio:.1%} of treasury) "
                f"to unknown recipient(s): {unknown_recipients[:2]}"
            ),
            recommendation=h["recommendations"][2]["description"],
            action="block",
        ))
    elif is_sweep:
        alerts.append(RiskAlert(
            heuristic_id="H1",
            heuristic_name=h["name"],
            severity=h["severity"],
            confidence=0.85,
            signal=f"Proposal sweeps {len(unique_tokens)} different token types in single execution",
            recommendation=h["recommendations"][1]["description"],
            skill="parameter_simulator",
            action="warn",
        ))
    elif is_large:
        alerts.append(RiskAlert(
            heuristic_id="H1",
            heuristic_name=h["name"],
            severity="high",
            confidence=0.75,
            signal=f"Proposal moves ${total_outflow:,.0f} ({outflow_ratio:.1%} of treasury) — large outflow",
            recommendation=h["recommendations"][0]["description"],
            action="warn",
        ))
    return alerts


def check_h2_parameter_manipulation(p: GovernanceProposal, profile: dict) -> list[RiskAlert]:
    """H2: Parameter changes outside historical range, oracle swaps, compound risk."""
    alerts: list[RiskAlert] = []
    h = profile["heuristics"]["H2_parameter_manipulation"]

    out_of_range: list[str] = []
    for pc in p.parameter_changes:
        if pc.historical_std > 0:
            z = abs(pc.new_value - pc.historical_mean) / pc.historical_std
            if z > PARAMETER_STDDEV_THRESHOLD:
                out_of_range.append(f"{pc.param_name}: {pc.old_value}→{pc.new_value} ({z:.1f}σ)")

    has_oracle_swap = bool(p.oracle_replacements)
    unverified_oracle_swap = any(not o.get("new_verified", True) for o in p.oracle_replacements)
    has_compound = bool(p.parameter_dependency_compounds)

    if out_of_range and has_compound:
        alerts.append(RiskAlert(
            heuristic_id="H2",
            heuristic_name=h["name"],
            severity="critical",
            confidence=0.85,
            signal=(
                f"Out-of-range parameter changes ({', '.join(out_of_range[:2])}) "
                f"AND compound risk: {p.parameter_dependency_compounds[0]}"
            ),
            recommendation=h["recommendations"][0]["description"],
            skill="parameter_simulator",
            action="block",
        ))
    elif unverified_oracle_swap:
        alerts.append(RiskAlert(
            heuristic_id="H2",
            heuristic_name=h["name"],
            severity=h["severity"],
            confidence=0.85,
            signal=f"Proposal replaces price oracle with unverified feed (count: {len(p.oracle_replacements)})",
            recommendation=h["recommendations"][0]["description"],
            skill="parameter_simulator",
            action="warn",
        ))
    elif out_of_range:
        alerts.append(RiskAlert(
            heuristic_id="H2",
            heuristic_name=h["name"],
            severity=h["severity"],
            confidence=0.75,
            signal=f"Parameters out of historical range: {'; '.join(out_of_range[:3])}",
            recommendation=h["recommendations"][1]["description"],
            action="warn",
        ))
    elif has_compound:
        alerts.append(RiskAlert(
            heuristic_id="H2",
            heuristic_name=h["name"],
            severity="medium",
            confidence=0.65,
            signal=f"Compound parameter risk: {p.parameter_dependency_compounds[0]}",
            recommendation=h["recommendations"][2]["description"],
            skill="parameter_simulator",
            action="warn",
        ))
    return alerts


def check_h3_proxy_upgrade(p: GovernanceProposal, profile: dict) -> list[RiskAlert]:
    """H3: Proxy upgrade to unverified or dangerous implementation."""
    alerts: list[RiskAlert] = []
    h = profile["heuristics"]["H3_proxy_upgrade"]

    for up in p.proxy_upgrades:
        # SELFDESTRUCT / unrestricted DELEGATECALL — strongest signal
        if up.has_selfdestruct or up.has_unrestricted_delegatecall:
            opcodes = []
            if up.has_selfdestruct:
                opcodes.append("SELFDESTRUCT")
            if up.has_unrestricted_delegatecall:
                opcodes.append("unrestricted DELEGATECALL")
            alerts.append(RiskAlert(
                heuristic_id="H3",
                heuristic_name=h["name"],
                severity="critical",
                confidence=0.95,
                signal=(
                    f"Proxy upgrade targets implementation containing dangerous opcodes: "
                    f"{', '.join(opcodes)} (proxy {up.proxy_address})"
                ),
                recommendation=h["recommendations"][1]["description"],
                action="block",
            ))
            continue

        # Unverified implementation
        if not up.new_implementation_verified:
            recent = (
                up.new_implementation_deployed_timestamp > 0
                and p.current_timestamp > 0
                and (p.current_timestamp - up.new_implementation_deployed_timestamp) < RECENT_DEPLOY_HOURS * 3600
            )
            confidence = 0.90 if recent else 0.85
            recent_note = " (and deployed <48h ago)" if recent else ""
            alerts.append(RiskAlert(
                heuristic_id="H3",
                heuristic_name=h["name"],
                severity="critical",
                confidence=confidence,
                signal=(
                    f"Proxy upgrade to UNVERIFIED implementation {up.new_implementation}"
                    f"{recent_note}"
                ),
                recommendation=h["recommendations"][1]["description"],
                skill="proposal_decoder",
                action="block",
            ))
            continue

        # Verified but large bytecode diff
        if up.bytecode_diff_size > 5000:  # arbitrary "many bytes changed" threshold
            alerts.append(RiskAlert(
                heuristic_id="H3",
                heuristic_name=h["name"],
                severity="high",
                confidence=0.70,
                signal=(
                    f"Proxy upgrade has large bytecode diff ({up.bytecode_diff_size} bytes) "
                    f"vs current implementation"
                ),
                recommendation=h["recommendations"][2]["description"],
                action="warn",
            ))

    return alerts


def check_h4_timelock_bypass(p: GovernanceProposal, profile: dict) -> list[RiskAlert]:
    """H4: Timelock reduction or removal — eliminates community veto window."""
    alerts: list[RiskAlert] = []
    h = profile["heuristics"]["H4_timelock_bypass"]

    # Substantial reduction or below minimum
    reduces = p.proposed_timelock_hours < p.current_timelock_hours
    below_min = p.proposed_timelock_hours < p.minimum_timelock_hours
    eliminated = p.proposed_timelock_hours <= 0

    if eliminated:
        alerts.append(RiskAlert(
            heuristic_id="H4",
            heuristic_name=h["name"],
            severity="critical",
            confidence=0.95,
            signal=f"Proposal ELIMINATES timelock (current: {p.current_timelock_hours:.0f}h → 0h)",
            recommendation="Reject proposal. Timelock is the community's veto window — eliminating it is a major red flag.",
            action="block",
        ))
    elif below_min:
        alerts.append(RiskAlert(
            heuristic_id="H4",
            heuristic_name=h["name"],
            severity="critical",
            confidence=0.90,
            signal=(
                f"Proposed timelock {p.proposed_timelock_hours:.0f}h below protocol minimum "
                f"{p.minimum_timelock_hours:.0f}h"
            ),
            recommendation="Reject proposal — violates protocol-defined minimum timelock.",
            action="block",
        ))
    elif reduces and p.proposed_timelock_hours < p.current_timelock_hours * 0.5:
        alerts.append(RiskAlert(
            heuristic_id="H4",
            heuristic_name=h["name"],
            severity="high",
            confidence=0.80,
            signal=(
                f"Proposal halves timelock or more "
                f"({p.current_timelock_hours:.0f}h → {p.proposed_timelock_hours:.0f}h)"
            ),
            recommendation="Investigate justification for timelock reduction; community review window shrinks.",
            action="warn",
        ))
    return alerts


def check_h5_voter_concentration(p: GovernanceProposal, profile: dict) -> list[RiskAlert]:
    """H5: Single voter dominates the yes side of quorum."""
    alerts: list[RiskAlert] = []
    h = profile["heuristics"]["H5_voter_concentration"]

    if p.top_voter_share > QUORUM_DOMINANCE_THRESHOLD:
        confidence = 0.85 if p.top_voter_share > 0.60 else 0.75
        alerts.append(RiskAlert(
            heuristic_id="H5",
            heuristic_name=h["name"],
            severity=h["severity"],
            confidence=confidence,
            signal=(
                f"Top voter {p.top_voter_address} contributes "
                f"{p.top_voter_share:.0%} of yes-vote weight (>{QUORUM_DOMINANCE_THRESHOLD:.0%} threshold)"
            ),
            recommendation="Investigate proposer/voter relationship. Single-actor governance capture risk.",
            skill="vote_analyzer",
            action="warn",
        ))
    return alerts


# ---------------------------------------------------------------------------
# Main analyzer
# ---------------------------------------------------------------------------

def analyze_proposal(p: GovernanceProposal, profile: dict) -> AnalysisResult:
    result = AnalysisResult(proposal=p)

    checks = [
        check_h1_treasury_drain(p, profile),
        check_h2_parameter_manipulation(p, profile),
        check_h3_proxy_upgrade(p, profile),
        check_h4_timelock_bypass(p, profile),
        check_h5_voter_concentration(p, profile),
    ]
    for alerts in checks:
        result.alerts.extend(alerts)

    if any(a.action == "block" and a.confidence >= 0.85 for a in result.alerts):
        result.should_block = True
        result.overall_risk = "critical"
    elif any(a.severity == "critical" for a in result.alerts):
        result.overall_risk = "high"
    elif any(a.severity == "high" for a in result.alerts):
        result.overall_risk = "medium"
    elif result.alerts:
        result.overall_risk = "low"

    return result


def format_result(result: AnalysisResult) -> str:
    p = result.proposal
    lines = [
        f"--- Proposal Risk Assessment: {result.overall_risk.upper()} ---",
        f"Proposal: {p.proposal_id} ({p.dao_name})",
        f"Proposer: {p.proposer_address}",
        f"Treasury: ${p.treasury_balance_usd:,.0f}, Transfers: {len(p.transfers)}, "
        f"Param changes: {len(p.parameter_changes)}, Upgrades: {len(p.proxy_upgrades)}",
        f"Top voter: {p.top_voter_share:.0%}",
        f"Alerts: {len(result.alerts)}",
    ]
    if result.should_block:
        lines.append("*** PROPOSAL FLAGGED FOR EMERGENCY REVIEW ***")
    for a in result.alerts:
        lines.append(f"\n  [{a.heuristic_id}] {a.heuristic_name} ({a.severity}, conf {a.confidence:.0%}, action: {a.action})")
        lines.append(f"    Signal: {a.signal}")
        lines.append(f"    Action: {a.recommendation}")
        if a.skill:
            lines.append(f"    Skill: {a.skill}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Benchmark simulation
# ---------------------------------------------------------------------------

def generate_synthetic_dataset(n: int = 100, seed: int = 42) -> list[GovernanceProposal]:
    """Generate synthetic proposals: ~70% routine, ~30% containing attack patterns."""
    rng = random.Random(seed)
    proposals: list[GovernanceProposal] = []
    now = 1730000000

    for i in range(n):
        is_attack = rng.random() < 0.30
        treasury = rng.uniform(1_000_000, 500_000_000)

        # Transfers
        transfers: list[TreasuryTransfer] = []
        recipient_counts: dict[str, int] = {}
        recipient_labels: dict[str, str] = {}

        if is_attack and rng.random() < 0.40:
            # Treasury drain attack
            attacker = f"0xattacker{i:032x}"
            transfers.append(TreasuryTransfer(
                recipient=attacker,
                token="USDC",
                amount_wei=int(treasury * rng.uniform(0.15, 0.50) * 1e6),
                value_usd=treasury * rng.uniform(0.15, 0.50),
            ))
            # Maybe multi-asset sweep
            if rng.random() < 0.50:
                for tok in ["WETH", "DAI", "WBTC"]:
                    transfers.append(TreasuryTransfer(
                        recipient=attacker,
                        token=tok,
                        amount_wei=int(treasury * 0.02 * 1e18),
                        value_usd=treasury * 0.02,
                    ))
            recipient_counts[attacker] = 0
        elif rng.random() < 0.30:
            # Legitimate grant
            grant = f"0xgrant{i:033x}"
            transfers.append(TreasuryTransfer(
                recipient=grant,
                token="USDC",
                amount_wei=int(treasury * 0.02 * 1e6),
                value_usd=treasury * 0.02,
            ))
            recipient_counts[grant] = 50
            recipient_labels[grant] = "grant"

        # Parameter changes
        param_changes: list[ParameterChange] = []
        oracle_replacements: list[dict] = []
        compounds: list[str] = []
        if is_attack and rng.random() < 0.30:
            # Out-of-range parameters
            param_changes.append(ParameterChange(
                param_name="liquidation_threshold",
                old_value=0.85,
                new_value=0.95,  # 4 sigma if mean=0.85, std=0.025
                historical_mean=0.85,
                historical_std=0.025,
            ))
            compounds.append("collateral factor up + liquidation incentive down")
        elif rng.random() < 0.20:
            # Routine adjustment
            param_changes.append(ParameterChange(
                param_name="reserve_factor",
                old_value=0.10,
                new_value=0.11,
                historical_mean=0.10,
                historical_std=0.015,
            ))
        if is_attack and rng.random() < 0.20:
            oracle_replacements.append({
                "old": "0xchainlink",
                "new": "0xunverified_oracle",
                "new_verified": False,
            })

        # Proxy upgrades
        upgrades: list[ProxyUpgrade] = []
        if is_attack and rng.random() < 0.30:
            upgrades.append(ProxyUpgrade(
                proxy_address=f"0xproxy{i:034x}",
                old_implementation="0xold",
                new_implementation=f"0xnewmalicious{i:028x}",
                new_implementation_verified=False,
                new_implementation_deployed_timestamp=now - rng.randint(3600, 100 * 3600),
                bytecode_diff_size=rng.randint(2000, 20000),
                has_selfdestruct=rng.random() < 0.30,
                has_unrestricted_delegatecall=rng.random() < 0.20,
            ))
        elif rng.random() < 0.15:
            upgrades.append(ProxyUpgrade(
                proxy_address=f"0xproxy{i:034x}",
                old_implementation="0xold",
                new_implementation=f"0xnewverified{i:029x}",
                new_implementation_verified=True,
                new_implementation_deployed_timestamp=now - rng.randint(7 * 86400, 30 * 86400),
                bytecode_diff_size=rng.randint(100, 1000),
            ))

        # Timelock
        if is_attack and rng.random() < 0.20:
            current_tl = 48.0
            proposed_tl = rng.choice([0.0, 12.0, 24.0])
        else:
            current_tl = 48.0
            proposed_tl = current_tl + rng.choice([0, 0, 24])

        # Voter concentration
        if is_attack and rng.random() < 0.30:
            top_share = rng.uniform(0.50, 0.95)
        else:
            top_share = rng.uniform(0.05, 0.35)

        proposals.append(GovernanceProposal(
            proposal_id=f"prop{i:04d}",
            dao_name=rng.choice(["Compound", "Aave", "Uniswap", "MakerDAO"]),
            proposer_address=f"0xprop{i:036x}",
            proposed_at=now - 86400,
            voting_ends_at=now + 86400,
            treasury_balance_usd=treasury,
            transfers=transfers,
            recipient_tx_counts=recipient_counts,
            recipient_labels=recipient_labels,
            parameter_changes=param_changes,
            oracle_replacements=oracle_replacements,
            parameter_dependency_compounds=compounds,
            proxy_upgrades=upgrades,
            current_timelock_hours=current_tl,
            proposed_timelock_hours=proposed_tl,
            minimum_timelock_hours=24.0,
            top_voter_share=top_share,
            top_voter_address=f"0xtop{i:037x}",
            current_timestamp=now,
        ))

    return proposals


def run_benchmark(profile: dict, n: int = 1000) -> dict:
    proposals = generate_synthetic_dataset(n)

    def is_attack(p: GovernanceProposal) -> bool:
        # Ground truth: attack if any of these are present
        if p.transfers and p.treasury_balance_usd > 0:
            ratio = sum(t.value_usd for t in p.transfers) / p.treasury_balance_usd
            for t in p.transfers:
                if ratio > 0.10 and p.recipient_tx_counts.get(t.recipient, 0) < 5 and not p.recipient_labels.get(t.recipient):
                    return True
        if any(not o.get("new_verified", True) for o in p.oracle_replacements):
            return True
        for up in p.proxy_upgrades:
            if up.has_selfdestruct or up.has_unrestricted_delegatecall or not up.new_implementation_verified:
                return True
        if p.proposed_timelock_hours < p.minimum_timelock_hours:
            return True
        if p.top_voter_share > 0.50:
            return True
        return False

    results = [(p, analyze_proposal(p, profile)) for p in proposals]
    tp = fp = tn = fn = 0
    for p, r in results:
        attack = is_attack(p)
        flagged = r.should_block or r.overall_risk in ("critical", "high")
        if flagged and attack:
            tp += 1
        elif flagged and not attack:
            fp += 1
        elif not flagged and attack:
            fn += 1
        else:
            tn += 1

    total_attack = tp + fn
    total_safe = tn + fp
    tpr = tp / total_attack if total_attack else 0.0
    fpr = fp / total_safe if total_safe else 0.0

    heuristic_counts: dict[str, int] = {}
    for _, r in results:
        for a in r.alerts:
            heuristic_counts[a.heuristic_id] = heuristic_counts.get(a.heuristic_id, 0) + 1

    return {
        "n_proposals": n,
        "attacks_in_dataset": total_attack,
        "safe_in_dataset": total_safe,
        "true_positive": tp,
        "false_positive": fp,
        "true_negative": tn,
        "false_negative": fn,
        "true_positive_rate": f"{tpr:.1%}",
        "false_positive_rate": f"{fpr:.1%}",
        "per_heuristic_alert_count": heuristic_counts,
        "target": "TPR >90% on known attack patterns; FPR depends on dataset (governance is judgment-heavy)",
    }


# ---------------------------------------------------------------------------
# Examples
# ---------------------------------------------------------------------------

def run_examples(profile: dict):
    now = 1730000000
    examples = [
        ("Routine grant: $200K to known program", GovernanceProposal(
            proposal_id="prop001",
            dao_name="Compound",
            proposer_address="0xproposer",
            proposed_at=now - 86400,
            voting_ends_at=now + 172800,
            treasury_balance_usd=100_000_000,
            transfers=[TreasuryTransfer(recipient="0xgrants", token="USDC", amount_wei=200_000_000_000, value_usd=200_000)],
            recipient_tx_counts={"0xgrants": 142},
            recipient_labels={"0xgrants": "grant"},
            current_timelock_hours=48.0,
            proposed_timelock_hours=48.0,
            top_voter_share=0.18,
            current_timestamp=now,
        )),
        ("ATTACK: treasury drain (Beanstalk-style)", GovernanceProposal(
            proposal_id="drain001",
            dao_name="Compound",
            proposer_address="0xattacker",
            proposed_at=now - 3600,
            voting_ends_at=now + 86400,
            treasury_balance_usd=100_000_000,
            transfers=[
                TreasuryTransfer(recipient="0xattacker_addr", token="USDC", amount_wei=30_000_000_000_000, value_usd=30_000_000),
                TreasuryTransfer(recipient="0xattacker_addr", token="WETH", amount_wei=int(5000 * 1e18), value_usd=15_000_000),
                TreasuryTransfer(recipient="0xattacker_addr", token="WBTC", amount_wei=int(100 * 1e8), value_usd=8_000_000),
            ],
            recipient_tx_counts={"0xattacker_addr": 0},
            current_timelock_hours=48.0,
            proposed_timelock_hours=48.0,
            top_voter_share=0.65,
            top_voter_address="0xattacker",
            current_timestamp=now,
        )),
        ("ATTACK: proxy upgrade to unverified malicious code", GovernanceProposal(
            proposal_id="upgrade001",
            dao_name="Aave",
            proposer_address="0xattacker",
            proposed_at=now - 3600,
            voting_ends_at=now + 86400,
            treasury_balance_usd=200_000_000,
            proxy_upgrades=[ProxyUpgrade(
                proxy_address="0xLendingPool",
                old_implementation="0xold_audited",
                new_implementation="0xnew_unverified_recent",
                new_implementation_verified=False,
                new_implementation_deployed_timestamp=now - 7200,
                bytecode_diff_size=15000,
                has_selfdestruct=True,
            )],
            current_timelock_hours=48.0,
            proposed_timelock_hours=48.0,
            top_voter_share=0.55,
            current_timestamp=now,
        )),
        ("ATTACK: timelock elimination", GovernanceProposal(
            proposal_id="timelock001",
            dao_name="MakerDAO",
            proposer_address="0xattacker",
            proposed_at=now - 3600,
            voting_ends_at=now + 86400,
            treasury_balance_usd=500_000_000,
            current_timelock_hours=48.0,
            proposed_timelock_hours=0.0,
            minimum_timelock_hours=24.0,
            top_voter_share=0.30,
            current_timestamp=now,
        )),
        ("ATTACK: parameter manipulation (oracle swap + compound)", GovernanceProposal(
            proposal_id="param001",
            dao_name="Compound",
            proposer_address="0xinsider",
            proposed_at=now - 3600,
            voting_ends_at=now + 86400,
            treasury_balance_usd=100_000_000,
            parameter_changes=[ParameterChange(
                param_name="liquidation_threshold",
                old_value=0.85, new_value=0.95,
                historical_mean=0.85, historical_std=0.025,
            )],
            oracle_replacements=[{"old": "0xchainlink", "new": "0xshady_feed", "new_verified": False}],
            parameter_dependency_compounds=["collateral factor raised + liquidation incentive lowered simultaneously"],
            current_timelock_hours=48.0,
            proposed_timelock_hours=48.0,
            top_voter_share=0.42,
            current_timestamp=now,
        )),
    ]

    for name, p in examples:
        print(f"\n{'='*60}")
        print(f"Scenario: {name}")
        print(f"{'='*60}")
        result = analyze_proposal(p, profile)
        print(format_result(result))


def main():
    profile_path = Path(__file__).parent / "profile.json"
    profile = load_profile(profile_path)

    if "--benchmark" in sys.argv:
        print("Running governance proposal benchmark (1000 synthetic proposals)...")
        results = run_benchmark(profile)
        print(json.dumps(results, indent=2))
    else:
        print(f"Governance Proposal Analyzer v{profile['meta']['version']}")
        print(f"Profile: {profile['meta']['domain_name']}")
        print(f"Source: {profile['meta'].get('source_paper', 'governance security research')}")
        run_examples(profile)


if __name__ == "__main__":
    main()
