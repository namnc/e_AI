# rpc_leakage — Demo

Flags privacy leakage to a hosted RPC provider: balance checks linking
multiple addresses, repeated `eth_call` to a lending position view, pre-trade
price simulations correlated with an imminent swap, stealth-address scanning
patterns, and price queries correlated with held tokens.

## Run

```sh
python3 examples/per_domain/rpc_leakage/demo.py
```

The demo loads `sample_tx.json` (a session against Infura that checks 4
distinct address balances, monitors one Aave position ~11 times in 3
minutes, and runs Uniswap/Chainlink price queries in the 5-minute window
before a swap), runs the rule-based analyzer, and augments with LLM
analysis. The LLM step degrades gracefully if Ollama is offline.

## What the guard catches (heuristics)

| ID | Name | Severity |
|---|---|---|
| H1 | Balance checks linking addresses | critical |
| H2 | Position monitoring via repeated eth_call | high |
| H3 | Pre-trade intent via swap simulation | critical |
| H4 | Stealth address scanning pattern | high |
| H5 | Token price checking correlated with holdings | medium |

Full profile + signal definitions: `domains/rpc_leakage/profile.json`

## Expected output

The sample triggers H1 + H2 + H3 (and possibly H5), producing CRITICAL
overall risk. LLM analysis (when available) recommends Helios / local node
/ batched cover queries.

## Limitations (epistemic status)

- Sample is **synthetic** — not a captured RPC trace.
- Selector lists for lending and price queries are small and Ethereum-mainnet
  oriented; production would maintain a curated registry.
- "Same user" assumption: queries are grouped by the user_originating_address
  field; in reality the RPC provider correlates by IP / API key / cookie.

## Trust assumptions

- The RPC trace itself is trusted as input (typically captured wallet-side).
- LLM is local-only (Ollama) by default; query trace does not leave the host.
