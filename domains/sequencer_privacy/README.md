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

## Analyzer

Rule-based analyzer at `analyzer.py` evaluates a `SequencerSubmission` against
H1-H5 algorithmically. Carries a `SEQUENCER_REGISTRY` mapping per-L2 to
operator + model + encrypted-mempool flag + force-inclusion path + shared-sequencer
status. The guard is largely informational today (mostly surfaces trust posture
rather than blocking) — true mitigation arrives with encrypted mempools and
sequencer decentralization. Demo at `examples/per_domain/sequencer_privacy/demo.py`.
Production deployment must reconcile `SEQUENCER_REGISTRY` against L2Beat data.

## What needs human effort

- [ ] Validate sequencer centralization data against L2Beat for top 20 L2s
- [ ] Build censorship detection dataset from known censorship incidents
- [ ] Measure actual pre-confirmation exposure windows across L2s
- [ ] Assess shared sequencer correlation in Espresso/Astria testnet deployments

## Improving this domain

See `docs/improving_a_domain.md`

## Prior art

Largely informational. Rollup-team docs disclose the trust-assumption; no runtime guard exists. **LUCID** and adjacent encrypted-mempool work at the protocol level (CROPS #15) is the future actionability.

**Where this guard differs**: Mostly informational until encrypted mempools land at L2. Today's actionability is limited; this guard is a placeholder for the architecture that will matter post-LUCID.

Full comparison: `docs/prior_art/sequencer_privacy.md`.
