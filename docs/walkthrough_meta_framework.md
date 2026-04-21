# Walkthrough: Meta-Framework for Domain-Agnostic Privacy Protection

This document walks through how the meta-framework automatically generates a privacy protection pipeline for any domain, using the DeFi pipeline as the reference implementation.

## The Goal

The hand-crafted DeFi pipeline (see [walkthrough_handcrafted.md](walkthrough_handcrafted.md)) took weeks of manual work: writing regex patterns, curating domain ontologies, designing templates, running benchmarks. The meta-framework automates this: given a JSONL dataset of domain queries, a local LLM generates all the tools and a validation engine verifies they meet formal properties.

## End-to-End Pipeline

```
Input Dataset (JSONL)
  │
  ▼
[Input Validation] ─── 6 checks: count, schema, labels, quality, duplicates, coherence
  │                     If FAIL → auto-enrich (web search + LLM synthesis)
  ▼
[Data Enrichment] ──── Web search for real queries from forums/docs
  │  (if needed)        LLM synthesis for underrepresented categories
  │                     Cap: max 50% synthetic. Dedup. Provenance tracked.
  │                     Loop: enrich → re-validate → until PASS or max rounds
  ▼
[Feedback Loading] ─── Cross-domain + same-domain diagnostics from prior runs
  │                     Adjusts prompts based on previous failures
  ▼
[Phase 1: Analysis] ── Local LLM analyzes dataset
  │  Step 1: Sensitivity extraction (identify private spans per query)
  │  Step 2: Subdomain clustering (group queries into 4-8 categories)
  │  Step 3: Vocabulary extraction (fill ontology per subdomain)
  │  Step 4: Template extraction (identify question structures)
  │  Step 5: Heuristic discovery (domain-specific sensitivity patterns for check 10)
  │
  ▼
[Phase 2a: Patterns] ── Local LLM generates regex patterns from sensitive spans
  │
  ▼
[Phase 2b: Web Search] ── Optional: enrich vocabulary + threat model via DuckDuckGo
  │                        Sanitized snippets, capped additions, provenance tracked
  │
  ▼
[Phase 2c: Privacy Refinement] ── Validate → repair false negatives → re-validate
  │                                Circuit breaker: stops if no improvement
  │
  ▼
[Phase 2d: Usability Refinement] ── Validate → add false-positive exceptions → re-validate
  │                                  Circuit breaker: escalates if stalled
  │
  ▼
[Write Profile] ── domains/<name>/profile.json
  │
  ▼
[Phase 3: Validation] ── 13 property checks
  │  Functional:  sanitizer completeness, false positive rate, profile completeness,
  │               template coverage, vocabulary depth, cover quality
  │  Security:    entity completeness, held-out sanitizer, ontology balance,
  │               sensitivity labels, vocabulary diversity
  │  Quality:     Tier 1 pipeline (decompose→genericize→synthesize),
  │               Tier 0 usability (sanitized query coherence)
  │
  ▼
[Acceptance Assessment] ── ACCEPTED / NEEDS_WORK / REJECTED
  │
  ▼
[Save Diagnostics] ── Feeds back to future runs (same-domain + cross-domain)
```

## Worked Example: Generating a Medical Privacy Profile

Suppose we have `data/medical_queries.jsonl`:
```json
{"text": "My oncologist said my PSA is 8.5 and recommended a biopsy next Tuesday", "label": "sensitive"}
{"text": "What are the side effects of metformin?", "label": "non_sensitive"}
{"text": "I was diagnosed with stage 3 breast cancer at age 42", "label": "sensitive"}
```

### Input Validation

```
$ python generate_profile.py --dataset data/medical_queries.jsonl --domain medical ...

Input validation: PASS
  [+] query_count: PASS (200 queries)
  [+] schema: PASS
  [+] label_distribution: PASS
  [+] language_quality: PASS
  [+] duplicates: PASS
  [+] domain_coherence: PASS (15% vocabulary coherence)
```

### Phase 1: Analysis

**Step 1: Sensitivity extraction** — The local LLM identifies private spans:
```json
{"text": "My oncologist said my PSA is 8.5...", "spans": [
  {"span": "PSA is 8.5", "category": "amount", "reason": "reveals medical test result"},
  {"span": "next Tuesday", "category": "timing", "reason": "reveals appointment schedule"},
  {"span": "oncologist", "category": "entity_name", "reason": "reveals specialist type"}
]}
```

**Step 2: Subdomain clustering** — Queries grouped into categories:
```
oncology: 45, cardiology: 30, endocrinology: 25, general: 50, ...
→ Pass 2 enforcement → 6 subdomains (max 8)
```

**Step 3: Vocabulary extraction** — Per-subdomain ontology:
```json
{"oncology": {
  "protocols": ["Memorial Sloan Kettering", "Mayo Clinic", "MD Anderson"],
  "mechanisms": ["tumor staging", "metastasis", "remission", "biopsy"],
  "operations": ["scheduling chemotherapy", "requesting second opinion"],
  "metrics": ["PSA level", "tumor size", "survival rate"],
  "generic_refs": ["cancer treatment centers", "oncology departments"],
  ...
}}
```

**Step 4: Template extraction**:
```
"How does {MECHANISM} affect {METRIC} in {GENERIC_REF}?"
"What are the risks of {OPERATION} for {ACTOR}?"
"How do {GENERIC_REF} handle {MECHANISM} during {TRIGGER}?"
```

### Phase 2: Pattern Generation

From the sensitive spans, the LLM generates regex patterns:
```json
{
  "amount_patterns_icase": [
    "\\bPSA\\s*(?:is|of|at|=|:)?\\s*\\d+(?:\\.\\d+)?\\b",
    "\\bstage\\s*\\d+\\b",
    "\\bage\\s*\\d+\\b"
  ],
  "entity_names": ["Memorial Sloan Kettering", "Mayo Clinic", "MD Anderson", ...],
  "emotional_words": ["terrified", "devastated", "hopeful", ...],
  "timing_patterns": ["\\bnext\\s+(?:Tuesday|appointment|visit)\\b", ...]
}
```

### Phase 2c-d: Refinement

**Privacy refinement**: If "PSA is 8.5" survives sanitization, the refiner generates a repair pattern:
```
Round 1: 195/200 spans stripped (MARGINAL), 5 false negatives
  Repairing: "PSA is 8.5" → generates \bPSA\s*(?:is|of|at)\s*\d+(?:\.\d+)?\b
  Applied 2 repairs
Round 2: 200/200 (PASS) — refinement complete
```

**Usability refinement**: If sanitization destroys queries (score 1/5), adds false-positive exceptions:
```
Destroyed: "What is stage 3 breast cancer?" → "What is breast cancer?"
  LLM suggests preserving "stage" as domain terminology (not a private param here)
  Added 1 false-positive exception: "stage"
```

### Phase 3: Validation (13 checks)

```
Checking sanitizer completeness...      200/200 PASS
Checking false positive rate...         1.2% PASS
Checking profile completeness...        200/200 PASS
Checking template coverage...           165/200 PASS
Checking vocabulary depth...            0 deficient PASS
Checking cover quality...               28% PASS
Checking entity completeness...         35/42 MARGINAL
Checking held-out sanitizer...          28/30 MARGINAL
Checking ontology balance...            0.65 PASS
Checking sensitivity labels...          timing 80%, emotional 90%, amounts 95% PASS
Checking vocabulary diversity...        2 near-duplicates PASS
Checking Tier 1 pipeline...             3.5/5, 78% retained PASS
Checking Tier 0 usability...            2.8/5 MARGINAL

VALIDATION SUMMARY: MARGINAL (10 PASS, 3 MARGINAL, 0 FAIL)
ACCEPTANCE: NEEDS_WORK (3 MARGINAL, max 2 allowed)
  Re-run to use feedback from this run's diagnostics.
```

### Feedback Loop

Diagnostics saved. On re-run, the framework loads them and adjusts:
```
Loaded feedback from previous run: ['entity_hints', 'usability_note']
```

The sensitivity extraction prompt now includes:
```
FEEDBACK FROM PREVIOUS RUN (address these issues):
- These entities were missed last time — include them: MD Anderson, Cleveland Clinic
- Previous run had low usability. Ensure patterns are specific enough to not strip domain terminology.
```

## Security Guardrails

### The Self-Certification Problem

The generating LLM controls both what it labels as "sensitive" and the patterns to catch it. Five guardrails address this:

| Guardrail | What it catches | How |
|-----------|----------------|-----|
| **Entity completeness** | LLM omits protocol names from entity list | Compares capitalized phrases in queries vs entity_names |
| **Held-out sanitizer** | LLM writes easy test + easy pattern | Tests against COMPLEX_QUERIES (independent dataset) |
| **Ontology balance** | LLM makes one subdomain richer (fingerprinting) | Checks min/max vocabulary ratio |
| **Sensitivity labels** | LLM under-labels timing/emotional/amounts | LLM-independent heuristic regex |
| **Vocabulary diversity** | LLM fills slots with near-duplicates | Edit-distance dedup |

### Web Search Guardrails

When `--web-search` is enabled:

| Guardrail | What it catches | How |
|-----------|----------------|-----|
| Snippet sanitization | Prompt injection via search results | Strip control chars, injection markers |
| Addition caps | Poisoned results flooding vocabulary | Max 10 additions per subdomain per slot |
| Provenance tracking | Can't distinguish web-sourced from LLM-analyzed | `_web_added` field in profile |
| DDGS timeout | Search service hanging | 15-second timeout, graceful degradation |

### Refinement Circuit Breakers

Both refinement loops detect stalls:
```
Round 1: 10 false negatives
Round 2: 10 false negatives (no improvement)
  STALLED: Refinement stopped. Recommend larger model or manual review.
```

## Acceptance Thresholds

| Status | Criteria | Action |
|--------|----------|--------|
| **ACCEPTED** | 0 FAIL, <=2 MARGINAL | Profile ready for use |
| **NEEDS_WORK** | 0 FAIL, >2 MARGINAL | Re-run with feedback (auto-improves) |
| **REJECTED** | Any FAIL | Fix dataset, use larger model, or manual review |

## Comparison: Hand-Crafted vs Meta-Framework

| Aspect | Hand-Crafted | Meta-Framework |
|--------|-------------|----------------|
| Time to create | Weeks | ~1 hour (14B model) |
| Domain expertise needed | Deep | Dataset only |
| Sanitizer patterns | 40+ hand-tuned regex | LLM-generated + refined |
| Domain ontology | 7 subdomains, 280+ terms | Auto-clustered, auto-extracted |
| Templates | 20 manually written | 12-20 auto-extracted |
| Validation | 6 benchmarks (A-F) | 13 automated property checks |
| Security guardrails | Manual review | 5 automated anti-malicious-LLM checks |
| Feedback loop | None (one-shot) | Cross-domain diagnostics |
| Reproducibility | Deterministic | Non-deterministic generation, deterministic validation |

## Files

| File | Role |
|------|------|
| `generate_profile.py` | CLI entry point |
| `meta/input_validator.py` | Pre-flight dataset validation (6 checks) |
| `meta/analyzer.py` | Phase 1: LLM dataset analysis |
| `meta/pattern_generator.py` | Phase 2a: regex + entity generation |
| `meta/web_enrichment.py` | Phase 2b: web search integration |
| `meta/refiner.py` | Phase 2c-d: privacy + usability refinement |
| `meta/validation_engine.py` | Phase 3: 13 property checks |
| `meta/feedback.py` | Diagnostics, acceptance, cross-domain feedback |
| `meta/prompts.py` | All LLM prompts centralized |
| `meta/data_enrichment.py` | Dataset enrichment (web search + LLM synthesis) |
| `meta/util.py` | Shared utilities (extract_json) |
| `core/profile_loader.py` | Load + validate profiles |
| `core/domain_profile.py` | DomainProfile schema |
