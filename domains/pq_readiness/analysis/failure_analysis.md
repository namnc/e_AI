# Failure Analysis: pq_readiness

*Auto-generated. Review and refine.*

1. **FALSE NEGATIVES**: 
   - It fails to address the risk of hybrid cryptographic implementations that may not fully utilize quantum-resistance, such as an ECDH + ML-KEM combination with weak fallback mechanisms.
   - The profile does not consider risks associated with other post-quantum key exchange algorithms like Lattice-based schemes that might be implemented in stealth addresses.

2. **FALSE POSITIVES**: 
   - It overflags the risk of classical-only smart accounts, which might still use quantum-resistant techniques for off-chain interactions or backups.
   - The profile incorrectly flags all BLS constructions as high risk without considering context; some BLS schemes can operate on non-pairing-friendly curves that are quantum-secure.

3. **FUNDAMENTAL LIMITATIONS**: 
   - Quantum computers pose an existential threat to all ECC-based systems, regardless of their implementation details.
   - Behavioral profiling remains a significant vulnerability even with strong cryptographic measures in place, as patterns can still be detected over time.
   - The profile cannot mitigate risks arising from human factors or operational errors, such as misconfigurations or user mistakes.