"""
Post-Quantum Readiness Analyzer — profile-based wallet PQ-vulnerability scan.

Loads pq_readiness/profile.json and evaluates a wallet snapshot against 5
heuristics (H1-H5) covering ECDH-only stealth registration, classical-only
smart accounts, on-chain ECDH-encrypted data, BLS threshold participation,
and long-term key reuse.

This is a DEMO / preliminary implementation. Production version would:
- Read ERC-6538 stealth meta-address registry on-chain
- Inspect smart account storage slots and module configuration
- Trace transaction calldata for ephemeral ECDH keys (33-byte secp256k1 points)
- Cross-reference known vulnerable protocols (Tornado, Umbra v1, Railgun v2)
- Track key age and transaction history per address

Note on threat model: HNDL = Harvest Now, Decrypt Later. CRQC timeline ~2030-2035.
All ECDH ciphertexts and BLS signatures already on-chain are permanently exposed.

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

ECDH_EPHEMERAL_KEY_LEN = 33    # compressed secp256k1
MLKEM_768_CIPHERTEXT_LEN = 1088
KEY_AGE_HIGH_DAYS = 730        # 2 years
HIGH_TX_COUNT = 1000
HIGH_VALUE_USD = 100_000.0
HIGH_VALUE_AGE_DAYS = 180      # 6 months

# Known protocols using ECDH-only encryption (vulnerable to HNDL)
VULNERABLE_ECDH_PROTOCOLS = {
    "0xtornado_eth_100",       # Tornado Cash 100 ETH pool
    "0xumbra_v1_announcer",    # Umbra v1 stealth address announcer
    "0xrailgun_v2_relay",      # Railgun v2 (note encryption uses ECDH)
    "0xfluidkey_announcer",    # Fluidkey stealth address (ECDH-only)
}

# Known BLS-dependent contracts (consensus-critical or threshold)
BLS_DEPENDENT_CONTRACTS = {
    "0x00000000219ab540356cbb839cbe05303d7705fa",  # Beacon Chain deposit contract
    "0xshutter_keyper_set",
    "0xdrand_quicknet",
    "0xssv_dvt_registry",
    "0xobol_dvt_registry",
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class AccountSnapshot:
    """A wallet account snapshot for PQ-readiness analysis."""
    address: str

    # Stealth address registry (H1)
    has_stealth_meta_address: bool = False
    meta_address_has_mlkem: bool = False
    stealth_protocol_version: str = ""    # "ERC-5564-v1" | "ERC-5564-pq" | ""

    # Smart account config (H2)
    is_smart_account: bool = False
    smart_account_has_pq_module: bool = False
    smart_account_upgradeable: bool = True
    smart_account_validation: list[str] = field(default_factory=list)  # ["ecdsa", "ml-dsa", "falcon"]

    # On-chain encryption interactions (H3)
    interacted_with_protocols: list[str] = field(default_factory=list)
    recent_ecdh_ephemeral_keys_seen: int = 0          # in last 30 days
    encrypted_blobs_without_pq_kem: int = 0           # count

    # BLS threshold participation (H4)
    bls_deposit_count: int = 0
    bls_committee_memberships: list[str] = field(default_factory=list)
    bls_attestations_count: int = 0

    # Long-term key reuse (H5)
    first_tx_timestamp: int = 0
    latest_tx_timestamp: int = 0
    tx_count: int = 0
    total_value_usd: float = 0.0
    has_rotated_key: bool = False                     # via smart account upgrade

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
    account: AccountSnapshot
    alerts: list[RiskAlert] = field(default_factory=list)
    overall_risk: str = "low"
    pq_readiness_score: float = 1.0  # 1.0 = fully PQ-ready, 0.0 = fully vulnerable


# ---------------------------------------------------------------------------
# Profile loader
# ---------------------------------------------------------------------------

def load_profile(path: str | Path) -> dict:
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Heuristic checks
# ---------------------------------------------------------------------------

def check_h1_ecdh_stealth(acc: AccountSnapshot, profile: dict) -> list[RiskAlert]:
    """H1: ECDH-only stealth address registration (no ML-KEM hybrid)."""
    alerts: list[RiskAlert] = []
    h = profile["heuristics"]["H1_ecdh_only_stealth_registration"]

    if not acc.has_stealth_meta_address:
        return alerts

    if not acc.meta_address_has_mlkem:
        is_pre_pq_protocol = "pq" not in acc.stealth_protocol_version.lower()
        confidence = 0.95 if is_pre_pq_protocol else 0.80
        alerts.append(RiskAlert(
            heuristic_id="H1",
            heuristic_name=h["name"],
            severity="critical",
            confidence=confidence,
            signal=(
                f"Meta-address registered with ECDH-only public key (no ML-KEM hybrid). "
                f"All future announcements to {acc.address} are HNDL-harvestable."
            ),
            recommendation=h["recommendations"][0]["description"],
            skill="pq_migration_advisor",
            action="warn",  # existing registrations -> warn; new ones would block
        ))
    return alerts


def check_h2_classical_smart_account(acc: AccountSnapshot, profile: dict) -> list[RiskAlert]:
    """H2: Smart account uses only ECDSA, no PQ fallback key."""
    alerts: list[RiskAlert] = []
    h = profile["heuristics"]["H2_classical_only_smart_account"]

    if not acc.is_smart_account:
        return alerts

    has_pq_validation = any(v in ("ml-dsa", "falcon", "slh-dsa") for v in acc.smart_account_validation)
    only_ecdsa = acc.smart_account_validation == ["ecdsa"] or (
        not has_pq_validation and "ecdsa" in acc.smart_account_validation
    )

    if only_ecdsa and not acc.smart_account_has_pq_module:
        if not acc.smart_account_upgradeable:
            alerts.append(RiskAlert(
                heuristic_id="H2",
                heuristic_name=h["name"],
                severity="critical",
                confidence=0.85,
                signal=(
                    f"Smart account at {acc.address} is non-upgradeable AND ECDSA-only — "
                    f"cannot add PQ fallback without full asset migration"
                ),
                recommendation=h["recommendations"][1]["description"],
                action="warn",
            ))
        else:
            alerts.append(RiskAlert(
                heuristic_id="H2",
                heuristic_name=h["name"],
                severity=h["severity"],
                confidence=0.80,
                signal=f"Smart account at {acc.address} uses only ECDSA validation, no PQ fallback module installed",
                recommendation=h["recommendations"][0]["description"],
                skill="pq_migration_advisor",
                action="warn",
            ))
    return alerts


def check_h3_onchain_ecdh_encryption(acc: AccountSnapshot, profile: dict) -> list[RiskAlert]:
    """H3: User has interacted with protocols using ECDH-only encryption (HNDL exposure)."""
    alerts: list[RiskAlert] = []
    h = profile["heuristics"]["H3_quantum_vulnerable_onchain_encryption"]

    vulnerable_hits = [
        p for p in acc.interacted_with_protocols
        if p.lower() in {q.lower() for q in VULNERABLE_ECDH_PROTOCOLS}
    ]

    if vulnerable_hits:
        alerts.append(RiskAlert(
            heuristic_id="H3",
            heuristic_name=h["name"],
            severity="critical",
            confidence=0.95,
            signal=(
                f"Account interacted with {len(vulnerable_hits)} known ECDH-only protocol(s): "
                f"{vulnerable_hits[:3]}{'...' if len(vulnerable_hits) > 3 else ''}. "
                f"All ciphertexts permanently HNDL-exposed."
            ),
            recommendation=h["recommendations"][0]["description"],
            skill="key_analyzer",
            action="warn",
        ))
    elif acc.recent_ecdh_ephemeral_keys_seen > 0 and acc.encrypted_blobs_without_pq_kem > 0:
        alerts.append(RiskAlert(
            heuristic_id="H3",
            heuristic_name=h["name"],
            severity="high",
            confidence=0.80,
            signal=(
                f"Recent activity includes {acc.recent_ecdh_ephemeral_keys_seen} ECDH ephemeral keys "
                f"and {acc.encrypted_blobs_without_pq_kem} encrypted blobs without ML-KEM"
            ),
            recommendation=h["recommendations"][0]["description"],
            skill="key_analyzer",
            action="warn",
        ))
    return alerts


def check_h4_bls_participation(acc: AccountSnapshot, profile: dict) -> list[RiskAlert]:
    """H4: BLS threshold signature participation (validators, drand, threshold committees)."""
    alerts: list[RiskAlert] = []
    h = profile["heuristics"]["H4_bls_threshold_participation"]

    is_validator = acc.bls_deposit_count > 0
    in_committees = bool(acc.bls_committee_memberships)
    has_attested = acc.bls_attestations_count > 0

    # Threshold per profile: bls_deposit -> INFO, threshold_committee_join -> WARNING
    if in_committees:
        alerts.append(RiskAlert(
            heuristic_id="H4",
            heuristic_name=h["name"],
            severity=h["severity"],
            confidence=0.85,
            signal=(
                f"Account participates in {len(acc.bls_committee_memberships)} BLS threshold "
                f"committee(s): {acc.bls_committee_memberships[:3]}"
            ),
            recommendation=h["recommendations"][0]["description"],
            skill="pq_migration_advisor",
            action="warn",
        ))
    elif is_validator:
        alerts.append(RiskAlert(
            heuristic_id="H4",
            heuristic_name=h["name"],
            severity="medium",
            confidence=0.70,
            signal=(
                f"Account has {acc.bls_deposit_count} validator deposit(s). BLS keys are "
                f"quantum-vulnerable but consensus migration is protocol-level."
            ),
            recommendation=h["recommendations"][1]["description"],
            action="inform",
        ))
    elif has_attested and acc.bls_attestations_count > 100:
        alerts.append(RiskAlert(
            heuristic_id="H4",
            heuristic_name=h["name"],
            severity="medium",
            confidence=0.55,
            signal=f"Account has signed {acc.bls_attestations_count} BLS attestations",
            recommendation=h["recommendations"][1]["description"],
            action="inform",
        ))
    return alerts


def check_h5_long_term_key_reuse(acc: AccountSnapshot, profile: dict) -> list[RiskAlert]:
    """H5: Long-term key reuse without rotation."""
    alerts: list[RiskAlert] = []
    h = profile["heuristics"]["H5_long_term_key_reuse"]

    if acc.is_smart_account and acc.has_rotated_key:
        return alerts  # rotation possible and used

    if acc.first_tx_timestamp == 0 or acc.current_timestamp == 0:
        return alerts

    age_days = (acc.current_timestamp - acc.first_tx_timestamp) / 86400
    is_old = age_days > KEY_AGE_HIGH_DAYS
    is_high_count = acc.tx_count > HIGH_TX_COUNT
    is_high_value_age = acc.total_value_usd > HIGH_VALUE_USD and age_days > HIGH_VALUE_AGE_DAYS

    if is_high_value_age:
        alerts.append(RiskAlert(
            heuristic_id="H5",
            heuristic_name=h["name"],
            severity="high",
            confidence=0.85,
            signal=(
                f"Key controls ${acc.total_value_usd:,.0f} and has been active "
                f"{age_days:.0f} days without rotation — high-value harvest target"
            ),
            recommendation=h["recommendations"][0]["description"],
            skill="key_analyzer",
            action="warn",
        ))
    elif is_old and is_high_count:
        alerts.append(RiskAlert(
            heuristic_id="H5",
            heuristic_name=h["name"],
            severity=h["severity"],
            confidence=0.75,
            signal=(
                f"Key has been active {age_days:.0f} days with {acc.tx_count} transactions "
                f"signed — large historical harvest surface"
            ),
            recommendation=h["recommendations"][0]["description"],
            skill="key_analyzer",
            action="warn",
        ))
    elif is_old:
        alerts.append(RiskAlert(
            heuristic_id="H5",
            heuristic_name=h["name"],
            severity="medium",
            confidence=0.60,
            signal=f"Key age {age_days:.0f} days exceeds {KEY_AGE_HIGH_DAYS}-day rotation threshold",
            recommendation=h["recommendations"][1]["description"],
            action="inform",
        ))
    return alerts


# ---------------------------------------------------------------------------
# Main analyzer
# ---------------------------------------------------------------------------

def analyze_account(acc: AccountSnapshot, profile: dict) -> AnalysisResult:
    """Run all 5 PQ-readiness heuristics against an account snapshot."""
    result = AnalysisResult(account=acc)

    checks = [
        check_h1_ecdh_stealth(acc, profile),
        check_h2_classical_smart_account(acc, profile),
        check_h3_onchain_ecdh_encryption(acc, profile),
        check_h4_bls_participation(acc, profile),
        check_h5_long_term_key_reuse(acc, profile),
    ]
    for alerts in checks:
        result.alerts.extend(alerts)

    # PQ readiness score: 1.0 - weighted alert severity sum
    severity_weight = {"critical": 0.30, "high": 0.20, "medium": 0.10, "low": 0.05}
    deduction = sum(severity_weight.get(a.severity, 0.0) * a.confidence for a in result.alerts)
    result.pq_readiness_score = max(0.0, 1.0 - deduction)

    if any(a.severity == "critical" and a.confidence >= 0.85 for a in result.alerts):
        result.overall_risk = "critical"
    elif any(a.severity == "critical" for a in result.alerts):
        result.overall_risk = "high"
    elif any(a.severity == "high" for a in result.alerts):
        result.overall_risk = "medium"
    elif result.alerts:
        result.overall_risk = "low"

    return result


def format_result(result: AnalysisResult) -> str:
    a = result.account
    lines = [
        f"--- PQ Readiness Assessment: {result.overall_risk.upper()} (score: {result.pq_readiness_score:.2f}/1.0) ---",
        f"Account: {a.address}",
        f"Smart account: {a.is_smart_account}" + (f" (PQ module: {a.smart_account_has_pq_module})" if a.is_smart_account else ""),
        f"Stealth meta-address: {a.has_stealth_meta_address}" + (f" (ML-KEM: {a.meta_address_has_mlkem})" if a.has_stealth_meta_address else ""),
        f"BLS deposits: {a.bls_deposit_count}, committees: {len(a.bls_committee_memberships)}",
        f"Tx count: {a.tx_count}, value: ${a.total_value_usd:,.0f}",
        f"Alerts: {len(result.alerts)}",
    ]
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

def generate_synthetic_dataset(n: int = 100, seed: int = 42) -> list[AccountSnapshot]:
    """Generate synthetic account snapshots for PQ readiness benchmarking.

    Realistic-ish distribution (April 2026):
    - ~0% have PQ-hybrid stealth meta-addresses (per profile baseline)
    - ~5% are smart accounts; of those, ~0% have PQ modules
    - ~30% have interacted with vulnerable ECDH protocols (Tornado / Umbra v1 / Railgun)
    - ~5% are validators (BLS deposit)
    - ~50% have keys >2 years old
    - 10% are high-value (>$100K) with long key age
    """
    rng = random.Random(seed)
    accounts: list[AccountSnapshot] = []
    now = 1730000000

    for i in range(n):
        addr = f"0x{i:040x}"

        # Stealth meta-address: 30% have one, of those 0% have ML-KEM
        has_meta = rng.random() < 0.30
        meta_pq = rng.random() < 0.001 if has_meta else False
        proto_version = ("ERC-5564-pq" if meta_pq else "ERC-5564-v1") if has_meta else ""

        # Smart account: 5% are smart accounts, of those 1% have PQ module
        is_smart = rng.random() < 0.05
        has_pq_module = rng.random() < 0.01 if is_smart else False
        upgradeable = rng.random() < 0.70 if is_smart else True
        validation = ["ecdsa"]
        if has_pq_module:
            validation.append(rng.choice(["ml-dsa", "falcon"]))

        # Vulnerable protocol interactions: 30% have hit at least one
        protocols = []
        if rng.random() < 0.30:
            protocols = rng.sample(list(VULNERABLE_ECDH_PROTOCOLS), k=rng.randint(1, 3))
        recent_ecdh = rng.randint(0, 50) if protocols else rng.randint(0, 5)
        blobs_no_pq = rng.randint(0, 100) if protocols else rng.randint(0, 10)

        # Validator: 5%
        bls_deposits = rng.randint(1, 32) if rng.random() < 0.05 else 0
        bls_committees = []
        if rng.random() < 0.005:
            bls_committees = [rng.choice(["shutter_keyper", "drand_quicknet", "ssv_dvt"])]
        bls_attestations = rng.randint(100, 100000) if bls_deposits else 0

        # Key age: 50% old (>2y)
        if rng.random() < 0.50:
            age_days = rng.randint(KEY_AGE_HIGH_DAYS, 3000)
        else:
            age_days = rng.randint(0, KEY_AGE_HIGH_DAYS - 1)
        first_ts = now - age_days * 86400
        latest_ts = now - rng.randint(0, 86400 * 7)
        tx_count = rng.randint(10, 5000)

        # Value: 10% high-value with long age
        if rng.random() < 0.10 and age_days > HIGH_VALUE_AGE_DAYS:
            value = rng.uniform(HIGH_VALUE_USD, 5_000_000.0)
        else:
            value = rng.uniform(0, 50_000.0)

        has_rotated = is_smart and rng.random() < 0.10

        accounts.append(AccountSnapshot(
            address=addr,
            has_stealth_meta_address=has_meta,
            meta_address_has_mlkem=meta_pq,
            stealth_protocol_version=proto_version,
            is_smart_account=is_smart,
            smart_account_has_pq_module=has_pq_module,
            smart_account_upgradeable=upgradeable,
            smart_account_validation=validation,
            interacted_with_protocols=protocols,
            recent_ecdh_ephemeral_keys_seen=recent_ecdh,
            encrypted_blobs_without_pq_kem=blobs_no_pq,
            bls_deposit_count=bls_deposits,
            bls_committee_memberships=bls_committees,
            bls_attestations_count=bls_attestations,
            first_tx_timestamp=first_ts,
            latest_tx_timestamp=latest_ts,
            tx_count=tx_count,
            total_value_usd=value,
            has_rotated_key=has_rotated,
            current_timestamp=now,
        ))

    return accounts


def run_benchmark(profile: dict, n: int = 1000) -> dict:
    accounts = generate_synthetic_dataset(n)
    results = [analyze_account(a, profile) for a in accounts]

    score_buckets = {"pq_ready (>0.8)": 0, "moderate (0.5-0.8)": 0, "vulnerable (<0.5)": 0}
    risk_counts = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    heuristic_counts: dict[str, int] = {}

    for r in results:
        if r.pq_readiness_score > 0.8:
            score_buckets["pq_ready (>0.8)"] += 1
        elif r.pq_readiness_score > 0.5:
            score_buckets["moderate (0.5-0.8)"] += 1
        else:
            score_buckets["vulnerable (<0.5)"] += 1
        risk_counts[r.overall_risk] = risk_counts.get(r.overall_risk, 0) + 1
        for a in r.alerts:
            heuristic_counts[a.heuristic_id] = heuristic_counts.get(a.heuristic_id, 0) + 1

    # Identify high-priority migration targets: critical risk + high value
    high_priority = sum(
        1 for r in results
        if r.overall_risk == "critical" and r.account.total_value_usd > HIGH_VALUE_USD
    )

    return {
        "n_accounts": n,
        "pq_readiness_score_distribution": score_buckets,
        "risk_distribution": risk_counts,
        "per_heuristic_alert_count": heuristic_counts,
        "high_priority_migration_targets": high_priority,
        "expected_pattern": "Most accounts vulnerable in 2026; H1 (~30% have stealth without PQ) and H3 (~30% used vulnerable ECDH protocols) dominate",
    }


# ---------------------------------------------------------------------------
# Example scenarios
# ---------------------------------------------------------------------------

def run_examples(profile: dict):
    now = 1730000000
    examples = [
        ("PQ-ready: hybrid stealth address + smart account with PQ module + key rotation", AccountSnapshot(
            address="0xpqready",
            has_stealth_meta_address=True,
            meta_address_has_mlkem=True,
            stealth_protocol_version="ERC-5564-pq",
            is_smart_account=True,
            smart_account_has_pq_module=True,
            smart_account_upgradeable=True,
            smart_account_validation=["ecdsa", "ml-dsa"],
            interacted_with_protocols=[],
            first_tx_timestamp=now - 365 * 86400,
            latest_tx_timestamp=now,
            tx_count=200,
            total_value_usd=50000.0,
            has_rotated_key=True,
            current_timestamp=now,
        )),
        ("Average user 2026: classical stealth + interacted with Umbra v1 + 3y EOA key", AccountSnapshot(
            address="0xaverage",
            has_stealth_meta_address=True,
            meta_address_has_mlkem=False,
            stealth_protocol_version="ERC-5564-v1",
            is_smart_account=False,
            interacted_with_protocols=["0xumbra_v1_announcer", "0xrailgun_v2_relay"],
            recent_ecdh_ephemeral_keys_seen=12,
            encrypted_blobs_without_pq_kem=20,
            first_tx_timestamp=now - 1100 * 86400,
            latest_tx_timestamp=now,
            tx_count=850,
            total_value_usd=15000.0,
            current_timestamp=now,
        )),
        ("WORST: high-value old EOA + Tornado history + ECDSA-only smart account", AccountSnapshot(
            address="0xworst",
            has_stealth_meta_address=True,
            meta_address_has_mlkem=False,
            stealth_protocol_version="ERC-5564-v1",
            is_smart_account=True,
            smart_account_has_pq_module=False,
            smart_account_upgradeable=False,
            smart_account_validation=["ecdsa"],
            interacted_with_protocols=["0xtornado_eth_100", "0xumbra_v1_announcer"],
            recent_ecdh_ephemeral_keys_seen=30,
            encrypted_blobs_without_pq_kem=50,
            first_tx_timestamp=now - 2000 * 86400,
            latest_tx_timestamp=now,
            tx_count=3500,
            total_value_usd=2_000_000.0,
            has_rotated_key=False,
            current_timestamp=now,
        )),
        ("Validator + threshold committee participation", AccountSnapshot(
            address="0xvalidator",
            is_smart_account=False,
            bls_deposit_count=4,
            bls_committee_memberships=["shutter_keyper"],
            bls_attestations_count=80000,
            first_tx_timestamp=now - 800 * 86400,
            latest_tx_timestamp=now,
            tx_count=200,
            total_value_usd=128000.0,
            current_timestamp=now,
        )),
        ("Fresh user: new EOA, no stealth, no smart account", AccountSnapshot(
            address="0xnewbie",
            first_tx_timestamp=now - 10 * 86400,
            latest_tx_timestamp=now,
            tx_count=15,
            total_value_usd=200.0,
            current_timestamp=now,
        )),
    ]

    for name, acc in examples:
        print(f"\n{'='*60}")
        print(f"Scenario: {name}")
        print(f"{'='*60}")
        result = analyze_account(acc, profile)
        print(format_result(result))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    profile_path = Path(__file__).parent / "profile.json"
    profile = load_profile(profile_path)

    if "--benchmark" in sys.argv:
        print("Running PQ readiness benchmark (1000 synthetic accounts)...")
        results = run_benchmark(profile)
        print(json.dumps(results, indent=2))
    else:
        print(f"PQ Readiness Analyzer v{profile['meta']['version']}")
        print(f"Profile: {profile['meta']['domain_name']}")
        print(f"Source: {profile['meta']['source_paper']}")
        print(f"Threat model: HNDL (Harvest Now, Decrypt Later); CRQC ETA ~2030-2035")
        run_examples(profile)


if __name__ == "__main__":
    main()
