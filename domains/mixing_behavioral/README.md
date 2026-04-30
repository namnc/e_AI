# Domain: Post-Mixer Linkability

**Type:** Transaction analysis
**CROPS property:** P (Privacy)
**Status:** Draft
**Schema:** `core/tx_profile.py` (TransactionProfile)
**Source:** arxiv 2308.01703 (ACM Web Conference 2024), Tornado Cash deposit analysis (Chainalysis), Privacy Pools (Buterin et al. 2023)

## What this domain does

Wallet guard (L2 access) that detects behavioral heuristics linking deposits to withdrawals across mixing protocols (Tornado Cash, Railgun, Privacy Pools). Generalizes stealth_address_ops H3 (timing correlation) and H6 (unique amounts) to the broader mixing context, adding multi-denomination fingerprinting, cross-protocol linkage, and mixer-specific metadata leaks.

## Heuristics

| # | Heuristic | Severity | Countermeasure |
|---|---|---|---|
| H1 | Timing correlation (deposit-to-withdrawal) | Critical | Delay 12-72 hours, withdraw during peak |
| H2 | Amount fingerprinting | High | Fixed denomination pools, amount normalization |
| H3 | Multi-denomination linkage | High | Stagger deposits, use single denomination |
| H4 | Cross-protocol linkage (mixer -> DeFi) | Critical | Hold before DeFi, vary behavioral pattern |
| H5 | Mixer-specific metadata (relay, gas, address reuse) | High | Fresh addresses, popular relayer, default gas |

## Relationship to stealth_address_ops

This domain generalizes two heuristics from `stealth_address_ops`:
- **SA H3 (timing)** -> **mixing H1**: same concept, applied to Tornado Cash / Railgun / Privacy Pools instead of stealth address spend timing
- **SA H6 (amounts)** -> **mixing H2**: same concept, extended with multi-denomination analysis (H3)

Additionally adds three mixer-specific heuristics (H3, H4, H5) that don't have stealth address equivalents.

## Shared skills

Reuses from `stealth_address_ops`: `timing_delay`, `amount_normalizer`, `pool_monitor` (with mixer-specific parameters).

## What needs human effort

- [ ] Calibrate timing thresholds per mixer protocol (pool activity levels vary significantly)
- [ ] Build relayer market share database for Tornado Cash and Railgun
- [ ] Quantify cross-protocol linkage success rates from public Chainalysis/TRM reports
- [ ] Validate multi-denomination fingerprinting against real deposit patterns
- [ ] Define L2-specific adaptations (different gas economics, faster blocks)

## Improving this domain

1. Run: `python -m meta.tx_validation_engine domains/mixing_behavioral/profile.json`
2. Add labeled deposit-withdrawal link datasets to `data/`
3. Adapt pool_monitor parameters per protocol
4. See `docs/improving_a_domain.md`
