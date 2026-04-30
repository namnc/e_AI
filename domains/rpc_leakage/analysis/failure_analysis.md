# Failure Analysis: rpc_leakage

*Auto-generated. Review and refine.*

1. **FALSE NEGATIVES**: This profile fails to detect risks associated with transactional metadata leaks, such as transaction signatures or private keys inadvertently exposed through RPC calls. It also misses the risk of data exfiltration via off-chain analytics tools that users might leverage for complex analyses, which could reveal sensitive information not directly queried.

2. **FALSE POSITIVES**: The profile may over-flag innocent user behavior in scenarios where multiple addresses are used to manage different assets or accounts independently, without any underlying linkage. Similarly, frequent balance checks by a wallet provider managing multiple customer accounts could trigger alerts unnecessarily.

3. **FUNDAMENTAL LIMITATIONS**: Technology cannot prevent all potential leaks from complex interactions with smart contracts. For instance, certain on-chain activities inherently reveal information that cannot be hidden, such as contract deployment parameters or interaction history visible to anyone on the blockchain. Additionally, technological limitations mean that it's impossible to fully protect against every possible vector of attack without potentially blocking legitimate user behavior.