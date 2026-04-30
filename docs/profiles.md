# Profiles: What They Are and How They Work

## What is a profile?

A profile is a JSON file that teaches the system what to watch for in a specific risk domain. It encodes domain expert knowledge as structured data -- not code.

There are two profile types:

- **v1 DomainProfile** (`core/domain_profile.py`): protects text queries sent to cloud LLMs. Defines sensitive patterns, entity names, and templates for sanitization and cover generation.
- **v2 TransactionProfile** (`core/tx_profile.py`): protects Ethereum user actions. Defines heuristics (risk patterns), detection signals, countermeasure recommendations, and skills (tools the system can invoke).

This document covers v2 TransactionProfiles.

## Anatomy of a profile

```
profile.json
├── meta                    ← name, version, source paper, validation status
├── risk_domain             ← what domain, which CROPS property, adversary model
├── heuristics              ← the core: what risks to detect
│   └── H1_some_heuristic
│       ├── id, name, severity, description
│       ├── detection
│       │   ├── type          (graph_analysis | statistical | temporal | ...)
│       │   └── signals[]     (what data patterns indicate this risk)
│       │       └── {name, description, data_needed[], confidence}
│       ├── recommendations[] (what to do about it)
│       │   └── {action, description, effectiveness, user_cost, skill_required}
│       ├── fundamental_limitation  (what technology can't fix)
│       └── benchmark_scenario      (how to measure detection)
├── skills                  ← tools the system can invoke
│   └── {tool, description, parameters}
├── combined_benchmark      ← end-to-end measurement methodology
└── templates               ← output format strings
```

### Example: one heuristic

```json
{
  "id": "H3",
  "name": "Timing correlation",
  "severity": "critical",
  "description": "Spending from a stealth address shortly after receiving narrows the anonymity set.",
  "detection": {
    "type": "temporal",
    "signals": [
      {
        "name": "short_dwell",
        "description": "Time between deposit and spend < 1 hour",
        "data_needed": ["deposit_timestamp", "spend_timestamp"],
        "confidence": 0.90
      }
    ]
  },
  "recommendations": [
    {
      "action": "delay_spend",
      "description": "Wait 6-24 hours before spending",
      "effectiveness": 0.85,
      "user_cost": "high (inconvenience)",
      "skill_required": "timing_delay"
    }
  ],
  "fundamental_limitation": "With few users, even 24h delay provides small anonymity set.",
  "benchmark_scenario": {
    "setup": "Stream of N deposits over 24h",
    "metric": "Adversary's ability to match deposit-withdrawal pairs",
    "baseline": "48.5% linkable (paper result)"
  }
}
```

**Confidence** = probability that this signal correctly identifies the risk (calibrated against data).
**Effectiveness** = estimated risk reduction if recommendation is followed.
**Fundamental limitation** = what no technology can fix (forces honesty about what we're selling).

## How a profile is created

There are three paths:

### Path 1: Hand-crafted (highest quality)

A domain expert reads the research, identifies heuristics, and writes the profile manually.

1. Read the source paper / incident reports
2. Identify discrete risk patterns (heuristics)
3. For each heuristic: define detection signals, data requirements, confidence estimates
4. Define countermeasure recommendations with effectiveness estimates
5. Document fundamental limitations
6. Define skills (tools) referenced by recommendations
7. Write benchmark scenarios
8. Validate: `python -m meta.tx_validation_engine domains/<name>/profile.json`
9. Iterate until 11/11 PASS

This is what we did for `stealth_address_ops`. It produces the most accurate profiles but requires domain expertise and time.

### Path 2: Auto-generated (via meta-framework)

The meta-framework generates a draft profile from labeled incident data using an LLM.

1. Prepare a JSONL file of labeled incidents:
   ```jsonl
   {"incident": "User spent within 10 min of deposit", "label": "timing_correlation", "deanonymized": true}
   {"incident": "User waited 2 days, clean withdrawal", "label": "timing_clean", "deanonymized": false}
   ```
2. Run the meta-framework:
   ```bash
   python -m meta.analyzer --dataset data/incidents.jsonl --domain my_domain
   ```
   This calls the LLM to: extract heuristics → extract signals → generate recommendations → assemble profile.
3. Validate and refine:
   ```bash
   python -m meta.refiner --profile domains/my_domain/profile.json
   ```
   The refiner runs validation, identifies failing checks, uses the LLM to fix them, and iterates.
4. **Human review is required.** Auto-generated profiles have generic recommendations (the LLM suggests "use 2FA" for timing correlation). The heuristic identification is useful; the recommendations need domain expertise.

### Path 3: Bootstrap (fastest, combines both)

The bootstrapper auto-generates ALL quality artifacts from an existing profile:

```bash
python -m meta.bootstrap_domain domains/my_domain
```

This generates:
- Labeled incident data (synthetic, from heuristic descriptions)
- Test file (per-heuristic structural tests + combined tests)
- Auto-generated profile variant (LLM-based, for comparison)
- Failure analysis (LLM-generated: false negatives, false positives, limitations)
- Benchmark script

Use `--skip-llm` to generate data + tests only (no LLM calls).

## How a profile is tested

Each domain has `test_profile.py` with these checks:

1. **Profile loads** without error
2. **Validation passes** 11/11 (see below)
3. **Per-heuristic structure**: correct severity, signals have confidence in [0,1], signals have data_needed, recommendations have effectiveness in [0,1]
4. **Skills complete**: every skill referenced in recommendations is defined
5. **Templates exist**: risk_assessment, summary, skill_suggestion
6. **Labeled data exists** and has entries
7. **Combined analysis** works end-to-end (for domains with an analyzer)

Run: `python domains/<name>/test_profile.py`

## How a profile is validated

The validation engine (`meta/tx_validation_engine.py`) checks 11 properties:

### Functional (F1-F5)
| Check | What it verifies | PASS condition |
|---|---|---|
| F1 | Every heuristic has detection signals with data requirements | 100% coverage |
| F2 | Every heuristic has recommendations with effectiveness > 0 | 100% coverage |
| F3 | Every referenced skill is defined with parameters | 0 missing |
| F4 | Confidence scores are distributed (not all same value) | ≥4 unique values |
| F5 | Every heuristic has a benchmark scenario | 100% coverage |

### Security (S1-S3)
| Check | What it verifies | PASS condition |
|---|---|---|
| S1 | Adversary model has capabilities AND limitations | ≥3 capabilities, ≥1 limitation |
| S2 | Critical heuristics have high-confidence signals | max confidence > 0.8 for each |
| S3 | Critical/high heuristics document fundamental limitations | ≥50% documented |

### Quality (Q1-Q3)
| Check | What it verifies | PASS condition |
|---|---|---|
| Q1 | Descriptions are specific, not stubs | All > 20 characters |
| Q2 | Output templates exist | risk_assessment, summary, skill_suggestion |
| Q3 | Heuristics balanced in depth | max signals ≤ 2× min signals + 1 |

Run: `python -m meta.tx_validation_engine domains/<name>/profile.json`

Output is a traffic-light report: PASS / MARGINAL / FAIL per check.

## How a profile is improved

See `docs/improving_a_domain.md` for the full guide. Key paths:

### Calibrate confidence scores
Confidence starts as an estimate. To calibrate:
1. Collect real incidents where the heuristic should/shouldn't fire
2. Run the analyzer against real data
3. Measure true positive rate
4. Update confidence to match measured rate

### Add detection signals
More signals = better detection. Each signal is an independent indicator. Adding signals doesn't change existing ones.

### Improve recommendations
Replace generic advice with specific, actionable countermeasures. Good recommendations reference skills (automated tools).

### Add profile variants
Generate variants with different LLM models and compare. The variant comparison (`analysis/variant_comparison.md`) shows what each model found that the hand-crafted version missed.

### Run real data benchmarks
Replace synthetic benchmarks with real on-chain data. The benchmark script in `benchmarks/` fetches real data and measures actual detection rates.

## How a profile is used at runtime

### In the wallet guard (EIP-1193)
```
User signs tx → wallet guard decodes calldata → routes to matching profile
→ checks signals → returns alerts → block/warn/pass
```

### In the RPC proxy
```
Wallet queries RPC → proxy logs query → accumulates state
→ checks patterns against profile → alerts if pattern detected
```

### In the cover generator (stealth_address_ops only, currently)
```
User wants to transact → cover generator reads current pool state
→ optimizes amount/timing/gas jointly against pool → returns cover parameters
with cover score and anonymity set estimate
```

### In the compiler (full pipeline)
```
Transaction → rule-based analyzer → cover generator → LLM analysis
→ compiled result with alerts + cover recommendation + natural language explanation
```

## Current domains

| Domain | Heuristics | Signals | Tests | Variants | Real data | Cover gen |
|---|---|---|---|---|---|---|
| stealth_address_ops | 6 | 19 | 23 | 3 (hand + 7b + 14b) | 20 real Umbra txs | Yes |
| approval_phishing | 5 | 12 | 10 | 0 | No | No |
| offchain_signature | 6 | 18 | 11 | 0 | No | No |
| governance_proposal | 5 | 16 | 10 | 0 | No | No |
| l2_bridge_linkage | 5 | 15 | 10 | 0 | No | No |
| cross_protocol_risk | 5 | 16 | 10 | 0 | No | No |
| l2_anonymity_set | 5 | 15 | 10 | 0 | No | No |
| rpc_leakage | 5 | 15 | 10 | 0 | No | No |

stealth_address_ops is the reference implementation. Others need the same depth (variants, real data, cover generators) -- this is "improve this domain" work.
