# Sanitizer Coverage: What's Caught, What's Not, and Recommended Filters

## What the Regex Sanitizer Catches (0% false negatives)

All numerically-formatted parameters are deterministically removed:

| Pattern | Examples | Regex |
|---|---|---|
| Dollar amounts | $1,000 / $1.5M / $500K | `\$[\d,]+(\.\d+)?[KMB]?` |
| Token quantities | 500 ETH / 1.8M USDC / 10,000 AAVE | `[\d,]+(\.\d+)?[KMB]?\s*(ETH\|BTC\|...)` |
| Wallet addresses | 0x742d...f2bD / 0xdead...beef | `0x[a-fA-F0-9]{3,}` |
| Percentages | 10% / 3.5% / 65% | `\d+(\.\d+)?%` |
| Health factor values | HF is 1.15 / health factor: 1.08 | `(health factor\|HF)\s*(is\|of\|at)?\s*\d+` |
| Leverage ratios | 5x / 10x | `\d+x` |
| Comma-formatted numbers | 1,000 / 10,000,000 | `\d{1,3}(,\d{3})+` |
| Timing references | by Friday / within 48 hours / tomorrow | keyword list |
| Emotional language | worried / anxious / emergency | keyword list |
| Qualitative descriptors | underwater / close to liquidation | keyword list |
| Directional verbs | buy → modify / sell → modify / exit → modify | substitution map |

Validated on 2,600 synthetic parameter variations (test_sanitizer_audit.py).

## What the Number-Word Filter Catches (secondary layer)

Natural language quantity expressions near financial context:

| Pattern | Examples | Status |
|---|---|---|
| "half a million USDC" | ✅ Caught | Number word + currency |
| "roughly two thousand ETH" | ✅ Caught | Approximation + number word + token |
| "my six-figure position" | ✅ Caught | Magnitude descriptor + "position" |
| "a few hundred thousand dollars" | ✅ Caught | Vague quantity + currency |
| "several thousand ETH" | ✅ Caught | Vague quantity + token |
| "over a hundred thousand USDC" | ✅ Caught | Comparison + number word + token |
| "nearly five million dollars worth" | ✅ Caught | Approximation + number word + currency |

Validated on 9 natural language variations (test_sanitizer.py::test_natural_language_quantities).

## What STILL Leaks (known gaps)

### Purely semantic quantity references
| Example | Why it leaks |
|---|---|
| "about double what I started with" | Relative quantity, no number words |
| "more than I can afford to lose" | Subjective scale, no numeric reference |
| "a whale-sized position" | Slang for "large", no pattern |

**Fix**: Requires true NLU — a small classifier trained on financial magnitude expressions. Beyond regex/keyword scope.

### Implicit position signals (no parameters, but reveals state)
| Example | What it reveals |
|---|---|
| "What's a good health factor to maintain?" | User HAS an Aave position |
| "How do I check my liquidation price?" | User has active debt position |
| "How long does Lido unstaking take?" | User wants to unstake from Lido |
| "Can I use my stETH as collateral?" | User holds stETH, wants leverage |

**Fix**: These are not parameter leaks — they're topic/intent leaks. Addressed by cover queries (Tier 1), not by the sanitizer.

### Protocol-specific identifiers
| Example | What it reveals |
|---|---|
| "vault #12345" | Specific MakerDAO vault (on-chain lookup) |
| "proposal #47" | Specific governance proposal |
| "pool 0x1234...5678" | Specific liquidity pool |

**Fix**: Add regex for `#\d+` and pool/vault identifiers. Simple extension to the existing pattern set.

## Recommended Downstream NLP Filter

For production deployment, add a lightweight secondary filter after the regex sanitizer:

```python
# Option 1: spaCy NER with custom DeFi entity types
# Catches: "half a million", "a whale-sized position", etc.
import spacy
nlp = spacy.load("en_core_web_sm")  # 12MB, runs in <10ms
nlp.add_pipe("entity_ruler", config={"patterns": defi_patterns})

# Option 2: Small classifier (DistilBERT fine-tuned on leakage detection)
# Input: sanitized query text
# Output: probability that private information remains
# Train on: (original query, sanitized query, binary label: still_leaks?)

# Option 3: LLM-based second pass (if local model available)
# "Does this text still contain any information about the user's 
#  specific financial position, holdings, or trading intent?"
```

**Recommended approach**: Option 1 (spaCy) for Tier 0 (adds <10ms, no GPU needed). Option 3 for Tier 1 (local LLM already running). Option 2 for maximum precision (requires training data from the bypass bounty program).
