# l2_anonymity_set — Demo

Flags L2-specific anonymity-set risks: thin privacy pools, sequencer
visibility, forced-inclusion deanonymization, L2 timing correlation, and
rollup-batch linkage.

## Run

```sh
python3 examples/per_domain/l2_anonymity_set/demo.py
```

The demo loads `sample_tx.json` (a privacy-pool tx on Arbitrum where the
pool has only 17 deposits, the user used L1 forced inclusion, and batch
linkage is visible), runs the rule-based analyzer, and augments with LLM
analysis. The LLM step degrades gracefully if Ollama is offline.

## What the guard catches (heuristics)

| ID | Name | Severity |
|---|---|---|
| H1 | Thin privacy pool | critical |
| H2 | Sequencer visibility | critical |
| H3 | Forced inclusion deanonymization | high |
| H4 | L2-specific timing correlation | high |
| H5 | Rollup batch linkage | high |

Full profile + signal definitions: `domains/l2_anonymity_set/profile.json`

## Expected output

The sample triggers H1 + H2 + H3 (and possibly H4/H5), producing CRITICAL
overall risk. LLM analysis (when available) recommends waiting for the pool
to grow and avoiding forced inclusion.

## Limitations (epistemic status)

- Sample is **synthetic** — not a captured L2 anonymity-set incident.
- Pool size is supplied as input; production would query the L2
  privacy-pool contract directly.
- "Sequencer visibility" is binary here; in practice a decentralized
  sequencer set has a continuum of trust assumptions.

## Trust assumptions

- Centralized-sequencer model assumed unless the L2 has a published
  decentralized-sequencer roadmap.
- LLM is local-only (Ollama) by default; L2 action data does not leave the host.
