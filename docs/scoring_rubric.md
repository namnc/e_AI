# Benchmark D: Answer Quality Scoring Rubric

## Scale

| Score | Label | Definition | Example |
|---|---|---|---|
| 5 | Directly useful | Answers the original question with relevant, specific information about the correct mechanism/protocol | Q: "How does Aave V3 HF change with collateral?" → A explains HF formula and collateral impact |
| 4 | Mostly relevant | Covers the core topic but misses some specifics (e.g., right domain, wrong mechanism) | Q: about HF → A explains Aave lending mechanics generally but not HF specifically |
| 3 | Partially relevant | Provides related DeFi knowledge but doesn't address the original question's mechanism | Q: about HF → A explains lending interest rates (same domain, different mechanism) |
| 2 | Tangentially related | Mostly about a different topic; only surface-level connection to the original question | Q: about HF → A explains DEX slippage (different domain entirely) |
| 1 | Irrelevant | About a completely different topic with no meaningful connection | Q: about HF → A explains governance voting mechanics |

## Scoring Procedure

1. The **original sanitized query** (user's actual question, params stripped) is shown to the judge
2. The **answer** (generated from the template-rewritten version of that query) is shown
3. The judge rates how useful the answer would be for someone who asked the original question
4. The judge provides a brief reason for the score

## What This Measures

The score captures the **utility cost of template rewriting** — the gap between what the user asked and what the cloud actually answered. A score of 5 means template rewriting preserved the question; a score of 1 means it changed the question entirely.

## Results (n=15, Qwen 2.5 7B)

| Score | Count | Percentage |
|---|---|---|
| 5 | 0 | 0% |
| 4 | 3 | 20% |
| 3 | 0 | 0% |
| 2 | 10 | 67% |
| 1 | 2 | 13% |
| **Average** | **2.3** | |

## Interpretation

Template rewriting changes not just the phrasing but the *mechanism* being asked about (e.g., "health factor" → "utilization rate"). This is expected: the v5 algorithm fills template slots with random vocabulary from the target domain, and the real query's specific mechanism is replaced by a random one.

The implication: covers achieve privacy by making the query indistinguishable, but the answer to the rewritten query is about a different mechanism. This is why **covers require LLM-based decomposition** — the local LLM first produces generic sub-queries (e.g., "How does the HF formula work?") that are already abstract enough that template rewriting doesn't change the core question.
