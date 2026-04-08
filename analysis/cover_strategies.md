# Cover Generation Strategy v4: Systematic Design

## The Four Signals (from failure_analysis.md)

| Signal | What Leaks | v1 | v2 | v3 | v4 (this) |
|--------|-----------|----|----|----|----|
| 1. Actionability | "About to do" vs "learning" | Leaked | Fixed | Fixed | Fixed |
| 2. Specificity | Protocol-level detail | Leaked | Partially fixed | Fixed | Fixed |
| 3. Template | Sentence structure | Leaked | Leaked | Fixed | Fixed |
| 4. Domain prior | Topic frequency distribution | Leaked | Leaked | Leaked | **Fixed** |

## v4 Algorithm

### Step 1: Sanitize the real query

Strip ALL private parameters. But also strip **qualitative descriptors** that leak position state:
- Remove: "underwater," "close to liquidation," "significantly imbalanced," "worried about"
- Replace directional verbs: "sell" → (remove), "buy" → (remove), "add" → "modify"
- Remove timing urgency: "now," "before Friday," "within 48 hours"
- Remove emotional language: "worried," "anxious," "should I"

Result: A generic operational question about a DeFi mechanism.

### Step 2: Extract structural template

Parse the sanitized query into a template with slots:

Example: "How does [MECHANISM] work for [ASSET_TYPE] in [PROTOCOL_TYPE] protocols?"

Slots: MECHANISM, ASSET_TYPE, PROTOCOL_TYPE, OPERATION, METRIC, COMPARISON

### Step 3: Build DeFi domain ontology (for slot filling)

Organize DeFi domains into parallel categories so that swapping one domain for another produces an equally valid question:

```
PROTOCOL_TYPES:
  lending:     [Aave, Compound, Morpho, Spark, Radiant]
  dex:         [Uniswap, Curve, Balancer, SushiSwap, Maverick]
  derivatives: [dYdX, GMX, Synthetix, Lyra, Opyn]
  bridges:     [Across, Stargate, LayerZero, Wormhole, Orbiter]
  staking:     [Lido, Rocket Pool, Eigenlayer, Frax, Swell]
  governance:  [Compound Gov, Aave Gov, Uniswap Gov, Curve Gov]
  aggregators: [Yearn, Beefy, Convex, Pendle]

MECHANISMS:
  lending:     [health factor, liquidation, borrowing, collateral, interest rate]
  dex:         [routing, slippage, liquidity depth, fee tiers, impermanent loss]
  derivatives: [margin, funding rate, liquidation, settlement, premium]
  bridges:     [finality, capacity, fees, security model, withdrawal delay]
  staking:     [yield, slashing, cooldown, withdrawal queue, delegation]
  governance:  [quorum, delegation, timelock, proposal lifecycle, voting power]
  aggregators: [compounding, vault strategy, rebalancing, fee structure, APY calculation]

OPERATIONS:
  [modify, close, enter, exit, rebalance, claim, migrate, withdraw, deposit]

METRICS:
  [gas cost, execution time, risk profile, yield, fees, slippage]
```

### Step 4: Generate covers by domain swapping

For each slot in the template, swap to a different domain category while keeping the template structure identical.

**Rule**: The real query's domain category (e.g., "lending") should NOT appear in any cover. Each cover uses a different domain.

**Rule**: Cover domains are sampled proportional to their real-world query frequency (approximated from public DeFi forum post distributions):
- Lending: 25%
- DEX/trading: 30%  
- Derivatives: 10%
- Bridges: 8%
- Staking: 15%
- Governance: 5%
- Aggregators: 7%

If the real query is about lending (25%), the three covers are drawn from the remaining 75% according to relative weights.

### Step 5: Quality verification

Each generated cover must pass:
1. **Validity check**: Is this a real, answerable DeFi question? (Not gibberish from template filling)
2. **Length check**: Within ±20% of the real query's length
3. **Complexity check**: Same number of sub-clauses and technical terms
4. **No self-reference**: Cover doesn't accidentally reference the real query's domain

### Step 6: Shuffle with fixed seed

Use a deterministic seed (hash of session ID + query index) for shuffling. This ensures reproducibility while appearing random to the adversary.

---

## v4 Test: 20 Query Sets with Multiple Detection Strategies

For each set, I'll attempt detection using THREE independent strategies:
1. **Intuitive**: Which "feels" most real? (simulates a human analyst)
2. **Structural**: Are there measurable differences in length, complexity, or specificity?
3. **Topical**: Which topic is most commonly asked about in real DeFi usage?

Final guess = majority vote of the three strategies. This is a stronger adversary than v1-v3.
