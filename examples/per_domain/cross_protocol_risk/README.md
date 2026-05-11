# cross_protocol_risk — Demo

Flags portfolio-level cross-protocol exposure: cascading liquidation across
correlated lending positions, correlated oracle dependencies, concentrated
protocol exposure, dangerous approval chains, and flash-loan-amplifiable
attack surfaces.

## Run

```sh
python3 examples/per_domain/cross_protocol_risk/demo.py
```

The demo loads `sample_tx.json` (a $1.5M portfolio with two ETH-collateralized
lending positions sharing one Chainlink oracle, an unlimited USDC approval
to a 6-hop aggregator chain ending in an unverified DEX, and a flash-loanable
oracle-manipulation surface on Morpho), runs the rule-based analyzer, and
augments with LLM analysis. The LLM step degrades gracefully if Ollama is
offline.

## What the guard catches (heuristics)

| ID | Name | Severity |
|---|---|---|
| H1 | Cascading liquidation | critical |
| H2 | Correlated oracle dependency | critical |
| H3 | Concentrated protocol exposure | high |
| H4 | Approval chain risk | critical |
| H5 | Flash loan attack surface | high |

Full profile + signal definitions: `domains/cross_protocol_risk/profile.json`

## Expected output

The sample triggers H1 + H2 + H4 + H5 (and likely H3), producing CRITICAL
overall risk with a non-trivial estimated maximum loss.

## Limitations (epistemic status)

- Sample is **synthetic** — not a captured portfolio.
- "Correlated oracle" check uses string equality on oracle IDs; production
  would model price-correlation across distinct oracles.
- Approval-chain depth is supplied; production would graph-walk delegate
  permissions across DEX routers and adapters.

## Trust assumptions

- Health factors and oracle IDs are trusted as inputs from the lending
  protocols' on-chain state.
- LLM is local-only (Ollama) by default; portfolio data does not leave the host.
