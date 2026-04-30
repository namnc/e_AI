# Failure Analysis: Stealth Address Ops Profile

*What the profile CAN'T catch, and why.*

## False negatives (risks we miss)

### 1. Cross-session behavioral fingerprinting
**Gap:** The analyzer checks one transaction at a time. It cannot detect patterns across sessions like "user always withdraws on Mondays" or "user's stealth addresses always interact with the same DeFi protocol."
**Impact:** An adversary with long-term observation can correlate stealth address activity through behavioral consistency even when individual transactions pass all 6 checks.
**Fix needed:** LLM behavioral analysis over transaction history (skeleton exists, untested).

### 2. Network-level deanonymization
**Gap:** The profile analyzes on-chain data only. An adversary at the RPC or mempool level sees the user's IP, query patterns, and pending transactions before they're mined.
**Impact:** All 6 heuristic countermeasures are irrelevant if the adversary identifies the user through network metadata.
**Fix needed:** Separate `rpc_leakage` profile + Helios/Tor integration.

### 3. Smart account bytecode fingerprinting
**Gap:** Stealth addresses using smart accounts (ERC-4337) have creation bytecode that may be unique. The profile doesn't analyze bytecode patterns.
**Impact:** Even with fresh addresses and paymasters, the smart account factory + bytecode can link all stealth addresses from the same user.
**Fix needed:** Bytecode analysis signal in H1 or new heuristic H7.

### 4. Inter-protocol linkage
**Gap:** If a user receives at a stealth address and then interacts with Aave/Uniswap from that address, the DeFi interaction creates a richer fingerprint than the stealth transfer alone.
**Impact:** DeFi behavior after receiving at stealth address can narrow the anonymity set even if the initial transfer was clean.
**Fix needed:** `cross_protocol_risk` profile.

### 5. Adversary with address clustering beyond our model
**Gap:** H1 uses a simple cluster check (is withdrawal address in sender's known cluster?). Real adversaries (Chainalysis) have much deeper clustering using heuristics we don't model: change address detection, exchange deposit correlation, smart contract interaction graphs.
**Impact:** We may clear a transaction as "clean" for H1 when Chainalysis would still link it.
**Fix needed:** Richer clustering model, or accept this as a fundamental limitation and document it.

## False positives (over-flagging)

### 1. H3 timing for legitimate urgency
**Problem:** User needs to spend from stealth address immediately (e.g., emergency, time-sensitive DeFi opportunity). H3 flags this as critical.
**Impact:** Blocking legitimate urgent transactions.
**Mitigation:** User override with explicit acknowledgment of timing risk.

### 2. H6 amount for exact payments
**Problem:** User is paying for a specific good/service at a specific price (e.g., 1.037 ETH). Rounding changes the payment amount.
**Impact:** Amount normalization breaks exact payment use cases.
**Mitigation:** "Match popular" recommendation (use pool amounts) rather than rounding.

### 3. H2 gas for custom strategies
**Problem:** Power users deliberately set custom gas for MEV strategies. H2 flags this.
**Impact:** False alert for sophisticated users.
**Mitigation:** User-configurable sensitivity threshold.

## Fundamental limitations (can't fix)

1. **Anonymity set is the floor.** All countermeasures are bounded by the number of stealth address users. With 10 daily active users, even perfect operational security gives anonymity set of 10.

2. **Deterministic links are permanent.** If H1 (cluster) or H5 (self-send) fires, the information is already on-chain and cannot be undone. Prevention is the only option.

3. **Paymaster fingerprint.** If few users use paymasters, paymaster usage itself becomes a fingerprint (H4 countermeasure creates a new H2-type signal).

4. **Time vs convenience.** H3 requires 6-24 hour delays. No technology can make this faster without shrinking the anonymity set.
