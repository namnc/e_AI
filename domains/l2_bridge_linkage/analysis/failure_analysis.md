# Failure Analysis: l2_bridge_linkage

*Auto-generated. Review and refine.*

1. **FALSE NEGATIVES**: 
   - The profile does not account for cases where users bridge assets through multi-sig wallets or smart contracts that obscure the direct user address, leading to a false sense of security.
   - It fails to detect when bridging is done through decentralized platforms like Polygon Linker, where user actions are less deterministic and harder to trace.

2. **FALSE POSITIVES**: 
   - H4 may over-flag instances where an L2 address receives gas funding from other sources unrelated to the bridge transaction, such as automated smart contracts.
   - H3 might falsely identify users who have a consistent but non-bridging pattern for legitimate reasons, such as regular application of protocols or services on different chains.

3. **FUNDAMENTAL LIMITATIONS**: 
   - The profile cannot mitigate risks associated with zero-knowledge proofs and zkRollups where transaction data is hidden from the blockchain.
   - It cannot address cases of bridge misuse by malicious actors who use complex, layered transactions to obfuscate their identities across L1 and L2.