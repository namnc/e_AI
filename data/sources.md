# Data Sources and Methodology

## Realistic Query Construction

Since real user LLM queries about DeFi are private (and collecting them would defeat the purpose of this research), we construct realistic test vectors from:

### Source 1: On-Chain Protocol Parameters (Verifiable)
- Aave V3 liquidation thresholds: from Aave docs (docs.aave.com/risk/asset-risk/risk-parameters)
  - ETH: LT = 83%, LB = 5%
  - WBTC: LT = 78%, LB = 6.5%
  - USDC: LT = 80%, LB = 4.5%
- Uniswap V3 fee tiers: 0.01%, 0.05%, 0.3%, 1%
- Gas costs: from etherscan.io gas tracker historical data
- DeFi TVL and protocol rankings: from defillama.com

### Source 2: Public DeFi Forum Queries (Real Questions)
- Reddit r/defi, r/ethfinance — real user questions (public)
- Ethereum StackExchange — real technical questions
- DeFi protocol Discord FAQs (public channels)
- These are used for NON-SENSITIVE queries and for calibrating what real DeFi questions sound like

### Source 3: On-Chain Position Distributions (Statistical Realism)
- Aave V3 position distributions (from Dune Analytics dashboards):
  - Median position size: ~$10K-50K
  - 90th percentile: ~$500K
  - 99th percentile: ~$5M
  - Health factor distribution: median ~2.0, concerning range <1.3
- Uniswap V3 LP positions: typical range widths, position sizes
- These ensure our test queries have realistic parameters

### Source 4: MEV Extraction Data (Verifiable)
- EigenPhi sandwich attack statistics
- Flashbots MEV-Explore data
- Aave liquidation event data (from Dune Analytics)

## Methodology
1. Construct sensitive queries by combining real protocol parameters with realistic position sizes drawn from on-chain distributions
2. Non-sensitive queries sourced directly from public forums (Reddit, StackExchange) with minor edits
3. Each query is tagged with: category, sensitivity level, private parameters, expected decomposition
4. All parameters are verifiable against on-chain data or protocol documentation
