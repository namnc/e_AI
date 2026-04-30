"""
Off-chain Signature Phishing Analyzer — profile-based signature request analysis.

Loads offchain_signature/profile.json and evaluates signature requests against
6 heuristics (H1-H6) covering Permit2 unlimited, EIP-712 disguised transfers,
setApprovalForAll to unknown operators, unverified dApp origin, batch permits,
and Seaport below-market orders.

This is a DEMO / preliminary implementation. Production version would:
- Decode EIP-712 typed data via wallet RPC (eth_signTypedData_v4 inspection)
- Verify dApp origin via curated registries (DeFi Llama, Etherscan)
- Check homoglyph similarity to known protocol domains
- Query NFT marketplace floor prices (OpenSea, Blur, Reservoir)
- Cross-check Permit2 spender against verified contract registry

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

PERMIT2_MAX_AMOUNT = (1 << 160) - 1      # MAX_UINT160
PERMIT2_UNLIMITED_THRESHOLD = (1 << 159)  # H1 unlimited threshold per profile
LONG_EXPIRY_DAYS = 30                    # H1 long expiry threshold

# Known marketplace operators (NFT setApprovalForAll legitimate targets)
KNOWN_NFT_MARKETPLACES = {
    "0x00000000006c3852cbef3e08e8df289169ede581",  # OpenSea Seaport 1.1
    "0x00000000000000adc04c56bf30ac9d3c0aaf14dc",  # OpenSea Seaport 1.5
    "0x000000000000ad05ccc4f10045630fb830b95127",  # Blur Marketplace
    "0x59728544b08ab483533076417fbbb2fd0b17ce3a",  # LooksRare
    "0x39da41747a83aee658334415666f3ef92dd0d541",  # X2Y2
}

# Known protocol domains (should be in registry; phishing copies are not)
KNOWN_PROTOCOL_DOMAINS = {
    "uniswap.org", "app.uniswap.org",
    "opensea.io",
    "blur.io",
    "1inch.io", "app.1inch.io",
    "cow.fi", "swap.cow.fi",
    "aave.com", "app.aave.com",
    "compound.finance",
    "curve.fi",
    "lido.fi",
}

# EIP-712 primary types that encode transfer/approval semantics
TRANSFER_PRIMARY_TYPES = {
    "Permit",          # EIP-2612
    "PermitSingle",    # Permit2
    "PermitBatch",     # Permit2 batch
    "PermitTransferFrom",
    "PermitBatchTransferFrom",
    "OrderComponents", # Seaport
    "ERC20Transfer",
    "ERC721Transfer",
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class SignatureRequest:
    """An off-chain signature request to analyze."""
    request_id: str
    user_address: str
    dapp_origin: str                  # URL of requesting dApp
    signature_type: str               # "permit2_single" | "permit2_batch" | "eip712" | "seaport" | "setApprovalForAll"

    # EIP-712 generic
    primary_type: str = ""
    typed_data: dict = field(default_factory=dict)
    eip712_domain_separator: str = ""

    # Permit2 / EIP-2612
    spender_address: str = ""
    approval_amount: int = 0
    expiry_seconds: int = 0           # absolute timestamp; 0 = no expiry
    spender_in_protocol_registry: bool = True
    token_address: str = ""

    # Permit2 batch (H5)
    batch_tokens: list[dict] = field(default_factory=list)  # [{token, amount, value_usd}, ...]

    # setApprovalForAll (H3)
    nft_collection_address: str = ""
    operator_address: str = ""
    operator_in_marketplace_registry: bool = True
    operator_creation_timestamp: int = 0

    # Seaport (H6)
    seaport_offer_assets: list[dict] = field(default_factory=list)   # [{token, amount, value_usd}, ...]
    seaport_consideration_eth: float = 0.0
    seaport_collection_floor_eth: float = 0.0
    seaport_total_offer_value_usd: float = 0.0

    # H2 mismatch
    ui_description: str = ""           # what the dApp's UI says the action is
    payload_semantic: str = ""         # decoded semantic: "login" | "transfer" | "approval" | "order"

    # H4 origin
    domain_in_protocol_registry: bool = True
    domain_age_days: int = 999
    is_homoglyph_of_known: bool = False

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
    request: SignatureRequest
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

def check_h1_permit2_unlimited_expiry(req: SignatureRequest, profile: dict) -> list[RiskAlert]:
    """H1: Permit2 unlimited amount or long expiry to unknown spender."""
    alerts: list[RiskAlert] = []
    h = profile["heuristics"]["H1_permit2_unlimited_expiry"]

    if req.signature_type not in ("permit2_single", "permit2_batch"):
        return alerts

    is_unlimited = req.approval_amount >= PERMIT2_UNLIMITED_THRESHOLD
    days_until_expiry = max(0, (req.expiry_seconds - req.current_timestamp) / 86400) if req.expiry_seconds else 1e9
    is_long_expiry = days_until_expiry > LONG_EXPIRY_DAYS
    spender_unknown = not req.spender_in_protocol_registry

    # BLOCK threshold: max_amount AND unknown_spender
    if is_unlimited and spender_unknown:
        alerts.append(RiskAlert(
            heuristic_id="H1",
            heuristic_name=h["name"],
            severity="critical",
            confidence=0.95,
            signal=(
                f"Permit2 unlimited amount ({req.approval_amount}) to UNKNOWN spender "
                f"{req.spender_address} — high phishing risk"
            ),
            recommendation=h["recommendations"][1]["description"],
            skill="dapp_verifier",
            action="block",
        ))
    elif is_unlimited:
        alerts.append(RiskAlert(
            heuristic_id="H1",
            heuristic_name=h["name"],
            severity="high",
            confidence=0.85,
            signal=f"Permit2 unlimited amount to {req.spender_address}",
            recommendation=h["recommendations"][0]["description"],
            skill="signature_decoder",
            action="warn",
        ))
    elif is_long_expiry and spender_unknown:
        alerts.append(RiskAlert(
            heuristic_id="H1",
            heuristic_name=h["name"],
            severity="high",
            confidence=0.80,
            signal=(
                f"Permit2 long expiry ({days_until_expiry:.0f} days) to unknown spender — "
                f"persistent phishing exposure"
            ),
            recommendation=h["recommendations"][0]["description"],
            skill="signature_decoder",
            action="warn",
        ))
    elif is_long_expiry:
        alerts.append(RiskAlert(
            heuristic_id="H1",
            heuristic_name=h["name"],
            severity="medium",
            confidence=0.65,
            signal=f"Permit2 expiry set {days_until_expiry:.0f} days out (>{LONG_EXPIRY_DAYS}d threshold)",
            recommendation=h["recommendations"][0]["description"],
            skill="signature_decoder",
            action="inform",
        ))
    return alerts


def check_h2_eip712_disguised_transfer(req: SignatureRequest, profile: dict) -> list[RiskAlert]:
    """H2: EIP-712 typed data encoding transfer or approval; UI mismatch."""
    alerts: list[RiskAlert] = []
    h = profile["heuristics"]["H2_eip712_disguised_transfer"]

    if req.signature_type not in ("eip712", "permit2_single", "permit2_batch", "seaport"):
        return alerts

    is_transfer_type = req.primary_type in TRANSFER_PRIMARY_TYPES
    has_transfer_fields = bool(req.typed_data and any(
        k in str(req.typed_data).lower() for k in ("recipient", "amount", "value", "spender", "deadline")
    ))

    ui_says_benign = req.ui_description.lower() in ("login", "verify identity", "sign in", "connect", "")
    payload_actually = req.payload_semantic in ("transfer", "approval", "order", "permit")
    mismatch = ui_says_benign and payload_actually

    if (is_transfer_type or has_transfer_fields) and mismatch:
        alerts.append(RiskAlert(
            heuristic_id="H2",
            heuristic_name=h["name"],
            severity="critical",
            confidence=0.90,
            signal=(
                f"UI says '{req.ui_description}' but payload encodes {req.payload_semantic} "
                f"(primary_type: {req.primary_type})"
            ),
            recommendation=h["recommendations"][1]["description"],
            skill="signature_decoder",
            action="block",
        ))
    elif is_transfer_type:
        alerts.append(RiskAlert(
            heuristic_id="H2",
            heuristic_name=h["name"],
            severity="high",
            confidence=0.85,
            signal=f"EIP-712 primary_type '{req.primary_type}' encodes transfer/approval semantics",
            recommendation=h["recommendations"][0]["description"],
            skill="signature_decoder",
            action="warn",
        ))
    return alerts


def check_h3_setApprovalForAll_unknown(req: SignatureRequest, profile: dict) -> list[RiskAlert]:
    """H3: setApprovalForAll to unknown operator (NFT collection-wide approval)."""
    alerts: list[RiskAlert] = []
    h = profile["heuristics"]["H3_setApprovalForAll_unknown"]

    if req.signature_type != "setApprovalForAll":
        return alerts

    operator_known = (
        req.operator_address.lower() in {a.lower() for a in KNOWN_NFT_MARKETPLACES}
        or req.operator_in_marketplace_registry
    )
    is_recent = (
        req.operator_creation_timestamp > 0
        and req.current_timestamp > 0
        and (req.current_timestamp - req.operator_creation_timestamp) < 48 * 3600
    )

    if not operator_known:
        if is_recent:
            alerts.append(RiskAlert(
                heuristic_id="H3",
                heuristic_name=h["name"],
                severity="critical",
                confidence=0.85,
                signal=(
                    f"setApprovalForAll to UNKNOWN, RECENTLY DEPLOYED operator {req.operator_address} "
                    f"for collection {req.nft_collection_address}"
                ),
                recommendation=h["recommendations"][0]["description"],
                skill="dapp_verifier",
                action="block",
            ))
        else:
            alerts.append(RiskAlert(
                heuristic_id="H3",
                heuristic_name=h["name"],
                severity=h["severity"],
                confidence=0.75,
                signal=f"setApprovalForAll to unknown operator {req.operator_address}",
                recommendation=h["recommendations"][0]["description"],
                skill="dapp_verifier",
                action="warn",
            ))
    return alerts


def check_h4_unverified_dapp_origin(req: SignatureRequest, profile: dict) -> list[RiskAlert]:
    """H4: Signature from unverified dApp domain (homoglyph, new, unknown)."""
    alerts: list[RiskAlert] = []
    h = profile["heuristics"]["H4_unverified_dapp_origin"]

    if not req.dapp_origin:
        return alerts

    domain = req.dapp_origin.lower()
    in_known = any(known in domain for known in KNOWN_PROTOCOL_DOMAINS)
    is_unknown = not (in_known or req.domain_in_protocol_registry)
    is_recent = req.domain_age_days < 30

    if req.is_homoglyph_of_known:
        alerts.append(RiskAlert(
            heuristic_id="H4",
            heuristic_name=h["name"],
            severity="critical",
            confidence=0.90,
            signal=f"Domain {domain} is visually similar to a known protocol (homoglyph attack)",
            recommendation=h["recommendations"][0]["description"],
            skill="dapp_verifier",
            action="block",
        ))
    elif is_unknown and is_recent:
        alerts.append(RiskAlert(
            heuristic_id="H4",
            heuristic_name=h["name"],
            severity=h["severity"],
            confidence=0.75,
            signal=f"Domain {domain} unknown AND recently registered ({req.domain_age_days} days old)",
            recommendation=h["recommendations"][0]["description"],
            skill="dapp_verifier",
            action="warn",
        ))
    elif is_unknown:
        alerts.append(RiskAlert(
            heuristic_id="H4",
            heuristic_name=h["name"],
            severity="medium",
            confidence=0.55,
            signal=f"Domain {domain} not in any curated protocol directory",
            recommendation=h["recommendations"][1]["description"],
            action="inform",
        ))
    return alerts


def check_h5_batch_permit(req: SignatureRequest, profile: dict) -> list[RiskAlert]:
    """H5: Permit2 PermitBatch with multiple tokens, high combined value (drainer pattern)."""
    alerts: list[RiskAlert] = []
    h = profile["heuristics"]["H5_batch_permit"]

    if req.signature_type != "permit2_batch":
        return alerts

    n_tokens = len(req.batch_tokens)
    total_value = sum(t.get("value_usd", 0.0) for t in req.batch_tokens)

    if n_tokens >= 2 and total_value > 1000.0:
        # Mixed token type signal — high + low value tokens together
        values = [t.get("value_usd", 0.0) for t in req.batch_tokens]
        mixed = max(values) > 5 * max(min(values), 1.0) if values else False

        confidence = 0.90 if mixed else 0.85
        signal = (
            f"Permit2 batch covers {n_tokens} tokens, combined ${total_value:.0f}"
            + (" (mixed value distribution suggests drainer sweep)" if mixed else "")
        )
        alerts.append(RiskAlert(
            heuristic_id="H5",
            heuristic_name=h["name"],
            severity="critical",
            confidence=confidence,
            signal=signal,
            recommendation=h["recommendations"][0]["description"],
            skill="signature_decoder",
            action="block",
        ))
    elif n_tokens >= 2:
        alerts.append(RiskAlert(
            heuristic_id="H5",
            heuristic_name=h["name"],
            severity="high",
            confidence=0.70,
            signal=f"Permit2 batch covers {n_tokens} tokens (combined ${total_value:.0f})",
            recommendation=h["recommendations"][1]["description"],
            skill="dapp_verifier",
            action="warn",
        ))
    return alerts


def check_h6_seaport_below_market(req: SignatureRequest, profile: dict) -> list[RiskAlert]:
    """H6: Seaport order at near-zero consideration or far below floor price."""
    alerts: list[RiskAlert] = []
    h = profile["heuristics"]["H6_seaport_below_market"]

    if req.signature_type != "seaport":
        return alerts

    consideration = req.seaport_consideration_eth
    floor = req.seaport_collection_floor_eth
    total_offer_usd = req.seaport_total_offer_value_usd
    n_assets = len(req.seaport_offer_assets)

    # Near-zero consideration with valuable offer
    if consideration < 0.001 and total_offer_usd > 100.0:
        alerts.append(RiskAlert(
            heuristic_id="H6",
            heuristic_name=h["name"],
            severity="critical",
            confidence=0.95,
            signal=(
                f"Seaport order: {consideration:.6f} ETH consideration for assets worth "
                f"${total_offer_usd:.0f}"
            ),
            recommendation=h["recommendations"][1]["description"],
            skill="price_checker",
            action="block",
        ))
        return alerts

    # Below floor for single-collection listing
    if floor > 0 and consideration < 0.5 * floor and total_offer_usd > 100.0:
        alerts.append(RiskAlert(
            heuristic_id="H6",
            heuristic_name=h["name"],
            severity=h["severity"],
            confidence=0.85,
            signal=(
                f"Seaport order at {consideration:.3f} ETH (<50% of {floor:.3f} ETH floor) "
                f"for collection {req.nft_collection_address}"
            ),
            recommendation=h["recommendations"][0]["description"],
            skill="price_checker",
            action="warn",
        ))
        return alerts

    # Bulk underpriced
    if n_assets >= 3 and total_offer_usd > 1000.0 and consideration * 4000 < total_offer_usd * 0.3:
        # consideration*4000 ~= consideration USD assuming $4000/ETH; <30% of value
        alerts.append(RiskAlert(
            heuristic_id="H6",
            heuristic_name=h["name"],
            severity="high",
            confidence=0.80,
            signal=(
                f"Seaport bundle of {n_assets} assets (${total_offer_usd:.0f}) for "
                f"{consideration:.3f} ETH — underpriced by >70%"
            ),
            recommendation=h["recommendations"][0]["description"],
            skill="price_checker",
            action="warn",
        ))
    return alerts


# ---------------------------------------------------------------------------
# Main analyzer
# ---------------------------------------------------------------------------

def analyze_signature(req: SignatureRequest, profile: dict) -> AnalysisResult:
    """Run all 6 heuristic checks against an off-chain signature request."""
    result = AnalysisResult(request=req)

    checks = [
        check_h1_permit2_unlimited_expiry(req, profile),
        check_h2_eip712_disguised_transfer(req, profile),
        check_h3_setApprovalForAll_unknown(req, profile),
        check_h4_unverified_dapp_origin(req, profile),
        check_h5_batch_permit(req, profile),
        check_h6_seaport_below_market(req, profile),
    ]
    for alerts in checks:
        result.alerts.extend(alerts)

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
    r = result.request
    lines = [
        f"--- Signature Risk Assessment: {result.overall_risk.upper()} ---",
        f"Request: {r.request_id}",
        f"Type: {r.signature_type}" + (f" / {r.primary_type}" if r.primary_type else ""),
        f"Origin: {r.dapp_origin}",
        f"Alerts: {len(result.alerts)}",
    ]
    if result.should_block:
        lines.append("*** SIGNATURE SHOULD BE BLOCKED ***")
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

def generate_synthetic_dataset(n: int = 100, seed: int = 42) -> list[SignatureRequest]:
    """Generate synthetic signature requests for benchmarking.

    Distribution: 40% legitimate DeFi (Uniswap, OpenSea, 1inch), 60% phishing patterns.
    Phishing breakdown: 25% permit2-unlimited, 15% disguised eip712,
    10% setApprovalForAll-unknown, 25% homoglyph-domain, 15% batch-drain, 10% seaport-cheap.
    """
    rng = random.Random(seed)
    requests: list[SignatureRequest] = []
    now = 1730000000

    legit_origins = list(KNOWN_PROTOCOL_DOMAINS)
    phish_origins = ["un1swap.org", "0pensea.io", "1inсh.io", "drainer.xyz", "free-eth.click"]
    legit_spenders = ["0x" + "1" * 40, "0x" + "a" * 40, "0x" + "b" * 40]

    for i in range(n):
        is_phish = rng.random() < 0.60

        # Pick signature type
        sig_type = rng.choice(["permit2_single", "permit2_batch", "eip712", "seaport", "setApprovalForAll"])
        primary_types_legit = {
            "permit2_single": "PermitSingle",
            "permit2_batch": "PermitBatch",
            "eip712": rng.choice(["LoginMessage", "Vote", "Permit"]),
            "seaport": "OrderComponents",
            "setApprovalForAll": "",
        }
        primary_type = primary_types_legit[sig_type]

        if is_phish:
            origin = rng.choice(phish_origins)
            domain_in_reg = False
            domain_age = rng.randint(1, 30)
            is_homoglyph = rng.random() < 0.50
            spender = "0x" + "f" * 40  # malicious
            spender_in_reg = False
            operator_known = False
            operator_age_h = rng.randint(1, 48)
        else:
            origin = rng.choice(legit_origins)
            domain_in_reg = True
            domain_age = rng.randint(365, 5000)
            is_homoglyph = False
            spender = rng.choice(legit_spenders)
            spender_in_reg = True
            operator_known = True
            operator_age_h = rng.randint(48, 1000)

        if sig_type == "permit2_single":
            amount = PERMIT2_MAX_AMOUNT if (is_phish and rng.random() < 0.85) else rng.randint(10**6, 10**9)
            expiry_days = rng.randint(31, 365) if is_phish else rng.randint(1, 7)
            req = SignatureRequest(
                request_id=f"sig{i:04d}",
                user_address="0xuser",
                dapp_origin=origin,
                signature_type=sig_type,
                primary_type=primary_type,
                payload_semantic="approval",
                ui_description="Approve token spend" if not is_phish else rng.choice(["login", "verify identity", "connect"]),
                spender_address=spender,
                approval_amount=amount,
                expiry_seconds=now + expiry_days * 86400,
                spender_in_protocol_registry=spender_in_reg,
                token_address="0xUSDC",
                domain_in_protocol_registry=domain_in_reg,
                domain_age_days=domain_age,
                is_homoglyph_of_known=is_homoglyph,
                current_timestamp=now,
            )
        elif sig_type == "permit2_batch":
            n_tokens = rng.randint(2, 6) if is_phish else rng.randint(2, 3)
            tokens = [
                {"token": f"0xtok{j:02x}", "amount": PERMIT2_MAX_AMOUNT, "value_usd": rng.uniform(50, 5000)}
                for j in range(n_tokens)
            ]
            req = SignatureRequest(
                request_id=f"sig{i:04d}",
                user_address="0xuser",
                dapp_origin=origin,
                signature_type=sig_type,
                primary_type=primary_type,
                payload_semantic="approval",
                ui_description="Batch approve" if not is_phish else "Sign in",
                spender_address=spender,
                approval_amount=PERMIT2_MAX_AMOUNT,
                spender_in_protocol_registry=spender_in_reg,
                batch_tokens=tokens,
                domain_in_protocol_registry=domain_in_reg,
                domain_age_days=domain_age,
                is_homoglyph_of_known=is_homoglyph,
                current_timestamp=now,
            )
        elif sig_type == "eip712":
            if is_phish:
                primary_type = rng.choice(list(TRANSFER_PRIMARY_TYPES))
                ui = rng.choice(["login", "verify identity", "connect"])
                semantic = rng.choice(["transfer", "approval"])
                td = {"recipient": "0xattacker", "amount": 999999, "spender": spender}
            else:
                primary_type = rng.choice(["LoginMessage", "Vote"])
                ui = "Sign message"
                semantic = "login"
                td = {"nonce": i, "session": "abc"}
            req = SignatureRequest(
                request_id=f"sig{i:04d}",
                user_address="0xuser",
                dapp_origin=origin,
                signature_type=sig_type,
                primary_type=primary_type,
                typed_data=td,
                ui_description=ui,
                payload_semantic=semantic,
                domain_in_protocol_registry=domain_in_reg,
                domain_age_days=domain_age,
                is_homoglyph_of_known=is_homoglyph,
                current_timestamp=now,
            )
        elif sig_type == "seaport":
            n_assets = rng.randint(1, 4)
            offer_value = rng.uniform(500, 10000) * n_assets
            if is_phish:
                consideration = rng.uniform(0.0, 0.001)
            else:
                # Legitimate listing at or near floor price (assume floor ~ avg asset value/4000)
                consideration = (offer_value / 4000) * rng.uniform(0.8, 1.2)
            offer_assets = [
                {"token": f"0xnft{j:02x}", "amount": 1, "value_usd": offer_value / n_assets}
                for j in range(n_assets)
            ]
            floor_eth = (offer_value / n_assets) / 4000
            req = SignatureRequest(
                request_id=f"sig{i:04d}",
                user_address="0xuser",
                dapp_origin=origin,
                signature_type=sig_type,
                primary_type="OrderComponents",
                payload_semantic="order",
                ui_description="List NFT for sale" if not is_phish else "Sign in",
                seaport_offer_assets=offer_assets,
                seaport_consideration_eth=consideration,
                seaport_collection_floor_eth=floor_eth,
                seaport_total_offer_value_usd=offer_value,
                nft_collection_address="0xCollection",
                domain_in_protocol_registry=domain_in_reg,
                domain_age_days=domain_age,
                is_homoglyph_of_known=is_homoglyph,
                current_timestamp=now,
            )
        else:  # setApprovalForAll
            operator = rng.choice(list(KNOWN_NFT_MARKETPLACES)) if not is_phish else "0x" + "f" * 40
            req = SignatureRequest(
                request_id=f"sig{i:04d}",
                user_address="0xuser",
                dapp_origin=origin,
                signature_type=sig_type,
                primary_type="",
                ui_description="List NFT" if not is_phish else "Sign in",
                payload_semantic="approval",
                operator_address=operator,
                operator_in_marketplace_registry=operator_known,
                operator_creation_timestamp=now - operator_age_h * 3600,
                nft_collection_address="0xCollection",
                domain_in_protocol_registry=domain_in_reg,
                domain_age_days=domain_age,
                is_homoglyph_of_known=is_homoglyph,
                current_timestamp=now,
            )
        requests.append(req)

    return requests


def run_benchmark(profile: dict, n: int = 1000) -> dict:
    """TP rate (catch phishing) vs FP rate (false alarm on legit)."""
    requests = generate_synthetic_dataset(n)

    def is_phishing(r: SignatureRequest) -> bool:
        # Ground truth: any of these signals indicate phishing in our synthetic data
        if r.is_homoglyph_of_known:
            return True
        if not r.spender_in_protocol_registry and r.signature_type in ("permit2_single", "permit2_batch"):
            return True
        if r.signature_type == "permit2_batch" and len(r.batch_tokens) >= 4:
            return True
        if r.signature_type == "seaport" and r.seaport_consideration_eth < 0.001 and r.seaport_total_offer_value_usd > 100:
            return True
        if r.signature_type == "setApprovalForAll" and not r.operator_in_marketplace_registry:
            return True
        if r.payload_semantic in ("transfer", "approval") and r.ui_description.lower() in ("login", "verify identity", "connect", "sign in"):
            return True
        return False

    results = [(r, analyze_signature(r, profile)) for r in requests]

    tp = fp = tn = fn = 0
    for r, a in results:
        actually = is_phishing(r)
        flagged = a.should_block or a.overall_risk in ("critical", "high")
        if flagged:
            (tp if actually else fp).__add__  # type: ignore  # placeholder
            if actually:
                tp += 1
            else:
                fp += 1
        else:
            if actually:
                fn += 1
            else:
                tn += 1

    total_phish = tp + fn
    total_legit = tn + fp
    tpr = tp / total_phish if total_phish else 0.0
    fpr = fp / total_legit if total_legit else 0.0

    heuristic_counts: dict[str, int] = {}
    for _, a in results:
        for alert in a.alerts:
            heuristic_counts[alert.heuristic_id] = heuristic_counts.get(alert.heuristic_id, 0) + 1

    return {
        "n_requests": n,
        "phishing_in_dataset": total_phish,
        "legit_in_dataset": total_legit,
        "true_positive": tp,
        "false_positive": fp,
        "true_negative": tn,
        "false_negative": fn,
        "true_positive_rate": f"{tpr:.1%}",
        "false_positive_rate": f"{fpr:.1%}",
        "per_heuristic_alert_count": heuristic_counts,
        "target_per_profile": "TPR >90%, FPR <5%",
    }


# ---------------------------------------------------------------------------
# Example scenarios
# ---------------------------------------------------------------------------

def run_examples(profile: dict):
    now = 1730000000
    examples = [
        ("Good practice: Permit2 single, exact amount, 1h expiry, verified spender", SignatureRequest(
            request_id="ok01",
            user_address="0xuser",
            dapp_origin="app.uniswap.org",
            signature_type="permit2_single",
            primary_type="PermitSingle",
            payload_semantic="approval",
            ui_description="Approve token spend",
            spender_address="0x" + "1" * 40,
            approval_amount=1_000_000,
            expiry_seconds=now + 3600,
            spender_in_protocol_registry=True,
            domain_in_protocol_registry=True,
            domain_age_days=2000,
            current_timestamp=now,
        )),
        ("BAD: Permit2 unlimited to unknown spender from new domain", SignatureRequest(
            request_id="bad01",
            user_address="0xuser",
            dapp_origin="drainer.xyz",
            signature_type="permit2_single",
            primary_type="PermitSingle",
            payload_semantic="approval",
            ui_description="Sign in",
            spender_address="0x" + "f" * 40,
            approval_amount=PERMIT2_MAX_AMOUNT,
            expiry_seconds=now + 365 * 86400,
            spender_in_protocol_registry=False,
            domain_in_protocol_registry=False,
            domain_age_days=3,
            current_timestamp=now,
        )),
        ("WORST: EIP-712 disguised transfer + homoglyph domain", SignatureRequest(
            request_id="worst01",
            user_address="0xuser",
            dapp_origin="un1swap.org",
            signature_type="eip712",
            primary_type="ERC20Transfer",
            typed_data={"recipient": "0xattacker", "amount": 99999, "token": "0xUSDC"},
            payload_semantic="transfer",
            ui_description="Verify identity",
            domain_in_protocol_registry=False,
            domain_age_days=2,
            is_homoglyph_of_known=True,
            current_timestamp=now,
        )),
        ("Batch drain: Permit2 PermitBatch, 5 tokens, $20K combined", SignatureRequest(
            request_id="batch01",
            user_address="0xuser",
            dapp_origin="drainer.xyz",
            signature_type="permit2_batch",
            primary_type="PermitBatch",
            payload_semantic="approval",
            ui_description="connect",
            spender_address="0x" + "f" * 40,
            approval_amount=PERMIT2_MAX_AMOUNT,
            spender_in_protocol_registry=False,
            batch_tokens=[
                {"token": "0xUSDC", "amount": PERMIT2_MAX_AMOUNT, "value_usd": 5000},
                {"token": "0xWETH", "amount": PERMIT2_MAX_AMOUNT, "value_usd": 8000},
                {"token": "0xLINK", "amount": PERMIT2_MAX_AMOUNT, "value_usd": 3000},
                {"token": "0xUNI", "amount": PERMIT2_MAX_AMOUNT, "value_usd": 2500},
                {"token": "0xLDO", "amount": PERMIT2_MAX_AMOUNT, "value_usd": 1500},
            ],
            domain_in_protocol_registry=False,
            domain_age_days=5,
            current_timestamp=now,
        )),
        ("Seaport zero-consideration steal: NFT worth $5K for 0.0001 ETH", SignatureRequest(
            request_id="seaport01",
            user_address="0xuser",
            dapp_origin="0pensea.io",
            signature_type="seaport",
            primary_type="OrderComponents",
            payload_semantic="order",
            ui_description="Sign in to claim airdrop",
            seaport_offer_assets=[{"token": "0xBoredApe", "amount": 1, "value_usd": 5000}],
            seaport_consideration_eth=0.0001,
            seaport_collection_floor_eth=1.25,
            seaport_total_offer_value_usd=5000.0,
            nft_collection_address="0xBoredApe",
            domain_in_protocol_registry=False,
            domain_age_days=10,
            is_homoglyph_of_known=True,
            current_timestamp=now,
        )),
        ("setApprovalForAll to unknown recently-deployed operator", SignatureRequest(
            request_id="nftphish01",
            user_address="0xuser",
            dapp_origin="claim-airdrop.click",
            signature_type="setApprovalForAll",
            primary_type="",
            payload_semantic="approval",
            ui_description="Connect to claim",
            operator_address="0x" + "f" * 40,
            operator_in_marketplace_registry=False,
            operator_creation_timestamp=now - 7200,  # 2h ago
            nft_collection_address="0xValuableCollection",
            domain_in_protocol_registry=False,
            domain_age_days=1,
            current_timestamp=now,
        )),
    ]

    for name, req in examples:
        print(f"\n{'='*60}")
        print(f"Scenario: {name}")
        print(f"{'='*60}")
        result = analyze_signature(req, profile)
        print(format_result(result))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    profile_path = Path(__file__).parent / "profile.json"
    profile = load_profile(profile_path)

    if "--benchmark" in sys.argv:
        print("Running off-chain signature phishing benchmark (1000 synthetic requests)...")
        results = run_benchmark(profile)
        print(json.dumps(results, indent=2))
    else:
        print(f"Off-chain Signature Phishing Analyzer v{profile['meta']['version']}")
        print(f"Profile: {profile['meta']['domain_name']}")
        print(f"Source: {profile['meta']['source_paper']}")
        run_examples(profile)


if __name__ == "__main__":
    main()
