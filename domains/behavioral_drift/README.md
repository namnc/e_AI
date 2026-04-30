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

## What needs human effort

- [ ] Calibrate concentration thresholds against historical protocol failure data
- [ ] Validate leverage creep detection against actual liquidation outcomes
- [ ] Build approval vulnerability database from past exploit data (Rekt, SlowMist)
- [ ] Test behavioral fingerprinting accuracy on real multi-address users

## Improving this domain

See `docs/improving_a_domain.md`
