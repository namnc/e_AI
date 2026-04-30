# Domain: Backup Encryption and Recovery Security

**Type:** Transaction analysis
**CROPS property:** S (Security)
**Status:** Draft
**Schema:** `core/tx_profile.py` (TransactionProfile)
**Source:** PSE encrypted_backup_recovery research (2026), SLIP-39, Juels-Ristenpart 2014, Ahmad et al. 2023

## What this domain does

Wallet guard that detects weak backup encryption, stale social recovery guardians, quantum-vulnerable backup key exchange, missing coercion resistance, and non-deterministic secrets that would be lost on device failure. Protects recoverability and confidentiality of wallet secrets.

## Heuristics

| # | Heuristic | Severity | Countermeasure |
|---|---|---|---|
| H1 | Password-only backup encryption | Critical | Add threshold factor (Shamir + hardware key) |
| H2 | Stale guardians (>6 months inactive) | High | Liveness checks, redundant guardian set |
| H3 | Quantum-vulnerable backup encryption (ECDH) | Critical | Symmetric-only or hybrid ML-KEM |
| H4 | No coercion resistance | High | Deniable / Honey Encryption |
| H5 | Non-deterministic secrets not backed up | High | Explicit backup or deterministic protocol |

## Research sources

- `AI_PS/projects/encrypted_backup_recovery/problem_list.md` -- P1 (circular dependency), P2 (coercion), P7 (guardian liveness), P9 (non-deterministic secrets), P10 (PQ backup)
- False-Bottom Encryption: Ahmad, Rass, Schartner (IEEE 2023)
- Honey Encryption: Juels-Ristenpart 2014
- Proactive secret sharing: GoSSamer (Xing et al. 2025), CHURP

## What needs human effort

- [ ] Define KDF parameter minimums for different threat levels (casual vs high-value vs dissident)
- [ ] Map which protocols use non-deterministic secrets (Tornado Cash confirmed; survey others)
- [ ] Implement guardian liveness check protocol (on-chain heartbeat vs off-chain attestation)
- [ ] Research deniable encryption adaptation for on-chain permanent ciphertext
- [ ] Validate brute-force cost estimates against current GPU rental prices

## Improving this domain

1. Run: `python -m meta.tx_validation_engine domains/backup_security/profile.json`
2. Add labeled backup security incidents to `data/`
3. Track guardian liveness statistics across wallet populations
4. See `docs/improving_a_domain.md`
