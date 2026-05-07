"""
Auto-generated tests for backup_security domain.

Run: python domains/backup_security/test_profile.py
"""

import json
import sys
from pathlib import Path

PROFILE_PATH = Path(__file__).parent / "profile.json"


def load_profile():
    with open(PROFILE_PATH) as f:
        return json.load(f)


def test_profile_loads():
    profile = load_profile()
    assert profile["meta"]["domain_name"] == "backup_security"
    assert len(profile["heuristics"]) == 5


def test_profile_validation():
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from meta.tx_validation_engine import validate_profile
    profile = load_profile()
    results = validate_profile(profile)
    assert results["overall"] == "PASS", f"Validation failed: {results}"


def test_h1_structure():
    """Test H1: Password-only backup encryption"""
    profile = load_profile()
    h = profile["heuristics"]["H1_password_only_backup"]
    assert h["severity"] == "critical"
    assert len(h["detection"]["signals"]) >= 3
    assert len(h["recommendations"]) >= 2
    for s in h["detection"]["signals"]:
        assert 0 <= s["confidence"] <= 1
        assert s.get("data_needed"), f"Signal {s['name']} missing data_needed"
    for r in h["recommendations"]:
        assert 0 <= r["effectiveness"] <= 1


def test_h2_structure():
    """Test H2: Stale guardians"""
    profile = load_profile()
    h = profile["heuristics"]["H2_stale_guardians"]
    assert h["severity"] == "high"
    assert len(h["detection"]["signals"]) >= 3
    assert len(h["recommendations"]) >= 2
    for s in h["detection"]["signals"]:
        assert 0 <= s["confidence"] <= 1
        assert s.get("data_needed"), f"Signal {s['name']} missing data_needed"
    for r in h["recommendations"]:
        assert 0 <= r["effectiveness"] <= 1


def test_h3_structure():
    """Test H3: Quantum-vulnerable backup encryption"""
    profile = load_profile()
    h = profile["heuristics"]["H3_quantum_vulnerable_backup_encryption"]
    assert h["severity"] == "critical"
    assert len(h["detection"]["signals"]) >= 3
    assert len(h["recommendations"]) >= 2
    for s in h["detection"]["signals"]:
        assert 0 <= s["confidence"] <= 1
        assert s.get("data_needed"), f"Signal {s['name']} missing data_needed"
    for r in h["recommendations"]:
        assert 0 <= r["effectiveness"] <= 1


def test_h4_structure():
    """Test H4: No coercion resistance"""
    profile = load_profile()
    h = profile["heuristics"]["H4_no_coercion_resistance"]
    assert h["severity"] == "high"
    assert len(h["detection"]["signals"]) >= 3
    assert len(h["recommendations"]) >= 2
    for s in h["detection"]["signals"]:
        assert 0 <= s["confidence"] <= 1
        assert s.get("data_needed"), f"Signal {s['name']} missing data_needed"
    for r in h["recommendations"]:
        assert 0 <= r["effectiveness"] <= 1


def test_h5_structure():
    """Test H5: Non-deterministic secrets not backed up"""
    profile = load_profile()
    h = profile["heuristics"]["H5_nondeterministic_secrets_not_backed_up"]
    assert h["severity"] == "high"
    assert len(h["detection"]["signals"]) >= 3
    assert len(h["recommendations"]) >= 2
    for s in h["detection"]["signals"]:
        assert 0 <= s["confidence"] <= 1
        assert s.get("data_needed"), f"Signal {s['name']} missing data_needed"
    for r in h["recommendations"]:
        assert 0 <= r["effectiveness"] <= 1


def test_skills_complete():
    """All referenced skills are defined."""
    profile = load_profile()
    skills = set(profile.get("skills", {}).keys())
    referenced = set()
    for h in profile["heuristics"].values():
        for r in h.get("recommendations", []):
            s = r.get("skill_required")
            if s:
                referenced.add(s)
    missing = referenced - skills
    assert not missing, f"Missing skills: {missing}"


def test_templates():
    """Required templates exist."""
    profile = load_profile()
    templates = profile.get("templates", {})
    for key in ["risk_assessment", "summary", "skill_suggestion"]:
        assert key in templates, f"Missing template: {key}"


def test_labeled_data_exists():
    """Labeled data file exists and has entries."""
    data_path = Path(__file__).parent / "data" / "labeled_incidents.jsonl"
    assert data_path.exists(), "No labeled data file"
    with open(data_path) as f:
        lines = [l for l in f if l.strip()]
    assert len(lines) >= 5, f"Only {len(lines)} incidents"


def test_analyzer_worst_case_fires():
    """Rule-based analyzer fires alerts on a maximally insecure backup config."""
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from domains.backup_security.analyzer import BackupConfig, analyze_backup
    profile = load_profile()
    bad = BackupConfig(
        user_address="0xUser",
        backup_method="encrypted_seed_blob_on_arweave",
        backup_encryption="ECDH(secp256k1) + AES-GCM",
        encryption_factor="password_only",
        password_strength_bits=38,
        kdf_algorithm="pbkdf2",
        kdf_iterations=10000,
        guardian_count=3,
        recovery_threshold=2,
        guardians_last_liveness_check_days=[300, 280, 240],
        uses_pq_kem=False,
        kem_scheme="ecdh-secp256k1",
        backup_is_permanent_onchain=True,
        non_deterministic_secrets_present=["tornado_cash_deposit_notes"],
        non_deterministic_secrets_backed_up=False,
    )
    res = analyze_backup(bad, profile)
    assert res.alerts, "Worst-case scenario produced no alerts"
    assert res.should_block, "Worst-case scenario should block"
    assert res.overall_risk == "critical"


def test_analyzer_healthy_clean():
    """Rule-based analyzer is silent on a strong backup config."""
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from domains.backup_security.analyzer import BackupConfig, analyze_backup
    profile = load_profile()
    good = BackupConfig(
        user_address="0xUser",
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
        non_deterministic_secrets_present=[],
        non_deterministic_secrets_backed_up=True,
    )
    res = analyze_backup(good, profile)
    assert not res.alerts, f"Healthy scenario produced alerts: {[a.heuristic_id for a in res.alerts]}"
    assert not res.should_block


if __name__ == "__main__":
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for test in tests:
        try:
            test()
            print(f"  PASS  {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {test.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed out of {passed + failed}")
    sys.exit(1 if failed else 0)
