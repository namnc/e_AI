# Domain: RPC Query Pattern Leakage

**Type:** Transaction analysis
**CROPS property:** P (Privacy)
**Status:** Draft
**Schema:** `core/tx_profile.py`
**Source:** Weintraub et al. 2022 (blockchain RPC privacy); EF Privacy & Scaling Explorations research

## What this domain does

Detects privacy leakage through RPC query patterns that reveal user intent, address ownership, portfolio composition, and trading behavior to RPC providers and network observers. Covers the metadata layer that most privacy tools ignore.

## Heuristics

| # | Heuristic | Severity | Countermeasure |
|---|---|---|---|
| H1 | Balance checks linking addresses | critical | Cover queries + local light client |
| H2 | Position monitoring (repeated eth_call) | high | Batched multicall + local state cache |
| H3 | Pre-trade intent (swap simulation) | critical | Local simulation via Helios |
| H4 | Stealth address scanning pattern | high | Local node or Tor-routed scanning |
| H5 | Token price checking correlated with holdings | medium | Broaden to top-50 tokens as cover |

## Skills

- **helios_local** -- Run Helios light client for local query execution
- **tor_routing** -- Route RPC queries through Tor with circuit rotation
- **query_batching** -- Aggregate queries into multicall with cover padding
- **cover_queries** -- Generate plausible cover traffic to obscure real queries

## What needs human effort

- [ ] Benchmark Helios light client query latency vs remote RPC
- [ ] Measure cover query effectiveness against statistical filtering over time
- [ ] Validate Tor circuit rotation does not cause rate limiting at RPC endpoints
- [ ] Quantify stealth address scanning leakage with real ERC-5564 data
- [ ] Assess cross-session fingerprinting resistance of cover query strategies

## Improving this domain

See `docs/improving_a_domain.md`
