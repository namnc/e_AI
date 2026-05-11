# approval_phishing — Demo

Flags pre-submission risk for token-approval transactions: unlimited allowances,
unverified spenders, scam-DB matches, suspicious function selectors, and stale
approvals carrying live exposure.

## Run

```sh
python examples/per_domain/approval_phishing/demo.py
```

The demo loads `sample_tx.json` (an unlimited USDC approval to a freshly-deployed
unverified contract whose bytecode matches a known approval-drainer template),
runs the rule-based analyzer (`domains/approval_phishing/analyzer.py`), and
optionally augments with LLM behavioral analysis via `core.llm_analyzer`. The LLM
step degrades gracefully if Ollama is offline — the demo still prints the
rule-based result.

## What the guard catches (heuristics)

| ID | Name | Severity |
|---|---|---|
| H1 | Unlimited token approval | high |
| H2 | Unverified spender contract | critical |
| H3 | Known scam address (DB or bytecode match) | critical |
| H4 | Suspicious function selector | medium |
| H5 | Stale approval with live exposure | medium |

Full profile + signal definitions: `domains/approval_phishing/profile.json`

## Expected output

The sample tx triggers H1 + H2 + H3, producing CRITICAL risk + `should_block: true`.
LLM behavioral analysis (when available) adds context on the combined risk.

## Limitations (epistemic status)

- Sample is **synthetic** — not a captured real-incident transaction.
- Bytecode-template matching is faked by the `spender_bytecode_match_scam`
  flag; a production version would compute bytecode similarity against a
  curated template DB.
- Scam DB lookup (`spender_in_scam_db`) is hard-coded false in the demo;
  production would query Forta / Scam Sniffer / ChainAbuse.

## Trust assumptions

- Block-explorer verification status is trusted as input.
- Protocol registry membership is trusted as input.
- LLM is local-only (Ollama) by default; no transaction data leaves the host.
