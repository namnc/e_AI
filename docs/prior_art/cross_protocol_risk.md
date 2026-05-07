# Prior art — cross_protocol_risk

## What this guard catches (one line)
Cascading liquidation and correlated exposure across DeFi protocols — a position that looks safe on Aave can cascade if the user is also borrowing on Morpho with the same collateral, or if a shared collateral asset experiences a depeg.

## Existing tools that implement this (FULL or substantive coverage)

### Gauntlet
- URL: https://www.gauntlet.xyz/, https://www.gauntlet.xyz/resources/risk-scores-for-defi---alpha-release
- What it does: Simulation-based DeFi risk modeling — agent-based simulation of stress events (Black Thursday, ETH crash, depeg cascades) for protocols (Aave, Compound, etc.). Publishes "Risk Scores for DeFi" alpha.
- Coverage of the heuristic set: Covers protocol-level risk parameters. Less explicit on per-user cross-protocol position risk.
- Notable: De-facto risk advisor for major lending protocols. Quantitative rigor.

### Chaos Labs
- URL: https://chaoslabs.xyz/, https://chaoslabs.xyz/posts/risk-oracles-real-time-risk-management-for-defi
- What it does: "Risk Oracles" — real-time risk data fed to smart contracts; combines on-chain analytics + off-chain market intelligence; emphasis on real-time observability.
- Coverage: Real-time per-protocol risk; cross-protocol composition partially covered via shared-collateral analysis.
- Notable: Direct competitor to Gauntlet; faster cycle.

### DeBank, Zapper, Zerion (portfolio aggregators)
- URL: https://debank.com/, https://zapper.xyz/, https://zerion.io/
- What it does: Cross-protocol position tracking — surfaces the user's full DeFi balance sheet across many protocols.
- Coverage of the heuristic set: Covers the *visibility* prerequisite (can see all positions); less on automated cascade analysis.
- Notable: User has the data; the synthesis to "cascade risk" is left to the user.

### DeFi Saver
- URL: https://defisaver.com/
- What it does: Automated CDP/lending position management — automated deleveraging, liquidation protection.
- Coverage: Active management of single-protocol risk; some cross-protocol awareness.
- Notable: User-facing automation already exists; the gap is reasoning across uncorrelated protocols.

## Existing tools that implement this PARTIALLY

### Forta agents
- URL: https://forta.org/
- What it does: Real-time threat detection bots; some bots monitor liquidation cascades.
- Coverage: Decentralized network; quality of cross-protocol bots varies.

### Risk-rating projects (e.g., Yellow's credit ratings article)
- URL: https://yellow.com/en-US/learn/crypto-credit-ratings-explained-how-risk-scoring-is-coming-on-chain
- What it does: Emerging on-chain credit scoring for protocols.
- Coverage: Industry trend, less mature.

## Adjacent / not-quite-this-guard

### Insurance protocols (Nexus Mutual, Sherlock)
- Why adjacent: Risk-transfer rather than risk-detection.

### Aave / Morpho risk dashboards (per-protocol)
- Why adjacent: Single-protocol risk; doesn't compose across protocols.

## Where e_AI cross_protocol_risk differs

Gauntlet and Chaos Labs operate at the *protocol governance* level — they advise Aave/Compound on parameter setting. DeBank et al. give the user *visibility*. There is no widely-deployed tool that, at the moment a user opens a borrow position, surfaces: "you already have $X collateral on Morpho with the same asset; this borrow on Aave brings your composite LTV to Y%; in a 20% ETH crash, both positions cascade." This is the user-side, pre-action, cross-protocol composition reasoning gap. Honest: per-protocol risk is solved; the *composition* across protocols at user level is genuinely under-served. But it's also a hard problem (requires correct understanding of every protocol's liquidation curve) — quality bar is high.

## Open positioning question for the post

Cross-protocol composition reasoning requires accurate per-protocol risk models that mostly only Gauntlet/Chaos Labs maintain. Is the framing "use Chaos Labs risk oracles + compose locally," or does e_AI need to maintain its own per-protocol risk models (high maintenance cost)?

## Sources

- [Gauntlet](https://www.gauntlet.xyz/)
- [Gauntlet Risk Scores alpha](https://www.gauntlet.xyz/resources/risk-scores-for-defi---alpha-release)
- [Chaos Labs](https://chaoslabs.xyz/)
- [Chaos Labs — Risk Oracles](https://chaoslabs.xyz/posts/risk-oracles-real-time-risk-management-for-defi)
- [Curating Liquidity — Gauntlet's role (HyperNest)](https://hypernest.xyz/curating-liquidity-how-gauntlet-became-defis-risk-brain/)
- [DeFi financial-risk solutions overview](https://medium.com/iosg-ventures/solutions-of-financial-risks-in-defi-12e350042eca)
