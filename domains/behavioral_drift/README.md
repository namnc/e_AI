# Domain: Behavioral Drift Monitoring

**Type:** Transaction analysis
**CROPS property:** S (Security)
**Status:** Draft
**Schema:** `core/tx_profile.py`
**Source:** DeFi risk monitoring research, approval exploit post-mortems (Revoke.cash)

## What this domain does

Long-term behavioral monitoring that detects gradual security and privacy degradation. Wallet + RPC guard tracking portfolio concentration, leverage creep, approval accumulation, gas inefficiency, and interaction pattern rigidity over time.

## Heuristics

| # | Heuristic | Severity | Countermeasure |
|---|---|---|---|
| H1 | Portfolio concentration | High | Diversification alert, concentration limit |
| H2 | Leverage creep | Critical | Leverage dashboard, leverage ceiling |
| H3 | Approval accumulation | Critical | Revoke stale approvals, use limited approvals |
| H4 | Gas spending trend | Medium | Gas efficiency report, batch transactions |
| H5 | Interaction pattern rigidity | High | Randomize timing, vary sequences |

## Skills

- **portfolio_tracker** -- multi-protocol composition and concentration trend analysis
- **leverage_monitor** -- aggregate leverage calculation with liquidation distance
- **approval_auditor** -- ERC-20 approval scanning and revocation management

## Analyzer

Rule-based analyzer at `analyzer.py` evaluates a `BehavioralSnapshot` (90-day
window) against H1-H5 algorithmically (concentration delta vs threshold, leverage
trend + health-factor floor, unlimited-approval count + revocation rate +
vulnerability-DB cross-reference, gas growth factor, pattern repeat rate +
temporal-variance fingerprint). LLM augments with intent inference (deliberate
strategy vs drift). Demo at `examples/per_domain/behavioral_drift/demo.py`.
Production deployment must wire snapshot fields from on-chain RPC + indexer.

## What needs human effort

- [ ] Calibrate concentration thresholds against historical protocol failure data
- [ ] Validate leverage creep detection against actual liquidation outcomes
- [ ] Build approval vulnerability database from past exploit data (Rekt, SlowMist)
- [ ] Test behavioral fingerprinting accuracy on real multi-address users

## Improving this domain

See `docs/improving_a_domain.md`

## Prior art

**Nansen** / **Arkham** observe at analytics level. **Forta** / **Hypernative** monitor *compromise*. No per-user-baseline drift detector — but user-demand evidence is vague.

**Where this guard differs**: User-baseline framing rather than absolute-position. Useful if there's adoption signal; honest open question if there isn't.

Full comparison: `docs/prior_art/behavioral_drift.md`.
