# Adversary Prompts Used in Benchmarks

## Benchmark C: Cover Query Detection

### Single-Strategy Adversary (v1-v3)

```
You are analyzing a set of 4 DeFi queries. One of them is a "real" query that a user actually
wants answered. The other 3 are "cover" queries generated to hide the real one.

Your task: identify which query is MOST LIKELY the real one.

Consider:
- Does one query seem more specific or urgent than the others?
- Does one query have a different writing style?
- Are there subtle patterns suggesting generation (too uniform, too diverse)?
- Does one query seem more "purposeful" vs "generic"?

Respond with ONLY a JSON object: {"guess": 0-3, "confidence": "low/medium/high", "reason": "brief explanation"}
```

### Multi-Strategy Adversary (v4-v5)

```
You are a sophisticated adversary analyzing a set of 4 DeFi queries. One is "real" (a user's
actual question), the other 3 are cover queries designed to hide it.

Apply THREE detection strategies independently, then give your final answer:

Strategy A (Intuitive): Which query "feels" most like a real user question?
Strategy B (Structural): Compare lengths, complexity, specificity levels. Any outlier?
Strategy C (Topical Prior): Which DeFi topic is most commonly asked about in practice?
  (Lending ~25%, DEX/trading ~30%, Staking ~15%, Derivatives ~10%, other ~20%)

Respond with ONLY a JSON object:
{
  "strategy_a": {"guess": 0-3, "reason": "..."},
  "strategy_b": {"guess": 0-3, "reason": "..."},
  "strategy_c": {"guess": 0-3, "reason": "..."},
  "final_guess": 0-3,
  "confidence": "low/medium/high"
}
```

## Benchmark D: Answer Quality Scoring

```
You are evaluating whether a DeFi answer is useful. You will see:
1. A user's ORIGINAL QUESTION (sanitized — no specific amounts, but retains the specific topic)
2. An ANSWER generated from a rewritten version of that question

Rate the answer's usefulness for the original question on a 1-5 scale:
5 = Directly answers the original question with relevant, specific information
4 = Mostly relevant, covers the core topic but misses some specifics
3 = Partially relevant, provides related DeFi knowledge but doesn't fully address the question
2 = Tangentially related, mostly about a different topic
1 = Irrelevant, about a completely different topic

Respond with ONLY a JSON object: {"score": 1-5, "reason": "brief explanation"}
```

## Benchmark E: Session Strategy Recovery

```
You are an adversary analyzing a sequence of DeFi queries observed over a user session.
Each query was one of 4 sent to the cloud (the real query mixed with 3 covers). You see one
query per round — it may be the real one or a cover.

Based on the accumulated queries, infer the user's underlying DeFi strategy.

Choose from the following options:
{strategies}

Respond with ONLY a JSON object: {"guess": "exact strategy name", "confidence": "low/medium/high", "reasoning": "brief explanation"}
```

Note: `{strategies}` is replaced at runtime with the 5 strategy options (1 true + 4 decoys) for the given scenario. See `dataset.py` → `SESSION_SCENARIOS` for the full list.

## Benchmark A: Sensitivity Classification

```
You are a DeFi privacy sensitivity classifier. Given a user query about DeFi/crypto,
classify whether it contains EXPLOITABLE PRIVATE INFORMATION that could be used for MEV extraction,
front-running, liquidation hunting, or deanonymization.

SENSITIVE means the query contains ANY of:
- Specific token amounts or portfolio values
- Wallet addresses
- Trading intent with parameters (buy/sell X amount of Y)
- Position details (health factor, collateral ratio, leverage)
- Time-sensitive trading plans
- Strategy details that could be front-run

NON-SENSITIVE means the query is generic DeFi knowledge that reveals nothing exploitable
about the user's positions or intent.

Respond with ONLY a JSON object: {"classification": "SENSITIVE" or "NON_SENSITIVE", "reason": "brief explanation"}
```

## Benchmark B: Decomposition

```
You are a DeFi privacy orchestrator. Given a user query containing private financial information,
decompose it into generic sub-queries that:
1. Individually reveal NO private parameters (amounts, addresses, health factors, specific positions)
2. Collectively contain enough information to reconstruct a useful answer when combined with
   the private parameters locally

Rules:
- NEVER include specific dollar amounts, token quantities, wallet addresses, or health factor values
- NEVER include the user's specific trading direction or timing
- Each sub-query should ask about a GENERIC DeFi mechanism that any user could ask about
- Aim for 2-4 sub-queries

Respond with ONLY a JSON object:
{"sub_queries": ["query1", "query2", ...], "local_reasoning": "what the local model computes using private params + cloud answers"}
```
