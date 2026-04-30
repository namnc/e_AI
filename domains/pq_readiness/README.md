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

- `AI_PS/projects/pq_stealth_address/frame_analysis.md` -- HNDL threat model, ML-KEM hybrid design, ecosystem mapping
- `AI_PS/projects/onchain_pq_ciphertext/report.md` -- HNDL honeypot quantification ($5B+), migration complexity analysis, KEM landscape

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
