"""
L2 Bridge Linkage Analyzer — privacy heuristics for cross-chain bridge usage.

Loads l2_bridge_linkage/profile.json and evaluates a bridge transaction (or
sequence) against 5 heuristics covering same-address bridge, amount correlation,
bridge sequence fingerprint, gas funding linkability, and NFT/token bridge.

Privacy property: bridges are a major linkability surface. Sender on L1 == receiver
on L2 == same identity. Amount, timing, and sequencing all leak.

Production version would:
- Cross-reference bridge events on both source and destination chains
- Track address relationship across chains via bridge contract logs
- Compute amount-distribution distances against bridge volume

Usage:
    python analyzer.py                     # examples
    python analyzer.py --benchmark         # benchmark
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

AMOUNT_DUST_FRACTION = 0.001       # H2: precise amount carryover (within 0.1%)
SHORT_BRIDGE_DELAY_SECS = 300      # H3: <5 min between bridge legs = sequencing
GAS_FUNDING_LINK_DELAY = 3600      # H4: gas funded from same source within 1h


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class BridgeTx:
    tx_id: str
    bridge_protocol: str           # "Hop" | "Across" | "Stargate" | "Native L2 bridge"
    source_chain: str              # "ethereum"
    dest_chain: str                # "arbitrum" | "optimism" | "base" | etc.
    sender_address: str            # on source
    receiver_address: str          # on destination
    amount_token: str
    amount_value: float            # native units (e.g., ETH or USDC)
    amount_usd: float
    timestamp: int

    # H4 gas funding
    dest_gas_funded_from: str = "" # address that funded gas on destination chain (if pre-funded)
    dest_gas_funding_timestamp: int = 0
    dest_gas_funding_via_paymaster: bool = False

    # H5 NFT bundle
    bundles_nft: bool = False
    nft_collection: str = ""
    nft_token_id: int = 0


@dataclass
class BridgeSequence:
    """A sequence of bridge transactions for sequence-fingerprint analysis."""
    user_address: str
    txs: list[BridgeTx] = field(default_factory=list)


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
    sequence: BridgeSequence
    alerts: list[RiskAlert] = field(default_factory=list)
    overall_risk: str = "low"


# ---------------------------------------------------------------------------
# Profile loader
# ---------------------------------------------------------------------------

def load_profile(path: str | Path) -> dict:
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Heuristic checks
# ---------------------------------------------------------------------------

def check_h1_same_address_bridge(seq: BridgeSequence, profile: dict) -> list[RiskAlert]:
    """H1: Same address used on both L1 and L2 — direct cross-chain identity link."""
    alerts: list[RiskAlert] = []
    h = profile["heuristics"]["H1_same_address_bridge"]

    same_addr_txs = [t for t in seq.txs if t.sender_address.lower() == t.receiver_address.lower()]
    if same_addr_txs:
        alerts.append(RiskAlert(
            heuristic_id="H1",
            heuristic_name=h["name"],
            severity="critical",
            confidence=0.95,
            signal=(
                f"{len(same_addr_txs)} bridge tx(s) use SAME address on source and destination — "
                f"direct cross-chain identity link"
            ),
            recommendation=(
                "Use a fresh address on the destination chain. Bridge to a new address with no prior "
                "history (and avoid funding gas from the source-side address — see H4)."
            ),
            skill="address_separator",
            action="block",
        ))
    return alerts


def check_h2_amount_correlation(seq: BridgeSequence, profile: dict) -> list[RiskAlert]:
    """H2: Amounts that don't appear in normal bridge volume distribution — fingerprint."""
    alerts: list[RiskAlert] = []
    h = profile["heuristics"]["H2_amount_correlation"]

    # Heuristic: precise amounts (lots of digits, not round) are fingerprints
    precise: list[BridgeTx] = []
    for t in seq.txs:
        v = t.amount_value
        # If amount has >3 significant decimals beyond round denominations, suspect
        is_round = any(abs(v - r) < 0.01 for r in [0.1, 0.5, 1.0, 5.0, 10.0, 100.0, 1000.0])
        digits_after_decimal = len(str(v).split(".")[-1]) if "." in str(v) else 0
        if not is_round and digits_after_decimal > 3:
            precise.append(t)

    if precise:
        alerts.append(RiskAlert(
            heuristic_id="H2",
            heuristic_name=h["name"],
            severity=h["severity"],
            confidence=0.75,
            signal=(
                f"{len(precise)} bridge tx(s) use unique amounts (e.g., {precise[0].amount_value} {precise[0].amount_token}) "
                f"— fingerprint linkable across chains"
            ),
            recommendation=(
                "Round bridge amounts to standard denominations or use a bridge that splits into "
                "many small transfers (amount_splitter skill)."
            ),
            skill="amount_splitter",
            action="warn",
        ))
    return alerts


def check_h3_bridge_sequence_fingerprint(seq: BridgeSequence, profile: dict) -> list[RiskAlert]:
    """H3: Sequence of bridges (e.g., L1→Arbitrum→Optimism→Base) is itself a fingerprint."""
    alerts: list[RiskAlert] = []
    h = profile["heuristics"]["H3_bridge_sequence_fingerprint"]

    if len(seq.txs) < 2:
        return alerts

    # Sort by timestamp
    txs_sorted = sorted(seq.txs, key=lambda t: t.timestamp)
    # Look for short-delay chains
    short_delays = sum(
        1 for i in range(1, len(txs_sorted))
        if (txs_sorted[i].timestamp - txs_sorted[i-1].timestamp) < SHORT_BRIDGE_DELAY_SECS
    )

    if short_delays >= 1:
        chains = " → ".join(t.dest_chain for t in txs_sorted)
        alerts.append(RiskAlert(
            heuristic_id="H3",
            heuristic_name=h["name"],
            severity=h["severity"],
            confidence=0.80,
            signal=(
                f"Bridge sequence with {short_delays} short-delay (<{SHORT_BRIDGE_DELAY_SECS}s) "
                f"hops: {chains} — temporal sequencing fingerprints the user"
            ),
            recommendation=(
                "Add random delays between bridge legs (hours, not seconds). Ideally interleave with "
                "unrelated activity on each chain so the bridge sequence is not a coherent burst."
            ),
            skill="bridge_monitor",
            action="warn",
        ))
    return alerts


def check_h4_gas_funding_post_bridge(seq: BridgeSequence, profile: dict) -> list[RiskAlert]:
    """H4: Destination-chain gas funded from a linkable source — recovers the link."""
    alerts: list[RiskAlert] = []
    h = profile["heuristics"]["H4_gas_funding_post_bridge"]

    for t in seq.txs:
        if t.dest_gas_funding_via_paymaster:
            continue
        # If destination address received gas from the same sender's chain, that's a link
        if t.dest_gas_funded_from and t.dest_gas_funded_from.lower() == t.sender_address.lower():
            alerts.append(RiskAlert(
                heuristic_id="H4",
                heuristic_name=h["name"],
                severity="critical",
                confidence=0.95,
                signal=(
                    f"Destination address {t.receiver_address} received gas from the SOURCE address "
                    f"{t.sender_address} — identity-link recovered post-bridge"
                ),
                recommendation=(
                    "Use a paymaster (sponsored gas) on the destination chain, or fund destination "
                    "gas via an unrelated channel (CEX withdrawal, peer transfer to fresh address)."
                ),
                skill="address_separator",
                action="block",
            ))
        elif t.dest_gas_funded_from:
            # gas from a different but possibly traceable address
            alerts.append(RiskAlert(
                heuristic_id="H4",
                heuristic_name=h["name"],
                severity="high",
                confidence=0.70,
                signal=(
                    f"Destination gas funded from {t.dest_gas_funded_from}; verify this address has "
                    f"no on-chain link to {t.sender_address}"
                ),
                recommendation=(
                    "Prefer a paymaster service (no on-chain funding trail). If self-funding, ensure "
                    "the funding address has zero overlap with source-chain history."
                ),
                skill="address_separator",
                action="warn",
            ))
    return alerts


def check_h5_nft_token_bridge_linkage(seq: BridgeSequence, profile: dict) -> list[RiskAlert]:
    """H5: NFT/token-id-bearing bridge — token id itself is a fingerprint across chains."""
    alerts: list[RiskAlert] = []
    h = profile["heuristics"]["H5_nft_token_bridge_linkage"]

    nft_txs = [t for t in seq.txs if t.bundles_nft]
    if nft_txs:
        # NFT collection + token id are 1-of-1 identity carriers
        for t in nft_txs:
            alerts.append(RiskAlert(
                heuristic_id="H5",
                heuristic_name=h["name"],
                severity="critical",
                confidence=0.95,
                signal=(
                    f"NFT bridge: collection {t.nft_collection} token #{t.nft_token_id} bridged "
                    f"{t.source_chain}→{t.dest_chain} — token ID is a permanent cross-chain link"
                ),
                recommendation=(
                    "Avoid bridging NFTs. If essential, use a wrapper that mints a new token ID on "
                    "destination (breaks cross-chain identity carry)."
                ),
                action="block",
            ))
            break  # one is enough to show
    return alerts


# ---------------------------------------------------------------------------
# Main analyzer
# ---------------------------------------------------------------------------

def analyze_sequence(seq: BridgeSequence, profile: dict) -> AnalysisResult:
    result = AnalysisResult(sequence=seq)

    checks = [
        check_h1_same_address_bridge(seq, profile),
        check_h2_amount_correlation(seq, profile),
        check_h3_bridge_sequence_fingerprint(seq, profile),
        check_h4_gas_funding_post_bridge(seq, profile),
        check_h5_nft_token_bridge_linkage(seq, profile),
    ]
    for alerts in checks:
        result.alerts.extend(alerts)

    if any(a.action == "block" and a.confidence >= 0.85 for a in result.alerts):
        result.overall_risk = "critical"
    elif any(a.severity == "critical" for a in result.alerts):
        result.overall_risk = "high"
    elif any(a.severity == "high" for a in result.alerts):
        result.overall_risk = "medium"
    elif result.alerts:
        result.overall_risk = "low"
    return result


def format_result(r: AnalysisResult) -> str:
    s = r.sequence
    lines = [
        f"--- Bridge Linkage Risk: {r.overall_risk.upper()} ---",
        f"User: {s.user_address}",
        f"Bridge txs: {len(s.txs)}",
    ]
    for t in s.txs[:5]:
        lines.append(f"  - {t.bridge_protocol}: {t.source_chain}→{t.dest_chain}, "
                     f"{t.amount_value} {t.amount_token}, sender→receiver: "
                     f"{t.sender_address}→{t.receiver_address}")
    lines.append(f"Alerts: {len(r.alerts)}")
    for a in r.alerts:
        lines.append(f"\n  [{a.heuristic_id}] {a.heuristic_name} ({a.severity}, conf {a.confidence:.0%}, action: {a.action})")
        lines.append(f"    Signal: {a.signal}")
        lines.append(f"    Action: {a.recommendation}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Benchmark
# ---------------------------------------------------------------------------

def generate_synthetic_dataset(n: int = 100, seed: int = 42) -> list[BridgeSequence]:
    rng = random.Random(seed)
    sequences: list[BridgeSequence] = []
    bridges = ["Hop", "Across", "Stargate", "Native_Arbitrum", "Native_Optimism"]
    for i in range(n):
        leaks = rng.random() < 0.55
        n_tx = rng.randint(1, 4)
        user = f"0xuser{i:038x}"
        txs = []
        ts = 1730000000 + rng.randint(0, 86400 * 30)
        for j in range(n_tx):
            same_addr = leaks and rng.random() < 0.40
            sender = user if rng.random() < 0.7 else f"0xsource{i:034x}{j:01x}"
            receiver = sender if same_addr else f"0xdest{i:036x}{j:01x}"
            amount = rng.choice([0.1, 0.5, 1.0, 100.0]) if not leaks or rng.random() < 0.3 else round(rng.uniform(0.001, 50.0), 6)
            ts += rng.randint(60, 600) if leaks else rng.randint(3600, 86400)
            gas_funded = sender if (leaks and rng.random() < 0.40) else ""
            paymaster = (not gas_funded) and rng.random() < 0.40
            has_nft = leaks and rng.random() < 0.10
            txs.append(BridgeTx(
                tx_id=f"tx{i:03d}-{j}",
                bridge_protocol=rng.choice(bridges),
                source_chain="ethereum",
                dest_chain=rng.choice(["arbitrum", "optimism", "base", "polygon"]),
                sender_address=sender,
                receiver_address=receiver,
                amount_token=rng.choice(["ETH", "USDC"]),
                amount_value=amount,
                amount_usd=amount * (3000 if amount < 50 else 1),
                timestamp=ts,
                dest_gas_funded_from=gas_funded,
                dest_gas_funding_timestamp=ts + 60 if gas_funded else 0,
                dest_gas_funding_via_paymaster=paymaster,
                bundles_nft=has_nft,
                nft_collection="0xBoredApe" if has_nft else "",
                nft_token_id=rng.randint(1, 9999) if has_nft else 0,
            ))
        sequences.append(BridgeSequence(user_address=user, txs=txs))
    return sequences


def run_benchmark(profile: dict, n: int = 1000) -> dict:
    sequences = generate_synthetic_dataset(n)

    def has_leak(seq: BridgeSequence) -> bool:
        for t in seq.txs:
            if t.sender_address.lower() == t.receiver_address.lower():
                return True
            if t.dest_gas_funded_from and t.dest_gas_funded_from.lower() == t.sender_address.lower():
                return True
            if t.bundles_nft:
                return True
        return False

    results = [(s, analyze_sequence(s, profile)) for s in sequences]
    tp = fp = tn = fn = 0
    for s, r in results:
        leak = has_leak(s)
        flagged = r.overall_risk in ("critical", "high")
        if flagged and leak:
            tp += 1
        elif flagged and not leak:
            fp += 1
        elif not flagged and leak:
            fn += 1
        else:
            tn += 1
    total_l = tp + fn
    total_safe = tn + fp
    return {
        "n_sequences": n,
        "leaky_in_dataset": total_l,
        "true_positive": tp,
        "false_positive": fp,
        "true_negative": tn,
        "false_negative": fn,
        "true_positive_rate": f"{tp / total_l:.1%}" if total_l else "n/a",
        "false_positive_rate": f"{fp / total_safe:.1%}" if total_safe else "n/a",
    }


# ---------------------------------------------------------------------------
# Examples
# ---------------------------------------------------------------------------

def run_examples(profile: dict):
    examples = [
        ("Privacy-preserving: fresh dest address + paymaster + round amount + delayed", BridgeSequence(
            user_address="0xprivate",
            txs=[BridgeTx(
                tx_id="ok01", bridge_protocol="Across",
                source_chain="ethereum", dest_chain="arbitrum",
                sender_address="0xL1addr", receiver_address="0xfreshL2",
                amount_token="ETH", amount_value=1.0, amount_usd=3000,
                timestamp=1730000000,
                dest_gas_funding_via_paymaster=True,
            )],
        )),
        ("LEAK: same address L1 ↔ L2", BridgeSequence(
            user_address="0xleak1",
            txs=[BridgeTx(
                tx_id="leak01", bridge_protocol="Hop",
                source_chain="ethereum", dest_chain="optimism",
                sender_address="0xSAME", receiver_address="0xSAME",
                amount_token="USDC", amount_value=5000, amount_usd=5000,
                timestamp=1730000000,
            )],
        )),
        ("LEAK: gas funded from sender", BridgeSequence(
            user_address="0xleak2",
            txs=[BridgeTx(
                tx_id="leak02", bridge_protocol="Stargate",
                source_chain="ethereum", dest_chain="base",
                sender_address="0xL1user", receiver_address="0xfreshL2",
                amount_token="ETH", amount_value=2.0, amount_usd=6000,
                timestamp=1730000000,
                dest_gas_funded_from="0xL1user",
                dest_gas_funding_timestamp=1730000060,
            )],
        )),
        ("LEAK: precise amount + short sequence + multi-chain", BridgeSequence(
            user_address="0xleak3",
            txs=[
                BridgeTx(tx_id="seq01", bridge_protocol="Across",
                         source_chain="ethereum", dest_chain="arbitrum",
                         sender_address="0xL1", receiver_address="0xfresh1",
                         amount_token="ETH", amount_value=1.234567, amount_usd=3704,
                         timestamp=1730000000),
                BridgeTx(tx_id="seq02", bridge_protocol="Hop",
                         source_chain="arbitrum", dest_chain="optimism",
                         sender_address="0xfresh1", receiver_address="0xfresh2",
                         amount_token="ETH", amount_value=1.234567, amount_usd=3704,
                         timestamp=1730000180),  # 3 min later
            ],
        )),
        ("LEAK: NFT bridge with token id", BridgeSequence(
            user_address="0xleak4",
            txs=[BridgeTx(
                tx_id="nft01", bridge_protocol="Native_Arbitrum",
                source_chain="ethereum", dest_chain="arbitrum",
                sender_address="0xL1", receiver_address="0xfresh",
                amount_token="ETH", amount_value=0, amount_usd=0,
                timestamp=1730000000,
                bundles_nft=True,
                nft_collection="0xBoredApe",
                nft_token_id=4242,
            )],
        )),
    ]
    for name, s in examples:
        print(f"\n{'='*60}")
        print(f"Scenario: {name}")
        print(f"{'='*60}")
        print(format_result(analyze_sequence(s, profile)))


def main():
    profile_path = Path(__file__).parent / "profile.json"
    profile = load_profile(profile_path)
    if "--benchmark" in sys.argv:
        print("Running L2 bridge linkage benchmark (1000 synthetic sequences)...")
        print(json.dumps(run_benchmark(profile), indent=2))
    else:
        print(f"L2 Bridge Linkage Analyzer v{profile['meta']['version']}")
        print(f"Profile: {profile['meta']['domain_name']}")
        run_examples(profile)


if __name__ == "__main__":
    main()
