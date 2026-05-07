"""
Wrong Chain / Address Analyzer — profile-based pre-send transfer validation.

Loads wrong_chain_address/profile.json and evaluates a pending transfer against
5 heuristics (H1-H5): no activity on target chain, contract cannot receive,
address poisoning, chain ID mismatch, deprecated contract.

This is a DEMO / preliminary implementation. Production version would:
- Pull recipient on-chain history per chain via RPC / indexer (Etherscan, Covalent)
- Pull bytecode + verified-source flags via block explorer
- Inspect address book + transaction history for poisoning signals
- Read live chain ID via wallet provider; compare to user-selected network
- Pull contract pause / migration state via standard event scanners

Usage:
    python analyzer.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# Common EIP-155 chain IDs for the wallet-targeted network sanity check.
CHAIN_NAMES_BY_ID = {
    1: "ethereum",
    10: "optimism",
    56: "bsc",
    100: "gnosis",
    137: "polygon",
    8453: "base",
    42161: "arbitrum",
    43114: "avalanche",
    324: "zksync",
    534352: "scroll",
    59144: "linea",
}


@dataclass
class TransferIntent:
    """A pending transfer being validated before broadcast."""
    tx_hash: str
    user_address: str
    recipient_address: str
    intended_target_chain_id: int
    intended_target_chain_name: str
    signing_chain_id: int

    # Per-chain activity counts (mapping chain_name -> tx_count)
    recipient_tx_count_on_target_chain: int = 0
    recipient_tx_count_on_other_chains: dict[str, int] = field(default_factory=dict)

    # Contract-shaped checks
    recipient_is_contract: bool = False
    recipient_implements_receive: bool = True
    recipient_implements_erc20_receiver: bool = True
    user_expects_eoa: bool = False  # wallet inferred destination should be EOA

    # Poisoning signals
    recipient_lookalike_in_history: Optional[str] = None  # the prior real address
    recipient_address_distance: Optional[str] = None
    recent_dust_from_lookalike: bool = False

    # ENS
    ens_name_resolved: Optional[str] = None
    ens_typed_address: Optional[str] = None  # if user typed an explicit address along with ENS

    # Deprecated contract
    recipient_paused: bool = False
    recipient_migrated_to: Optional[str] = None
    recipient_last_activity_age_days: int = 0

    # Token / value
    token_being_sent: str = ""
    amount_value_usd: float = 0.0
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
    action: Optional[str] = None  # block | warn | inform


@dataclass
class AnalysisResult:
    transfer: TransferIntent
    alerts: list[RiskAlert] = field(default_factory=list)
    overall_risk: str = "low"
    should_block: bool = False


def load_profile(path: str | Path) -> dict:
    with open(path) as f:
        return json.load(f)


def _is_eip55_checksum_valid(address: str) -> bool:
    """Conservative EIP-55 checksum check. Returns True for all-lower or all-upper hex (legacy)."""
    if not address.startswith("0x") or len(address) != 42:
        return False
    body = address[2:]
    if body == body.lower() or body == body.upper():
        return True  # legacy non-checksummed; not invalid by EIP-55
    # Mixed case: would need keccak; without crypto deps assume well-formed unless obviously not
    if not all(c in "0123456789abcdefABCDEF" for c in body):
        return False
    return True


def check_h1_no_activity_on_target_chain(t: TransferIntent, profile: dict) -> list[RiskAlert]:
    if t.recipient_tx_count_on_target_chain > 0:
        return []
    other_total = sum(t.recipient_tx_count_on_other_chains.values())
    if other_total == 0:
        # Brand-new address everywhere — different signal (covered partly by H3 age check)
        return []

    h = profile["heuristics"]["H1_no_activity_on_target_chain"]
    other_chains = ", ".join(sorted(t.recipient_tx_count_on_other_chains.keys()))
    return [
        RiskAlert(
            heuristic_id="H1",
            heuristic_name=h["name"],
            severity=h["severity"],
            confidence=0.85,
            signal=(
                f"Recipient has 0 txs on {t.intended_target_chain_name} but "
                f"{other_total} txs across other chains ({other_chains}); likely wrong-chain send."
            ),
            recommendation="Confirm chain with recipient. Send a minimal test amount before transferring full value.",
            skill="chain_checker",
            action="warn",
        )
    ]


def check_h2_contract_cannot_receive(t: TransferIntent, profile: dict) -> list[RiskAlert]:
    if not t.recipient_is_contract:
        # If user expected a contract but got an EOA, surface a soft signal
        if t.user_expects_eoa is False and t.recipient_tx_count_on_target_chain == 0:
            return []
        return []

    h = profile["heuristics"]["H2_contract_cannot_receive"]
    alerts: list[RiskAlert] = []

    if t.user_expects_eoa:
        alerts.append(
            RiskAlert(
                heuristic_id="H2",
                heuristic_name=h["name"],
                severity="high",
                confidence=0.80,
                signal="Recipient is a CONTRACT but the wallet inferred user expected an EOA (transfer recipient).",
                recommendation="Re-verify recipient identity; sending to an unexpected contract risks locked funds.",
                skill="contract_status_checker",
                action="warn",
            )
        )

    if not t.recipient_implements_receive and not t.recipient_implements_erc20_receiver:
        alerts.append(
            RiskAlert(
                heuristic_id="H2",
                heuristic_name=h["name"],
                severity=h["severity"],
                confidence=0.95,
                signal="Recipient contract implements neither receive()/fallback() nor an ERC-20/721 receiver — funds will be permanently locked.",
                recommendation="BLOCK the transfer. If contract has a deposit() function, use that instead.",
                skill="contract_status_checker",
                action="block",
            )
        )
    return alerts


def check_h3_address_poisoning(t: TransferIntent, profile: dict) -> list[RiskAlert]:
    if not t.recipient_lookalike_in_history:
        return []

    h = profile["heuristics"]["H3_address_poisoning"]
    severity = h["severity"]
    confidence = 0.85
    if t.recent_dust_from_lookalike:
        confidence = 0.95

    return [
        RiskAlert(
            heuristic_id="H3",
            heuristic_name=h["name"],
            severity=severity,
            confidence=confidence,
            signal=(
                f"Recipient {t.recipient_address} is a lookalike of prior contact "
                f"{t.recipient_lookalike_in_history} ({t.recipient_address_distance or 'similar prefix/suffix'})"
                + ("; recent dust from lookalike confirms poisoning campaign." if t.recent_dust_from_lookalike else ".")
            ),
            recommendation="BLOCK. Re-verify recipient address through a second channel; never copy from transaction history.",
            skill="address_validator",
            action="block",
        )
    ]


def check_h4_chain_id_mismatch(t: TransferIntent, profile: dict) -> list[RiskAlert]:
    alerts: list[RiskAlert] = []
    h = profile["heuristics"]["H4_chain_id_mismatch"]

    if t.signing_chain_id != t.intended_target_chain_id:
        signed_name = CHAIN_NAMES_BY_ID.get(t.signing_chain_id, f"chain-{t.signing_chain_id}")
        alerts.append(
            RiskAlert(
                heuristic_id="H4",
                heuristic_name=h["name"],
                severity=h["severity"],
                confidence=0.98,
                signal=(
                    f"Wallet is signing with chain id {t.signing_chain_id} ({signed_name}) but user intends "
                    f"{t.intended_target_chain_id} ({t.intended_target_chain_name})."
                ),
                recommendation="BLOCK. Switch wallet to the correct network before signing.",
                skill="chain_checker",
                action="block",
            )
        )

    if not _is_eip55_checksum_valid(t.recipient_address):
        alerts.append(
            RiskAlert(
                heuristic_id="H4",
                heuristic_name=h["name"],
                severity="medium",
                confidence=0.80,
                signal=f"Recipient address {t.recipient_address} fails EIP-55 checksum validation.",
                recommendation="Re-enter or re-check the address; bad checksum suggests typo or copy error.",
                skill="address_validator",
                action="warn",
            )
        )

    if t.ens_name_resolved and t.ens_typed_address and t.ens_name_resolved.lower() != t.ens_typed_address.lower():
        alerts.append(
            RiskAlert(
                heuristic_id="H4",
                heuristic_name=h["name"],
                severity="high",
                confidence=0.90,
                signal=(
                    f"ENS resolution mismatch: typed {t.ens_typed_address} but ENS resolved to {t.ens_name_resolved}."
                ),
                recommendation="Confirm intended recipient. ENS may have been re-pointed; do not assume the typed address matches.",
                skill="address_validator",
                action="warn",
            )
        )

    return alerts


def check_h5_deprecated_contract(t: TransferIntent, profile: dict) -> list[RiskAlert]:
    if not t.recipient_is_contract:
        return []

    h = profile["heuristics"]["H5_deprecated_contract"]
    alerts: list[RiskAlert] = []

    if t.recipient_paused:
        alerts.append(
            RiskAlert(
                heuristic_id="H5",
                heuristic_name=h["name"],
                severity=h["severity"],
                confidence=0.90,
                signal="Recipient contract is paused; interactions will revert or have undefined behavior.",
                recommendation="Do not send. Wait for unpause or use migrated contract.",
                skill="contract_status_checker",
                action="warn",
            )
        )

    if t.recipient_migrated_to:
        alerts.append(
            RiskAlert(
                heuristic_id="H5",
                heuristic_name=h["name"],
                severity=h["severity"],
                confidence=0.85,
                signal=f"Recipient contract has migrated to {t.recipient_migrated_to}.",
                recommendation=f"Send to the new contract at {t.recipient_migrated_to} instead.",
                skill="contract_status_checker",
                action="warn",
            )
        )

    if t.recipient_last_activity_age_days >= 90 and not t.recipient_paused and not t.recipient_migrated_to:
        alerts.append(
            RiskAlert(
                heuristic_id="H5",
                heuristic_name=h["name"],
                severity="medium",
                confidence=0.60,
                signal=f"Recipient contract has had no activity in {t.recipient_last_activity_age_days} days; possibly abandoned.",
                recommendation="Verify contract is still in active use before sending value.",
                skill="contract_status_checker",
                action="inform",
            )
        )

    return alerts


_CHECKS = [
    check_h1_no_activity_on_target_chain,
    check_h2_contract_cannot_receive,
    check_h3_address_poisoning,
    check_h4_chain_id_mismatch,
    check_h5_deprecated_contract,
]


def analyze_transfer(transfer: TransferIntent, profile: dict) -> AnalysisResult:
    alerts: list[RiskAlert] = []
    for chk in _CHECKS:
        alerts.extend(chk(transfer, profile))

    severity_rank = {"low": 1, "medium": 2, "high": 3, "critical": 4}
    overall = "low"
    block = False
    for a in alerts:
        if severity_rank.get(a.severity, 0) > severity_rank.get(overall, 0):
            overall = a.severity
        if a.action == "block":
            block = True

    return AnalysisResult(transfer=transfer, alerts=alerts, overall_risk=overall, should_block=block)


# ---------------------------------------------------------------------------
# Local self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    profile_path = Path(__file__).parent / "profile.json"
    profile = load_profile(profile_path)

    bad = TransferIntent(
        tx_hash="0xtest1",
        user_address="0xUser0000000000000000000000000000000000Sender",
        recipient_address="0xRecipient00000000000000000000000Lookalike",
        intended_target_chain_id=137,
        intended_target_chain_name="polygon",
        signing_chain_id=1,
        recipient_tx_count_on_target_chain=0,
        recipient_tx_count_on_other_chains={"ethereum": 1284, "arbitrum": 540},
        recipient_is_contract=True,
        recipient_implements_receive=False,
        recipient_implements_erc20_receiver=False,
        recipient_lookalike_in_history="0xRecipient00000000000000000000000Original",
        recipient_address_distance="first 6 chars + last 4 chars match",
        recent_dust_from_lookalike=True,
        recipient_paused=True,
        recipient_migrated_to="0xNewVersion000000000000000000000000000v2",
        recipient_last_activity_age_days=900,
        token_being_sent="USDC",
        amount_value_usd=50000.0,
    )
    print("=== Worst-case ===")
    res = analyze_transfer(bad, profile)
    print(f"overall={res.overall_risk} block={res.should_block} alerts={len(res.alerts)}")
    for a in res.alerts:
        print(f"  [{a.severity}] {a.heuristic_id}: {a.signal[:80]}")

    good = TransferIntent(
        tx_hash="0xtest2",
        user_address="0xUserClean",
        recipient_address="0x71C7656EC7ab88b098defB751B7401B5f6d8976F",
        intended_target_chain_id=1,
        intended_target_chain_name="ethereum",
        signing_chain_id=1,
        recipient_tx_count_on_target_chain=420,
        recipient_tx_count_on_other_chains={},
        recipient_is_contract=False,
        recipient_implements_receive=True,
        recipient_implements_erc20_receiver=True,
    )
    print("\n=== Healthy ===")
    res = analyze_transfer(good, profile)
    print(f"overall={res.overall_risk} block={res.should_block} alerts={len(res.alerts)}")
