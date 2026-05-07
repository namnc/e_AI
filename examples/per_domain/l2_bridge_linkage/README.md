# l2_bridge_linkage — Demo

Flags cross-chain linkage risks across a bridge sequence: same address on
both sides, amount correlation across bridges, bridge-sequence
fingerprinting, gas-funding linkage on destination chains, and NFT/token
bundling that links accounts.

## Run

```sh
python3 examples/per_domain/l2_bridge_linkage/demo.py
```

The demo loads `sample_tx.json` (three Hop bridges from the same address to
Arbitrum, Optimism, and Base with near-identical $25K amounts, gas
pre-funded on each destination from the user's own L1 address, plus a
bundled NFT on the second bridge), runs the rule-based analyzer, and
augments with LLM analysis. The LLM step degrades gracefully if Ollama is
offline.

## What the guard catches (heuristics)

| ID | Name | Severity |
|---|---|---|
| H1 | Same address bridge | critical |
| H2 | Amount correlation | high |
| H3 | Bridge sequence fingerprint | high |
| H4 | Gas funding post-bridge | critical |
| H5 | NFT/token bridge linkage | critical |

Full profile + signal definitions: `domains/l2_bridge_linkage/profile.json`

## Expected output

The sample triggers H1 + H2 + H3 + H4 + H5, producing CRITICAL overall risk.
LLM analysis (when available) recommends fresh receiver addresses,
randomized amounts, and paymaster-funded gas on the destination side.

## Limitations (CROPS #14: epistemic status)

- Sample is **synthetic** — not a captured cross-chain incident.
- Bridge-sequence fingerprinting uses simple structural matches; production
  would consider time spacing, protocol fingerprints, and concurrent CEX
  activity.

## Trust assumptions (CROPS #13)

- Bridge-protocol labels and destination-gas funding metadata are trusted as
  inputs.
- LLM is local-only (Ollama) by default; bridge-sequence data does not leave the host.
