# Deployment Guide: Dataset Privacy, Runtime Options, and Quality Tradeoffs

## Dataset Privacy Model

The meta-framework has two phases with different privacy requirements:

```
GENERATION (one-time, build the profile):
  Input: dataset of domain queries
  Output: profile.json (domain knowledge, no private data)

RUNTIME (every query, protect the user):
  Input: user's private query
  Output: sanitized/covered query sent to cloud
```

The profile itself contains only domain knowledge (ontology, regex patterns, templates) — no private user data. It's safe to share, publish, and inspect.

### Decision Matrix: What Backend for What Data

| Dataset type | Generation backend | Validation backend | Runtime backend |
|---|---|---|---|
| **Public/research** (synthetic, forum-sourced) | Cloud LLM (best quality) | Programmatic (11/13 checks) + local LLM (2 quality checks) | Local LLM |
| **Private** (real user queries) | **Local LLM only** | Programmatic (11/13 checks) + local LLM (2 quality checks) | Local LLM |
| **Community profile** (pre-built) | N/A (download profile) | Programmatic validation | Local LLM |

### For Private Datasets: All-Local Pipeline

When the dataset contains real user queries, the entire generation must be local:

```bash
python generate_profile.py \
  --dataset private_queries.jsonl \
  --domain medical \
  --backend ollama --model qwen2.5:14b \
  --output domains/medical/profile.json
```

**Quality gap vs cloud generation**: The local 14B model produces fewer regex patterns (6-8 vs 40+), less precise vocabulary (12-51% recall), and noisier taxonomy. Accept this tradeoff or mitigate with the strategies below.

### Deployment Configurations (Private Data Safe)

All configurations below guarantee **no private data reaches any cloud LLM**.

### Config 1: Cloud Synthetic + Local Train (Recommended for new domains)

```
Cloud LLM: "Generate 500 realistic [domain] queries with sensitivity labels"
  → synthetic_dataset.jsonl (no real data, just domain patterns)
    → Local: generate_profile.py --dataset synthetic_dataset.jsonl
      → Local: validate against REAL private queries
```

Cloud sees only the domain name. The synthetic dataset captures query STRUCTURES without real values. Local validation ensures the profile catches real private patterns.

### Config 2: Cloud Ontology + Local Patterns

```
Cloud LLM: build ontology from public sources (Wikipedia, forums, docs)
  → templates, entity names, vocabulary (public knowledge)
    → Local LLM: generate sanitizer PATTERNS from private dataset
      → Merge ontology + patterns into final profile
```

Separation of concerns: domain knowledge (public) vs sensitivity patterns (private). The ontology reveals nothing about users; only the patterns encode what's "sensitive."

### Config 3: Cloud Profile Review

```
Local LLM: generate full profile from private data
  → profile.json contains domain KNOWLEDGE only (no private data)
    → Cloud LLM: "Review this profile for completeness"
      → Cloud suggests: "missing entity X, pattern Y is too broad"
        → Local: apply suggestions + re-validate
```

Safe because the profile is inspectable JSON containing vocabulary and regex — no private user data. The cloud reviews domain knowledge, not user queries.

### Config 4: Multi-Model Local (Anti-Self-Certification)

```
Qwen 14B:   generation (analyze, patterns, ontology)
Llama 14B:  validation (judge usability, check sensitivity labels)
Mistral:    adversarial testing (try to identify real queries in covers)
```

Three independent models cannot coordinate a self-certification attack. Each validates the others' work. Requires downloading multiple models (~30GB total) but maximum security.

### Config 5: Community Profile + Local Adaptation

```
Download: community-curated profile for [domain]
  → Local LLM: validate against private dataset
    → Local: refine (add patterns for private-data-specific formats)
      → Contribute PROFILE improvements back (not data)
```

No generation needed. The community profile encodes collective domain knowledge. Each user validates and adapts locally, contributes improvements to the profile without sharing queries.

### Config 6: Bootstrap (Cloud Base + Local Adapt)

```
Cloud LLM: generate base profile from public domain data
  → High-quality base (97% vocabulary recall)
    → Local LLM: adapt to private dataset
      → Add patterns for formats unique to private data
        → Validate locally (13 checks)
```

Tested in Experiment 5. Cloud provides the strong starting point; local closes domain-specific gaps. Private data never leaves the machine.

## Closing the Quality Gap (Private Data)

**1. Larger local model**

More capable models produce better profiles. Hardware cost, not privacy cost.

| Model | RAM needed | Expected improvement |
|-------|-----------|---------------------|
| Qwen 14B (current) | 10 GB | Baseline |
| Qwen 32B | 20 GB | Better taxonomy, more regex patterns |
| Llama 70B | 40 GB | Near-cloud quality |

**2. Multiple feedback rounds**

Each generation run saves diagnostics. Re-running loads them and adjusts prompts:

```bash
# Round 1: initial generation
python generate_profile.py --dataset data.jsonl --domain medical --backend ollama

# Round 2: uses feedback from round 1
python generate_profile.py --dataset data.jsonl --domain medical --backend ollama

# Round 3: uses feedback from rounds 1+2
python generate_profile.py --dataset data.jsonl --domain medical --backend ollama
```

Each round addresses weaknesses identified by the 13 validation checks.

**3. Human review of the profile (not the data)**

The generated `profile.json` is inspectable and contains NO private data:

```bash
# Review what was generated
cat domains/medical/profile.json | python -m json.tool | less

# Check: are the subdomains reasonable?
# Check: are the entity names complete?
# Check: do the regex patterns look correct?
# Check: are the templates natural?
```

A domain expert can edit the JSON directly — add missing entities, fix regex patterns, improve templates. This is safe because the profile is domain knowledge, not user data.

**4. Community profiles**

For common domains, download a curated profile instead of generating one:

```bash
# Use the hand-crafted DeFi profile (published, audited)
cp domains/defi/profile.json domains/my_defi/profile.json
```

No generation needed. No private data exposure. The hand-crafted DeFi profile has 40+ regex patterns, 280+ vocabulary terms, and 2,600/2,600 audit coverage.

## Runtime Options

At runtime, the user's private query passes through the protection pipeline. Three deployment tiers:

### Tier 0: Browser Extension ($0, no hardware)

```
User query → [Regex sanitizer] → Sanitized query → Cloud LLM → Answer
```

- **What runs locally**: Regex sanitization (from profile.json)
- **What goes to cloud**: Sanitized query (amounts/addresses stripped)
- **Hardware**: None (runs in browser)
- **Privacy**: Format-matchable params removed. Semantic leaks possible.
- **Usability**: ~2/5 (amounts lost, question structure preserved)

### Tier 1: Local LLM ($200-500/yr, Mac Mini with 14B+)

```
User query → [Local LLM: decompose] → Sub-queries
  → [Genericize: strip protocol names] → Generic sub-queries
    → [Cover generator: add k-1 decoy queries per sub-query]
      → [Tor: different IP per query] → Cloud LLM → Answers
        → [Local LLM: synthesize with private params] → Final answer
```

- **What runs locally**: Decomposition, genericization, cover generation, synthesis
- **What goes to cloud**: Genericized sub-queries mixed with covers
- **Hardware**: Mac Mini with 14B+ model (~$200-500/yr amortized)
- **Privacy**: Topic hiding via covers (34% detection on 14B, 20% on hand-crafted)
- **Usability**: ~3.8/5 (mechanism questions preserved, private params re-injected locally)

### Tier 1.5: Local LLM + TEE (Research)

```
Same as Tier 1, but cloud LLM runs in Trusted Execution Environment.
Covers provide defense-in-depth; TEE provides computational privacy.
```

- **Privacy**: Strongest — even the cloud operator can't see queries
- **Hardware**: Same as Tier 1 locally; cloud needs TEE-capable hardware
- **Status**: Research agenda (see companion_post_active_adversary.md)

### Runtime Model Recommendations

| Local model | Tier 0 | Tier 1 decomposition | Tier 1 synthesis |
|---|---|---|---|
| No model (browser only) | Works | Not available | Not available |
| Qwen 7B | Works | 30% param leakage (NOT recommended) | Weak synthesis |
| **Qwen 14B** | Works | **0% leakage, good quality** | Good synthesis |
| Qwen 32B | Works | 0% leakage, best quality | Best synthesis |

**14B is the minimum for Tier 1 production use.** 7B leaks private params during decomposition 30% of the time (Benchmark B).

## Benchmarking a Generated Profile

After generating a profile, run the standard benchmarks to measure quality:

```bash
# Validate the profile (13 checks, programmatic + local LLM)
python generate_profile.py \
  --validate-only domains/medical/profile.json \
  --dataset data/medical_queries.jsonl

# Compare against a baseline (if available)
python compare_profiles.py domains/defi/profile.json domains/medical/profile.json

# Run full benchmarks A-F (requires LLM backend)
python run_benchmarks.py --benchmark all --backend ollama --model qwen2.5:14b

# Run specific benchmarks
python run_benchmarks.py --benchmark C --samples 50    # Cover indistinguishability
python run_benchmarks.py --benchmark D2                 # Tier 1 pipeline utility
```

### Benchmark Targets (Based on Hand-Crafted DeFi Baseline)

| Benchmark | Hand-crafted | Target for generated | What it measures |
|---|---|---|---|
| A (sensitivity F1) | 97% | >=90% | Can LLM detect sensitive queries? |
| B (decomposition leakage) | 0% (14B+) | 0% | Do sub-queries leak private params? |
| C (cover detection) | 20% | <=40% | Can adversary find real query? |
| D2 (pipeline utility) | 3.8/5 | >=3.0/5 | Does Tier 1 produce useful answers? |
| E (session composition) | 20-60% | <=60% | Can adversary infer strategy over time? |

### Interpreting Validation Results

```
ACCEPTANCE: ACCEPTED     → Profile ready for deployment
ACCEPTANCE: NEEDS_WORK   → Re-run with feedback, or human-review profile
ACCEPTANCE: REJECTED     → Larger model, better dataset, or manual crafting needed
```

## Security Properties by Tier

| Property | Tier 0 | Tier 1 | Evidence |
|---|---|---|---|
| Parameter hiding | Yes (regex) | Yes (regex + decomposition) | 2,600/2,600 audit |
| Topic hiding | No | Yes (covers) | 20-34% detection |
| Transport unlinkability | No | Yes (Tor) | Per-set different IPs |
| Answer quality | 2/5 | 3.8/5 | Benchmark D2 |
| Active adversary defense | No | Partial (statelessness) | Research agenda |

## Experimental Results: Generation Quality by Backend

Tested on the DeFi 216-query benchmark dataset. All profiles validated by the same programmatic checks.

### Vocabulary Recall vs Hand-Crafted Baseline

| Metric | Local 7B | Local 14B | Local 14B+Web | **Cloud Claude** |
|--------|:-:|:-:|:-:|:-:|
| Protocols | 51% | 46% | — | **100%** |
| Mechanisms | 12% | 11% | — | **91%** |
| Metrics | 10% | 10% | — | **100%** |
| Overall vocabulary | 22% | 22% | — | **97%** |

### Profile Quality Comparison

| Metric | Hand-Crafted | Local 7B | Local 14B | Local 14B+Web | **Cloud Claude** |
|--------|:-:|:-:|:-:|:-:|:-:|
| Subdomains | 7 | 31 (noisy) | 7 | 5 | 9 |
| Regex patterns | 40+ | 0 | 6 | 8 | **40+** |
| Entity names | 96 | 191 (noisy) | 45 | 56 | **100+** |
| Cover detection | 26% | 24% | 34% | 32% | **22%** |
| False positive words | 45 | 43 | 43 | 43 | **55** |
| Templates | 20 | 20 | 12 | 18 | 20 |
| Sanitizer (spans caught) | — | 302/302 | 305/305 | 304/304 | — |

### Final Validation Verdicts (All Profiles)

| Profile | SD | Tmpl | Ents | Cover | PASS | MARG | FAIL | Acceptance |
|---------|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| **Hand-crafted** | 7 | 20 | 96 | 20% | 7 | 2 | 0 | **ACCEPTED** |
| Local 7B | 31 | 20 | 191 | 50% | 4 | 2 | 3 | REJECTED |
| Local 14B | 7 | 12 | 45 | 66% | 6 | 2 | 1 | REJECTED |
| **Local 14B+web** | **5** | **18** | **56** | **32%** | **7** | **2** | **0** | **ACCEPTED** |
| Cloud Claude | 9 | 20 | 102 | 22% | 5 | 4 | 0 | NEEDS_WORK |
| Bootstrap | 9 | 20 | 102 | 22% | 5 | 4 | 0 | NEEDS_WORK |

### Tier 1 Pipeline Quality (Blinded A/B, Local 14B Judge)

| Profile | Pipeline score | Quality retained | Verdict |
|---------|:-:|:-:|:-:|
| **Cloud Claude** | **3.8/5** | **87%** | **PASS** |
| Hand-crafted | 3.25/5 | 81% | PASS |
| Bootstrap | 3.2/5 | 78% | PASS |

### Key Findings

1. **Local 14B+web is the best local-only result**: ACCEPTED (7P/2M/0F) — the only auto-generated profile matching hand-crafted acceptance. Web search + 14B is sufficient for production.

2. **Cloud Claude has the best Tier 1 quality**: 3.8/5 pipeline score, 87% retained — outperforms hand-crafted (3.25/5, 81%). Richer ontology produces better genericization.

3. **Cloud Claude profiles need review**: 97% vocabulary recall but 4 MARGINAL checks → NEEDS_WORK. The extra subdomains (9 vs 7) cause ontology balance issues.

4. **Bootstrap didn't improve over cloud-only**: Local adaptation didn't close the MARGINAL gaps and broke sanitizer_completeness in one run. The cloud profile is already strong; local refinement adds risk without clear benefit.

5. **14B is the minimum for local generation**: 7B produces 0 valid regex and 31 noisy subdomains (REJECTED). 14B produces clean taxonomy and usable patterns.

6. **Web search makes the critical difference for local**: 14B alone = REJECTED (cover detection 66%). 14B+web = ACCEPTED (cover detection 32%). Web enrichment provides the vocabulary diversity that the 14B model can't generate alone.

7. **For public data, use cloud generation**: Best Tier 1 quality (3.8/5), best cover detection (22%), 97% vocabulary recall.

8. **For private data, use local 14B+web**: Only ACCEPTED local profile. Web search is safe (searches domain terminology, not private data).

## Iteration Effectiveness: Local LLM Quality Ceiling

### Observed Improvement Across Iterations (Qwen 14B)

| Metric | Run 1 (no feedback) | Run 2 (+web search) | Run 3 (+feedback) | Hand-crafted |
|--------|:-:|:-:|:-:|:-:|
| Raw subdomains (before consolidation) | 44 | 44 | **23** | — |
| Final subdomains | 7 | 5 | 7 | 7 |
| Templates | 12 | 18 | **22** | 20 |
| Regex patterns | 6 | 8 | TBD | 40+ |
| Spans caught | 305/305 | 304/304 | TBD | 2,600/2,600 |

Iteration improves what is **prompt-tunable**: taxonomy quality, template count, vocabulary breadth, sensitivity coverage. It cannot fix what is **model-bounded**: regex engineering depth, vocabulary precision, nuanced reasoning.

### Estimated Quality Ceiling by Model Size

Based on observed scaling behavior (14B → Claude) and known capability thresholds:

| Model | Params | RAM | Taxonomy | Regex Patterns | Vocab Recall | Cover Detection | Estimated Quality vs Hand-Crafted |
|-------|--------|-----|----------|:-:|:-:|:-:|:-:|
| Qwen 7B | 7B | 6 GB | 31 noisy | 0 | 12% | 24% | ~20% |
| **Qwen 14B** | 14B | 10 GB | 7 clean | 6-8 | ~25% | 34% | **~40%** |
| Qwen 14B (3 iterations) | 14B | 10 GB | 7 clean | 8-10 | ~35% | ~30% | **~55%** |
| Qwen 32B | 32B | 20 GB | ~7 clean | ~15-20 | ~50% | ~28% | **~65%** |
| Llama 70B | 70B | 40 GB | ~7 clean | ~25-30 | ~70% | ~25% | **~80%** |
| Qwen 72B / Llama 90B | 72-90B | 48-56 GB | 7 clean | ~30-35 | ~80% | ~24% | **~85%** |
| Llama 120B+ / DeepSeek | 120B+ | 64+ GB | 7 clean | ~35-40 | ~90% | ~23% | **~90%** |
| **Claude (cloud)** | ~200B+ | Cloud | 9 clean | 40+ | 97% | 22% | **~97%** |

**Key thresholds:**
- **14B**: Minimum for production Tier 1 runtime (0% decomposition leakage). Generation quality limited.
- **32B**: Significant jump in regex generation and vocabulary precision. Requires 32GB unified memory (M2/M4 Pro/Max).
- **70B**: Near-cloud quality for most tasks. Requires 40GB+ (Mac Studio or dedicated GPU).
- **120B+**: Diminishing returns vs cloud. Requires enterprise hardware.

### What Each Model Size Unlocks

**7B → 14B** (biggest practical jump):
- Taxonomy consolidation works (31 → 7 subdomains)
- Some valid regex patterns (0 → 6-8)
- Decomposition stops leaking private params (30% → 0%)
- Iteration becomes effective (feedback loop has something to improve)

**14B → 32B** (next practical jump for 32GB Macs):
- Regex patterns double (~15-20, covering more edge cases)
- Vocabulary precision improves (exact term matching, not paraphrases)
- Template quality approaches hand-crafted
- Fewer iteration rounds needed (2 vs 3-4)

**32B → 70B** (diminishing returns begin):
- Regex engineering approaches expert level
- Vocabulary recall hits ~70% in single pass
- Domain-specific heuristic discovery much more reliable
- One iteration may suffice

**70B → 120B+** (marginal improvements):
- Last 10-20% of vocabulary coverage
- Subtle sensitivity classification (semantic leaks)
- Complex regex with lookaheads, Unicode handling
- For private data, still worth it — no privacy cost to running locally, only hardware cost

### Practical Recommendation: Iteration Strategy by Hardware

| Hardware | Model | Strategy | Expected Quality |
|----------|-------|----------|:-:|
| 16 GB Mac (M1/M2/M4) | Qwen 14B | 3-4 iterations + human review | ~55% |
| 32 GB Mac (M2/M4 Pro) | Qwen 32B | 2-3 iterations + light review | ~70% |
| 64 GB Mac (M2/M4 Max) | Llama 70B | 1-2 iterations | ~80% |
| Mac Studio 96-192 GB | 120B+ model | Single pass + validation | ~90% |
| Cloud (any hardware) | Claude Sonnet/Opus | Single pass + local validation | ~97% |
| **Best ROI (public data)** | Cloud generation + local validation | One cloud pass + 11 programmatic checks | ~97% |
| **Best ROI (private data)** | **Largest local model that fits** | Fewer iterations needed, zero privacy cost | Hardware-dependent |

### The Iteration + Human Review Strategy

For all-local pipelines, the recommended workflow:

```
Round 1: Generate with local model
  → Validate (13 checks)
  → Save diagnostics

Round 2: Re-generate with feedback
  → Validation improves (templates, taxonomy)
  → Save diagnostics

Round 3: Re-generate with accumulated feedback
  → Diminishing returns
  → Export profile.json

Human review: Inspect profile.json (15 min)
  → Add missing entity names
  → Fix regex patterns
  → Adjust vocabulary
  → Result: ~70-80% quality regardless of model size
```

The profile is inspectable JSON — a domain expert spending 15 minutes can close the gap that a larger model would close automatically. This is the most cost-effective approach for private datasets where cloud LLMs cannot be used.

## Summary: What to Use When

| Scenario | Recommendation |
|---|---|
| DeFi user, casual privacy | Tier 0 with hand-crafted profile ($0) |
| DeFi user, serious privacy | Tier 1 with hand-crafted profile + 14B Mac Mini |
| New domain, public dataset | Generate with cloud LLM, validate locally |
| New domain, private dataset | Generate all-local, multiple feedback rounds + human review |
| Enterprise deployment | Community profile + human audit + Tier 1 runtime |
