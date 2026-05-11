# Per-Domain Demos

A runnable demonstration for every v2 production guard. Each subdirectory is
self-contained: a `demo.py`, a `sample_tx.json` (a transaction the guard would
flag), and a `README.md` explaining what the guard catches.

**Run any demo:**

```sh
python examples/per_domain/<domain>/demo.py
```

For example:

```sh
python examples/per_domain/approval_phishing/demo.py
```

Each demo prints:
1. Rule-based alerts (from the domain's `analyzer.py`)
2. LLM behavioral analysis (via `core.llm_analyzer`, falls back gracefully if
   Ollama is offline)
3. Suggested countermeasures

## Guards demonstrated

Wallet method:
- `approval_phishing/` — flag unlimited approvals to unverified spenders
- `backup_security/` — flag risky guardian-set / coercion-vulnerable backups
- `behavioral_drift/` — flag concentration / leverage creep relative to baseline
- `mev_vulnerability/` — flag pre-submission sandwich / front-running risk
- `offchain_signature/` — flag malicious EIP-712 / Permit2 signatures
- `pq_readiness/` — flag operations that are quantum-vulnerable
- `stealth_address_ops/` — flag deanonymization patterns (timing, amounts, gas)
- `wrong_chain_address/` — flag chain-ID / contract-vs-EOA mismatches

Application method:
- `cross_protocol_risk/` — flag cascading liquidation / correlated exposure
- `governance_proposal/` — flag treasury drain / parameter manipulation
- `mixing_behavioral/` — flag post-mixer linkability across chains

AI method:
- `rpc_leakage/` — flag query patterns revealing strategy

L2 method:
- `builder_censorship/` — flag tx routes through censoring builders/relays
- `l2_anonymity_set/` — flag L2 tx exposure given small anonymity set
- `l2_bridge_linkage/` — flag cross-chain identity correlation via bridge usage
- `sequencer_privacy/` — flag tx visibility to a centralized sequencer

## Demo structure

Each `demo.py` follows the same shape:

```python
1. Resolve repo root and load the domain's profile.json
2. Construct a sample tx (loaded from sample_tx.json or built inline)
3. Run the rule-based analyzer (if domains/<domain>/analyzer.py exists)
4. Run the LLM behavioral analyzer (graceful degradation if Ollama is down)
5. Pretty-print the combined result
```

## What this is and isn't

Per the v2 publication's epistemic-status disclaimer:
- These demos use **synthetic** sample transactions, not real captured incidents.
- The heuristics are CLAIMs (evidence-grounded patterns), not THEOREMs.
- A production deployment would replace synthetic samples with labeled
  real-incident data and the rule-based analyzer with chain-data integrations
  (block explorer, scam DB, oracle telemetry).
