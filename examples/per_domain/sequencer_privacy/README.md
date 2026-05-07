# sequencer_privacy — Demo

Flags L2 sequencer-trust risks: centralized sequencer, observed censorship,
sequencer MEV extraction, shared-sequencer cross-rollup linkage, and
preconfirmation privacy leaks.

## Run

```sh
python3 examples/per_domain/sequencer_privacy/demo.py
```

The demo loads `sample_tx.json` (a privacy-pool deposit on a centralized
Arbitrum-class sequencer where the user is sanctioned and the tx isn't
included after 5 minutes, plus heavy sequencer MEV extraction, shared-
sequencer participation across 3 rollups, and 30-second preconfirmations
that leak content), runs the rule-based analyzer, and adds LLM behavioral
context. Falls back to rule-based-only if Ollama is offline.

## What the guard catches (heuristics)

| ID | Name | Severity |
|---|---|---|
| H1 | Centralized sequencer | high |
| H2 | Sequencer censorship | critical |
| H3 | Sequencer MEV extraction | high |
| H4 | Shared sequencer linkage | high |
| H5 | Pre-confirmation privacy leak | high |

Full profile + signal definitions: `domains/sequencer_privacy/profile.json`

## Expected output

The sample triggers H1 (centralized sequencer) + H2 (censorship suspected
+ persistent exclusion) + H3 (78% L2 MEV share) + H4 (shared sequencer
across 3 rollups) + H5 (30-second public preconfirmation), producing
CRITICAL risk + `should_block: true`.

## Limitations (CROPS #14: epistemic status)

- Sample is **synthetic** — not a captured incident.
- Sequencer trust posture is read from `SEQUENCER_REGISTRY` in
  `domains/sequencer_privacy/analyzer.py`. Production must reconcile this
  against L2Beat's live sequencer-status data.
- Censorship signal relies on `expected_inclusion_by` as a heuristic
  threshold, not a protocol-defined SLA.
- This guard is largely informational today: actionable mitigation arrives
  with encrypted mempools and sequencer decentralization (CROPS #15).

## Trust assumptions (CROPS #13)

- Sequencer-model classification and MEV statistics are trusted as inputs.
- Censorship "expected_inclusion_by" is a heuristic threshold, not protocol-defined.
- LLM is local-only (Ollama) by default; sequencer-context data does not leave the host.
