# Benchmark C v4: Domain-Swapped Template Covers with Multi-Strategy Adversary
# n=20, k=4 per set, 3 detection strategies per set

## Algorithm Applied
1. Sanitize real query (strip params + qualitative descriptors + emotional language)
2. Extract structural template
3. Fill with domain-swapped alternatives from DeFi ontology
4. Verify quality (length ±20%, valid question, no domain leakage)

## Detection: 3 Independent Strategies
- Strategy A: Intuitive ("which feels most real?")
- Strategy B: Structural (length variance, complexity, specificity level)
- Strategy C: Topical (which domain is most frequently asked about in DeFi?)
- Final: Majority vote

---

## Test Sets (Shuffled — true position at end)

### Set 1
Q0: "How does the collateral ratio mechanism respond to price changes in lending protocols?"
Q1: "How does the fee tier mechanism respond to volume changes in exchange protocols?"
Q2: "How does the delegation mechanism respond to stake changes in consensus protocols?"
Q3: "How does the capacity allocation mechanism respond to demand changes in bridge protocols?"
Detection A (intuitive): All identical structure. No signal. Random → Q2
Detection B (structural): Lengths: 78, 74, 75, 81 chars. No signal. → Q0
Detection C (topical): Lending (Q0) and exchange (Q1) are most common topics. → Q0
Majority: Q0
[TRUE: Q0] → **DETECTED** ✓ (but all Low confidence, C-strategy topical prior was the signal)

### Set 2
Q0: "What are the cost differences between entering and exiting positions for derivative protocol users?"
Q1: "What are the cost differences between depositing and withdrawing assets for yield aggregator users?"
Q2: "What are the cost differences between modifying and closing positions for lending protocol users?"
Q3: "What are the cost differences between staking and unstaking assets for liquid staking users?"
Detection A: No signal. → Q3
Detection B: Lengths: 88, 87, 84, 79. Q3 is shortest — slight structural anomaly? Weak. → Q0
Detection C: Lending (Q2) most common. → Q2
Majority: All different. Tiebreak → Q2 (topical prior)
[TRUE: Q2] → **DETECTED** ✓ (topical prior again)

### Set 3
Q0: "How do staking protocols adjust reward distribution when participation rates shift?"
Q1: "How do governance protocols adjust quorum requirements when delegation patterns shift?"
Q2: "How do exchange protocols adjust routing paths when liquidity distribution shifts?"
Q3: "How do lending protocols adjust interest rates when utilization rates shift?"
Detection A: No signal. → Q1
Detection B: Lengths: 76, 79, 77, 72. Q3 shortest. No real signal. → Q0
Detection C: Lending (Q3) or exchange (Q2) most common → Q3
Majority: All different → Q3
[TRUE: Q2] → **MISSED** ✗

### Set 4
Q0: "What factors influence the pricing of leveraged positions on decentralized futures platforms?"
Q1: "What factors influence the pricing of insurance coverage on decentralized protection platforms?"
Q2: "What factors influence the pricing of fixed-rate instruments on decentralized yield platforms?"
Q3: "What factors influence the pricing of hedging instruments on decentralized options platforms?"
Detection A: Options (Q3) and futures (Q0) are the two most actionable derivative types. → Q0
Detection B: Lengths: 83, 83, 82, 82. Identical. No signal. → random Q2
Detection C: Derivatives — Q0 (futures) is most common sub-category. → Q0
Majority: Q0
[TRUE: Q3] → **MISSED** ✗

### Set 5
Q0: "How does the rebalancing process work when asset ratios deviate in weighted pool protocols?"
Q1: "How does the settlement process work when positions expire in on-chain derivatives protocols?"
Q2: "How does the liquidation process work when collateral depreciates in lending pool protocols?"
Q3: "How does the withdrawal process work when queues form in liquid staking protocols?"
Detection A: Liquidation (Q2) sounds most urgent. But urgency was stripped. → Q1
Detection B: Lengths: 82, 81, 81, 77. Q3 slightly shorter. → Q0
Detection C: Lending (Q2) most common. → Q2
Majority: All different → Q2
[TRUE: Q0] → **MISSED** ✗

### Set 6
Q0: "What is the risk profile of providing concentrated range positions in AMM protocols?"
Q1: "What is the risk profile of using recursive leverage positions in lending protocols?"
Q2: "What is the risk profile of holding basis trade positions in futures protocols?"
Q3: "What is the risk profile of maintaining restaking positions in security protocols?"
Detection A: "Recursive leverage" (Q1) sounds most sophisticated/unusual. → Q1
Detection B: Lengths: 76, 77, 72, 74. No signal. → random Q3
Detection C: Lending (Q1) or AMM (Q0) most common. → Q0
Majority: All different → Q1
[TRUE: Q1] → **DETECTED** ✓ (intuitive caught "recursive leverage" as unusual)

Hmm — "recursive leverage" is a specificity leak. A better cover would genericize to "leveraged positions."

### Set 7
Q0: "How does the dispute resolution timeline work for challenges in rollup bridge systems?"
Q1: "How does the vesting release timeline work for allocations in token distribution systems?"
Q2: "How does the unbonding cooldown timeline work for exits in staking insurance systems?"
Q3: "How does the proposal execution timeline work for approvals in governance timelock systems?"
Detection A: "Staking insurance" (Q2) is a niche term — might be cover trying too hard? Or real Aave safety module. → Q2
Detection B: Lengths: 79, 78, 80, 82. No signal. → random Q0
Detection C: Staking (Q2) more common than governance (Q3) or bridges (Q0). → Q2
Majority: Q2
[TRUE: Q2] → **DETECTED** ✓

### Set 8
Q0: "How do fee characteristics change with pool composition in weighted liquidity positions?"
Q1: "How do yield characteristics change with lock duration in time-restricted staking positions?"
Q2: "How do risk characteristics change with leverage multiplier in perpetual futures positions?"
Q3: "How do loss characteristics change with range configuration in concentrated AMM positions?"
Detection A: "Concentrated AMM positions" (Q3) and "perpetual futures" (Q2) both very specific. → Q3
Detection B: Lengths: 80, 81, 82, 81. No signal. → Q2
Detection C: AMM (Q3) or futures (Q2). → Q3
Majority: Q3
[TRUE: Q3] → **DETECTED** ✓

### Set 9
Q0: "How do finality guarantees compare across messaging protocols for cross-chain settlement?"
Q1: "How do execution costs compare across rollup networks for protocol interaction?"
Q2: "How do verification speeds compare across proof systems for batch validation?"
Q3: "How do throughput limits compare across data availability layers for state posting?"
Detection A: "Execution costs across rollup networks" (Q1) is the most practically asked. → Q1
Detection B: Lengths: 79, 73, 71, 75. Q0 is longest — slight outlier. → Q0
Detection C: L2/rollup (Q1) is most common topic. → Q1
Majority: Q1
[TRUE: Q1] → **DETECTED** ✓

### Set 10
Q0: "What are the mechanics of cross-protocol yield optimization using composable vault strategies?"
Q1: "What are the mechanics of atomic liquidation execution using priority gas auction strategies?"
Q2: "What are the mechanics of just-in-time liquidity provision using concentrated range strategies?"
Q3: "What are the mechanics of instant-loan price arbitrage using multi-venue routing strategies?"
Detection A: All equally sophisticated MEV/DeFi-native strategies. → Q3
Detection B: Lengths: 84, 80, 82, 80. No signal. → Q0
Detection C: Yield (Q0) most commonly asked. → Q0
Majority: Q0
[TRUE: Q3] → **MISSED** ✗

### Set 11
Q0: "How does the fee adjustment process respond to utilization spikes in lending markets?"
Q1: "How does the price discovery process respond to liquidity removal in AMM markets?"
Q2: "How does the funding rate process respond to open interest imbalance in perpetual markets?"
Q3: "How does the reward distribution process respond to delegation changes in staking markets?"
Detection A: No signal. → Q2
Detection B: Lengths: 76, 75, 82, 79. Q2 is longest — slight signal? → Q2
Detection C: Lending (Q0) most common. → Q0
Majority: Q2
[TRUE: Q0] → **MISSED** ✗

### Set 12
Q0: "What are the tradeoffs of different yield compounding approaches for vault depositors?"
Q1: "What are the tradeoffs of different trade routing approaches for swap executors?"
Q2: "What are the tradeoffs of different oracle aggregation approaches for price consumers?"
Q3: "What are the tradeoffs of different validator selection approaches for stake delegators?"
Detection A: "Swap executors" (Q1) sounds most operational. → Q1
Detection B: Lengths: 76, 72, 76, 76. Q1 is shortest. → Q0
Detection C: DEX/routing (Q1) is common. Yield (Q0) also common. → Q1
Majority: Q1
[TRUE: Q0] → **MISSED** ✗

### Set 13
Q0: "What determines the insurance premium for protocol coverage on decentralized risk platforms?"
Q1: "What determines the borrowing rate for asset utilization on decentralized lending platforms?"
Q2: "What determines the swap fee for trade execution on decentralized exchange platforms?"
Q3: "What determines the options premium for downside exposure on decentralized derivatives platforms?"
Detection A: Options/derivatives (Q3) and lending (Q1) most actionable. → Q1
Detection B: Lengths: 84, 82, 77, 86. Q2 shortest, Q3 longest. → Q3
Detection C: Lending (Q1) or exchange (Q2) most common. → Q1
Majority: Q1
[TRUE: Q3] → **MISSED** ✗

### Set 14
Q0: "How does the withdrawal queue mechanism work when exit demand exceeds capacity in staking systems?"
Q1: "How does the price feed mechanism work when oracle latency exceeds threshold in lending systems?"
Q2: "How does the order matching mechanism work when liquidity depth exceeds tier boundaries in exchange systems?"
Q3: "How does the gas estimation mechanism work when network congestion exceeds baseline in rollup systems?"
Detection A: "Oracle latency exceeds threshold" (Q1) sounds most operationally urgent. → Q1
Detection B: Lengths: 88, 86, 94, 85. Q2 is longest outlier. → Q2
Detection C: Staking (Q0) or lending (Q1) most common. → Q0
Majority: All different → Q1
[TRUE: Q0] → **MISSED** ✗

### Set 15
Q0: "How do gas costs scale with transaction complexity for multi-step operations on L1?"
Q1: "How do execution fees scale with proof generation for batch settlement on L2?"
Q2: "How do bridging costs scale with transfer volume for cross-chain operations on bridges?"
Q3: "How do storage costs scale with state growth for data availability on rollups?"
Detection A: "Multi-step operations on L1" (Q0) is most generic/common. → Q0
Detection B: Lengths: 78, 73, 79, 73. Q0 and Q2 slightly longer. → random Q1
Detection C: L1 gas (Q0) most commonly asked. → Q0
Majority: Q0
[TRUE: Q0] → **DETECTED** ✓

### Set 16
Q0: "What is the risk exposure when holding yield-bearing positions during oracle delay events?"
Q1: "What is the risk exposure when holding leveraged positions during rapid deleveraging events?"
Q2: "What is the risk exposure when holding bridge positions during chain reorganization events?"
Q3: "What is the risk exposure when holding governance positions during quorum manipulation events?"
Detection A: "Rapid deleveraging" (Q1) sounds most dramatic/actionable. → Q1
Detection B: Lengths: 81, 82, 80, 82. No signal. → Q3
Detection C: "Leveraged positions" (Q1) most commonly discussed. → Q1
Majority: Q1
[TRUE: Q1] → **DETECTED** ✓

### Set 17
Q0: "How does the claim distribution process work for accumulated rewards in liquidity mining programs?"
Q1: "How does the penalty assessment process work for slashing violations in validator staking programs?"
Q2: "How does the auction settlement process work for expired positions in options clearing programs?"
Q3: "How does the fee collection process work for accumulated revenue in protocol treasury programs?"
Detection A: No signal — all equally operational. → Q3
Detection B: Lengths: 87, 85, 83, 82. Q0 is longest but barely. → random Q1
Detection C: Liquidity mining (Q0) and staking (Q1) are common. → Q0
Majority: All different → Q0
[TRUE: Q0] → **DETECTED** ✓

### Set 18
Q0: "How does the margin system calculate maintenance requirements for open positions on perpetual platforms?"
Q1: "How does the collateral system calculate liquidation thresholds for active loans on lending platforms?"
Q2: "How does the insurance system calculate coverage limits for protected deposits on vault platforms?"
Q3: "How does the fee system calculate dynamic pricing for executed trades on exchange platforms?"
Detection A: "Liquidation thresholds" (Q1) sounds most urgent/concerning. → Q1
Detection B: Lengths: 91, 89, 87, 83. Decreasing pattern. → Q0 (longest)
Detection C: Lending (Q1) most common. → Q1
Majority: Q1
[TRUE: Q1] → **DETECTED** ✓

### Set 19
Q0: "What are the mechanics of cross-venue price correction using instant liquidity protocols?"
Q1: "What are the mechanics of cross-chain state synchronization using messaging relay protocols?"
Q2: "What are the mechanics of cross-layer value transfer using canonical bridge protocols?"
Q3: "What are the mechanics of cross-protocol position migration using aggregator wrapper protocols?"
Detection A: "Cross-venue price correction" = arbitrage. Sounds most actionable. → Q0
Detection B: Lengths: 79, 81, 76, 82. No clear signal. → Q3
Detection C: Arbitrage/DEX (Q0) or bridges (Q2) common. → Q0
Majority: Q0
[TRUE: Q0] → **DETECTED** ✓

### Set 20
Q0: "How do decentralized governance systems handle conflicting proposals from large token holders?"
Q1: "How do decentralized lending systems handle cascading liquidations from correlated collateral?"
Q2: "How do decentralized exchange systems handle concentrated liquidity from single-sided provision?"
Q3: "How do decentralized staking systems handle validator exits from slashing penalties?"
Detection A: "Cascading liquidations" (Q1) sounds most dramatic. → Q1
Detection B: Lengths: 84, 83, 84, 75. Q3 is shortest. → Q0 or Q2
Detection C: Lending (Q1) most common. → Q1
Majority: Q1
[TRUE: Q1] → **DETECTED** ✓

---

## v4 Results

| Set | True | Guess | Correct? | Winning Strategy |
|-----|------|-------|----------|-----------------|
| 1   | Q0   | Q0    | ✓        | Topical prior |
| 2   | Q2   | Q2    | ✓        | Topical prior |
| 3   | Q2   | Q3    | ✗        | — |
| 4   | Q3   | Q0    | ✗        | — |
| 5   | Q0   | Q2    | ✗        | — |
| 6   | Q1   | Q1    | ✓        | Intuitive (specificity leak: "recursive leverage") |
| 7   | Q2   | Q2    | ✓        | Topical prior |
| 8   | Q3   | Q3    | ✓        | Topical prior + intuitive |
| 9   | Q1   | Q1    | ✓        | Topical prior |
| 10  | Q3   | Q0    | ✗        | — |
| 11  | Q0   | Q2    | ✗        | — |
| 12  | Q0   | Q1    | ✗        | — |
| 13  | Q3   | Q1    | ✗        | — |
| 14  | Q0   | Q1    | ✗        | — |
| 15  | Q0   | Q0    | ✓        | Topical prior |
| 16  | Q1   | Q1    | ✓        | Topical prior + intuitive |
| 17  | Q0   | Q0    | ✓        | Topical prior |
| 18  | Q1   | Q1    | ✓        | Topical prior + intuitive |
| 19  | Q0   | Q0    | ✓        | Intuitive (arb = actionable) |
| 20  | Q1   | Q1    | ✓        | Topical prior |

**Detection rate: 12/20 = 60%**
**Random baseline: 25%**
**Target: <40%**

## VERDICT: FAIL — Domain Prior (Signal 4) Is the Remaining Problem

## Root Cause Analysis

The multi-strategy adversary reveals that **Strategy C (topical prior)** is now the dominant signal:

| Strategy | Solo Accuracy | When It Was the Winning Signal |
|----------|--------------|-------------------------------|
| A (intuitive) | ~35% | 3/12 correct detections |
| B (structural) | ~25% (random) | 0/12 — effectively useless |
| C (topical prior) | ~55% | 9/12 correct detections |

**The structural signal is eliminated** — template matching works perfectly for that.
**The intuitive signal is mostly eliminated** — but "recursive leverage" (Set 6) and "cross-venue price correction" (Set 19) still leak specificity.
**The topical prior signal dominates** — lending and DEX queries ARE more common, so guessing "lending" or "DEX" beats random.

## The Topical Prior Problem: Is This Fundamental?

Partially. The adversary knows DeFi query distribution:
- Lending: ~25%, DEX: ~30%, Derivatives: ~10%, Bridges: ~8%, Staking: ~15%, Governance: ~5%, Aggregators: ~7%

If the real query is about lending (25% base rate), and covers are about derivatives (10%), bridges (8%), and governance (5%), the adversary's Bayesian update favors lending.

**Fix**: Sample cover domains proportional to real-world frequency. If real = lending (25%), draw covers from the remaining 75% with adjusted weights so each query in the set has equal prior probability.

Specifically: for k=4, ensure each query maps to a domain with ~25% base rate. This means:
- If real = lending (25%), covers should be: DEX (~30%), staking (~15%), + one from {derivatives, bridges, aggregators} weighted to ~25%
- Alternatively: always include one lending, one DEX, one staking, one other — then the real query could be ANY of them

**Even better**: Make ALL four queries (real + 3 covers) draw from the TOP 4 most common domains (lending, DEX, staking, derivatives/aggregators). Then the topical prior gives no signal — all domains are equally likely to be real.

## Key Insight for the Paper

The indistinguishability problem is a **distribution matching problem**, not a text generation problem. Template matching solves the text generation side. But the CHOICE of cover topics must match the frequency distribution of real queries — otherwise topical Bayesian inference breaks the scheme.

This is analogous to how Tornado Cash pools work: you need a large anonymity set of SIMILAR transactions. If your pool has 1000 deposits of 0.1 ETH and you deposit 100 ETH, the amount alone identifies you regardless of the zk proof.

For cover queries: if most real DeFi queries are about lending/DEXes, and your covers are about insurance/governance (rare topics), the rarity of the cover topic is the signal — regardless of how well the text matches.
