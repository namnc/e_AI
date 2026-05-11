# stealth_address_ops — Demo

Flags pre-submission deanonymization risk for stealth-address transactions:
same-entity withdrawals, gas-price fingerprinting, timing correlation
(deposit→withdrawal too fast), funding linkability (gas paid directly by the
depositor), self-sends, and unique non-round amounts.

## Run

```sh
python3 examples/per_domain/stealth_address_ops/demo.py
```

The demo loads `sample_tx.json` (a withdrawal where deposit and withdrawal
addresses share an entity cluster, the withdrawal happens 60 seconds after
deposit, gas is funded directly from the depositor, and the amount is
unique and non-round), runs the rule-based analyzer, and augments with LLM
analysis. The LLM step degrades gracefully if Ollama is offline.

## What the guard catches (heuristics)

| ID | Name | Severity |
|---|---|---|
| H1 | Same-entity withdrawal | critical |
| H2 | Gas price fingerprinting | high |
| H3 | Timing correlation | critical |
| H4 | Funding linkability | critical |
| H5 | Same sender = recipient | critical |
| H6 | Unique amounts | high |

Full profile + signal definitions: `domains/stealth_address_ops/profile.json`

## Expected output

The sample triggers H1 + H3 + H4 + H6, producing CRITICAL overall risk and
`deanonymized: True`. LLM analysis (when available) explains the compound
linkage.

## Limitations (epistemic status)

- Sample is **synthetic** — not a captured stealth-protocol withdrawal.
- The address cluster is supplied as input; production would derive it from
  on-chain heuristic clustering (common-input ownership, change-address
  patterns, etc.).
- Block median/std gas defaults are coarse — production would query a
  per-block gas oracle.

## Trust assumptions

- Cluster membership is trusted as input.
- LLM is local-only (Ollama) by default; transaction details do not leave the host.
