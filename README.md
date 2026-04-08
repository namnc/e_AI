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
| **A** | Sensitivity classification | >90% F1 | **98-100% F1** (n=40-100) | PASS |
| **B** | Decomposition quality | >85% coverage, 0% leakage | **100%/0%** (frontier), **70%/30%** (7B) | PASS/MARGINAL |
| **C** | Cover indistinguishability (LLM adversary) | <55% detection | **20%** (n=30, v5) | PASS |
| **C-ext** | Cover indistinguishability (DistilBERT) | <55% set-level | **35%** (n=2000, balanced) | PASS |
| **D** | Answer quality (template rewrite only) | >80% scoring >=4/5 | **20%** (avg 2.3/5, n=15) | **FAIL** |
| **D2** | Answer quality (full pipeline) | >80% scoring >=4/5 | **60%** (avg 3.6/5, n=5, 7B model) | MARGINAL |
| **E** | Session composition attack | <40% recovery at 5 queries | **40% with covers** vs **100% without** | PASS |
| **F** | Damage reduction (simulated) | >85% profit reduction | **100% for parameter-dependent attacks** | PASS |

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

- **Same-model bias — addressed**: Trained independent DistilBERT classifier; result (25-34%) consistent with LLM adversary
- **Benchmark D/D2**: Template rewriting alone degrades quality to 2.3/5 (FAIL). Full pipeline (decompose → covers → synthesize) scores 3.6/5 with 7B model (MARGINAL); 14B+ expected to reach 4+/5
- **Local model capability gap**: 7B models leak private parameters 30% of the time during decomposition. Need 14B+ for production
- **Small sample sizes**: n=10-40 per benchmark — larger-scale validation needed
- **No real user queries**: We scanned 1M WildChat conversations and found <40 real DeFi queries (0.004% hit rate) — almost all about coding, not personal positions. Real DeFi position queries are inherently private and do not appear in public datasets at usable scale. Our 216-query synthetic benchmark (`data/benchmark_dataset.jsonl`) includes forum-sourced phrasings from Aave governance but has not been validated for realism by independent DeFi users

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
