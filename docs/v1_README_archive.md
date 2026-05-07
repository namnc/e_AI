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
- **`ethresearch_post.md`** — the main ethresear.ch post (Part 1: the private query problem)
- **`companion_post_active_adversary.md`** — Part 2: active adversaries, verifiable inference, cryptoeconomic accountability
- **`ethresearch_meta_framework_draft.md`** — Part 3 (draft): domain-agnostic meta-framework for auto-generating privacy protection
- Benchmark suite (A-F), DistilBERT classifier, cover generator, sanitizer tests
- **Meta-framework** for auto-generating privacy pipelines from any dataset

**Walkthroughs:**
- **[Hand-crafted pipeline](docs/walkthrough_handcrafted.md)** — how the DeFi privacy pipeline works, step by step (Alice example, Tier 0 + Tier 1)
- **[Meta-framework](docs/walkthrough_meta_framework.md)** — how the auto-generation pipeline works (input validation → analysis → generation → refinement → validation → feedback)
- **[Deployment guide](docs/deployment_guide.md)** — dataset privacy model, runtime tiers, quality tradeoffs, benchmarking generated profiles

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
├── cover_generator.py           # v5 cover algorithm — reads from domain profile
├── llm_backend.py               # Backend abstraction (Anthropic API + Ollama)
├── dataset.py                   # Test vectors and session scenarios
├── rewrite_strategies.py        # Sub-query rewriting (Approach A/B/C comparison)
├── test_sanitizer.py            # Unit tests for regex sanitizer (47 tests)
├── test_sanitizer_audit.py      # Completeness audit (2,600 synthetic params)
├── test_sanitizer_fuzz.py       # Adversarial fuzz test (Unicode tricks, format mutations)
├── test_benchmarks.py           # Benchmark regression tests (24 tests)
├── .github/workflows/tests.yml  # CI pipeline (runs on every PR)
├── Dockerfile                   # Reproducible test environment
├── run_all.sh                   # One-click full benchmark run
│
│── core/                        # Profile-based architecture
│   ├── domain_profile.py        # DomainProfile schema (TypedDict)
│   └── profile_loader.py        # Load, validate, and cache profiles from JSON
│
├── domains/                     # Domain profile instances
│   ├── defi/
│   │   └── profile.json         # Hand-crafted DeFi profile (extracted from v5 constants)
│   ├── defi_generated/
│   │   └── profile.json         # Auto-generated by Qwen 7B (round-trip test)
│   ├── defi_14b/
│   │   └── profile.json         # Auto-generated by Qwen 14B (improved round-trip)
│   └── _feedback/               # Cross-domain diagnostics for feedback loop
│
├── meta/                        # Meta-framework: auto-generate profiles from datasets
│   ├── analyzer.py              # Phase 1: LLM analyzes dataset (sensitivity, clustering, vocabulary, templates)
│   ├── pattern_generator.py     # Phase 2a: generates regex patterns + entity lists from spans
│   ├── refiner.py               # Phase 2c: iterative repair loop (validate → fix → re-validate)
│   ├── input_validator.py        # Pre-flight dataset validation (6 checks)
│   ├── data_enrichment.py       # Dataset enrichment (web search + LLM synthesis + refinement loop)
│   ├── feedback.py              # Diagnostics, acceptance thresholds, cross-domain feedback loop
│   ├── validation_engine.py     # 13 property checks (6 functional + 5 security + 2 quality)
│   ├── profile_sanitizer.py      # Genericize profiles for safe cloud review
│   ├── util.py                  # Shared utilities (extract_json)
│   ├── web_enrichment.py        # Web search integration (ontology, threat model, false positives)
│   └── prompts.py               # All LLM prompts for the meta pipeline
│
├── generate_profile.py          # CLI: dataset → analyze → generate → refine → validate → profile.json
├── compare_profiles.py          # Compare hand-crafted vs generated profiles
│
├── docs/
│   ├── walkthrough_handcrafted.md  # Step-by-step: how the DeFi pipeline works
│   ├── walkthrough_meta_framework.md # Step-by-step: how auto-generation works
│   ├── deployment_guide.md      # Dataset privacy, runtime tiers, quality tradeoffs
│   ├── adversary_prompt.md      # All LLM prompts used in benchmarks
│   ├── scoring_rubric.md        # Benchmark D quality scoring rubric
│   ├── transport_assumptions.md # Tor circuit pool, mixnet, timing mitigations
│   ├── latency_projections.md   # Per-hardware latency estimates (M1→M4 Max)
│   ├── sanitizer_gaps.md        # What's caught, what leaks, recommended NLP filters
│   ├── staking_mechanism.md     # On-chain staking interface (Solidity), slashing tiers
│   ├── research_directions.md   # 10 open problems with approaches and priority ranking
│   └── research_solutions.md    # Analytical solutions: formal proof, optimal k, Shannon capacity, collusion analysis
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

## Meta-Framework: Domain-Agnostic Profile Generation

The privacy protection pipeline is now **domain-agnostic**. All domain-specific constants (ontology, sanitizer patterns, templates, entity names) are loaded from a `profile.json` file. The DeFi pipeline is the first instance; the meta-framework can generate profiles for any domain.

### Architecture

```
Dataset (JSONL)  ──┐
                   ▼
            ┌─────────────┐     ┌──────────────┐
            │  Domain      │────>│  Tool         │──┐
            │  Analyzer    │     │  Generator    │  │
            │  (local LLM) │     │  (local LLM)  │  │
            └─────────────┘     └──────────────┘  │
                   ▲                               │
                   │ web search                    ▼
                   │ (enrichment)         ┌──────────────┐
                   │                      │  Domain       │
                   │                      │  Profile      │
                   │                      │  (JSON)       │
                   │                      └──────┬───────┘
                   │                             │
            ┌──────┴──────┐              ┌───────▼───────┐
            │  Validation  │◄────────────│  Protection   │
            │  Engine      │  refine     │  Runtime      │
            └─────────────┘              └───────────────┘
```

### Generating a Profile

```bash
# Generate from any JSONL dataset (local LLM, privacy-preserving)
python generate_profile.py \
  --dataset data/benchmark_dataset.jsonl \
  --domain defi \
  --backend ollama --model qwen2.5:14b \
  --output domains/defi/profile.json

# With web search to enrich vocabulary and threat model
python generate_profile.py \
  --dataset data/medical_queries.jsonl \
  --domain medical \
  --backend ollama \
  --web-search \
  --output domains/medical/profile.json

# Validate an existing profile against a dataset
python generate_profile.py \
  --validate-only domains/defi/profile.json \
  --dataset data/benchmark_dataset.jsonl
```

### Dataset Format

Input datasets are JSONL with one query per line:
```json
{"text": "My Aave V3 position has 500 ETH collateral...", "label": "sensitive"}
{"text": "What is impermanent loss?", "label": "non_sensitive"}
```

Minimum fields: `text`, `label` (`sensitive` | `non_sensitive` | `borderline`).
Optional: `category`, `private_params`, `difficulty`, `exploitable_by`, `estimated_damage_usd`.

### Profile Schema

A `profile.json` contains all domain-specific constants:

| Section | Contents | Replaces |
|---------|----------|----------|
| `meta` | Domain name, version, generation model, validation status | — |
| `domain_distribution` | Subdomain frequency weights | `DOMAIN_DISTRIBUTION` |
| `top_domains` | Most frequent subdomains | `TOP_DOMAINS` |
| `subdomains` | Vocabulary per subdomain (entities, mechanisms, operations, triggers, metrics, actors, risk_concepts, generic_refs) | `DOMAIN_ONTOLOGY` |
| `sensitive_patterns` | Regex patterns, entity names, emotional/timing/qualitative word lists, false positives | All `_AMOUNT_PATTERNS_*`, `_ADDRESS_PATTERNS`, etc. |
| `templates` | Question templates with `{SLOT}` placeholders | `TEMPLATES` |
| `template_slots` | Maps slot names to ontology categories | Hardcoded in `_fill()` |
| `domain_heuristics` | LLM-discovered sensitivity patterns (amounts, timing, emotional) | Used by check 10 for domain-agnostic validation |

### Formal Properties

The validation engine checks 13 properties (6 functional + 5 anti-malicious-LLM guardrails + 2 quality):

| Property | Definition | Threshold | Test |
|----------|-----------|-----------|------|
| Parameter Hiding | No labeled sensitive span survives sanitization | 0% FN | Sanitizer audit |
| False Positive Rate | Non-sensitive queries not over-stripped | <5% words removed | Run on non-sensitive set |
| Profile Completeness | Dataset queries map to subdomains | >=95% coverage | Domain classifier |
| Template Coverage | Dataset queries match templates | >=60% match rate | Template matching |
| Vocabulary Depth | Each subdomain has sufficient vocabulary | >=3 items per slot | Schema check |
| k-Indistinguishability | Adversary detection rate on cover sets | <=40% (vs 25% random) | Quick classifier |
| Entity Completeness | Dataset entities covered by entity_names | >=70% coverage | Anti-omission guardrail |
| Held-Out Sanitizer | Independent test data not from generating LLM | 0% param leakage | Anti-self-certification |
| Ontology Balance | Subdomain vocabulary sizes balanced | >=0.40 min/max ratio | Anti-fingerprinting |
| Sensitivity Labels | Heuristic regex detects categories LLM may omit | >=50% per category | Anti-self-certification |
| Vocabulary Diversity | Edit-distance dedup catches near-duplicate fills | <=10 duplicates | Anti-inflation |
| Tier 1 Pipeline | End-to-end decompose→genericize→answer→synthesize | >=70% quality retained | Blinded A/B vs direct |
| Tier 0 Usability | Sanitized queries still coherent and answerable | >=2.0/5 avg, no destroyed | LLM-as-judge |

### Experimental Results (DeFi, 216-Query Benchmark)

Six generation strategies tested, all validated by the same 13 programmatic checks:

| Profile | Subdomains | Templates | Entities | Cover Detection | Acceptance |
|---------|:-:|:-:|:-:|:-:|:-:|
| **Hand-crafted** | 7 | 20 | 96 | **20%** | **ACCEPTED** |
| Local 7B | 31 | 20 | 191 | 50% | REJECTED |
| Local 14B | 7 | 12 | 45 | 66% | REJECTED |
| **Local 14B+web** | **5** | **18** | **56** | **32%** | **ACCEPTED** |
| Cloud Claude | 9 | 20 | 102 | **22%** | NEEDS_WORK |
| Bootstrap (cloud+local) | 9 | 20 | 102 | **22%** | NEEDS_WORK |

Tier 1 pipeline quality (blinded A/B, local judge):

| Profile | Pipeline Score | Quality Retained |
|---------|:-:|:-:|
| **Cloud Claude** | **3.8/5** | **87%** |
| Hand-crafted | 3.25/5 | 81% |
| Bootstrap | 3.2/5 | 78% |

**Key findings**: Local 14B+web is the best private-data-safe option (ACCEPTED). Cloud Claude produces the best Tier 1 quality (3.8/5, outperforms hand-crafted). See [deployment guide](docs/deployment_guide.md) for full analysis and configuration options.

## Benchmark Results

| Benchmark | What It Tests | Target | Result | Verdict |
|---|---|---|---|---|
| **A** | Sensitivity classification | >90% F1 | **97% F1** (n=100, Qwen 7B) | PASS |
| **B** | Decomposition quality (string-match only) | >85% coverage, 0% leakage | **100%/0%** (frontier), **70%/30%** (7B) | PASS/MARGINAL |
| **C** | Template indistinguishability | Near 25% random | **20%** (LLM, n=20), **AUC 0.507** (DistilBERT) | PASS |
| **C2** | Genericized-static detectability (NOT full pipeline — uses curated SANITIZED_QUERIES, not decomposition output) | Near 25% random | **40%** (genericized sub-queries, n=20) | MARGINAL (+15pp above random) |
| **D** | Answer quality (template rewrite only) | >80% scoring >=4/5 | **20%** (avg 2.3/5, n=15) | **FAIL** |
| **D2** | Utility only: genericized-direct query (NO covers, blinded A/B, same-model judge) | >80% quality retained | **3.8/5** (capped at 100% vs direct, n=5) | PASS |
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
./run_all.sh ollama qwen2.5:7b    # runs everything (NOTE: 7B leaks params 30% — use 14B+ for production)
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

**All contributions protect your privacy by design.** The benchmark dataset is synthetic. Real queries are private by definition. Every contribution path below ensures no private data leaves your machine.

### Sanitizer & Privacy

**1. Sanitizer bypass bounty (highest value)**
Find queries where exploitable information survives sanitization. Report the *pattern*, not your query:
```bash
python -c "
from cover_generator import sanitize_query
q = input('Paste query (stays local): ')
print(f'Sanitized: {sanitize_query(q)}')
# Report ONLY the pattern: 'worded fractions like half a million bypass'
"
```
Open a GitHub issue with the pattern class. Past bounty finds: Unicode bypasses, locale-formatted numbers, truncated addresses, split-token amounts.

**2. Local-only validation**
Run the sanitizer on your actual queries locally. Report only the binary result (leaked/clean), never the query:
```bash
python test_sanitizer_fuzz.py --rounds 5000  # adversarial mutations
python test_sanitizer_audit.py               # 2,600 synthetic params
```

**3. Fuzz corpus expansion**
Add adversarial test cases to `test_sanitizer_fuzz.py` — Unicode tricks, format mutations, locale variants, novel encoding bypasses. The fuzz test is now blocking in CI at a 5% threshold.

### Profile & Ontology

**4. Profile improvement (safe — profiles contain no private data)**
Review `domains/defi/profile.json` for:
- Missing protocol names the genericizer should strip
- Missing mechanisms, metrics, or vocabulary per subdomain
- False-positive words that shouldn't be stripped
Submit as PR. Profiles are domain knowledge, not user data.

**5. Community profiles for new domains**
Generate a profile for medical, legal, TradFi, or other domains using public datasets:
```bash
python generate_profile.py --dataset public_medical_queries.jsonl --domain medical --backend ollama
```
Submit the profile (not the dataset). Others validate locally against their private data.

### Benchmarks & Validation

**6. Independent labeling**
Label 100 queries from `data/benchmark_dataset.jsonl` as sensitive/non_sensitive/borderline. Target: Cohen's kappa > 0.7 inter-annotator agreement.

**7. Benchmark validation on different hardware/models**
Run benchmarks A-F on your hardware and report results. Helps establish the quality-hardware curve documented in [deployment_guide.md](docs/deployment_guide.md):
```bash
python run_benchmarks.py --benchmark all --backend ollama --model qwen2.5:32b
```

**8. Meta-framework audit**
Review `meta/` modules for validation gaps, pattern generation bugs, feedback contamination, or privacy side channels. Past audit finds: self-certification attacks, search query privacy leaks, profile sanitizer JSON crashes, feedback global mutation.

### What NOT to share
- Never share your actual queries, wallet addresses, or position details
- Never share your private dataset (use it locally only)
- Profiles and patterns are safe to share — they contain domain knowledge, not user data
