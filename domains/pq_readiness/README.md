# Domain: Post-Quantum Readiness

**Type:** Transaction analysis
**CROPS property:** S (Security)
**Status:** Draft
**Schema:** `core/tx_profile.py` (TransactionProfile)
**Source:** NIST FIPS 203 (ML-KEM), pq.ethereum.org threat timeline, PSE pq_stealth_address research, PQ Encryption Migration analysis

## What this domain does

Wallet guard that detects quantum-vulnerable keys and cryptographic operations before transactions are submitted. Flags ECDH-only stealth address registrations, classical-only smart account keys, on-chain data encrypted with quantum-breakable schemes, BLS threshold participation, and long-term key reuse patterns that increase harvest value under HNDL.

## Heuristics

| # | Heuristic | Severity | Countermeasure |
|---|---|---|---|
| H1 | ECDH-only stealth address registration | Critical | Register hybrid ECDH + ML-KEM meta-address |
| H2 | Classical-only key in smart account | High | Add PQ fallback signer module |
| H3 | On-chain ECDH-encrypted data | Critical | Use hybrid encryption or symmetric-only |
| H4 | BLS threshold signature participation | High | Plan PQ migration, minimize BLS exposure |
| H5 | Long-term key reuse without rotation | High | Rotate to smart account, split across keys |

## Research sources

- Internal HNDL threat-model analysis (not in this public repo): pq stealth address frame, ML-KEM hybrid design, ecosystem mapping.
- Internal on-chain PQ ciphertext study (not in this public repo): HNDL honeypot quantification (~$5B+ exposed), migration complexity analysis, KEM landscape.

## What needs human effort

- [ ] Define threshold for "high value" key (currently $100K -- needs calibration per user profile)
- [ ] Map complete set of ECDH-using protocol contracts for known_vulnerable_protocol signal
- [ ] Track EIP-8051/8052 precompile progress for smart account PQ sig verification feasibility
- [ ] Calibrate confidence scores against real smart account populations
- [ ] Define BLS migration path once PQ alternatives mature

## Improving this domain

1. Run: `python -m meta.tx_validation_engine domains/pq_readiness/profile.json`
2. Add known ECDH-using contract addresses to vulnerable protocol registry
3. Track PQ adoption metrics as baseline evolves
4. See `docs/improving_a_domain.md`

## Prior art

**QuantumShield**, **Quantum Canary** cover *static scan* (audit static state for quantum exposure). NIST PQC standards (ML-KEM, ML-DSA, SLH-DSA) define the migration target.

**Where this guard differs**: Behavioral pre-submission angle — "when to rotate", first-use exposure warnings — vs static audit. Currently small population; will grow as PQ migration becomes practical.

Full comparison: `docs/prior_art/pq_readiness.md`.
