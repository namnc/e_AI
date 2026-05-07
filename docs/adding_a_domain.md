# Adding a New Domain to e_AI

## Prerequisites

- Understand the risk you're targeting (paper, incident data, or threat model)
- Know which CROPS property it protects: **C**ensorship resistance, **R**obustness, **O**penness, **P**rivacy, **S**ecurity
- Know which access method it guards: **AI**, **Wallet**, **Application**, **L2**

## Steps

### 1. Create domain directory

```bash
cp -r domains/_template domains/your_domain_name
```

### 2. Edit profile.json

Replace all `CHANGE_ME` fields. Key decisions:

- **Heuristics**: What patterns indicate risk? Each needs detection signals with confidence scores and recommendations with effectiveness estimates.
- **Skills**: What tools can the system invoke? (paymaster, simulator, revoker, etc.)
- **Adversary model**: What can the attacker do? What can't they do?

For v1 profiles (text query analysis): use `core/domain_profile.py` schema.
For v2 profiles (transaction analysis): use `core/tx_profile.py` schema.

### 3. Validate

```bash
# For v2 (transaction analysis) profiles:
python -m meta.tx_validation_engine domains/your_domain/profile.json

# For v1 (text query) profiles:
python -m meta.validation_engine domains/your_domain/profile.json
```

Fix all FAIL checks. MARGINAL is acceptable for draft status.

### 4. Add labeled data (optional but recommended)

Add a JSONL file to `domains/your_domain/data/` with labeled incidents:

```jsonl
{"incident": "User approved unlimited USDC to unverified contract 0x1234", "label": "unlimited_approval"}
{"incident": "Stealth address spent 10 min after deposit", "label": "timing_correlation"}
```

### 5. Write domain-specific analyzer (optional)

If the generic analyzer isn't sufficient, write `domains/your_domain/analyzer.py` with domain-specific checks. Import the profile and implement heuristic checks.

### 6. Add benchmarks

Write benchmark scripts in `domains/your_domain/benchmarks/`. At minimum:
- Synthetic data generation
- Detection rate per heuristic
- False positive rate

### 7. Write tests

Create `domains/your_domain/test_profile.py` mirroring an existing domain
(see `domains/builder_censorship/test_profile.py` for the canonical layout).
Required tests:

- `test_profile_loads` — profile parses, expected heuristic count
- `test_profile_validation` — `meta.tx_validation_engine` returns Overall PASS
- `test_h<N>_structure` — per heuristic: severity, signal count, recommendation
  count
- `test_recommendations_well_formed` — each recommendation has action,
  description, effectiveness in [0,1]
- `test_skills_complete` — every skill referenced in recommendations is defined
- `test_templates` — risk_assessment, summary, skill_suggestion exist
- `test_labeled_data_exists` — `data/labeled_incidents.jsonl` has ≥5 entries

Run: `python domains/your_domain/test_profile.py`

The CI workflow (`.github/workflows/tests.yml`, job `v2-domain-tests`) will
auto-run this on every push to `v2`.

### 8. Update domain README

Fill in `domains/your_domain/README.md` with: heuristics table, what each
heuristic catches, detection mechanism (rule-based / LLM-only / both), data
caveats, trust assumptions (CROPS #13), epistemic status (CROPS #14).

### 9. Build a per-domain demo

Create `examples/per_domain/your_domain/`:

- `sample_tx.json` — a sample input that triggers multiple heuristics
- `demo.py` — loads profile + runs analyzer + invokes `core.llm_analyzer`
  (Ollama, qwen2.5:7b, graceful degradation). See
  `examples/per_domain/approval_phishing/demo.py` for the canonical pattern.
- `README.md` — what the demo shows, how to run, expected output, limitations,
  trust assumptions.

Run: `python examples/per_domain/your_domain/demo.py`

This is the surface external readers and contributors will hit first; keep it
runnable, self-explanatory, and honest about the synthetic-sample caveat.

### 10. Wire into integration points (optional)

If the guard should fire in a specific access method, register it in:

- **RPC proxy** (`proxy/rpc_proxy.py`): the proxy is currently an
  illustrative adapter with hard-coded detection logic for `rpc_leakage`,
  `cross_protocol_risk`, and `l2_anonymity_set`. The `--profiles` flag is
  parsed but is a no-op pending the canonical profile-driven runtime; if
  your guard is RPC-driven, add a branch in `analyze_request` /
  `analyze_response` directly until that runtime exists. (Maturity-gate
  item, see README.)
- **Wallet EIP-1193** (`examples/wallet_eip1193/guard.ts`): add a hook in the
  pre-submission middleware
- **AI agent** (`examples/ai_agent/guard.py`): add to the agent's pre-action
  checklist
- **DApp frontend** (`examples/dapp_frontend/`): add to the frontend guard's
  policy set

### 11. Auto-generate (alternative to hand-crafting)

If you have a labeled dataset, the meta-framework can bootstrap a draft:

```bash
python -m meta.bootstrap_domain domains/your_domain
```

The bootstrapper produces:
1. Labeled incident data (synthetic, derived from heuristics)
2. Test file
3. LLM-generated profile variant (`profile_generated.json`)
4. Failure analysis
5. Benchmark script
6. Cover generator skeleton (where applicable)

Generated profiles need manual review and calibration. Treat all output as
UNVERIFIED until you check it against your threat model.

## What "DONE" looks like

| Artifact | Required | Path |
|---|---|---|
| profile.json | yes | `domains/<name>/profile.json` |
| README.md | yes | `domains/<name>/README.md` |
| test_profile.py | yes | `domains/<name>/test_profile.py` |
| labeled_incidents.jsonl (≥5) | yes | `domains/<name>/data/labeled_incidents.jsonl` |
| analyzer.py | only if rule-based detection applies | `domains/<name>/analyzer.py` |
| cover_generator.py | only if generative countermeasures apply | `domains/<name>/cover_generator.py` |
| Per-domain demo | yes | `examples/per_domain/<name>/{demo.py,README.md,sample_tx.json}` |
| Integration hooks | optional | various |
| Validation Overall: PASS | yes | `python -m meta.tx_validation_engine ...` |
| All tests PASS | yes | `python domains/<name>/test_profile.py` |
