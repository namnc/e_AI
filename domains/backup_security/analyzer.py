"""
Backup Security Analyzer — profile-based backup configuration risk analysis.

Loads backup_security/profile.json and evaluates a wallet backup configuration
against 5 heuristics (H1-H5): password-only encryption, stale guardians,
PQ-vulnerable key exchange, missing coercion resistance, non-deterministic
secrets not backed up.

This is a DEMO / preliminary implementation. Production deployment must wire
guardian liveness from on-chain RPC + an off-chain liveness registry, KDF
parameters from backup metadata, and protocol classification (deterministic
vs non-deterministic secret generation) from a curated registry.

Usage:
    python analyzer.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# Protocols known to mint non-deterministic per-action secrets that must be
# explicitly backed up (cannot be derived from seed).
NON_DETERMINISTIC_SECRET_PROTOCOLS = {
    "tornado_cash",
    "tornadocash",
    "stealth_address_meta",
    "old_zcash_sprout",
    "old_railgun",
}

# Encryption-scheme tags considered PQ-vulnerable as backup wrap.
PQ_VULNERABLE_KEM_TAGS = {
    "ecdh", "ecies", "x25519", "secp256k1_kem", "ecdh-x25519",
}

# KDF minima (Argon2id reference; less for scrypt/PBKDF2 we just flag the algo).
ARGON2_MIN_MEMORY_MB = 64
ARGON2_MIN_ITERATIONS = 3
PASSWORD_MIN_ENTROPY_BITS = 50


@dataclass
class BackupConfig:
    """A wallet backup / recovery configuration being audited."""
    user_address: str
    backup_method: str
    backup_encryption: str  # textual descriptor, e.g. "ECDH(secp256k1) ephemeral + AES-GCM"

    # H1: password-only encryption
    encryption_factor: str = "password_only"  # password_only | password_plus_hardware | threshold
    password_strength_bits: int = 50
    kdf_algorithm: str = "argon2id"
    kdf_memory_mb: int = 64
    kdf_iterations: int = 3
    has_hardware_factor: bool = False

    # H2: guardians
    guardian_count: int = 0
    recovery_threshold: int = 0
    guardians_last_liveness_check_days: list[int] = field(default_factory=list)
    inactivity_threshold_days: int = 180

    # H3: PQ-safety
    uses_pq_kem: bool = False
    kem_scheme: str = ""  # e.g. "ecdh-x25519", "ml-kem-768+ecdh", "aes-only"
    backup_is_permanent_onchain: bool = False

    # H4: coercion resistance
    has_deniable_layer: bool = False
    has_honey_encryption: bool = False

    # H5: non-deterministic secrets
    non_deterministic_secrets_present: list[str] = field(default_factory=list)
    non_deterministic_secrets_backed_up: bool = False

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
    config: BackupConfig
    alerts: list[RiskAlert] = field(default_factory=list)
    overall_risk: str = "low"
    should_block: bool = False


def load_profile(path: str | Path) -> dict:
    with open(path) as f:
        return json.load(f)


def _kdf_is_weak(c: BackupConfig) -> bool:
    if c.kdf_algorithm.lower() == "argon2id":
        return c.kdf_memory_mb < ARGON2_MIN_MEMORY_MB or c.kdf_iterations < ARGON2_MIN_ITERATIONS
    if c.kdf_algorithm.lower() in ("pbkdf2", "sha256", "none"):
        return True
    if c.kdf_algorithm.lower() == "scrypt":
        # scrypt N parameter conventionally encoded in iterations field for this guard
        return c.kdf_iterations < (1 << 17)
    return False  # unknown KDFs treated as not-weak; analyst must classify


def check_h1_password_only_backup(c: BackupConfig, profile: dict) -> list[RiskAlert]:
    h = profile["heuristics"]["H1_password_only_backup"]
    alerts: list[RiskAlert] = []
    is_password_only = c.encryption_factor == "password_only" and not c.has_hardware_factor

    if is_password_only and c.password_strength_bits < PASSWORD_MIN_ENTROPY_BITS:
        alerts.append(
            RiskAlert(
                heuristic_id="H1",
                heuristic_name=h["name"],
                severity=h["severity"],
                confidence=0.90,
                signal=(
                    f"Password-only backup with {c.password_strength_bits}-bit password "
                    f"(<{PASSWORD_MIN_ENTROPY_BITS}-bit minimum); brute-forceable on-chain."
                ),
                recommendation="Add a hardware factor (YubiKey HMAC) or split into 2-of-3 Shamir shares.",
                skill="backup_auditor",
                action="block",
            )
        )
    if is_password_only and _kdf_is_weak(c):
        alerts.append(
            RiskAlert(
                heuristic_id="H1",
                heuristic_name=h["name"],
                severity="high",
                confidence=0.85,
                signal=(
                    f"KDF '{c.kdf_algorithm}' with memory={c.kdf_memory_mb}MB iter={c.kdf_iterations} "
                    f"is below recommended minimums for password-only backup."
                ),
                recommendation="Use Argon2id with memory>=256MB and iterations>=4; this only buys time, not safety, against weak passwords.",
                skill="backup_auditor",
                action="warn",
            )
        )
    return alerts


def check_h2_stale_guardians(c: BackupConfig, profile: dict) -> list[RiskAlert]:
    if c.guardian_count == 0 or not c.guardians_last_liveness_check_days:
        return []

    h = profile["heuristics"]["H2_stale_guardians"]
    alerts: list[RiskAlert] = []

    stale = [d for d in c.guardians_last_liveness_check_days if d > c.inactivity_threshold_days]
    active = c.guardian_count - len(stale)

    if stale:
        alerts.append(
            RiskAlert(
                heuristic_id="H2",
                heuristic_name=h["name"],
                severity=h["severity"],
                confidence=0.80,
                signal=(
                    f"{len(stale)}/{c.guardian_count} guardians inactive >{c.inactivity_threshold_days} days "
                    f"(oldest: {max(stale)}d)."
                ),
                recommendation="Run a liveness ceremony; replace any guardian who does not respond within 30 days.",
                skill="guardian_monitor",
                action="warn",
            )
        )

    if c.recovery_threshold and active < c.recovery_threshold:
        alerts.append(
            RiskAlert(
                heuristic_id="H2",
                heuristic_name=h["name"],
                severity="critical",
                confidence=0.95,
                signal=(
                    f"Only {active} active guardians vs {c.recovery_threshold} required for recovery; "
                    f"WALLET ALREADY UNRECOVERABLE."
                ),
                recommendation="BLOCK new actions that depend on recovery; immediately re-enroll guardians.",
                skill="guardian_monitor",
                action="block",
            )
        )

    return alerts


def check_h3_quantum_vulnerable_backup(c: BackupConfig, profile: dict) -> list[RiskAlert]:
    h = profile["heuristics"]["H3_quantum_vulnerable_backup_encryption"]
    enc_lower = c.backup_encryption.lower()
    kem_lower = c.kem_scheme.lower()

    pq_vuln = (
        any(tag in enc_lower for tag in PQ_VULNERABLE_KEM_TAGS)
        or any(tag in kem_lower for tag in PQ_VULNERABLE_KEM_TAGS)
    ) and not c.uses_pq_kem

    if not pq_vuln:
        return []

    severity = "critical" if c.backup_is_permanent_onchain else h["severity"]
    return [
        RiskAlert(
            heuristic_id="H3",
            heuristic_name=h["name"],
            severity=severity,
            confidence=0.90,
            signal=(
                f"Backup uses {c.backup_encryption} (ECDH-class KEM) without PQ wrap; "
                + ("permanent on-chain blob is harvest-now-decrypt-later target." if c.backup_is_permanent_onchain
                   else "vulnerable to future CRQC.")
            ),
            recommendation="Switch to AES-256 with password-derived key (PQ-safe symmetric) or hybrid ECDH+ML-KEM-768.",
            skill="backup_auditor",
            action="block" if c.backup_is_permanent_onchain else "warn",
        )
    ]


def check_h4_no_coercion_resistance(c: BackupConfig, profile: dict) -> list[RiskAlert]:
    if c.has_deniable_layer or c.has_honey_encryption:
        return []
    if c.encryption_factor != "password_only":
        return []  # coercion resistance is largely a single-password concern

    h = profile["heuristics"]["H4_no_coercion_resistance"]
    return [
        RiskAlert(
            heuristic_id="H4",
            heuristic_name=h["name"],
            severity=h["severity"],
            confidence=0.75,
            signal="Single password reveals real seed; no deniable / honey layer for duress scenarios.",
            recommendation="Add a duress-decoy layer (False-Bottom Encryption) or Honey Encryption for high-risk profiles.",
            skill="backup_auditor",
            action="inform",
        )
    ]


def check_h5_nondeterministic_secrets(c: BackupConfig, profile: dict) -> list[RiskAlert]:
    if not c.non_deterministic_secrets_present:
        return []
    if c.non_deterministic_secrets_backed_up:
        return []

    h = profile["heuristics"]["H5_nondeterministic_secrets_not_backed_up"]
    secrets = ", ".join(c.non_deterministic_secrets_present[:3])
    return [
        RiskAlert(
            heuristic_id="H5",
            heuristic_name=h["name"],
            severity=h["severity"],
            confidence=0.90,
            signal=f"Non-deterministic secrets present ({secrets}) but NOT backed up; loss of device = loss of funds.",
            recommendation="BLOCK further interactions with non-deterministic protocols until per-action secrets are persisted.",
            skill="backup_auditor",
            action="block",
        )
    ]


_CHECKS = [
    check_h1_password_only_backup,
    check_h2_stale_guardians,
    check_h3_quantum_vulnerable_backup,
    check_h4_no_coercion_resistance,
    check_h5_nondeterministic_secrets,
]


def analyze_backup(config: BackupConfig, profile: dict) -> AnalysisResult:
    alerts: list[RiskAlert] = []
    for chk in _CHECKS:
        alerts.extend(chk(config, profile))

    severity_rank = {"low": 1, "medium": 2, "high": 3, "critical": 4}
    overall = "low"
    block = False
    for a in alerts:
        if severity_rank.get(a.severity, 0) > severity_rank.get(overall, 0):
            overall = a.severity
        if a.action == "block":
            block = True

    return AnalysisResult(config=config, alerts=alerts, overall_risk=overall, should_block=block)


# ---------------------------------------------------------------------------
# Local self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    profile_path = Path(__file__).parent / "profile.json"
    profile = load_profile(profile_path)

    bad = BackupConfig(
        user_address="0xUserBackup1",
        backup_method="encrypted_seed_blob_on_arweave",
        backup_encryption="ECDH(secp256k1) ephemeral + AES-GCM",
        encryption_factor="password_only",
        password_strength_bits=38,
        kdf_algorithm="pbkdf2",
        kdf_memory_mb=0,
        kdf_iterations=10000,
        has_hardware_factor=False,
        guardian_count=3,
        recovery_threshold=2,
        guardians_last_liveness_check_days=[320, 280, 240],
        uses_pq_kem=False,
        kem_scheme="ecdh-secp256k1",
        backup_is_permanent_onchain=True,
        has_deniable_layer=False,
        has_honey_encryption=False,
        non_deterministic_secrets_present=["tornado_cash_deposit_notes_x4", "stealth_address_meta_secret"],
        non_deterministic_secrets_backed_up=False,
    )
    print("=== Worst-case ===")
    res = analyze_backup(bad, profile)
    print(f"overall={res.overall_risk} block={res.should_block} alerts={len(res.alerts)}")
    for a in res.alerts:
        print(f"  [{a.severity}] {a.heuristic_id}: {a.signal[:80]}")

    good = BackupConfig(
        user_address="0xUserBackupClean",
        backup_method="threshold_2of3_with_hardware",
        backup_encryption="AES-256-GCM",
        encryption_factor="threshold",
        password_strength_bits=128,
        kdf_algorithm="argon2id",
        kdf_memory_mb=512,
        kdf_iterations=4,
        has_hardware_factor=True,
        guardian_count=5,
        recovery_threshold=3,
        guardians_last_liveness_check_days=[10, 12, 8, 30, 5],
        uses_pq_kem=True,
        kem_scheme="ml-kem-768+ecdh",
        backup_is_permanent_onchain=False,
        has_deniable_layer=True,
        has_honey_encryption=False,
        non_deterministic_secrets_present=[],
        non_deterministic_secrets_backed_up=True,
    )
    print("\n=== Healthy ===")
    res = analyze_backup(good, profile)
    print(f"overall={res.overall_risk} block={res.should_block} alerts={len(res.alerts)}")
