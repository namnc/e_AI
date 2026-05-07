# Prior art — l2_bridge_linkage

## What this guard catches (one line)
Cross-chain identity correlation introduced by bridge usage — implicit cues (timing, amount, gas, counterparty) that link a user's identity across L1/L2/sidechain ecosystems via specific bridge-protocol fingerprints.

## Existing tools that implement this (FULL or substantive coverage)

### Chainalysis Reactor
- URL: https://www.chainalysis.com/, https://www.chainalysis.com/blog/introduction-to-cross-chain-bridges/
- What it does: Commercial forensics tool that traces funds across hundreds of bridge protocols and DEXs; uses bridge-specific implicit cues (transaction patterns inherent to each bridge) to correlate cross-chain identity.
- Coverage of the heuristic set: Defines the offensive baseline — covers timing correlation, amount preservation, counterparty linking, multi-input clustering across UTXO + account chains.
- Notable: Commercial; the threat being defended against. 50+ chains, 640+ bridges.

### Elliptic / TRM Labs
- URL: https://www.elliptic.co/blog/following-funds-across-blockchains, https://www.trmlabs.com/glossary/cross-chain-tracing
- What it does: Cross-chain tracing platforms used by law enforcement and AML; automated bridge tracing across major bridges.
- Coverage: Same as Chainalysis — the offensive side.

### AnChain.AI
- URL: https://www.anchain.ai/blog/cross-chain-bridge-tracing
- What it does: Cross-chain bridge tracing toolkit.
- Coverage: Commercial cross-chain analytics.

### "Track and Trace" (arXiv 2504.01822, 2025)
- URL: https://arxiv.org/html/2504.01822v1
- What it does: Academic paper on automatically uncovering cross-chain transactions in multi-blockchain ecosystems.
- Coverage: Open methodology that documents what commercial tools do.
- Notable: Primary academic reference for cross-chain heuristics.

## Existing tools that implement this PARTIALLY

### Merkle Science cross-chain analytics
- URL: https://www.merklescience.com/blog/cross-chain-analytics-law-enforcement-2025
- What it does: AML / law-enforcement cross-chain analytics.
- Coverage: Same family as Chainalysis.

### Chain Bridge research (privacy-preserving routing)
- URL: https://www.sciencedirect.com/science/article/pii/S2096720925001630
- What it does: Privacy-preserving framework for anonymous authentication and cross-chain routing.
- Coverage: Defensive research, not a runtime tool.

## Adjacent / not-quite-this-guard

### Privacy-preserving bridges (zkBridge proposals, Penumbra IBC, etc.)
- Why adjacent: Protocol-level mitigation that hides the linkage; out of scope for a wallet-side guard against existing bridges.

### Multi-Input Clustering heuristic (UTXO origin)
- Why adjacent: Bitcoin-era heuristic that gets repurposed in account-chain clustering; foundational but not bridge-specific.

## Where e_AI l2_bridge_linkage differs

Commercial forensics (Chainalysis et al.) operate the offensive side; academic literature documents the methodology. There is no widely-deployed *user-side* tool that warns at the moment of bridging: "this bridge tx will be linkable to your destination identity within ~minutes via timing + amount; consider [delay / split / different bridge] to break the link." e_AI's wedge: pre-bridge runtime classification + actionable mitigation (split into multiple txs, delay, route through pool, use different bridge). Honest: the heuristics are well-known to forensics firms; novelty is in user-side runtime delivery + the recommendation engine. The existence of large analytics firms means there's no shortage of demand on the offensive side — defensive runtime is genuinely under-served.

## Open positioning question for the post

This is the inverse of Chainalysis. Is the framing "Chainalysis-defense for users" too adversarial for the EF context, or is it precisely the framing CROPS calls for? Also: per-bridge heuristic curation is a significant ongoing maintenance burden — how does the publication handle the staleness?

## Sources

- [Chainalysis — Cross-chain Bridges intro](https://www.chainalysis.com/blog/introduction-to-cross-chain-bridges/)
- [Elliptic — Following funds across blockchains](https://www.elliptic.co/blog/following-funds-across-blockchains)
- [TRM Labs — Cross-Chain Tracing glossary](https://www.trmlabs.com/glossary/cross-chain-tracing)
- [AnChain.AI cross-chain tracing](https://www.anchain.ai/blog/cross-chain-bridge-tracing)
- [Track and Trace (arXiv 2504.01822)](https://arxiv.org/html/2504.01822v1)
- [Merkle Science cross-chain analytics](https://www.merklescience.com/blog/cross-chain-analytics-law-enforcement-2025)
