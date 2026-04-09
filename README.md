# The Private Query Problem: Privacy-Preserving AI Query Orchestration for DeFi

## Overview

When DeFi users consult cloud LLMs before transacting, they leak intent, strategy, portfolio context, and reasoning to the provider — two steps earlier than RPC reads, with orders of magnitude richer information. We call this the **Private Query Problem**.

We propose a **tiered architecture**: a regex sanitizer (browser extension, $0) deterministically removes numeric private parameters — the most directly exploitable data. Adding topic hiding via cover queries requires a local LLM for decomposition ($200-500/yr) and strong transport assumptions (per-query-set unlinkability).

### At a Glance

| Tier | What | Hardware | Cost/yr | Privacy | Assumptions |
|---|---|---|---|---|---|
| **0: Sanitize** | Regex strips numeric params | Browser extension | **$0** | Deterministic param removal | Regex covers the param format |
| **1: Full pipeline** | + LLM decompose + covers | Mac Mini 14B+ | **$200-500** | + topic hiding (25-34%) | + per-set Tor unlinkability |

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
| v5 | Template + domain-distribution matched | **0%** | Below random | Domain prior |

**Root cause of failure**: Not a fundamental impossibility, but an engineering problem. Naive covers leak an "actionability" signal — real queries sound like "someone about to do something" while covers sound "educational." A stronger adversary can also exploit domain frequency priors (lending queries are more common than governance queries). When all four signals are eliminated via template + distribution matching, the adversary is reduced to random guessing.

## Repository Structure

```
├── ethresearch_post.md          # Main ethresear.ch post
├── README.md
├── requirements.txt
├── run_benchmarks.py            # Benchmark runner (Claude API or Ollama)
├── classifier_validation.py     # External DistilBERT classifier validation
├── cover_generator.py           # v5 cover algorithm (template + distribution matching)
├── llm_backend.py               # Backend abstraction (Anthropic API + Ollama)
├── dataset.py                   # Test vectors and session scenarios
├── test_sanitizer.py            # Unit tests for regex sanitizer (16 tests)
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
│   ├── benchmark_dataset.jsonl  # Unified dataset: 170 queries (JSONL, reusable)
│   ├── build_dataset.py         # Dataset builder (merges sources, adds borderline cases)
│   ├── real_queries.json        # Rich metadata source (category, damage, exploitability)
│   └── sources.md               # Data provenance and methodology
├── results/
│   ├── benchmark_a_results.md   # Sensitivity classification (100% F1)
│   ├── benchmark_b_results.md   # Decomposition quality (0% leakage)
│   ├── benchmark_c_results.md   # Cover indistinguishability v1 (95% — FAIL)
│   ├── benchmark_c_detection.md # v1 adversarial detection detail
│   ├── benchmark_c_v2.md        # v2 tone-matched (60% — FAIL)
│   ├── benchmark_c_v3.md        # v3 template-matched (10% — PASS)
│   ├── benchmark_c_v4.md        # v4 multi-strategy adversary (60% — FAIL)
│   ├── benchmark_c_v5.md        # v5 distribution-matched (0% — PASS)
│   ├── results.json             # Benchmark F damage simulation data
│   └── classifier_results.json  # External classifier validation results
└── analysis/
    ├── failure_analysis.md      # Why v1/v2 failed, is indistinguishability hard?
    └── cover_strategies.md      # Systematic cover generation algorithm design
```

## Benchmark Results

| Benchmark | What It Tests | Target | Result | Verdict |
|---|---|---|---|---|
| **A** | Sensitivity classification | >90% F1 | **96-100% F1** (n=100, 7B + frontier) | PASS |
| **B** | Decomposition quality | >85% coverage, 0% leakage | **100%/0%** (frontier), **70%/30%** (7B) | PASS/MARGINAL |
| **C** | Template indistinguishability | <55% detection | **27%** (LLM), **25-29%** (DistilBERT) | PASS |
| **C2** | Deployed-pipeline detectability | <55% detection | **35%** (genericized sub-queries, n=20) | PASS |
| **D** | Answer quality (template rewrite only) | >80% scoring >=4/5 | **20%** (avg 2.3/5, n=15) | **FAIL** |
| **D2** | Full pipeline (genericized, blinded A/B) | >80% quality retained | **3.8/5** (133% retained, n=5) | PASS |
| **E** | Session composition (simulation) | <40% recovery at 5 queries | **40% with covers** vs **100% without** | PASS |
| **F** | Economic damage model (illustrative) | — | Sanitization → $0 in modeled attacks | Illustrative |

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

## Caveats

**This is a research prototype, not an audit-complete privacy tool.**

- **Classifier validation is partially external**: DistilBERT trains on data from the same `cover_generator` — it tests whether a second model exploits this generator's artifacts, not robustness against truly external distributions or human adversaries
- **Benchmark B leakage detection is string-matching only**: Misses paraphrases ("large position"), abstractions ("near liquidation"), and derived disclosures. A stronger detector (NER, entailment-based) is needed
- **Benchmarks E and F are simulations, not attack benchmarks**: E assumes per-set unlinkability (best case). F hard-codes adversary profit reduction from k=4 as 75% — an assumption, not a measurement
- **Benchmark D2 is a blinded A/B comparison** (direct vs pipeline answer, randomized order, same judge). Previous versions had a methodological bug where the direct answer was unused
- **Local model capability gap**: 7B models leak private parameters 30% during decomposition. Need 14B+ for production
- **Small sample sizes**: n=5-40 per benchmark — larger-scale validation needed
- **No real user queries**: 216-query synthetic benchmark includes forum-sourced phrasings but has not been validated by independent DeFi users. Real DeFi position queries are inherently private (0.004% hit rate in 1M WildChat conversations)
- **Requirements pinned to exact versions** for reproducibility. Results may differ with other package versions or LLM backends

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
- **Regex has a natural language gap**: "half a million USDC" and "roughly two thousand ETH" bypass the sanitizer; a secondary NLP filter is recommended
