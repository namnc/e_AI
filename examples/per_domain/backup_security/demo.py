"""
backup_security demo — runs the rule-based + LLM analyzers on a sample backup config.

Run:
    python examples/per_domain/backup_security/demo.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from core.llm_analyzer import LLMAnalyzer
from domains.backup_security.analyzer import (
    BackupConfig,
    analyze_backup,
    load_profile,
)


HERE = Path(__file__).parent
PROFILE_PATH = REPO_ROOT / "domains" / "backup_security" / "profile.json"
SAMPLE_PATH = HERE / "sample_tx.json"


def build_config() -> BackupConfig:
    raw = json.loads(SAMPLE_PATH.read_text())
    # Parse "M-of-N" style threshold, e.g. "2-of-3"
    threshold = 0
    sr = raw.get("social_recovery_threshold", "")
    if isinstance(sr, str) and "-of-" in sr:
        try:
            threshold = int(sr.split("-of-")[0])
        except ValueError:
            threshold = 0

    return BackupConfig(
        user_address=raw["user_address"],
        backup_method=raw["backup_method"],
        backup_encryption=raw["backup_encryption"],
        encryption_factor=raw.get("encryption_factor", "password_only"),
        password_strength_bits=raw.get("password_strength_bits", 50),
        kdf_algorithm=raw.get("kdf_algorithm", "argon2id"),
        kdf_memory_mb=raw.get("kdf_memory_mb", 64),
        kdf_iterations=raw.get("kdf_iterations", 3),
        has_hardware_factor=raw.get("has_hardware_factor", False),
        guardian_count=raw.get("guardian_count", 0),
        recovery_threshold=threshold,
        guardians_last_liveness_check_days=raw.get("guardians_last_liveness_check_days", []),
        uses_pq_kem=raw.get("uses_pq_kem", False),
        kem_scheme=raw.get("kem_scheme", ""),
        backup_is_permanent_onchain=raw.get("backup_is_permanent_onchain", False),
        has_deniable_layer=raw.get("has_deniable_layer", False),
        has_honey_encryption=raw.get("has_honey_encryption", False),
        non_deterministic_secrets_present=raw.get("non_deterministic_secrets_present", []),
        non_deterministic_secrets_backed_up=raw.get("non_deterministic_secrets_backed_up", False),
        current_timestamp=raw.get("current_timestamp", 0),
    )


def print_result(result, llm_result):
    c = result.config
    print("=" * 70)
    print("backup_security — backup configuration risk")
    print("=" * 70)
    print(f"User: {c.user_address}")
    print(f"Backup: {c.backup_method} ({c.backup_encryption})")
    print(f"Factor: {c.encryption_factor}; password_bits={c.password_strength_bits}; pq_kem={c.uses_pq_kem}")
    print(f"Guardians: {c.guardian_count} ({c.recovery_threshold} required); inactive>180d: "
          f"{sum(1 for d in c.guardians_last_liveness_check_days if d > 180)}")
    print()
    print(f"OVERALL RISK: {result.overall_risk.upper()}")
    print(f"SHOULD BLOCK: {result.should_block}")
    print(f"ALERTS: {len(result.alerts)}")
    print()
    for a in result.alerts:
        print(f"  [{a.severity.upper():8s}] {a.heuristic_id} {a.heuristic_name} "
              f"(confidence {a.confidence:.2f})")
        print(f"    signal: {a.signal}")
        print(f"    recommend: {a.recommendation}")
        if a.action:
            print(f"    action: {a.action}")
        print()
    print("-" * 70)
    print("LLM behavioral analysis")
    print("-" * 70)
    if llm_result.get("degraded_mode"):
        print(f"[degraded] {llm_result.get('degraded_reason')}")
        print(f"Synthesized result: {llm_result.get('explanation')}")
    else:
        print(f"Risk: {llm_result.get('risk_level')}")
        print(f"Explanation: {llm_result.get('explanation')}")
        if llm_result.get("recommendations"):
            print("Recommendations:")
            for r in llm_result["recommendations"]:
                print(f"  - {r}")


def main():
    profile = load_profile(PROFILE_PATH)
    config = build_config()
    result = analyze_backup(config, profile)

    rule_alerts_dicts = [
        {
            "heuristic_id": a.heuristic_id,
            "severity": a.severity,
            "signal": a.signal,
            "recommendation": a.recommendation,
        }
        for a in result.alerts
    ]
    llm = LLMAnalyzer(profile, backend="ollama", model="qwen2.5:7b")
    llm.connect()
    llm_result = llm.analyze(
        tx={
            "method": config.backup_method,
            "encryption": config.backup_encryption,
            "factor": config.encryption_factor,
            "password_bits": config.password_strength_bits,
            "guardians": config.guardian_count,
            "non_det_secrets": config.non_deterministic_secrets_present,
        },
        rule_based_alerts=rule_alerts_dicts,
    )

    print_result(result, llm_result)


if __name__ == "__main__":
    main()
