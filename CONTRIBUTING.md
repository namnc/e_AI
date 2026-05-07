# Contributing to e_AI

e_AI is an Ethereum Access Layer privacy/safety substrate organized around
**domains** — each domain is a self-contained guard with a profile, an
optional rule-based analyzer, an LLM behavioral layer, tests, and a demo.

## Quick start

```sh
git clone https://github.com/namnc/e_AI.git
cd e_AI
git checkout v2
pip install -r requirements.txt

# Run all v2 domain tests
for d in domains/*/test_profile.py; do python3 $d; done

# Run a per-domain demo
python3 examples/per_domain/approval_phishing/demo.py
```

The full test + validation pass runs in CI on every push to `v2`. See
`.github/workflows/tests.yml` job `v2-domain-tests`.

## Adding a new domain

The full step-by-step is in [`docs/adding_a_domain.md`](docs/adding_a_domain.md).
Summary:

1. Copy `domains/_template/` → `domains/<your_name>/`
2. Edit `profile.json` (heuristics, signals, recommendations, skills,
   adversary model, benchmark scenarios)
3. `python -m meta.tx_validation_engine domains/<your_name>/profile.json`
   must return Overall: PASS
4. Add `data/labeled_incidents.jsonl` (≥5 synthetic or real labeled examples)
5. Write `test_profile.py` (mirror `domains/builder_censorship/test_profile.py`)
6. (If detection is algorithmic) write `analyzer.py` with `analyze_*` function
7. Write `examples/per_domain/<your_name>/{demo.py, sample_tx.json, README.md}`
   (mirror `examples/per_domain/approval_phishing/`)
8. Update `domains/<your_name>/README.md` with heuristics table, detection
   mechanism, honest limitations, and explicit trust assumptions
9. (Optional) wire into integration demos: RPC proxy, wallet, agent, DApp,
   L2 monitor

## Engineering conventions

- **Profile schema**: `domains/_template/profile.json` is the canonical
  starting point. Required top-level keys: `meta`, `risk_domain`, `heuristics`,
  `skills`, `combined_benchmark`, `templates`. The 11-check
  `meta.tx_validation_engine` enforces structural integrity.
- **Tests**: every domain ships its own `test_profile.py` covering profile
  load, validation engine pass, per-heuristic structure, recommendation
  shape, skill completeness, and labeled-data presence.
- **LLM**: `core.llm_analyzer.LLMAnalyzer` — local-first via Ollama
  (`qwen2.5:7b` default). `connect()` is graceful by default: returns False
  on Ollama unreachable; `analyze()` falls back to rule-based-only result.
- **Heuristics**: each heuristic in a profile is a CLAIM (evidence-grounded
  pattern), not a THEOREM. Profiles SHOULD declare data caveats and
  fundamental limitations honestly.
- **Trust transparency**: if your guard depends on a trusted external
  service (oracle, scam DB, registry, threshold service), make this
  explicit in the README so integrators don't inherit unclear standards.
- **No private data leaves the host by default**: the LLM step is local-only
  unless explicitly opted into a cloud backend via `LLMAnalyzer(backend="anthropic")`.

## Reviewing a contribution

- Profile validates (`meta.tx_validation_engine` Overall: PASS)
- Tests pass (`python domains/<name>/test_profile.py`)
- Demo runs (`python examples/per_domain/<name>/demo.py`)
- README documents detection mechanism, limitations, trust assumptions
- Heuristics are domain-grounded (sourced from a threat model, paper, or
  observed-incident class)
- No silent dependency on unverified external state

## Out of scope (for now)

- Deployment-ready confidence calibration with large real-incident datasets
- Frontend phishing / URL verification (separate from transaction analysis;
  may belong in a different module)
- Sybil multi-wallet linkability (designed but not implemented; see
  `domains/_template/` and the v2 problem brief for the framing)

## License + attribution

This codebase is AI-assisted (see commit history for specific provenance) and
human-reviewed before being merged to `v2`. Per the project's
epistemic-transparency rule, contributors should mark the type of any new
claim explicitly: THEOREM (proved), CLAIM (evidence-backed), or FRAMING
(analytical lens).
