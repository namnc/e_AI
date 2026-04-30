# Domain: Cross-Chain Identity Linkage via Bridge Usage

**Type:** Transaction analysis (L2 access method)
**CROPS property:** P (Privacy)
**Status:** Draft
**Schema:** `core/tx_profile.py`
**Source:** Cross-chain deanonymization research, bridge protocol analysis

## What this domain does

Detects privacy-breaking patterns in L1-to-L2 bridge usage that allow an observer to link addresses across chains. Covers same-address reuse, amount correlation, bridge sequence fingerprinting, gas funding chains, and unique token bridging.

## Heuristics

| # | Heuristic | Severity | Countermeasure |
|---|---|---|---|
| H1 | Same address bridge (trivial linkage) | critical | Use separate addresses per chain |
| H2 | Amount correlation (exact match + timing) | high | Split into round amounts across time windows |
| H3 | Bridge sequence fingerprint (multi-chain pattern) | high | Randomize bridge order and timing |
| H4 | Gas funding post-bridge (funding chain) | critical | Use faucet/paymaster, pre-fund from independent source |
| H5 | NFT/token bridge linkage (unique asset) | critical | Avoid bridging unique tokens; use fungible + round amounts |

## Skills

- **bridge_monitor** -- index bridge events across L1 and L2s for deposit/withdrawal pair tracking
- **address_separator** -- generate fresh addresses on destination chains with private mapping
- **amount_splitter** -- split bridge amounts into round-number transfers across time windows

## What needs human effort

- [ ] Collect ground-truth bridge linkage dataset across major L2 canonical bridges
- [ ] Validate amount correlation thresholds against real bridge volume data
- [ ] Benchmark bridge sequence fingerprinting against realistic user population sizes
- [ ] Integrate with bridge protocol APIs for real-time volume and fee data
- [ ] Test gas funding chain detection depth on actual L2 transaction graphs

## Improving this domain

See `docs/improving_a_domain.md`
