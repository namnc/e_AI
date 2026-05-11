# builder_censorship

Pre-submission censorship-resistance audit for transaction submission paths.
Flags configurations where the transaction may be silently dropped by a
censoring builder, relay, or non-circumventable centralized L2 sequencer.

## Heuristics

| ID | Name | Severity | Trigger |
|---|---|---|---|
| H1 | Censoring relay route | high | Selected relay matches censoring registry; all-censoring → BLOCK |
| H2 | Sanctioned address interaction | critical | Tx interacts with OFAC SDN address |
| H3 | L2 no forced-inclusion | high | Destination L2 has no production forced-inclusion, or wallet lacks L1-inbox path |
| H4 | Builder monoculture | medium | <10 unique builders in recent 100 blocks, or top builder >40% share |
| H5 | No circumvention path (compound) | high | All relays censoring + no private mempool + (sanctioned tx OR no L2 remedy) |

## Skills

- `relay_diversity_audit` — read wallet relay config, cross-reference against censoring registry
- `l1_inbox_submission` — submit via L1 forced-inclusion inbox (escape hatch)
- `builder_diversity_dashboard` — monitor HHI of builder share over recent window
- `private_mempool_routing` — bypass relay layer entirely

## Why this guard

Censorship resistance is a foundational Ethereum property: protocol provides
bounded primitives, the access layer composes. When all available submission
paths gate on off-chain operator policy, CR collapses to operator-trust. This guard surfaces the
routing risk pre-submission so the user can switch relays, add a private
mempool, or fall back to a forced-inclusion escape hatch.

## Detection mechanism

`analyzer.py` provides rule-based detection over a `BuilderCensorshipTx`
dataclass that captures: selected relays, private mempool config, destination
chain, sanctioned-address touches, recent-builder diversity stats, and
wallet capabilities.

`core.llm_analyzer` provides behavioral augmentation; falls back gracefully
if Ollama is offline.

## Data and limitations

- `data/labeled_incidents.jsonl`: 11 synthetic positive/clean incidents
  illustrating each heuristic.
- The censoring-relay registry and OFAC SDN list are hard-coded in the
  analyzer for the demo; production would pull from maintained sources.
- Builder share figures (recent_block_builder_count, dominant_builder_share)
  are inputs, not measurements; production would integrate
  mevboost.org / relayscan / similar live feeds.
- All facts and tool comparisons are UNVERIFIED until checked against
  primary sources per house rules.

## Prior art

**MEV Watch**, **Censorship.pics**, **Relayscan** are dominant on the *observation* side — they expose builder/relay censorship state. Justin Drake's CR-MEV writeups cover the analysis. No runtime, pre-submission guard wired into the wallet.

**Where this guard differs**: "MEV Watch in your wallet" — pre-submission framing is the contribution. Honest: this is closer to operationalization than novelty. Inclusion is motivated by the access-layer composition view + extension-framework validation, not by detection-novelty.

Full comparison: `docs/prior_art/builder_censorship.md`.
