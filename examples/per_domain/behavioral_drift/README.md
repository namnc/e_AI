# behavioral_drift — Demo

Flags multi-week behavioral risks: portfolio concentration drift, leverage
creep, approval accumulation, gas-spending trends, and interaction-pattern
rigidity that constitutes a behavioral fingerprint.

## Run

```sh
python3 examples/per_domain/behavioral_drift/demo.py
```

The demo loads `sample_tx.json` (a 12-week observation showing 30% -> 82%
single-protocol concentration, 1.1x -> 2.9x leverage with flat collateral,
47 unlimited approvals with 18 added / 0 revoked in 30 days, 5x gas
growth, and an 86%-rigid weekday-morning interaction pattern), runs the
rule-based analyzer, and adds LLM behavioral context. Falls back to
rule-based-only if Ollama is offline.

## What the guard catches (heuristics)

| ID | Name | Severity |
|---|---|---|
| H1 | Portfolio concentration | high |
| H2 | Leverage creep | critical |
| H3 | Approval accumulation | critical |
| H4 | Gas spending trend | medium |
| H5 | Interaction pattern rigidity | high |

Full profile + signal definitions: `domains/behavioral_drift/profile.json`

## Expected output

The sample triggers H1 (concentration drift + single-chain) + H2 (leverage
creep with flat collateral) + H3 (47 unlimited approvals, none revoked) +
H4 (gas growth + high gas-to-value) + H5 (rigid pattern + low temporal
variance), producing CRITICAL risk.

## Limitations (CROPS #14: epistemic status)

- Sample is **synthetic** — not captured user behavior.
- The analyzer cannot distinguish deliberate strategy (yield farming,
  conviction bets) from drift; treats persistent concentration / leverage
  as a signal regardless of intent.
- Aggregate health-factor and approval-vulnerability cross-reference are
  inputs the analyzer trusts; production deployment must wire these from
  on-chain RPC + a maintained vulnerability database.

## Trust assumptions (CROPS #13)

- Weekly aggregates are trusted as inputs from the wallet's local history.
- LLM is local-only (Ollama) by default; behavioral data does not leave the host.
