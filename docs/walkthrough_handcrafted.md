# Walkthrough: Hand-Crafted DeFi Privacy Pipeline

This document walks through how the hand-crafted DeFi privacy pipeline works, from a user query to a privacy-protected cloud LLM interaction.

## The Problem

Alice asks Claude: "My Aave V3 WETH position has health factor 1.12 with 450 ETH collateral ($1.125M) and 680K USDC borrowed. Should I add more collateral before Friday?"

This query leaks:
- **Position size**: 450 ETH, $1.125M, 680K USDC
- **Health factor**: 1.12 (near liquidation)
- **Protocol**: Aave V3 (reveals which platform)
- **Timing**: "before Friday" (reveals urgency)
- **Intent**: adding collateral (reveals defensive posture)

A cloud provider (or anyone with log access) could front-run her collateral addition or trigger her liquidation.

## Tier 0: Sanitization ($0, browser extension)

### Step 1: Input Normalization

`_normalize_input()` canonicalizes the input before regex matching:
- NFKC Unicode normalization (fullwidth `０x` → `0x`)
- Strip zero-width characters
- Normalize currency symbols (`€` → `$`)
- Fix locale separators (EU `1.234,56` → US `1234.56`)
- Split joined tokens (`125ETH` → `125 ETH`)

### Step 2: Sanitization (9-pass regex)

`sanitize_query()` strips private parameters in order:

```
Pass 0a: Addresses + ENS names
  0x742d35Cc... → (removed)
  vitalik.eth → (removed)

Pass 0b: Pre-normalization patterns (from profile)
  1.5e6 USDC → (removed)        # scientific notation
  500k → (removed)               # bare magnitudes
  500-1000 ETH → (removed)       # ranges

Pass 0c: Space-separated thousands
  1 000 ETH → (removed)

Pass 0d: Full input normalization

Pass 1: Known token amounts (case-insensitive)
  "450 ETH" → (removed)
  "680K USDC" → (removed)
  "$1.125M" → (removed)

Pass 2: Dollar amounts + suffixed numbers
  "$1,000" → (removed)

Pass 3: Broad token-like words (case-sensitive, with false-positive carve-outs)
  "500 eETH" → (removed)  but "V3" preserved (false positive list)

Health factor: "health factor 1.12" → "health factor"
Leverage: "5x" → (removed)
Percentages: "10%" → (removed)
Emotional: "worried", "panicking" → (removed)
Timing: "before Friday" → (removed)
Qualitative: "underwater" → (removed)
Directional: "buy" → "modify", "sell" → "modify"
```

**Result**: "My Aave V3 WETH position has health factor with collateral ($) and USDC borrowed. add more collateral?"

The cloud sees the topic (Aave health factor, collateral) but not the position size, health factor value, or timing.

### What's preserved, what's stripped

| Category | Example | Stripped? | Why |
|----------|---------|-----------|-----|
| Protocol name | "Aave V3" | No | Needed for useful answer (stripped by genericizer in Tier 1) |
| Mechanism | "health factor" | No | The question's topic |
| Amount | "450 ETH" | Yes | Position size enables MEV |
| HF value | "1.12" | Yes | Reveals liquidation proximity |
| Timing | "before Friday" | Yes | Reveals urgency |
| Dollar value | "$1.125M" | Yes | Position value |

### Known limitations

The sanitizer is format-bounded, not semantically aware:
- "about double what I started with" → NOT caught (no numeric format)
- "a whale-sized position" → NOT caught (metaphorical)
- "three quarters of my portfolio" → caught (worded fraction pattern)

Coverage: 2,600/2,600 synthetic parameters stripped (100%). Zero false negatives on recognized formats.

## Tier 1: Full Pipeline ($200-500/yr, local LLM)

### Step 1: Decompose (local LLM)

The local LLM (never leaves device) decomposes Alice's query into generic sub-queries:

```
Original: "My Aave V3 WETH position has health factor 1.12..."

Sub-queries:
  1. "How does health factor respond to collateral changes in lending protocols?"
  2. "What are typical gas costs for collateral operations?"
  3. "How do liquidation thresholds work in lending platforms?"
```

Private params (450 ETH, 1.12, Friday) stay local — only mechanism questions go to cloud.

### Step 2: Genericize (regex)

`genericize_subquery()` strips protocol names while preserving mechanism questions:

```
"How does health factor respond to collateral changes in Aave V3?"
→ "How does health factor respond to collateral changes in lending protocols?"
```

The cloud gets the RIGHT question without knowing Alice uses Aave.

### Step 3: Cover queries (template + domain matching)

For each sub-query, `generate_cover_set()` generates k-1 additional queries from other subdomains:

```
[REAL] "How does health factor respond to collateral changes in lending protocols?"
[COVER] "How does funding rate respond to volatility spikes in derivatives platforms?"
[COVER] "How does reward rate respond to participation rates in staking protocols?"
[COVER] "How does slippage respond to volume patterns in exchange protocols?"
```

All 4 use the same template, drawn from different subdomains via equiprobable sampling. The cloud sees 4 indistinguishable queries. Correct answer probability: 1/k = 25%.

### Step 4: Transport (Tor circuit pool)

Each query in the cover set is sent via a different Tor circuit (different exit IP, 0.5-5s random delay). The cloud cannot link the 4 queries to the same user.

### Step 5: Synthesize (local LLM)

The local LLM receives answers to all sub-queries and synthesizes a complete answer using Alice's private params:

```
"Based on your health factor of 1.12 with 450 ETH collateral and 680K USDC borrowed:
Your liquidation threshold is approximately [calculated from sub-answers].
Adding collateral would improve your HF to approximately [calculated].
Gas cost estimate: [from sub-answer 2]. Recommend acting before Friday given..."
```

Alice gets a personalized answer. The cloud never saw her specific numbers.

## Formal Guarantees

| Property | Guarantee | Evidence |
|----------|-----------|---------|
| Parameter hiding | Pattern-matchable params deterministically removed | 2,600/2,600 audit, 47 unit tests |
| Template k-indistinguishability | P(correct) = 1/k when template identical, domains equiprobable | Formal theorem + 20% empirical detection |
| Cover verification | Length ±30%, ends with ?, no cross-domain protocol leakage | verify_cover() gates |
| Answer quality | 3.8/5 with genericized pipeline (Benchmark D2) | Blinded A/B, n=5 |

## Files

| File | Role |
|------|------|
| `cover_generator.py` | Sanitizer, domain classifier, template matching, cover generation |
| `domains/defi/profile.json` | All DeFi-specific constants (ontology, patterns, templates) |
| `run_benchmarks.py` | Benchmarks A-F validating each component |
| `test_sanitizer.py` | 47 unit tests for regex sanitizer |
| `test_sanitizer_audit.py` | 2,600-parameter completeness audit |
| `classifier_validation.py` | DistilBERT external classifier validation |
