# builder_censorship — Demo

Audits a transaction's submission path for censorship resistance: relay
choice, OFAC interaction, L2 forced-inclusion availability, builder
monoculture, and the compound no-circumvention case.

## Run

```sh
python examples/per_domain/builder_censorship/demo.py
```

The demo loads `sample_tx.json` (a worst-case configuration: censoring relays
only, no private mempool, sanctioned destination, narrow builder set), runs
the rule-based analyzer, and adds LLM behavioral context. Falls back to
rule-based-only if Ollama is offline.

## What the guard catches (heuristics)

| ID | Name | Severity |
|---|---|---|
| H1 | Censoring relay route | high |
| H2 | Sanctioned address interaction | critical |
| H3 | L2 no forced-inclusion | high |
| H4 | Builder monoculture | medium |
| H5 | No circumvention path (compound) | high |

Full profile + signal definitions: `domains/builder_censorship/profile.json`

## Expected output

The sample tx triggers H1 (all relays censoring) + H2 (sanctioned destination)
+ H4 (twice: low builder count + dominant builder share) + H5 (compound — no
available inclusion path), producing CRITICAL risk + `should_block: true`.

## Limitations (CROPS #14: epistemic status)

- Sample is **synthetic** — not a captured event.
- Censoring-relay registry and OFAC SDN list are hard-coded in
  `domains/builder_censorship/analyzer.py` for the demo. Production would
  pull from maintained sources (relayscan / mevboost / OFAC live list).
- Builder share figures are inputs, not live measurements; production would
  poll mevboost.org or equivalent.

## Trust assumptions (CROPS #13)

- Local-only execution; LLM via Ollama (qwen2.5:7b) by default.
- No transaction or routing data leaves the host in this demo.
- The OFAC SDN list itself is a US-jurisdictional artifact; treating it as a
  detection signal does NOT imply endorsement of policy. The guard's role is
  to surface routing-risk so the user can decide.
