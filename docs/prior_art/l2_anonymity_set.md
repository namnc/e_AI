# Prior art — l2_anonymity_set

## What this guard catches (one line)
Privacy-degrading conditions on L2s — thin anonymity sets, sequencer visibility into pre-confirmation transactions, deanonymization risk via forced-inclusion fallback to L1, and L2-specific stealth-address effectiveness (ranges 25.8% Polygon to 65.7% Arbitrum recovery rates).

## Existing tools that implement this (FULL or substantive coverage)

### "Anonymity Analysis of the Umbra Stealth Address Scheme" (Wahrstätter et al. 2023)
- URL: https://arxiv.org/pdf/2308.01703
- What it does: Quantifies per-L2 deanonymization rates: 48.5% Ethereum mainnet, 25.8% Polygon, 65.7% Arbitrum, 52.6% Optimism. Reveals that smaller L2 user bases produce thinner anonymity sets and higher deanon rates.
- Coverage: The empirical foundation for the "L2 anonymity set is smaller" claim.
- Notable: Counter-intuitive: Polygon (large user base) was *least* deanonymized; Arbitrum (heavier on-chain power-user activity) most.

### Aztec
- URL: https://aztec.network/, https://l2beat.com/scaling/projects/aztec
- What it does: Privacy-first L2 with default-private accounts and transactions; runs ~617 decentralized sequencer nodes (PoS).
- Coverage: Anonymity set = the entire Aztec user base (~500K cumulative users, ~$8.74M TVL); structural rather than operational guard.
- Notable: Where you go *to escape* the L2 anonymity-set problem.

### L2BEAT
- URL: https://l2beat.com/
- What it does: L2 risk dashboard — tracks sequencer centralization, escape hatches, data availability, governance for every L2.
- Coverage: Network-level posture data. Doesn't compute anonymity sets but provides the inputs (active addresses, sequencer model, forced-inclusion model).
- Notable: De-facto data source for L2-risk analysis.

### Quantstamp L2 Security Framework
- URL: https://github.com/quantstamp/l2-security-framework
- What it does: Open framework for assessing L2 security posture.
- Coverage: Security framework, partly covers privacy-relevant items like sequencer trust.

## Existing tools that implement this PARTIALLY

### Arbitrum sequencer + censorship-resistance docs
- URL: https://docs.arbitrum.io/how-arbitrum-works/deep-dives/sequencer
- What it does: Documents Arbitrum's centralized sequencer + delayed-inbox forced-inclusion fallback (~24h).
- Coverage: Provides the mechanism docs needed to reason about deanon risk.

### Academic L2-privacy taxonomy work (e.g., ScienceDirect 2025 taxonomy)
- URL: https://www.sciencedirect.com/science/article/pii/S2096720925001150
- What it does: Comprehensive taxonomy of security assumptions in permissionless blockchains and L2s.
- Coverage: Academic framework, not a runtime guard.

## Adjacent / not-quite-this-guard

### Privacy-preserving L2s (Aztec, Linea privacy attempts, Anoma applications)
- Why adjacent: Architectural escape route, not a guard for users on non-private L2s.

### Forced-inclusion analysis (research thread on rollup escape hatches)
- Why adjacent: Separate concern — censorship-resistance, not anonymity.

## Where e_AI l2_anonymity_set differs

The Wahrstätter paper and L2BEAT provide the data; no existing tool surfaces a per-transaction "this L2 currently has a thin anonymity set for this operation" warning to a user. e_AI's wedge: real-time anonymity-set sizing per L2 per operation type (e.g., "your stealth-address withdraw on Optimism today has effective anonymity set of N — below your threshold; consider mainnet or Aztec instead"). This is genuinely under-served. Honest: the heuristic is published; turning it into a runtime guard is the contribution.

## Open positioning question for the post

The empirical work (Wahrstätter) is strong. Is the contribution "operationalize Wahrstätter into a runtime per-L2 anonymity-set warning" — and if so, does it need to extend beyond Umbra/stealth-address to general privacy-set sizing on L2s (which is a much bigger research project)?

## Sources

- [Anonymity Analysis of Umbra (per-L2 rates)](https://arxiv.org/pdf/2308.01703)
- [Aztec Network](https://aztec.network/)
- [Aztec on L2BEAT](https://l2beat.com/scaling/projects/aztec)
- [Arbitrum sequencer docs](https://docs.arbitrum.io/how-arbitrum-works/deep-dives/sequencer)
- [Quantstamp L2 Security Framework](https://github.com/quantstamp/l2-security-framework)
- [L2 Security Taxonomy (ScienceDirect)](https://www.sciencedirect.com/science/article/pii/S2096720925001150)
