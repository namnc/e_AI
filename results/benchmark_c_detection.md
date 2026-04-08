# Benchmark C Phase 3: Adversarial Detection Attempt
# I attempt to identify the "real" query from each shuffled set of 4.
# Being maximally adversarial — looking for any distinguishing signal.

## Detection Strategy
I'll look for:
- Which query sounds most "actionable" (user about to do something)
- Which is most specific to a single protocol operation
- Structural patterns (length, complexity mismatches)
- Whether one query seems more "practical" vs "academic"

---

## Set 1
Q0: Morpho Blue matching mechanics
Q1: Aave V3 HF + collateral
Q2: Compound V3 USDC interest rate
Q3: Maker DSR governance

**Guess: Q1** — "health factor change when collateral is supplied" is the most operationally specific. The others ask about general protocol mechanics.
Confidence: Medium
[TRUE: Q1] → **DETECTED** ✓

## Set 2
Q0: Gas for Gnosis Safe deployment
Q1: Gas for token approval vs permit2
Q2: Gas for Aave collateral add vs closure
Q3: Gas for Uniswap V3 LP position

**Guess: Q2** — "adding collateral vs full position closure" implies a user deciding between two specific actions. The others are more general comparisons.
Confidence: Medium
[TRUE: Q2] → **DETECTED** ✓

## Set 3
Q0: CoW Protocol batch auction
Q1: Curve StableSwap invariant
Q2: 1inch aggregation
Q3: Uniswap V3 routing large swaps

**Guess: Q3** — "route large swaps" includes the word "large" which implies a specific trade. The others are about general mechanisms.
Confidence: Low — "large" could just be educational
[TRUE: Q3] → **DETECTED** ✓

## Set 4
Q0: MakerDAO optimal collateralization ratio
Q1: Optimal split ratio Uniswap/Curve for stablecoin swaps
Q2: Optimal gas price strategy
Q3: Balancer weighted pool rebalancing

**Guess: Q1** — Mentions specific protocols (Uniswap AND Curve) together, suggesting a user planning a real trade across both.
Confidence: Medium
[TRUE: Q1] → **DETECTED** ✓

## Set 5
Q0: Frax collateral ratio adjustment
Q1: Balancer V2 flash loan handling
Q2: Curve 3pool rebalancing when imbalanced
Q3: Lido stETH/ETH peg + withdrawal queues

**Guess: Q2** — "significantly imbalanced" suggests the user is observing a current market condition, not asking academically.
Confidence: Medium
[TRUE: Q2] → **DETECTED** ✓

## Set 6
Q0: Governance token delegation
Q1: Sandwich attack mechanics
Q2: Flash loan arbitrage mechanics
Q3: Liquidation cascades

**Guess: Q2** — Flash loan arbitrage is the most "actionable" — someone asking this is more likely planning to do it.
Confidence: Low — all are equally mechanical questions
[TRUE: Q2] → **DETECTED** ✓

## Set 7
Q0: Pendle yield tokens + implied APY
Q1: Lyra ETH put options + premium
Q2: dYdX perpetual funding rates
Q3: Opyn Squeeth + premium

**Guess: Q1** — Hard to tell. All follow the same pattern "How do X work? What determines Y?"
Let me pick Q3 (Opyn Squeeth) — it's less mainstream, might be a cover trying too hard.
Actually, I'll go Q1 (Lyra) — options + premium is actionable.
Confidence: Low
[TRUE: Q1] → **DETECTED** ✓

## Set 8
Q0: Liquidity depth Ethereum vs Base
Q1: Gas cost Arbitrum vs Optimism
Q2: Security model zkSync vs Polygon zkEVM
Q3: Bridging time comparison

**Guess: Q1** — "gas cost comparison" is the most operationally relevant to someone about to deploy.
Confidence: Low — all are comparison questions
[TRUE: Q1] → **DETECTED** ✓

## Set 9
Q0: Rocket Pool minipool dissolution
Q1: Ethereum validator exit queue
Q2: Aave safety module unstaking cooldown
Q3: Lido withdrawal queue after Shapella

**Guess: Q2** — "unstaking cooldown" implies someone currently staked who needs to know the timeline.
Confidence: Low — all are about staking/unstaking mechanics
[TRUE: Q2] → **DETECTED** ✓

## Set 10
Q0: Cross-chain bridge risks
Q1: Early-stage DeFi governance risks
Q2: New LP pair risks
Q3: Leveraged staking risks

**Guess: Q3** — "leveraged staking strategies using lending protocols" is the most specific and actionable.
Confidence: Low — all follow same "What are the risks of X?" template
[TRUE: Q3] → **DETECTED** ✓

## Set 11
Q0: Slippage scaling with trade size
Q1: Gas cost scaling with calldata
Q2: Impermanent loss scaling with price divergence
Q3: Validator reward variance scaling

**Guess: Q2** — "concentrated liquidity positions" is the most specific DeFi concept; the others are more generic.
Confidence: Low
[TRUE: Q2] → **DETECTED** ✓

## Set 12
Q0: Options settlement on Ethereum
Q1: Perpetual futures liquidation on dYdX
Q2: Dutch auction liquidation in MakerDAO
Q3: Isolated vs cross-margin

**Guess: Q1** — "dYdX" is specifically named, and "liquidation" is actionable (someone with a position).
Wait — Q2 also names MakerDAO specifically and is about liquidation.
I'll go Q1 — perpetual futures liquidation is more "urgent" operationally.
Confidence: Low
[TRUE: Q1] → **DETECTED** ✓

## Set 13
Q0: Chainlink OCR price feeds
Q1: MakerDAO liquidation auction
Q2: Aave interest rate model
Q3: Compound Governor Bravo lifecycle

**Guess: Q1** — "liquidation auction system" is most actionable (someone concerned about liquidation).
Confidence: Medium
[TRUE: Q1] → **DETECTED** ✓

## Set 14
Q0: Gas price → inclusion probability
Q1: Validator stake → MEV capability
Q2: ETH IV → options premium on Lyra
Q3: TVL → yield in AMMs

**Guess: Q2** — Most specific: names a specific protocol (Lyra), specific asset (ETH), specific metric (implied volatility).
Confidence: Medium
[TRUE: Q2] → **DETECTED** ✓

## Set 15
Q0: Hard forks → gas fee dynamics
Q1: Governance proposals → token prices
Q2: Stablecoin depegging → DeFi propagation
Q3: Token unlocks → selling pressure

**Guess: Q1** — "governance proposals affect token prices historically" — the word "historically" makes it sound research-oriented rather than operational. Hmm. Actually that makes it LESS likely to be real...
Let me go Q3 — "token unlock schedules affect selling pressure" is most actionable for someone holding VC-backed tokens.
Confidence: Low
[TRUE: Q1] → **MISSED** ✗ (guessed Q3)

## Set 16
Q0: MEV-boost relay centralization risks
Q1: Cross-chain bridge risks
Q2: Upgradeability pattern risks
Q3: Oracle manipulation risks

**Guess: Q1** — cross-chain bridges are the most common operational concern.
Confidence: Low — all follow same template
[TRUE: Q1] → **DETECTED** ✓

## Set 17
Q0: Intent-based trading (CoW Swap, UniswapX)
Q1: Yield compounding (Yearn)
Q2: Vote-escrow tokenomics (Curve, Balancer)
Q3: Cross-chain messaging (LayerZero, Axelar)

**Guess: Q1** — yield compounding is the most "user-action-oriented" (someone depositing into Yearn).
Confidence: Low — all name specific protocols
[TRUE: Q1] → **DETECTED** ✓

## Set 18
Q0: Yield: native staking vs LSD
Q1: Gas overhead: Gnosis Safe vs EOA
Q2: MEV exposure: public mempool vs Flashbots
Q3: Latency: Ethereum vs Arbitrum

**Guess: Q1** — "gas overhead of using Gnosis Safe vs EOA" is the most operationally specific decision.
Confidence: Low
[TRUE: Q1] → **DETECTED** ✓

## Set 19
Q0: Restaking yield: Eigenlayer vs Lido
Q1: Rocket Pool minipool bond vs solo staking capital
Q2: Eigenlayer slashing risk vs native staking
Q3: Lido socialized slashing vs solo validator

**Guess: Q2** — "slashing risk" is most fear-driven/actionable.
Confidence: Low — all are staking comparisons
[TRUE: Q2] → **DETECTED** ✓

## Set 20
Q0: L2 data availability tradeoffs
Q1: On-chain identity/reputation tradeoffs
Q2: DEX aggregator routing tradeoffs
Q3: Oracle design tradeoffs

**Guess: Q2** — DEX aggregator routing is the most operationally relevant to a trader.
Confidence: Low
[TRUE: Q2] → **DETECTED** ✓

---

## Results

| Set | True Position | My Guess | Correct? | Confidence |
|-----|--------------|----------|----------|------------|
| 1   | Q1 | Q1 | ✓ | Medium |
| 2   | Q2 | Q2 | ✓ | Medium |
| 3   | Q3 | Q3 | ✓ | Low |
| 4   | Q1 | Q1 | ✓ | Medium |
| 5   | Q2 | Q2 | ✓ | Medium |
| 6   | Q2 | Q2 | ✓ | Low |
| 7   | Q1 | Q1 | ✓ | Low |
| 8   | Q1 | Q1 | ✓ | Low |
| 9   | Q2 | Q2 | ✓ | Low |
| 10  | Q3 | Q3 | ✓ | Low |
| 11  | Q2 | Q2 | ✓ | Low |
| 12  | Q1 | Q1 | ✓ | Low |
| 13  | Q1 | Q1 | ✓ | Medium |
| 14  | Q2 | Q2 | ✓ | Medium |
| 15  | Q1 | Q3 | ✗ | Low |
| 16  | Q1 | Q1 | ✓ | Low |
| 17  | Q1 | Q1 | ✓ | Low |
| 18  | Q1 | Q1 | ✓ | Low |
| 19  | Q2 | Q2 | ✓ | Low |
| 20  | Q2 | Q2 | ✓ | Low |

**Detection rate: 19/20 = 95%**
**Random baseline: 25%**
**Target: <40%**

## VERDICT: FAIL

The covers are trivially distinguishable. Detection rate of 95% is close to TrackMeNot's 99.98%.

## Root Cause Analysis

The problem is clear: **the real queries are systematically more "operationally specific" and "actionable" than the covers.** The covers tend to be about general protocol mechanics, while the real queries tend to ask about specific operations a user would perform (adding collateral, closing positions, optimal routing).

This is because the real queries were DESIGNED as "what the orchestrator would send after sanitization" — they still carry the semantic fingerprint of "someone about to do something." The covers were generated to be "plausible DeFi questions" but skew toward "educational/research" tone.

## What Needs to Change

1. **Covers must match the actionability level of real queries** — not just the topic, but the "I'm about to do this" tone
2. **Real queries need to be further sanitized toward generic/educational framing** — strip not just parameters but also operational specificity
3. **The cover generation prompt needs to explicitly instruct: "generate queries that sound like someone who is ABOUT TO DO something, not just learning about it"**
4. **Consider sampling covers from real user query distributions** (e.g., LMSYS-Chat-1M filtered for DeFi) rather than generating them
