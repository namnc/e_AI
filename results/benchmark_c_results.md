# Benchmark C: Cover Query Indistinguishability
# Run date: 2026-04-07
# Method: Claude generates covers, shuffles, then attempts detection (adversarial)
# Target: Detection rate <40% (random baseline = 25% for k=4)

## Protocol
1. Take 20 sanitized DeFi queries (representing what the orchestrator would send after stripping private params)
2. For each, generate 3 cover queries (k=4 total)
3. Shuffle randomly, record true position
4. In a separate adversarial pass, attempt to identify the "real" query from each set of 4
5. Report detection rate

---

## Phase 1: Generation (20 query sets)

### Set 1
Real: "How does Aave V3 health factor change when additional collateral is supplied?"
Covers:
- A: "How does Compound V3 calculate the interest rate for USDC borrowers?"
- B: "How does Maker's DAI Savings Rate adjust based on governance votes?"
- C: "How does Morpho Blue match lenders with borrowers at optimal rates?"

### Set 2
Real: "What are the gas costs for adding collateral vs full position closure on Aave V3?"
Covers:
- A: "What are the gas costs for creating a new Uniswap V3 liquidity position vs modifying an existing one?"
- B: "What are the gas costs for approving a token vs using permit2 on Ethereum mainnet?"
- C: "What are the gas costs for deploying a Gnosis Safe with 3-of-5 signers?"

### Set 3
Real: "How does Uniswap V3 route large swaps across multiple fee tiers to minimize slippage?"
Covers:
- A: "How does 1inch aggregate liquidity across DEXes to find optimal swap paths?"
- B: "How does Curve's StableSwap invariant reduce slippage for pegged asset pairs?"
- C: "How does CoW Protocol's batch auction mechanism reduce MEV for traders?"

### Set 4
Real: "What is the optimal split ratio between Uniswap and Curve for large stablecoin swaps?"
Covers:
- A: "What is the optimal strategy for rebalancing a Balancer weighted pool after a large token price movement?"
- B: "What is the optimal gas price strategy for submitting transactions during network congestion?"
- C: "What is the optimal collateralization ratio for opening a MakerDAO vault?"

### Set 5
Real: "How does Curve 3pool rebalancing work when the pool is significantly imbalanced?"
Covers:
- A: "How does Balancer V2's vault architecture handle flash loan requests?"
- B: "How does Lido's stETH/ETH peg mechanism respond to large withdrawal queues?"
- C: "How does Frax's algorithmic stability mechanism adjust the collateral ratio?"

### Set 6
Real: "What are the mechanics of flash loan arbitrage between lending protocols?"
Covers:
- A: "What are the mechanics of liquidation cascades during rapid market downturns?"
- B: "What are the mechanics of sandwich attacks on decentralized exchanges?"
- C: "What are the mechanics of governance token delegation in compound-style protocols?"

### Set 7
Real: "How do ETH put options on Lyra work? What determines the premium?"
Covers:
- A: "How do perpetual futures funding rates on dYdX work? What determines the rate?"
- B: "How do Opyn's Squeeth options provide leveraged ETH exposure? What determines the premium?"
- C: "How do Pendle's yield tokens work? What determines the implied APY?"

### Set 8
Real: "What is the gas cost comparison between Arbitrum and Optimism for DeFi operations?"
Covers:
- A: "What is the security model comparison between zkSync Era and Polygon zkEVM?"
- B: "What is the bridging time comparison between the canonical bridges of major L2s?"
- C: "What is the liquidity depth comparison between Ethereum mainnet and Base for major tokens?"

### Set 9
Real: "How does the Aave safety module unstaking cooldown work?"
Covers:
- A: "How does the Ethereum validator exit queue processing work?"
- B: "How does the Lido withdrawal request queue operate after Shapella?"
- C: "How does the Rocket Pool minipool dissolution process work?"

### Set 10
Real: "What are the risks of leveraged staking strategies using lending protocols?"
Covers:
- A: "What are the risks of providing liquidity to newly launched token pairs on AMMs?"
- B: "What are the risks of using cross-chain bridges for large value transfers?"
- C: "What are the risks of participating in early-stage DeFi protocol governance?"

### Set 11
Real: "How does impermanent loss scale with price divergence in concentrated liquidity positions?"
Covers:
- A: "How does gas cost scale with calldata size in Ethereum L1 transactions?"
- B: "How does slippage scale with trade size relative to pool liquidity depth?"
- C: "How does validator reward variance scale with the number of validators in the network?"

### Set 12
Real: "What are the mechanics of perpetual futures liquidation on dYdX?"
Covers:
- A: "What are the mechanics of Dutch auction liquidation in MakerDAO's DAI system?"
- B: "What are the mechanics of isolated margin vs cross-margin on centralized exchanges?"
- C: "What are the mechanics of options settlement on Ethereum-based protocols?"

### Set 13
Real: "How does MakerDAO's liquidation auction system work?"
Covers:
- A: "How does Aave's interest rate model switch between variable and stable rates?"
- B: "How does Compound Governor Bravo's proposal lifecycle work?"
- C: "How does Chainlink's off-chain reporting (OCR) protocol aggregate price feeds?"

### Set 14
Real: "What is the relationship between ETH implied volatility and options premium on Lyra?"
Covers:
- A: "What is the relationship between gas price and transaction inclusion probability on Ethereum?"
- B: "What is the relationship between TVL and yield in automated market makers?"
- C: "What is the relationship between validator stake size and MEV extraction capability?"

### Set 15
Real: "How do governance proposals affect protocol token prices historically?"
Covers:
- A: "How do token unlock schedules affect selling pressure for VC-backed protocols?"
- B: "How do Ethereum hard forks affect gas fee dynamics in the weeks surrounding the upgrade?"
- C: "How do stablecoin depegging events propagate through interconnected DeFi protocols?"

### Set 16
Real: "What are the security risks of cross-chain bridge transfers?"
Covers:
- A: "What are the security risks of upgradeability patterns in proxy-based smart contracts?"
- B: "What are the security risks of oracle manipulation in DeFi lending protocols?"
- C: "What are the security risks of MEV-boost relay centralization in Ethereum?"

### Set 17
Real: "How does yield compounding work across DeFi aggregators like Yearn?"
Covers:
- A: "How does vote-escrow tokenomics work across protocols like Curve and Balancer?"
- B: "How does intent-based trading work on platforms like CoW Swap and UniswapX?"
- C: "How does cross-chain messaging work across protocols like LayerZero and Axelar?"

### Set 18
Real: "What is the gas overhead of using Gnosis Safe vs EOA for DeFi transactions?"
Covers:
- A: "What is the MEV exposure difference between submitting via public mempool vs Flashbots Protect?"
- B: "What is the yield difference between staking ETH natively vs using a liquid staking derivative?"
- C: "What is the latency difference between Ethereum mainnet and Arbitrum for swap execution?"

### Set 19
Real: "How does Eigenlayer slashing risk compare to native ETH staking risk?"
Covers:
- A: "How does Lido's socialized slashing mechanism compare to solo validator slashing?"
- B: "How does Rocket Pool's minipool bond compare to full 32 ETH solo staking capital requirements?"
- C: "How does restaking yield on Eigenlayer compare to liquid staking yields on Lido?"

### Set 20
Real: "What are the tradeoffs between different DEX aggregator routing algorithms?"
Covers:
- A: "What are the tradeoffs between different L2 data availability solutions?"
- B: "What are the tradeoffs between different oracle designs for DeFi price feeds?"
- C: "What are the tradeoffs between different approaches to on-chain identity and reputation?"

---

## Phase 2: Shuffled Sets (for adversarial detection)

Each set is shuffled. True position recorded separately.

### Set 1 — Shuffled:
Q0: "How does Morpho Blue match lenders with borrowers at optimal rates?"
Q1: "How does Aave V3 health factor change when additional collateral is supplied?"
Q2: "How does Compound V3 calculate the interest rate for USDC borrowers?"
Q3: "How does Maker's DAI Savings Rate adjust based on governance votes?"
[TRUE: Q1]

### Set 2 — Shuffled:
Q0: "What are the gas costs for deploying a Gnosis Safe with 3-of-5 signers?"
Q1: "What are the gas costs for approving a token vs using permit2 on Ethereum mainnet?"
Q2: "What are the gas costs for adding collateral vs full position closure on Aave V3?"
Q3: "What are the gas costs for creating a new Uniswap V3 liquidity position vs modifying an existing one?"
[TRUE: Q2]

### Set 3 — Shuffled:
Q0: "How does CoW Protocol's batch auction mechanism reduce MEV for traders?"
Q1: "How does Curve's StableSwap invariant reduce slippage for pegged asset pairs?"
Q2: "How does 1inch aggregate liquidity across DEXes to find optimal swap paths?"
Q3: "How does Uniswap V3 route large swaps across multiple fee tiers to minimize slippage?"
[TRUE: Q3]

### Set 4 — Shuffled:
Q0: "What is the optimal collateralization ratio for opening a MakerDAO vault?"
Q1: "What is the optimal split ratio between Uniswap and Curve for large stablecoin swaps?"
Q2: "What is the optimal gas price strategy for submitting transactions during network congestion?"
Q3: "What is the optimal strategy for rebalancing a Balancer weighted pool after a large token price movement?"
[TRUE: Q1]

### Set 5 — Shuffled:
Q0: "How does Frax's algorithmic stability mechanism adjust the collateral ratio?"
Q1: "How does Balancer V2's vault architecture handle flash loan requests?"
Q2: "How does Curve 3pool rebalancing work when the pool is significantly imbalanced?"
Q3: "How does Lido's stETH/ETH peg mechanism respond to large withdrawal queues?"
[TRUE: Q2]

### Set 6 — Shuffled:
Q0: "What are the mechanics of governance token delegation in compound-style protocols?"
Q1: "What are the mechanics of sandwich attacks on decentralized exchanges?"
Q2: "What are the mechanics of flash loan arbitrage between lending protocols?"
Q3: "What are the mechanics of liquidation cascades during rapid market downturns?"
[TRUE: Q2]

### Set 7 — Shuffled:
Q0: "How do Pendle's yield tokens work? What determines the implied APY?"
Q1: "How do ETH put options on Lyra work? What determines the premium?"
Q2: "How do perpetual futures funding rates on dYdX work? What determines the rate?"
Q3: "How do Opyn's Squeeth options provide leveraged ETH exposure? What determines the premium?"
[TRUE: Q1]

### Set 8 — Shuffled:
Q0: "What is the liquidity depth comparison between Ethereum mainnet and Base for major tokens?"
Q1: "What is the gas cost comparison between Arbitrum and Optimism for DeFi operations?"
Q2: "What is the security model comparison between zkSync Era and Polygon zkEVM?"
Q3: "What is the bridging time comparison between the canonical bridges of major L2s?"
[TRUE: Q1]

### Set 9 — Shuffled:
Q0: "How does the Rocket Pool minipool dissolution process work?"
Q1: "How does the Ethereum validator exit queue processing work?"
Q2: "How does the Aave safety module unstaking cooldown work?"
Q3: "How does the Lido withdrawal request queue operate after Shapella?"
[TRUE: Q2]

### Set 10 — Shuffled:
Q0: "What are the risks of using cross-chain bridges for large value transfers?"
Q1: "What are the risks of participating in early-stage DeFi protocol governance?"
Q2: "What are the risks of providing liquidity to newly launched token pairs on AMMs?"
Q3: "What are the risks of leveraged staking strategies using lending protocols?"
[TRUE: Q3]

### Set 11 — Shuffled:
Q0: "How does slippage scale with trade size relative to pool liquidity depth?"
Q1: "How does gas cost scale with calldata size in Ethereum L1 transactions?"
Q2: "How does impermanent loss scale with price divergence in concentrated liquidity positions?"
Q3: "How does validator reward variance scale with the number of validators in the network?"
[TRUE: Q2]

### Set 12 — Shuffled:
Q0: "What are the mechanics of options settlement on Ethereum-based protocols?"
Q1: "What are the mechanics of perpetual futures liquidation on dYdX?"
Q2: "What are the mechanics of Dutch auction liquidation in MakerDAO's DAI system?"
Q3: "What are the mechanics of isolated margin vs cross-margin on centralized exchanges?"
[TRUE: Q1]

### Set 13 — Shuffled:
Q0: "How does Chainlink's off-chain reporting (OCR) protocol aggregate price feeds?"
Q1: "How does MakerDAO's liquidation auction system work?"
Q2: "How does Aave's interest rate model switch between variable and stable rates?"
Q3: "How does Compound Governor Bravo's proposal lifecycle work?"
[TRUE: Q1]

### Set 14 — Shuffled:
Q0: "What is the relationship between gas price and transaction inclusion probability on Ethereum?"
Q1: "What is the relationship between validator stake size and MEV extraction capability?"
Q2: "What is the relationship between ETH implied volatility and options premium on Lyra?"
Q3: "What is the relationship between TVL and yield in automated market makers?"
[TRUE: Q2]

### Set 15 — Shuffled:
Q0: "How do Ethereum hard forks affect gas fee dynamics in the weeks surrounding the upgrade?"
Q1: "How do governance proposals affect protocol token prices historically?"
Q2: "How do stablecoin depegging events propagate through interconnected DeFi protocols?"
Q3: "How do token unlock schedules affect selling pressure for VC-backed protocols?"
[TRUE: Q1]

### Set 16 — Shuffled:
Q0: "What are the security risks of MEV-boost relay centralization in Ethereum?"
Q1: "What are the security risks of cross-chain bridge transfers?"
Q2: "What are the security risks of upgradeability patterns in proxy-based smart contracts?"
Q3: "What are the security risks of oracle manipulation in DeFi lending protocols?"
[TRUE: Q1]

### Set 17 — Shuffled:
Q0: "How does intent-based trading work on platforms like CoW Swap and UniswapX?"
Q1: "How does yield compounding work across DeFi aggregators like Yearn?"
Q2: "How does vote-escrow tokenomics work across protocols like Curve and Balancer?"
Q3: "How does cross-chain messaging work across protocols like LayerZero and Axelar?"
[TRUE: Q1]

### Set 18 — Shuffled:
Q0: "What is the yield difference between staking ETH natively vs using a liquid staking derivative?"
Q1: "What is the gas overhead of using Gnosis Safe vs EOA for DeFi transactions?"
Q2: "What is the MEV exposure difference between submitting via public mempool vs Flashbots Protect?"
Q3: "What is the latency difference between Ethereum mainnet and Arbitrum for swap execution?"
[TRUE: Q1]

### Set 19 — Shuffled:
Q0: "How does restaking yield on Eigenlayer compare to liquid staking yields on Lido?"
Q1: "How does Rocket Pool's minipool bond compare to full 32 ETH solo staking capital requirements?"
Q2: "How does Eigenlayer slashing risk compare to native ETH staking risk?"
Q3: "How does Lido's socialized slashing mechanism compare to solo validator slashing?"
[TRUE: Q2]

### Set 20 — Shuffled:
Q0: "What are the tradeoffs between different L2 data availability solutions?"
Q1: "What are the tradeoffs between different approaches to on-chain identity and reputation?"
Q2: "What are the tradeoffs between different DEX aggregator routing algorithms?"
Q3: "What are the tradeoffs between different oracle designs for DeFi price feeds?"
[TRUE: Q2]
