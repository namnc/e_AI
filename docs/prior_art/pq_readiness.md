# Prior art — pq_readiness

## What this guard catches (one line)
Operations that expose quantum-vulnerable secrets — broadcasting an ECDSA public key, reusing keys, holding long-lived ECDSA-protected balances, signing with non-PQ schemes when a PQ alternative (ERC-4337 with ML-DSA / SLH-DSA) is available.

## Existing tools that implement this (FULL or substantive coverage)

### QuantumShield (Quantum Wallet Check)
- URL: https://quantumwalletcheck.com/wiki/quantum-safe-wallets
- What it does: Scans Bitcoin, Ethereum, and Solana addresses for quantum-vulnerability markers — exposed public keys, legacy address formats, key-reuse patterns.
- Coverage of the heuristic set: Most direct prior art. Covers (a) public-key exposure on-chain, (b) address-format vulnerability, (c) key reuse.
- Notable: Specifically called "QuantumShield" — naming overlap; e_AI must differentiate.

### Quantum Canary — Crypto Checker Online
- URL: https://www.quantumcanary.org/insights/is-your-crypto-secure
- What it does: Read-only scanner that flags whether a wallet's public key has been exposed (Bitcoin: scriptSig/witness reveal; Ethereum: any signed tx).
- Coverage: Public-key-exposure heuristic; categorizes holdings into rotation buckets.
- Notable: User-facing checker, similar surface to e_AI's pq_readiness.

### pq.ethereum.org (EF PQ Security Hub)
- URL: https://pq.ethereum.org/, https://ethereum.org/roadmap/future-proofing/quantum-resistance/
- What it does: Reference hub for Ethereum's PQ migration roadmap; documents leanXMSS, leanSig, leanMultisig, leanVM. Targets L1 PQ upgrade by 2029.
- Coverage: Reference + research, not a runtime guard. Defines what "PQ-ready" means for ERC-4337 wallets (ML-DSA, SLH-DSA support).
- Notable: Anchors what a "PQ readiness" guard should test against.

### PQShield
- URL: https://pqshield.com/post-quantum-cryptography/
- What it does: PQ cryptography solutions — silicon IP, software libraries, PQC implementations of Dilithium/Kyber/SPHINCS+.
- Coverage: Provides the PQ primitives, not user-side readiness scanning.
- Notable: Industry standard for PQ implementation libraries.

## Existing tools that implement this PARTIALLY

### leanSig / leanXMSS (EF + Irreducible)
- URL: https://github.com/IrreducibleOSS/leansig, https://eprint.iacr.org/2025/1332
- What it does: Reference implementation of EF's hash-based signature scheme for the consensus layer.
- Coverage: Validator-layer PQ — not directly relevant to a user-wallet guard but defines the consensus PQ direction.

### Hedera / IBM Quantum Safe writeups
- URL: https://hedera.com/blog/post-quantum-cryptography-and-blockchain/, https://www.ibm.com/quantum/quantum-safe
- What it does: Industry analysis of PQ migration for blockchain.
- Coverage: Educational, not a runtime guard.

## Adjacent / not-quite-this-guard

### "Harvest Now, Decrypt Later" frameworks
- Why adjacent: Threat-model framing for backups (see backup_security guard) more than for live transactions.

### NIST PQC standards (FIPS 203/204/205)
- URL: https://csrc.nist.gov/projects/post-quantum-cryptography
- Why adjacent: Standards body, not a runtime tool.

## Where e_AI pq_readiness differs

QuantumShield and Quantum Canary cover the *static scan* angle (does this address have an exposed public key?). e_AI's wedge is **action-time guidance**: "this transaction will broadcast your public key for the first time — consider rotating to a fresh key after this batch" or "you're signing with ECDSA when your ERC-4337 wallet supports ML-DSA — use the PQ path." This is operational PQ hygiene at the moment of action, not a static scorecard. Honest: detection of "is this address quantum-vulnerable?" is solved by the existing scanners; e_AI's surface is the *behavioral* dimension (when to rotate, when to use the PQ path) — which is genuinely under-served. Caveat: the user population that benefits today is small (most wallets don't yet have a PQ alternative); this guard is forward-looking.

## Open positioning question for the post

QuantumShield + Quantum Canary already exist for the static angle. Is the operational/behavioral framing ("when to rotate, when to use the PQ path") strong enough to publish, given that the PQ path is mostly hypothetical until ERC-4337 wallets ship ML-DSA validators? Or should this guard wait until the leanSig / EF PQ infrastructure ships?

## Sources

- [QuantumShield — Quantum-safe wallets guide](https://quantumwalletcheck.com/wiki/quantum-safe-wallets)
- [Quantum Canary — Crypto Checker](https://www.quantumcanary.org/insights/is-your-crypto-secure)
- [pq.ethereum.org](https://pq.ethereum.org/)
- [EF — Quantum Resistance Roadmap](https://ethereum.org/roadmap/future-proofing/quantum-resistance/)
- [PQShield](https://pqshield.com/post-quantum-cryptography/)
- [leanSig — Technical Note (eprint 2025/1332)](https://eprint.iacr.org/2025/1332)
- [leanSig GitHub](https://github.com/IrreducibleOSS/leansig)
