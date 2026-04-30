# Domain: L2 Anonymity Set Monitoring

**Type:** Transaction analysis
**CROPS property:** P (Privacy)
**Access method:** L2
**Status:** Draft
**Schema:** `core/tx_profile.py`
**Source:** L2 privacy limitations -- sequencer visibility, timing analysis, rollup batch correlation

## What this domain does

Monitors privacy degradation on Layer 2 rollups where faster block times, centralized sequencers, and rollup batch posting create deanonymization vectors absent on L1. Warns users when L2 anonymity sets are too thin, when sequencer visibility undermines privacy guarantees, and when rollup-specific mechanics (forced inclusion, batch boundaries) leak information.

## Heuristics

| # | Heuristic | Severity | Countermeasure |
|---|---|---|---|
| H1 | Thin privacy pool | critical | Wait for larger pool, use L1 instead, standard denominations |
| H2 | Sequencer visibility | critical | Tor for RPC, different endpoints, prefer decentralized sequencers |
| H3 | Forced inclusion deanonymization | high | Avoid forced inclusion for privacy txs, fresh L1 address |
| H4 | L2-specific timing correlation | high | Increase dwell time, time to peak activity, randomize delays |
| H5 | Rollup batch linkage | high | Span multiple batches, time to large batches, cross batch posters |

## Skills

- **pool_size_monitor** -- Real-time L2 privacy pool depositor count and amount distribution
- **sequencer_analyzer** -- Checks sequencer decentralization and encrypted mempool status
- **batch_inspector** -- Inspects L1 batch postings for batch size, frequency, and co-inclusion
- **timing_advisor** -- Recommends optimal timing based on L2 activity patterns

## What needs human effort

- [ ] Collect real anonymity set sizes from L2 privacy protocols (Railgun on Arbitrum, etc.)
- [ ] Map sequencer decentralization roadmaps for each major L2
- [ ] Measure actual batch sizes and posting frequencies across rollups
- [ ] Validate timing correlation model against real L2 deposit-withdrawal data
- [ ] Research encrypted mempool proposals (Shutter, threshold encryption) and their privacy impact

## Improving this domain

See `docs/improving_a_domain.md`
