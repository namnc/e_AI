# Profile Schema Reference

Each domain ships a `profile.json` conforming to the schema below. The
canonical starting point is `domains/_template/profile.json`. The
`meta.tx_validation_engine` enforces structural integrity via 11 checks (5
functional, 3 security, 3 quality).

## Top-level keys

| Key | Required | Type | Notes |
|---|---|---|---|
| `meta` | yes | object | domain_name, version, generated_by, validation_status, source_paper |
| `risk_domain` | yes | object | name, crops_property, description, protocols, adversary_model |
| `heuristics` | yes | object | map of `<id>_<slug>` → heuristic; min 3 |
| `skills` | yes | object | map of skill name → skill definition (must cover all referenced) |
| `combined_benchmark` | yes | object | description, methodology, target, metrics |
| `templates` | yes | object | risk_assessment, summary, skill_suggestion (all required) |

## `meta` object

```json
{
  "domain_name": "your_domain",
  "version": "0.1.0",
  "generated_by": "hand-crafted | bootstrap | llm-generated | refined",
  "validation_status": "draft | reviewed | accepted",
  "source_paper": "<paper title or threat model reference>"
}
```

## `risk_domain` object

```json
{
  "name": "Human-readable domain name",
  "crops_property": "C | R | O | P | S",
  "description": "1-3 sentences on what this domain protects",
  "protocols": ["Uniswap", "Aave", ...],
  "adversary_model": {
    "capabilities": ["..."],
    "limitations": ["no private key access", "..."]
  }
}
```

`crops_property`: maps to one CROPS principle:
- **C**: censorship resistance
- **R**: robustness
- **O**: openness
- **P**: privacy
- **S**: security (UX-as-security included)

## Heuristic object

```json
"H1_short_slug": {
  "id": "H1",
  "name": "Human-readable name",
  "severity": "low | medium | high | critical",
  "description": "What this catches (1-3 sentences)",
  "detection": {
    "type": "identity | statistical | structural | compound",
    "signals": [
      {
        "name": "signal_slug",
        "description": "...",
        "data_needed": ["field1", "field2"],
        "confidence": 0.85
      }
    ],
    "threshold": "human-readable threshold description"
  },
  "recommendations": [
    {
      "action": "action_slug",
      "description": "what user should do",
      "effectiveness": 0.85,
      "user_cost": "low | medium | high",
      "skill_required": "skill_slug | null"
    }
  ],
  "fundamental_limitation": "what this guard fundamentally cannot catch",
  "benchmark_scenario": {
    "setup": "how to construct a test case",
    "metric": "what to measure",
    "baseline": "expected reference behavior"
  }
}
```

Validation rules:
- ≥1 signal per heuristic; min/max ratio of signals across heuristics enforced
  by `Q3_profile_balance`
- `confidence` ∈ [0,1]; spread across heuristics enforced by `F4_confidence_calibration`
- Critical/high heuristics MUST have `fundamental_limitation` (`S3`)
- Critical heuristics MUST have at least one high-confidence signal (`S2`)
- ≥2 recommendations per heuristic enforced by `F2_recommendation_coverage`
- Every benchmark must have setup + metric + baseline (`F5`)

## Skill object

```json
"skill_slug": {
  "id": "S1",
  "name": "Human-readable skill name",
  "description": "What the skill does",
  "parameters": {
    "param1": "type — explanation",
    "param2": "..."
  }
}
```

Validation: `F3_skill_completeness` checks all skills referenced in
recommendations are defined; MARGINAL if skill objects lack `parameters`.

## Templates

Three required string templates with placeholder variables:

```json
"templates": {
  "risk_assessment": "Transaction triggers {heuristic_id}: {signal_description}. Confidence: {confidence}.",
  "summary": "Analyzed {n_txs} transactions. {n_risky} flagged.",
  "skill_suggestion": "To mitigate {heuristic_name}: {skill_action}."
}
```

## Validation checks (11 total)

Functional (5):
- F1 heuristic_coverage
- F2 recommendation_coverage
- F3 skill_completeness
- F4 confidence_calibration
- F5 benchmark_coverage

Security (3):
- S1 adversary_model
- S2 severity_consistency
- S3 fundamental_limitations

Quality (3):
- Q1 vocabulary_depth
- Q2 template_coverage
- Q3 profile_balance

Run: `python -m meta.tx_validation_engine domains/<your_domain>/profile.json`

Overall verdict: PASS (all PASS) | MARGINAL (≥1 MARGINAL, 0 FAIL) | FAIL (≥1 FAIL).
