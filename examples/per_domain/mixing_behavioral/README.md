# mixing_behavioral — Demo

Flags pre-withdrawal post-mixer linkability patterns: timing correlation
between deposit and withdrawal, amount fingerprinting, multi-denomination
linkage when a target amount is split across pools, cross-protocol linkage
when a withdrawal is immediately reused in DeFi, and mixer-specific
metadata leaks (relay choice, withdrawal-address reuse, gas-price
fingerprinting). Profile heuristics map to Tutela's seven post-deposit
heuristics applied as a *pre-withdrawal* runtime check.

## Run

```sh
python3 examples/per_domain/mixing_behavioral/demo.py
```

The demo loads `sample_tx.json` (a worst-case mixer withdrawal: 30-min
dwell into a thin pool, uniquely-identifying deposit amount, multi-pool
deposit-sum matching withdrawal-sum, planned defi swap within 1 block,
known-cluster behavioral match, rare relayer, reused withdrawal address,
20σ gas-price outlier, consistent prior-dwell pattern), runs the
rule-based analyzer (`domains/mixing_behavioral/analyzer.py`), and adds
LLM behavioral context. The LLM step degrades gracefully if Ollama is
offline.

## What the guard catches (heuristics)

| ID | Name | Severity |
|---|---|---|
| H1 | Timing correlation | critical |
| H2 | Amount fingerprinting | high |
| H3 | Multi-denomination linkage | high |
| H4 | Cross-protocol linkage | critical |
| H5 | Mixer-specific metadata leaks | high |

Full profile + signal definitions: `domains/mixing_behavioral/profile.json`

## Expected output

The sample triggers ~12 alerts across all 5 heuristics, OVERALL CRITICAL,
`should_block: true` (driven by H4 known-cluster-match). The LLM layer
adds compound-risk context.

## Limitations

- The rule-based analyzer takes pre-computed inputs that production must
  wire from chain data: pool deposit-count windows, address-cluster
  behavioral matching, gas-price block stats, planned-post-withdrawal-
  action prediction. The analyzer trusts the caller to source these.
- Sample is synthetic — not a captured mixer transaction. False-positive
  and false-negative rates against real corpora are unknown.
- Cross-pool linkage detection requires an address-cluster map; without
  one, H3 falls back to soft-signal recommendations.

## Trust assumptions

- Pool deposit-count + timing data is trusted as input from a chain-data
  integration.
- Address-cluster matching is trusted as input (typically from Chainalysis-
  style clustering, or a privacy-respecting equivalent).
- LLM is local-only (Ollama) by default; mixer pattern data does not leave
  the host unless the user opts into a cloud backend.
