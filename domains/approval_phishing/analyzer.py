"""
Approval Phishing Analyzer — profile-based transaction risk analysis.

Loads approval_phishing/profile.json and evaluates approval transactions
against 5 heuristics (H1-H5) covering unlimited approvals, unverified
spenders, known scams, suspicious function selectors, and stale approvals.

This is a DEMO / preliminary implementation. Production version would:
- Decode calldata via etherscan / 4byte.directory APIs
- Query Forta / Scam Sniffer / ChainAbuse for scam database
- Read on-chain contract verification status via block explorer
- Track user approval history via RPC (eth_getLogs Approval events)

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
# Constants
# ---------------------------------------------------------------------------

MAX_UINT256 = (1 << 256) - 1
UNLIMITED_THRESHOLD = (1 << 255)  # H1 threshold per profile spec

KNOWN_FUNCTION_SELECTORS = {
    "0x095ea7b3": "approve(address,uint256)",
    "0x39509351": "increaseAllowance(address,uint256)",
    "0xa22cb465": "setApprovalForAll(address,bool)",
    "0xd505accf": "permit(address,address,uint256,uint256,uint8,bytes32,bytes32)",
    "0x2b67b570": "permit2_approve",
    "0xa9059cbb": "transfer(address,uint256)",
    "0x23b872dd": "transferFrom(address,address,uint256)",
    "0xac9650d8": "multicall(bytes[])",
}

# selectors that indicate approval-bearing operations
APPROVAL_SELECTORS = {"0x095ea7b3", "0x39509351", "0xa22cb465", "0xd505accf", "0x2b67b570"}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ApprovalTx:
    """An approval-bearing transaction to analyze."""
    tx_hash: str
    user_address: str
    spender_address: str
    token_address: str
    function_selector: str           # 4-byte selector hex
    approval_amount: int             # raw uint256 amount (use MAX_UINT256 for unlimited)
    is_permit: bool = False          # EIP-2612 / Permit2 signed approval
    permit_expiry_seconds: int = 0   # 0 = no expiry
    spender_verified: bool = True    # block explorer verification
    spender_creation_timestamp: int = 0  # unix seconds, 0 = unknown
    spender_in_scam_db: bool = False
    spender_in_protocol_registry: bool = True  # known DeFi/NFT protocol
    spender_bytecode_match_scam: bool = False  # bytecode similarity to known scam template
    is_multicall_with_approval: bool = False   # batched call with embedded approval
    nested_calls: list[str] = field(default_factory=list)  # decoded inner selectors for multicall
    last_interaction_with_spender_days: int = 0  # 0 = current interaction
    exposed_value_usd: float = 0.0   # for stale approval H5
    current_timestamp: int = 0       # unix seconds (for staleness math)


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
    action: Optional[str] = None  # block | warn | inform


@dataclass
class AnalysisResult:
    """Complete analysis of an approval transaction."""
    tx: ApprovalTx
    alerts: list[RiskAlert] = field(default_factory=list)
    overall_risk: str = "low"     # low | medium | high | critical
    should_block: bool = False    # True if any critical-confidence signal triggers BLOCK


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

def check_h1_unlimited_approval(tx: ApprovalTx, profile: dict) -> list[RiskAlert]:
    """H1: Unlimited token approval — approve()/increaseAllowance() with amount >= 2^255."""
    alerts = []
    h = profile["heuristics"]["H1_unlimited_approval"]

    # Only relevant for approval-bearing selectors (or permit)
    if tx.function_selector not in APPROVAL_SELECTORS and not tx.is_permit:
        return alerts

    if tx.approval_amount >= UNLIMITED_THRESHOLD:
        # Distinguish raw approval vs permit
        if tx.is_permit:
            confidence = 0.90
            signal = f"EIP-2612/Permit2 signed with unlimited amount ({tx.approval_amount})"
            if tx.permit_expiry_seconds == 0:
                signal += " and NO expiry — permanent unlimited approval"
                confidence = 0.95
        else:
            confidence = 0.95
            signal = f"approve()/increaseAllowance() called with unlimited amount ({tx.approval_amount} >= 2^255)"

        alerts.append(RiskAlert(
            heuristic_id="H1",
            heuristic_name=h["name"],
            severity=h["severity"],
            confidence=confidence,
            signal=signal,
            recommendation=h["recommendations"][0]["description"],
            skill="approval_limiter",
            action="warn",
        ))
    return alerts


def check_h2_unverified_spender(tx: ApprovalTx, profile: dict) -> list[RiskAlert]:
    """H2: Unverified spender — contract not verified, recently deployed, or unknown."""
    alerts = []
    h = profile["heuristics"]["H2_unverified_spender"]

    # Combine three signals; threshold is unverified_source AND recently_deployed → BLOCK
    is_unverified = not tx.spender_verified
    is_recent = (
        tx.spender_creation_timestamp > 0
        and tx.current_timestamp > 0
        and (tx.current_timestamp - tx.spender_creation_timestamp) < 86400  # 24h
    )
    is_unknown = not tx.spender_in_protocol_registry

    if is_unverified and is_recent:
        # Strong combined signal — BLOCK threshold
        alerts.append(RiskAlert(
            heuristic_id="H2",
            heuristic_name=h["name"],
            severity="critical",
            confidence=0.90,
            signal="Spender is UNVERIFIED and recently deployed (<24h) — high phishing risk",
            recommendation=h["recommendations"][0]["description"],
            skill=None,
            action="block",
        ))
    elif is_unverified and is_unknown:
        alerts.append(RiskAlert(
            heuristic_id="H2",
            heuristic_name=h["name"],
            severity=h["severity"],
            confidence=0.75,
            signal="Spender is unverified and not in any known protocol registry",
            recommendation=h["recommendations"][1]["description"],
            skill="tx_simulator",
            action="warn",
        ))
    elif is_unverified:
        alerts.append(RiskAlert(
            heuristic_id="H2",
            heuristic_name=h["name"],
            severity="medium",
            confidence=0.55,
            signal="Spender contract source not verified on block explorer",
            recommendation=h["recommendations"][1]["description"],
            skill="tx_simulator",
            action="warn",
        ))
    return alerts


def check_h3_known_scam(tx: ApprovalTx, profile: dict) -> list[RiskAlert]:
    """H3: Known scam address — spender appears in scam database or matches scam bytecode."""
    alerts = []
    h = profile["heuristics"]["H3_known_scam_address"]

    if tx.spender_in_scam_db:
        alerts.append(RiskAlert(
            heuristic_id="H3",
            heuristic_name=h["name"],
            severity="critical",
            confidence=0.99,
            signal=f"Spender {tx.spender_address} is in scam/phishing database with confirmed reports",
            recommendation=h["recommendations"][0]["description"],
            action="block",
        ))
    elif tx.spender_bytecode_match_scam:
        alerts.append(RiskAlert(
            heuristic_id="H3",
            heuristic_name=h["name"],
            severity="critical",
            confidence=0.80,
            signal=f"Spender bytecode matches a known scam template",
            recommendation=h["recommendations"][0]["description"],
            action="block",
        ))
    return alerts


def check_h4_suspicious_function(tx: ApprovalTx, profile: dict) -> list[RiskAlert]:
    """H4: Suspicious function selector — unknown selector or hidden multicall approval."""
    alerts = []
    h = profile["heuristics"]["H4_suspicious_function"]

    # multicall_with_approval is the BLOCK threshold
    if tx.is_multicall_with_approval:
        approval_count = sum(1 for sel in tx.nested_calls if sel in APPROVAL_SELECTORS)
        alerts.append(RiskAlert(
            heuristic_id="H4",
            heuristic_name=h["name"],
            severity="critical",
            confidence=0.85,
            signal=f"Multicall contains {approval_count} hidden approval(s) — calldata: {tx.nested_calls}",
            recommendation=h["recommendations"][1]["description"],
            skill="tx_simulator",
            action="block",
        ))
        return alerts

    # setApprovalForAll to unknown operator (NFT)
    if tx.function_selector == "0xa22cb465" and not tx.spender_in_protocol_registry:
        alerts.append(RiskAlert(
            heuristic_id="H4",
            heuristic_name=h["name"],
            severity="high",
            confidence=0.75,
            signal=f"setApprovalForAll() to unknown operator {tx.spender_address}",
            recommendation=h["recommendations"][0]["description"],
            skill="tx_simulator",
            action="warn",
        ))
        return alerts

    # Unknown function selector
    if tx.function_selector and tx.function_selector not in KNOWN_FUNCTION_SELECTORS:
        alerts.append(RiskAlert(
            heuristic_id="H4",
            heuristic_name=h["name"],
            severity="medium",
            confidence=0.55,
            signal=f"Function selector {tx.function_selector} not in 4byte.directory or known interfaces",
            recommendation=h["recommendations"][0]["description"],
            skill="tx_simulator",
            action="warn",
        ))
    return alerts


def check_h5_stale_approval(tx: ApprovalTx, profile: dict) -> list[RiskAlert]:
    """H5: Stale token approval — long-dormant unlimited approval with value at risk."""
    alerts = []
    h = profile["heuristics"]["H5_stale_approval"]

    # Only relevant for unlimited approvals to start with (otherwise ignored)
    is_unlimited = tx.approval_amount >= UNLIMITED_THRESHOLD
    is_stale = tx.last_interaction_with_spender_days > 30
    is_high_value = tx.exposed_value_usd > 1000.0

    if is_unlimited and is_stale and is_high_value:
        alerts.append(RiskAlert(
            heuristic_id="H5",
            heuristic_name=h["name"],
            severity="high",
            confidence=0.85,
            signal=(
                f"Stale unlimited approval (idle {tx.last_interaction_with_spender_days}d) "
                f"exposes ${tx.exposed_value_usd:.0f} of token value"
            ),
            recommendation=h["recommendations"][0]["description"],
            skill="approval_revoker",
            action="warn",
        ))
    elif is_unlimited and is_stale:
        alerts.append(RiskAlert(
            heuristic_id="H5",
            heuristic_name=h["name"],
            severity=h["severity"],
            confidence=0.70,
            signal=(
                f"Stale unlimited approval (idle {tx.last_interaction_with_spender_days}d, "
                f"exposed ~${tx.exposed_value_usd:.0f})"
            ),
            recommendation=h["recommendations"][1]["description"],
            skill="approval_auditor",
            action="inform",
        ))
    return alerts


# ---------------------------------------------------------------------------
# Main analyzer
# ---------------------------------------------------------------------------

def analyze_transaction(tx: ApprovalTx, profile: dict) -> AnalysisResult:
    """Run all 5 heuristic checks against an approval transaction."""
    result = AnalysisResult(tx=tx)

    checks = [
        check_h1_unlimited_approval(tx, profile),
        check_h2_unverified_spender(tx, profile),
        check_h3_known_scam(tx, profile),
        check_h4_suspicious_function(tx, profile),
        check_h5_stale_approval(tx, profile),
    ]

    for alerts in checks:
        result.alerts.extend(alerts)

    # Block if any critical+high-confidence signal asks for block
    if any(a.action == "block" and a.confidence >= 0.80 for a in result.alerts):
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
    """Format analysis result for display."""
    lines = [
        f"--- Risk Assessment: {result.overall_risk.upper()} ---",
        f"Tx: {result.tx.tx_hash}",
        f"Spender: {result.tx.spender_address}",
        f"Token: {result.tx.token_address}",
        f"Selector: {result.tx.function_selector} ({KNOWN_FUNCTION_SELECTORS.get(result.tx.function_selector, 'UNKNOWN')})",
        f"Amount: {'UNLIMITED' if result.tx.approval_amount >= UNLIMITED_THRESHOLD else result.tx.approval_amount}",
        f"Alerts: {len(result.alerts)}",
    ]
    if result.should_block:
        lines.append("*** TRANSACTION SHOULD BE BLOCKED ***")

    for alert in result.alerts:
        lines.append(f"\n  [{alert.heuristic_id}] {alert.heuristic_name} ({alert.severity}, conf {alert.confidence:.0%}, action: {alert.action})")
        lines.append(f"    Signal: {alert.signal}")
        lines.append(f"    Action: {alert.recommendation}")
        if alert.skill:
            lines.append(f"    Skill: {alert.skill}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Benchmark simulation
# ---------------------------------------------------------------------------

def generate_synthetic_dataset(n: int = 100, seed: int = 42) -> list[ApprovalTx]:
    """Generate synthetic approval transactions for benchmarking.

    Distribution modeled after Forta/Scam Sniffer 2025 phishing data:
    - 60% unlimited approvals (Etherscan baseline for DeFi)
    - 15% unverified spenders (mix of legitimate-new and malicious)
    - 10% known-scam-database hits
    - 5% multicall with hidden approval (rapidly growing per Scam Sniffer)
    - 30% stale approvals (>30 days idle) among unlimited subset
    """
    rng = random.Random(seed)
    txs: list[ApprovalTx] = []
    now = 1730000000  # ref timestamp

    for i in range(n):
        user = f"0x{'u' * 38}{i:02x}"
        spender = f"0x{'s' * 38}{i:02x}"
        token = f"0x{'t' * 38}{i % 16:02x}"

        # Function selector: 70% standard approve, 10% increaseAllowance, 5% setApprovalForAll, 10% permit, 5% multicall
        sel_draw = rng.random()
        if sel_draw < 0.70:
            selector = "0x095ea7b3"
        elif sel_draw < 0.80:
            selector = "0x39509351"
        elif sel_draw < 0.85:
            selector = "0xa22cb465"
        elif sel_draw < 0.95:
            selector = "0xd505accf"  # permit
        else:
            selector = "0xac9650d8"  # multicall

        is_permit = (selector == "0xd505accf")
        is_multicall = (selector == "0xac9650d8")

        # 60% unlimited
        if rng.random() < 0.60:
            amount = MAX_UINT256
        else:
            amount = rng.randint(10**15, 10**21)  # 0.001 to 1000 tokens (wei)

        # 15% unverified spender
        unverified = rng.random() < 0.15
        # of those unverified, 40% are recently deployed
        recent_deploy_ts = (now - rng.randint(0, 86400)) if (unverified and rng.random() < 0.40) else (now - rng.randint(86400 * 30, 86400 * 365 * 3))

        # 10% in scam db
        scam_hit = rng.random() < 0.10
        # 5% bytecode match (independent)
        bytecode_match = rng.random() < 0.05

        # Multicall: 80% of multicalls hide approval (this is the phishing pattern)
        is_multicall_with_approval = is_multicall and rng.random() < 0.80
        nested = []
        if is_multicall_with_approval:
            n_inner = rng.randint(2, 5)
            inner_pool = ["0xa9059cbb", "0x23b872dd", "0x095ea7b3", "0x39509351"]
            nested = [rng.choice(inner_pool) for _ in range(n_inner)]
            if "0x095ea7b3" not in nested and "0x39509351" not in nested:
                nested[0] = "0x095ea7b3"  # ensure embedded approval

        # In protocol registry: 80% (most legitimate)
        in_registry = rng.random() < 0.80 and not (unverified and scam_hit)

        # Stale: 30% of unlimited approvals are stale (>30d, value-at-risk)
        is_stale = (amount >= UNLIMITED_THRESHOLD) and (rng.random() < 0.30)
        last_interaction_days = rng.randint(31, 365) if is_stale else rng.randint(0, 7)
        exposed_value = rng.uniform(50, 50000) if is_stale else rng.uniform(0, 500)

        # Permit expiry: 50% no expiry (worst case), 50% 1h-7d
        permit_expiry = 0 if (is_permit and rng.random() < 0.50) else (rng.randint(3600, 7 * 86400) if is_permit else 0)

        txs.append(ApprovalTx(
            tx_hash=f"0xtx{i:062x}",
            user_address=user,
            spender_address=spender,
            token_address=token,
            function_selector=selector,
            approval_amount=amount,
            is_permit=is_permit,
            permit_expiry_seconds=permit_expiry,
            spender_verified=not unverified,
            spender_creation_timestamp=recent_deploy_ts,
            spender_in_scam_db=scam_hit,
            spender_in_protocol_registry=in_registry,
            spender_bytecode_match_scam=bytecode_match,
            is_multicall_with_approval=is_multicall_with_approval,
            nested_calls=nested,
            last_interaction_with_spender_days=last_interaction_days,
            exposed_value_usd=exposed_value,
            current_timestamp=now,
        ))

    return txs


def run_benchmark(profile: dict, n: int = 1000) -> dict:
    """Run benchmark: TP rate (catch phishing) vs FP rate (false alarm on legit)."""
    txs = generate_synthetic_dataset(n)

    # Heuristic ground truth: a tx is "phishing" if any of these are true
    def is_phishing(tx: ApprovalTx) -> bool:
        return (
            tx.spender_in_scam_db
            or tx.spender_bytecode_match_scam
            or tx.is_multicall_with_approval
            or (not tx.spender_verified and (1730000000 - tx.spender_creation_timestamp) < 86400)
        )

    results = [(tx, analyze_transaction(tx, profile)) for tx in txs]

    tp = fp = tn = fn = 0
    flagged_count = 0
    for tx, r in results:
        actually_phish = is_phishing(tx)
        flagged = r.should_block or r.overall_risk in ("critical", "high")
        if flagged:
            flagged_count += 1
            if actually_phish:
                tp += 1
            else:
                fp += 1
        else:
            if actually_phish:
                fn += 1
            else:
                tn += 1

    total_phish = tp + fn
    total_legit = tn + fp
    tpr = tp / total_phish if total_phish else 0.0
    fpr = fp / total_legit if total_legit else 0.0

    # Per-heuristic counts
    heuristic_counts: dict[str, int] = {}
    for _, r in results:
        for a in r.alerts:
            heuristic_counts[a.heuristic_id] = heuristic_counts.get(a.heuristic_id, 0) + 1

    # Stale value-at-risk total
    var_total = sum(tx.exposed_value_usd for tx, r in results
                    if any(a.heuristic_id == "H5" for a in r.alerts))

    return {
        "n_transactions": n,
        "phishing_in_dataset": total_phish,
        "legit_in_dataset": total_legit,
        "true_positive": tp,
        "false_positive": fp,
        "true_negative": tn,
        "false_negative": fn,
        "true_positive_rate": f"{tpr:.1%}",
        "false_positive_rate": f"{fpr:.1%}",
        "flagged_total": flagged_count,
        "per_heuristic_alert_count": heuristic_counts,
        "stale_value_at_risk_usd": round(var_total, 0),
        "target_per_profile": "TPR >90%, FPR <5%",
    }


# ---------------------------------------------------------------------------
# Example scenarios
# ---------------------------------------------------------------------------

def run_examples(profile: dict):
    """Run illustrative example scenarios."""
    now = 1730000000
    examples = [
        ("Good practice: limited approval to verified protocol", ApprovalTx(
            tx_hash="0xgood01",
            user_address="0xuser",
            spender_address="0xUniswapRouter",
            token_address="0xUSDC",
            function_selector="0x095ea7b3",
            approval_amount=1_000_000,  # 1 USDC, exact amount
            spender_verified=True,
            spender_in_protocol_registry=True,
            current_timestamp=now,
        )),
        ("BAD: unlimited approve to unverified, recently deployed contract", ApprovalTx(
            tx_hash="0xbad01",
            user_address="0xuser",
            spender_address="0xMaliciousNewContract",
            token_address="0xUSDC",
            function_selector="0x095ea7b3",
            approval_amount=MAX_UINT256,
            spender_verified=False,
            spender_creation_timestamp=now - 3600,  # 1h ago
            spender_in_protocol_registry=False,
            current_timestamp=now,
        )),
        ("WORST: known scam in database", ApprovalTx(
            tx_hash="0xscam01",
            user_address="0xuser",
            spender_address="0xConfirmedScamAddress",
            token_address="0xUSDC",
            function_selector="0x095ea7b3",
            approval_amount=MAX_UINT256,
            spender_verified=False,
            spender_in_scam_db=True,
            current_timestamp=now,
        )),
        ("Multicall with hidden approval (Permit2 phishing pattern)", ApprovalTx(
            tx_hash="0xmulti01",
            user_address="0xuser",
            spender_address="0xPhishingContract",
            token_address="0xUSDC",
            function_selector="0xac9650d8",  # multicall
            approval_amount=MAX_UINT256,
            spender_verified=False,
            is_multicall_with_approval=True,
            nested_calls=["0xa9059cbb", "0x095ea7b3", "0x23b872dd"],
            current_timestamp=now,
        )),
        ("Stale approval: idle 90 days, $5K exposed", ApprovalTx(
            tx_hash="0xstale01",
            user_address="0xuser",
            spender_address="0xOldDexRouter",
            token_address="0xWETH",
            function_selector="0x095ea7b3",
            approval_amount=MAX_UINT256,
            spender_verified=True,
            spender_in_protocol_registry=True,
            last_interaction_with_spender_days=90,
            exposed_value_usd=5000.0,
            current_timestamp=now,
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
    profile_path = Path(__file__).parent / "profile.json"
    profile = load_profile(profile_path)

    if "--benchmark" in sys.argv:
        print("Running approval phishing benchmark (1000 synthetic transactions)...")
        results = run_benchmark(profile)
        print(json.dumps(results, indent=2))
    else:
        print(f"Approval Phishing Analyzer v{profile['meta']['version']}")
        print(f"Profile: {profile['meta']['domain_name']}")
        print(f"Source: {profile['meta']['source_paper']}")
        print(f"Annual loss baseline: ${profile['meta']['baseline_loss_rate']:,}")
        run_examples(profile)


if __name__ == "__main__":
    main()
