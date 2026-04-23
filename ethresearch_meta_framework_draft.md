# The Private Query Problem, Part 3: A Meta-Framework for Domain-Agnostic Privacy Protection

**Draft — not yet published**

## Abstract

In Parts [1] and [2], we identified the Private Query Problem — cloud LLM queries leaking intent, strategy, and portfolio data before DeFi transactions — and proposed a tiered privacy architecture (regex sanitizer + cover queries + local LLM decomposition). That architecture was hand-crafted for DeFi, requiring weeks of domain expertise to build.

This post presents a **meta-framework** that auto-generates equivalent privacy protection for any domain. Given a JSONL dataset of domain queries, a local LLM analyzes sensitivity patterns, generates sanitizer regex, builds domain ontology for cover queries, and validates the result against 13 formal properties. The framework is fully domain-agnostic (17/17 components), includes 5 anti-malicious-LLM guardrails, and produces profiles that match hand-crafted quality when using a frontier model for generation.

We validate on the DeFi benchmark (216 queries) across 6 generation strategies. Key findings: (1) local 14B+web search achieves ACCEPTED status matching hand-crafted, (2) cloud-generated profiles achieve 97% vocabulary recall and 3.8/5 Tier 1 pipeline quality (outperforming hand-crafted at 3.25/5), (3) the quality gap is entirely in the generating model, not the framework.

## 1. Motivation

### 1.1 The Generalization Problem

The DeFi pipeline from Part 1 works, but it's brittle:
- 40+ hand-tuned regex patterns specific to DeFi token formats
- 7 subdomains with 280+ curated vocabulary terms
- 20 manually written question templates
- 96 protocol names for the genericizer

This took weeks of iteration and 8+ audit rounds to harden. For a new domain (medical, legal, TradFi), the entire process must be repeated from scratch. The privacy problem is universal — anyone querying a cloud LLM about sensitive topics leaks information — but the solution was domain-specific.

### 1.2 The Self-Certification Problem

Any automated system that generates its own privacy tools faces a fundamental challenge: the generating LLM controls both what it labels as sensitive AND the patterns to catch it. A subtly biased model can label only easy-to-catch patterns, generate a sanitizer that passes its own tests, and claim 100% coverage — while real sensitive data leaks.

This is equivalent to letting a student write their own exam. The meta-framework must include independent validation that the generating LLM cannot game.

## 2. Architecture

### 2.1 Pipeline

```
Input Dataset (JSONL)
  → Input Validation (6 checks, no LLM)
    → Data Enrichment (web search + LLM synthesis, if dataset is thin)
      → Phase 1: Analysis (local LLM)
        Step 1: Sensitivity extraction (identify private spans per query)
        Step 2: Subdomain clustering (4-8 categories)
        Step 3: Vocabulary extraction (ontology per subdomain)
        Step 4: Template extraction (question structures)
        Step 5: Heuristic discovery (domain-specific sensitivity patterns)
      → Phase 2: Generation
        2a: Regex patterns from observed sensitive spans
        2b: Web enrichment (optional, search queries sanitized)
        2c: Privacy refinement (fix false negatives, circuit breaker)
        2d: Usability refinement (fix over-stripping, circuit breaker)
      → Write profile.json
        → Phase 3: Validation (13 property checks)
          → Feedback loop (cross-domain diagnostics)
            → Acceptance assessment
```

### 2.2 The Domain Profile

All domain-specific constants live in a single JSON file:

| Section | What it replaces |
|---------|-----------------|
| `subdomains` | Hand-crafted domain ontology (protocols, mechanisms, operations, triggers, metrics, actors, risk_concepts, generic_refs) |
| `sensitive_patterns` | Hand-crafted regex patterns, entity names, emotional/timing/qualitative word lists |
| `templates` | Hand-crafted question templates with {SLOT} placeholders |
| `domain_heuristics` | LLM-discovered sensitivity patterns for independent validation |

The hand-crafted DeFi pipeline becomes the first *instance* of this schema. The runtime code (`cover_generator.py`) reads from the profile instead of hardcoded constants. All 71 existing tests pass with zero behavior change.

### 2.3 Domain Agnosticism

17 of 17 framework components are fully domain-agnostic:
- Held-out test auto-generates via 80/20 dataset split (no DeFi fallback)
- Sensitivity heuristics discovered per domain by the LLM (Step 5)
- Cross-domain feedback filtered: only flags issues in 2+ different domains
- Privacy guards: usability and Tier 1 checks SKIP on cloud backends
- DeFi-specific items (profile, dataset, tests) are instances, not dependencies

## 3. Validation Engine: 13 Property Checks

### 3.1 Functional Properties (6)

| Property | Threshold | What it catches |
|----------|-----------|-----------------|
| Sanitizer completeness | 0% FN on labeled spans | Patterns that miss sensitive data |
| False positive rate | <5% word removal | Over-stripping that destroys queries |
| Profile completeness | >=95% subdomain coverage | Queries that fall outside the ontology |
| Template coverage | >=60% match rate | Templates that don't cover query diversity |
| Vocabulary depth | >=3 items per slot | Subdomains too thin for cover generation |
| Cover quality | <=40% detection (vs 25% random) | Covers that are distinguishable |

### 3.2 Anti-Malicious-LLM Guardrails (5)

These counter the self-certification problem:

| Guardrail | Attack it prevents | How |
|-----------|-------------------|-----|
| Entity completeness | LLM omits protocol names from entity list | Compares capitalized phrases in queries vs entity_names |
| Held-out sanitizer | LLM writes easy test + easy pattern | Tests against dataset private_params or auto-extracted held-out set |
| Ontology balance | LLM makes one subdomain richer (fingerprinting) | Checks min/max vocabulary ratio |
| Sensitivity labels | LLM under-labels timing/emotional/amounts | LLM-independent heuristic regex (discovered per domain) |
| Vocabulary diversity | LLM fills slots with near-duplicates | Edit-distance dedup |

**Key design principle**: 11 of 13 checks are fully programmatic (no LLM). Security validation cannot be influenced by model quality or bias.

### 3.3 Quality Properties (2)

| Property | Threshold | Requires |
|----------|-----------|----------|
| Tier 1 pipeline | >=70% quality retained (blinded A/B) | Local LLM |
| Tier 0 usability | >=2.0/5 avg score | Local LLM |

These require a local LLM as judge and SKIP on cloud backends (privacy guard: unsanitized queries are never sent to cloud).

### 3.4 Acceptance Thresholds

| Status | Criteria | Action |
|--------|----------|--------|
| ACCEPTED | 0 FAIL, <=2 MARGINAL | Profile ready for deployment |
| NEEDS_WORK | 0 FAIL, >2 MARGINAL | Re-run with feedback |
| REJECTED | Any FAIL | Larger model, better dataset, or manual review |

## 4. Experimental Results

### 4.1 Setup

216-query DeFi benchmark dataset. Six generation strategies tested, all validated by the same 13 programmatic checks. Hardware: M1 Pro 16GB.

### 4.2 Profile Quality

| Profile | Subdomains | Templates | Entities | Cover Detection | Acceptance |
|---------|:-:|:-:|:-:|:-:|:-:|
| **Hand-crafted** | 7 | 20 | 96 | **20%** | **ACCEPTED** |
| Local 7B | 31 | 20 | 191 | 50% | REJECTED |
| Local 14B | 7 | 12 | 45 | 66% | REJECTED |
| **Local 14B+web** | 5 | 18 | 56 | 32% | **ACCEPTED** |
| Cloud Claude | 9 | 20 | 102 | 22% | NEEDS_WORK |
| Bootstrap (cloud+local) | 9 | 20 | 102 | 22% | NEEDS_WORK |

### 4.3 Tier 1 Pipeline Quality (Blinded A/B)

| Profile | Pipeline Score | Quality Retained |
|---------|:-:|:-:|
| **Cloud Claude** | **3.8/5** | **87%** |
| Hand-crafted | 3.25/5 | 81% |
| Bootstrap | 3.2/5 | 78% |

### 4.4 Vocabulary Recall vs Hand-Crafted

| Metric | Local 14B | Cloud Claude |
|--------|:-:|:-:|
| Protocols | 46% | **100%** |
| Mechanisms | 11% | **91%** |
| Metrics | 10% | **100%** |
| Overall | 22% | **97%** |

### 4.5 Key Findings

1. **Local 14B+web is the best private-data-safe option** — the only auto-generated profile achieving ACCEPTED. Web search provides vocabulary diversity the 14B model cannot generate alone.

2. **Cloud Claude produces the best Tier 1 quality** (3.8/5, 87% retained) — outperforms hand-crafted (3.25/5, 81%). Richer ontology produces better genericization.

3. **The quality gap is in the generating model, not the framework** — same architecture, same validation, dramatically different results depending on model capability.

4. **Iteration helps local models** — feedback loop reduced raw subdomains from 44 to 23 between runs, improved template count from 12 to 22.

5. **14B is the minimum for useful generation** — 7B produces 0 valid regex patterns and 31 noisy subdomains.

## 5. Security Analysis

### 5.1 Dataset Privacy

The framework supports 6 deployment configurations, all private-data-safe:

1. **Cloud synthetic → local train**: cloud generates synthetic queries for the domain, local trains on them
2. **Cloud ontology → local patterns**: cloud builds domain knowledge from public sources, local generates sensitive patterns
3. **Cloud profile review**: genericize entity names before sending profile for cloud review (profile sanitizer strips and restores)
4. **Multi-model local**: different models for generation, validation, and adversarial testing
5. **Community profiles**: download curated profiles, validate locally
6. **Bootstrap**: cloud base profile + local adaptation

### 5.2 Web Search Side Channel

Web enrichment searches for domain terminology. Outbound search queries are sanitized to prevent private data leaking via the search side channel:
- Amounts, addresses, percentages, decimals stripped from search queries
- Queries too short after sanitization are rejected
- Impact on search quality: negligible for the 90% case (generic terminology searches unaffected)

### 5.3 Profile as Attack Surface

A generated profile contains domain knowledge, not user data. Before cloud review, the profile sanitizer:
- Replaces entity names with ENTITY_001..N placeholders
- Redacts domain_name to "redacted"
- Strips domain_heuristics
- Uses structured traversal for de-genericization (no JSON crash on escaped tokens)

## 6. Limitations

### 6.1 What we have NOT shown

- **NOT tested on non-DeFi domains.** The framework is architecturally domain-agnostic but experimentally validated only on DeFi.
- **NOT validated with real private datasets.** All experiments use synthetic/public data. The dataset enrichment module can generate queries, but they may not represent real user patterns.
- **NOT a production deployment.** No browser extension, no Tor transport, no real-time query interception.
- **D2 measures genericized-direct utility, NOT the covered pipeline.** The 3.8/5 score is for sending genericized sub-queries directly, not mixed with covers.
- **C2 uses static curated queries, NOT actual decomposition output.** The 40% detection rate may differ on real pipeline outputs.

### 6.2 Sanitizer Gaps

The regex sanitizer is format-bounded:
- Semantic leaks ("about double what I started with") not caught
- Novel token formats not in the known list may bypass broad patterns
- Adversarial fuzzing shows 0.4% leak rate on obfuscated inputs (CI threshold: 5%)

### 6.3 Self-Certification Residual Risk

Despite 5 guardrails, the generating LLM still has influence:
- Sensitivity labeling determines what patterns are generated
- Vocabulary extraction quality affects cover diversity
- Template design affects pipeline usability
- 2 of 13 validation checks require an LLM judge (quality, not security)

Mitigation: 11/13 checks are fully programmatic. Security validation is LLM-independent.

## 7. Beyond Sanitization: Toward a Privacy Protection Compiler

### 7.1 Limitations of the Current Approach

This meta-framework generates one specific protection strategy: regex sanitization + LLM decomposition + cover queries + genericization. This is Layer 1 — query transformation. It is effective against passive observers but has inherent limits:

- **Format-bounded**: regex cannot catch semantic leaks ("about double what I started with")
- **Statistical, not cryptographic**: cover queries provide k-plausible deniability, not formal privacy guarantees
- **Local LLM required**: Tier 1 quality depends on a capable local model
- **Cloud still sees content**: even genericized sub-queries reveal the topic domain

### 7.2 A More General Architecture

The natural generalization is a **privacy protection compiler** — a system that takes a threat model and hardware constraints as input, and outputs a composed pipeline of privacy tools.

```
Threat Model + Domain Profile + Hardware Constraints
  → [Privacy Protection Compiler]
    → Composed Pipeline Configuration
      → Formal Property Guarantees + Residual Risk Assessment
```

The compiler would select from a **tool library** across three layers:

**Layer 1: Query Transformation (this work)**
- Regex sanitization, LLM decomposition, cover queries, genericization
- Strength: fast, no special hardware, works today
- Limitation: format-bounded, statistical hiding only

**Layer 2: Cryptographic Infrastructure (emerging)**
- **TEE inference**: cloud LLM runs in hardware enclave (SGX, TDX, SEV-SNP). Cloud operator cannot inspect queries. Requires attestation and trusting the TEE vendor.
- **Split inference**: run embedding layers locally, send intermediate activations to cloud. Activations are less interpretable than raw text but not provably private.
- **Secure Multi-Party Computation**: query split across N non-colluding servers. Information-theoretic security. Impractical latency for full LLM inference today, but feasible for embedding-level operations.
- **Private Information Retrieval**: retrieve relevant context from a cloud knowledge base without revealing which records were accessed. Useful for RAG architectures.

**Layer 3: AI-Native Privacy (research frontier)**
- **Semantic sanitization**: NER + paraphrase models that remove meaning, not just format. Catches "whale-sized position" and "near liquidation" that regex misses.
- **Prompt obfuscation**: rewrite queries to preserve the answer while hiding intent. "What happens to a lending position when collateral drops 20%?" is equivalent to Alice's specific question but reveals no private parameters.
- **Local distillation**: distill the cloud model's capabilities for the user's specific domain into a local model. Zero cloud exposure after distillation.
- **Adversarial embeddings**: add perturbations to token embeddings that preserve semantic content for the model but confuse reconstruction attacks by eavesdroppers.

### 7.3 Compiler-Selected Pipelines

Different threat models produce different composed pipelines:

| Threat Model | Hardware | Compiler Output | Residual Risk |
|---|---|---|---|
| Casual privacy (passive observer) | Browser only | Regex sanitizer (Layer 1) | Semantic leaks, topic visible |
| Serious privacy (passive + analytics) | Local 14B | Sanitize → decompose → cover → Tor (Layer 1) | Session composition, timing |
| Regulatory compliance (HIPAA/GDPR) | Local GPU + TEE cloud | Semantic sanitize → TEE inference → audit (Layer 1+2) | TEE side channels |
| Adversarial (nation-state) | Air-gapped 70B | Local distilled model (Layer 3) | Model quality bounded |
| Maximum (defense-in-depth) | Local 70B + TEE + MPC | Sanitize → obfuscate → split across TEE servers (Layer 1+2+3) | Implementation complexity |

### 7.4 Relationship to This Work

The current meta-framework becomes the **first backend** of the compiler:
- **Profile generation** (this work) provides the domain knowledge for any tool to use
- **Validation engine** (this work) provides the property-checking framework
- **Tool library** becomes pluggable — new tools register with their formal properties
- **Compiler** is new — selects and composes tools, verifies combined guarantees

The 13 validation properties generalize naturally: parameter hiding is checked the same way whether the tool is regex or NER or encryption. Cover quality is measured the same way whether covers are template-filled or adversarially generated.

### 7.5 Open Research Questions

1. **Composability**: do privacy guarantees compose? If Layer 1 provides ε₁-privacy and Layer 2 provides ε₂-privacy, what does the composition provide?
2. **Verification**: how do you verify a TEE is running the correct model without trusting the hardware vendor?
3. **Latency budget**: cryptographic tools add latency. How much is acceptable for interactive LLM use?
4. **Adversarial robustness**: can a cloud provider with access to the model architecture undo prompt obfuscation?
5. **Distillation fidelity**: how much domain-specific capability survives distillation to a local model?

## 8. Short-Term Future Work

1. **Validate on medical/legal/TradFi domains** — prove the generalization claim with non-DeFi data
2. **Implement covered D2 benchmark** — measure utility when sub-queries are mixed with covers
3. **Run C2 on actual decomposition output** — validate detectability end-to-end
4. **Browser extension** — port Tier 0 sanitizer to JavaScript
5. **Semantic sanitization prototype** — NER-based sanitizer as Layer 3 proof-of-concept
6. **TEE integration** — deploy Tier 1 pipeline with TEE-hosted cloud inference

## 9. Conclusion

This work makes three contributions:

**1. Domain-agnostic meta-framework.** Privacy protection pipelines can be auto-generated from datasets, validated against 13 formal properties (11 programmatic, 5 anti-malicious-LLM), and iteratively improved through feedback loops — without domain expertise or hand-crafting.

**2. Experimental validation.** Six generation strategies tested on a 216-query DeFi benchmark. Local 14B + web search achieves ACCEPTED (matching hand-crafted). Cloud Claude achieves 97% vocabulary recall and 3.8/5 Tier 1 quality (outperforming hand-crafted). The quality gap is in the generating model, not the framework.

**3. Path to a privacy protection compiler.** The current framework (query transformation) is Layer 1 of a three-layer architecture. Layers 2 (cryptographic: TEE, MPC, split inference) and 3 (AI-native: semantic sanitization, prompt obfuscation, local distillation) compose with Layer 1 through a compiler that selects tools based on threat models.

The critical insight for practitioners: **security validation doesn't need an LLM** (11/13 checks are programmatic), but **quality generation benefits enormously from model capability**. The recommended architecture — cloud generation for public data, local validation for all data, local runtime for private queries — gives the best of both worlds.

For private datasets, local 14B + web search + iteration + human profile review achieves 70-80% of hand-crafted quality with zero privacy exposure. The remaining gap closes with larger local models, community profiles, or the Layer 2/3 tools outlined in Section 7.

The Private Query Problem is universal. This framework is the first step toward making the solution universal too.

## References

[1] The Private Query Problem: Privacy-Preserving AI Query Orchestration for DeFi (Part 1)
[2] The Private Query Problem: Active Adversaries and Verifiable Inference (Part 2)
[3] Repository: https://github.com/namnc/e_AI
