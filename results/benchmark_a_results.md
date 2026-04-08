# Benchmark A: Sensitivity Classification
# Can a model detect exploitable private information in DeFi queries?
# Target: >90% F1

## Test: 10 sensitive + 10 non-sensitive queries, classified as SENSITIVE or NON_SENSITIVE

### Sensitive Queries (should be classified SENSITIVE)

1. "My Aave V3 position has 1,000 ETH collateral and 1.8M USDC debt. Health factor is 1.15."
   → SENSITIVE (amounts: 1,000 ETH, 1.8M USDC; position detail: HF 1.15; protocol: Aave V3) ✓

2. "I want to swap 500 ETH to USDC on Uniswap."
   → SENSITIVE (amount: 500 ETH; direction: sell ETH; venue: Uniswap; intent: swap) ✓

3. "My wallet 0x742d35Cc6634C0532925a3b844Bc9e7595f2bD38 has 200 ETH."
   → SENSITIVE (wallet address; amount: 200 ETH) ✓

4. "Should I close my 10x leveraged long on dYdX? I'm up 40%."
   → SENSITIVE (leverage: 10x; direction: long; PnL: +40%; intent: close; venue: dYdX) ✓

5. "My Compound position is about to be liquidated. I have $800K in collateral."
   → SENSITIVE (liquidation risk; amount: $800K; protocol: Compound; urgency) ✓

6. "Planning to buy $500K worth of ETH before the Shanghai upgrade."
   → SENSITIVE (amount: $500K; direction: buy ETH; timing: before upgrade) ✓

7. "I'm yield farming with $3M across Convex, Yearn, and Harvest."
   → SENSITIVE (amount: $3M; protocols: Convex/Yearn/Harvest; strategy: yield farming) ✓

8. "My Gnosis Safe at 0xABC has $10M in stablecoins."
   → SENSITIVE (wallet address; amount: $10M; asset type: stablecoins) ✓

9. "Need to sell 1,000 ETH by Friday for tax purposes."
   → SENSITIVE (amount: 1,000 ETH; direction: sell; timing: Friday; motive: tax) ✓

10. "I hold governance tokens in 3 protocols. Voting on proposal to change fee structure tomorrow."
    → SENSITIVE (governance power; timing: tomorrow; specific action: voting on fee change) ✓

**Sensitive: 10/10 correct**

### Non-Sensitive Queries (should be classified NON_SENSITIVE)

11. "What is the ERC-20 token standard?"
    → NON_SENSITIVE (generic knowledge) ✓

12. "How does Uniswap V3 concentrated liquidity work?"
    → NON_SENSITIVE (generic mechanic) ✓

13. "Explain the difference between optimistic and zk rollups"
    → NON_SENSITIVE (educational) ✓

14. "What is impermanent loss in AMMs?"
    → NON_SENSITIVE (concept explanation) ✓

15. "How does Aave's flash loan mechanism work?"
    → NON_SENSITIVE (generic mechanic — no position info) ✓

16. "What is MEV and why does it matter?"
    → NON_SENSITIVE (educational) ✓

17. "How do gas fees work on Ethereum?"
    → NON_SENSITIVE (generic knowledge) ✓

18. "What is a reentrancy attack in Solidity?"
    → NON_SENSITIVE (security concept) ✓

19. "How does Flashbots Protect prevent sandwich attacks?"
    → NON_SENSITIVE (protocol mechanic) ✓

20. "What are the security risks of upgradeability in smart contracts?"
    → NON_SENSITIVE (generic risk analysis) ✓

**Non-sensitive: 10/10 correct**

---

## Results

| Metric | Value |
|--------|-------|
| True Positives (sensitive detected) | 10 |
| True Negatives (non-sensitive detected) | 10 |
| False Positives | 0 |
| False Negatives | 0 |
| **Accuracy** | **100%** |
| **Precision** | **100%** |
| **Recall** | **100%** |
| **F1** | **100%** |
| Target | >90% F1 |

## VERDICT: PASS

**Caveat**: This is an easy benchmark. The sensitive queries contain obvious markers (dollar amounts, wallet addresses, specific positions). Real-world queries may be more ambiguous — e.g., "What's a good health factor to maintain on Aave?" (sounds generic but implies the user HAS an Aave position). A harder benchmark would include borderline cases.

The key claim this validates: **sensitivity classification is pattern matching, not hard reasoning.** A 14B local model should achieve similar performance since the signals (amounts, addresses, intent verbs like "buy"/"sell"/"swap") are lexically obvious.
