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

## Analyzer

Rule-based analyzer at `analyzer.py` evaluates a `BackupConfig` against H1-H5
algorithmically (password entropy + KDF strength threshold, guardian liveness
vs threshold, ECDH-class KEM detection in encryption descriptor, deniable-layer
flag, non-deterministic secret class enumeration). LLM augments with reasoning
about subjective items (recovery topology, jurisdictional risk). Demo at
`examples/per_domain/backup_security/demo.py`.

## Research sources

- Internal threat-model analysis (not in this public repo): axes covered include circular dependency (P1), coercion (P2), guardian liveness (P7), non-deterministic secrets (P9), PQ backup (P10).
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

## Prior art

**Argent guardian model** + **Safe (multisig)** docs cover *guardian configuration*. **OpenZeppelin Guardian (Miden PSM)** addresses multi-device shielded recovery. No tool composes guardian + cloud-backup + quantum axes into a unified pre-submission guard.

**Where this guard differs**: Synthesis-novelty across three usually-separate axes (guardian, cloud, quantum). Thin novelty but real.

Full comparison: `docs/prior_art/backup_security.md`.
