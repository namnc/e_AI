# The Private Query Problem: Privacy-Preserving AI Query Orchestration for DeFi

## Overview

When DeFi users consult cloud LLMs before transacting, they leak intent, strategy, portfolio context, and reasoning to the provider — two steps earlier than RPC reads, with orders of magnitude richer information. We call this the **Private Query Problem**.

We propose a **tiered architecture**: a regex sanitizer (browser extension, $0) strips numerically-formatted private parameters from queries before they reach the cloud. Under a constrained synthetic threat model, this removes the data most directly exploitable for MEV — but the sanitizer only covers patterns it recognizes, and has not been tested on real user queries. Adding topic hiding via cover queries requires a local LLM ($200-500/yr) and strong transport assumptions that are achievable but operationally non-trivial.

### At a Glance

| Tier | What | Hardware | Cost/yr | Privacy | Assumptions |
|---|---|---|---|---|---|
| **0: Sanitize** | Regex strips params + input normalization | Browser extension | **$0** | Format-matchable params removed | Regex covers the param format; no semantic/NL coverage |
| **1: Full pipeline** | + LLM decompose + genericize + covers | Mac Mini 14B+ | **$200-500** | + topic hiding (40% detection, n=20) | + per-set Tor unlinkability; small-sample result |

This repository contains:
- **`ethresearch_post.md`** — the main ethresear.ch post (Part 1)
- **`companion_post_active_adversary.md`** — Part 2: active adversaries, verifiable inference, cryptoeconomic accountability
- Benchmark suite (A-F), DistilBERT classifier, cover generator, sanitizer tests

## Key Finding

Cover query indistinguishability depends critically on the generation strategy. We identified four independent signals an adversary can exploit, and fixed them iteratively:

| Version | Strategy | Detection Rate | vs Random (25%) | Signal Eliminated |
|---------|----------|---------------|-----------------|-------------------|
| v1 | Naive covers (different tone) | **95%** | 3.8x above | — |
| v2 | Tone-matched | **60%** | 2.4x above | Actionability |
| v3 | Template-matched | **10%** | Below random | Template structure |
| v4 | Template-matched, stronger adversary | **60%** | 2.4x above | (Domain prior re-emerged) |
| v5 | Template + top-4 equiprobable domains | **0%** | Below random | Domain prior |

**Root cause of failure**: Not a fundamental impossibility, but an engineering problem. Naive covers leak an "actionability" signal — real queries sound like "someone about to do something" while covers sound "educational." A stronger adversary can also exploit domain frequency priors (lending queries are more common than governance queries). When all four signals are eliminated via template + distribution matching, the adversary is reduced to random guessing.

## Repository Structure

```
├── ethresearch_post.md          # Main ethresear.ch post
├── README.md
├── requirements.txt
├── run_benchmarks.py            # Benchmark runner (Claude API or Ollama)
├── classifier_validation.py     # External DistilBERT classifier validation
├── cover_generator.py           # v5 cover algorithm (template + top-4 equiprobable domains)
├── llm_backend.py               # Backend abstraction (Anthropic API + Ollama)
├── dataset.py                   # Test vectors and session scenarios
├── test_sanitizer.py            # Unit tests for regex sanitizer (39+ tests)
├── test_sanitizer_audit.py      # Completeness audit (2,600 synthetic params, 0% FN)
├── run_all.sh                   # One-click full benchmark run
├── docs/
│   ├── adversary_prompt.md      # All LLM prompts used in benchmarks
│   ├── scoring_rubric.md        # Benchmark D quality scoring rubric
│   ├── transport_assumptions.md # Tor circuit pool, mixnet, timing mitigations
│   ├── latency_projections.md   # Per-hardware latency estimates (M1→M4 Max)
│   ├── sanitizer_gaps.md        # What's caught, what leaks, recommended NLP filters
│   └── staking_mechanism.md     # On-chain staking interface (Solidity), slashing tiers
├── data/
│   ├── benchmark_dataset.jsonl  # Unified dataset: 216 queries (JSONL, reusable)
│   ├── build_dataset.py         # Dataset builder (merges sources, adds borderline cases)
│   ├── real_queries.json        # Rich metadata source (category, damage, exploitability)
│   └── sources.md               # Data provenance and methodology
├── results/
│   ├── benchmark_a_results.md   # Sensitivity classification (97% F1 at n=100)
│   ├── benchmark_b_results.md   # Decomposition quality (0% leakage)
│   ├── benchmark_c_results.md   # Cover indistinguishability v1 (95% — FAIL)
│   ├── benchmark_c_detection.md # v1 adversarial detection detail
│   ├── benchmark_c_v2.md        # v2 tone-matched (60% — FAIL)
│   ├── benchmark_c_v3.md        # v3 template-matched (10% — PASS)
│   ├── benchmark_c_v4.md        # v4 multi-strategy adversary (60% — FAIL)
│   ├── benchmark_c_v5.md        # v5 top-4 equiprobable (0% — PASS)
│   ├── results.json             # Benchmark F damage simulation data
│   └── classifier_results.json  # External classifier validation results
└── analysis/
    ├── failure_analysis.md      # Why v1/v2 failed, is indistinguishability hard?
    └── cover_strategies.md      # Systematic cover generation algorithm design
```

## Benchmark Results

| Benchmark | What It Tests | Target | Result | Verdict |
|---|---|---|---|---|
| **A** | Sensitivity classification | >90% F1 | **97% F1** (n=100, Qwen 7B) | PASS |
| **B** | Decomposition quality (string-match only) | >85% coverage, 0% leakage | **100%/0%** (frontier), **70%/30%** (7B) | PASS/MARGINAL |
| **C** | Template indistinguishability | <55% detection | **20%** (LLM), **AUC 0.507** (DistilBERT) | PASS |
| **C2** | Deployed-pipeline detectability | <55% detection | **40%** (genericized sub-queries, n=20) | MARGINAL |
| **D** | Answer quality (template rewrite only) | >80% scoring >=4/5 | **20%** (avg 2.3/5, n=15) | **FAIL** |
| **D2** | Full pipeline (genericized, blinded A/B) | >80% quality retained | **3.8/5** (128% retained vs direct, n=5) | PASS |
| **E** | Session composition (simulation) | <40% recovery at 5 queries | **20-60% with covers** vs **100% without** | MARGINAL |
| **F** | Economic damage model (illustrative) | — | Sanitization → ~$0 for param-dependent attacks | Illustrative |

## Reproducing Results

### Option 1: With Claude API
```bash
export ANTHROPIC_API_KEY=sk-ant-...
python run_benchmarks.py --benchmark all
python run_benchmarks.py --benchmark C --cover-version v1  # compare naive vs v5
python run_benchmarks.py --benchmark C --cover-version v5 --samples 50
python run_benchmarks.py --benchmark E  # session composition
```

### Option 2: With Ollama (local, free)
```bash
ollama pull qwen2.5:32b
python run_benchmarks.py --benchmark all --backend ollama --model qwen2.5:32b
```

### Option 3: External classifier validation (no API needed for data gen)
```bash
pip install torch transformers scikit-learn numpy
python classifier_validation.py run --n-sets 1000
```

### Option 4: One-click full run
```bash
./run_all.sh ollama qwen2.5:7b    # runs everything with local model
./run_all.sh                       # runs only non-LLM benchmarks (F, classifier, sanitizer tests)
```

### Previous results
The `results/*.md` files contain earlier in-conversation results generated with Claude acting as both generator and adversarial detector. See `analysis/failure_analysis.md` for methodology.

## What This Repo Does NOT Prove

- **NOT a general privacy guarantee.** The sanitizer removes patterns it recognizes. Novel formats, natural-language quantities ("three quarters of my portfolio"), semantic leakage ("near liquidation"), and implicit intent signals ("What's a good health factor?") are not caught.
- **NOT tested on real user queries.** All evaluation uses synthetic data. Real DeFi queries are inherently private and unavailable at scale (0.004% hit rate in 1M WildChat conversations).
- **NOT robust against adversarial formatting.** Input normalization handles known Unicode/format tricks, but the regex approach is inherently brittle against adversaries who craft novel bypass encodings.
- **NOT independently evaluated.** The same model generates and judges in D2 (n=5). The classifier trains on data from the same generator. Benchmark B is exact-string-only. No independent red-team or human evaluation has been conducted.
- **NOT a stable release.** The commit history shows rapid sanitizer fixes over 2 days (mixed-case tokens, Unicode bypasses, timing leaks, false positives). The code is still stabilizing.

Read all benchmark results as **"under a constrained synthetic threat model"**, not as general production claims.

## Caveats

**This is a research prototype, not an audit-complete privacy tool.**

- **Sanitizer coverage is format-bounded**: Input normalization handles Unicode bypasses and joined tokens, but the completeness audit covers 14 base symbols. Novel tokens not in the known-token list and not matching the broad pattern (all-lowercase, no crypto suffix) can leak. Natural-language quantities ("three quarters of my portfolio") and semantic leakage ("near liquidation") are not caught
- **C2 at 40% (15 points above random)**: The deployed pipeline is more detectable than template-filled sets (C at 20%) because genericized sub-queries retain natural phrasing that differs from template-filled covers. This is an engineering gap, not a fundamental one
- **Classifier validation is partially external**: DistilBERT trains on data from the same `cover_generator` (AUC 0.507, effectively random). Train/test text overlap is removed but the generator artifacts are shared
- **Benchmark B uses string-matching only**: Misses paraphrases, abstractions, and derived disclosures. "0% leakage" means no exact-string copies, not no semantic leakage
- **Benchmarks E and F are simulations**: E assumes per-set unlinkability (best case). F models param-dependent attacks only — topic-only attacks not modeled
- **D2 uses same model for answering and judging** (blinded A/B, n=5). D2 refuses cloud backends by default (requires ALLOW_CLOUD_D2=1 to override)
- **Local model capability gap**: 7B models leak private parameters 30% during decomposition. Need 14B+ for production
- **Small sample sizes**: n=5-20 for most benchmarks. Directionally correct but not statistically robust
- **No real user queries**: 216-query synthetic benchmark. Real DeFi position queries are inherently private (0.004% hit rate in 1M WildChat conversations)

## Contributing

**Help validate the sanitizer — without sharing any private data.** The benchmark dataset (216 queries) is synthetic. We need real-world validation, but real DeFi queries are private by definition. Three ways to contribute that protect your privacy:

**1. Local-only validation (nothing leaves your machine)**
Run the sanitizer on your actual queries locally and report only the binary result:
```bash
python -c "
from cover_generator import sanitize_query
q = input('Paste your query (stays local): ')
print(f'Sanitized: {sanitize_query(q)}')
# Report ONLY: 'leaked' or 'clean' — never the query itself
"
```

**2. Sanitizer bypass bounty**
Try to write a query that contains exploitable private information but passes the regex sanitizer. Report the *pattern* (e.g., "natural language numbers like 'half a million'"), not your actual query. Open a GitHub issue with the pattern.

**3. Independent labeling**
Label 100 queries from `data/benchmark_dataset.jsonl` as sensitive/non-sensitive/borderline. We'll compute inter-annotator agreement (target: Cohen's kappa > 0.7).
- **Damage reduction is simulated**: 100% reduction holds for parameter-dependent attacks; topic-only attacks (narrowing search by domain) are not modeled
- **Regex has a natural language gap**: Common worded quantities ("half a million USDC", "twenty ETH") are now caught, but compound forms ("twenty five ETH" → partially leaks), semantic quantities ("three quarters of my portfolio"), and novel phrasings still bypass the sanitizer
