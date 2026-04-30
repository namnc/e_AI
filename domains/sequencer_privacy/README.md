# Domain: Sequencer Privacy Risks

**Type:** Transaction analysis
**CROPS property:** P (Privacy)
**Status:** Draft
**Schema:** `core/tx_profile.py`
**Source:** L2Beat sequencer analysis, Espresso/Astria shared sequencer research

## What this domain does

Detects privacy risks specific to L2 sequencer architectures. RPC guard that analyzes centralization, censorship patterns, MEV extraction, shared sequencer cross-rollup correlation, and pre-confirmation information leakage. Extends l2_anonymity_set H2.

## Heuristics

| # | Heuristic | Severity | Countermeasure |
|---|---|---|---|
| H1 | Centralized sequencer | High | Privacy relay, monitor decentralization |
| H2 | Sequencer censorship | Critical | Forced L1 inclusion, monitor inclusion timing |
| H3 | Sequencer MEV extraction | High | Fair ordering L2s, monitor ordering |
| H4 | Shared sequencer linkage | High | Diversify sequencers, break timing correlation |
| H5 | Pre-confirmation privacy leak | High | Delay sensitive actions, monitor preconf gap |

## Skills

- **sequencer_monitor** -- ordering pattern analysis and MEV detection
- **decentralization_checker** -- L2 sequencer architecture tracker
- **inclusion_timer** -- submission-to-inclusion timing and censorship detection

## What needs human effort

- [ ] Validate sequencer centralization data against L2Beat for top 20 L2s
- [ ] Build censorship detection dataset from known censorship incidents
- [ ] Measure actual pre-confirmation exposure windows across L2s
- [ ] Assess shared sequencer correlation in Espresso/Astria testnet deployments

## Improving this domain

See `docs/improving_a_domain.md`
