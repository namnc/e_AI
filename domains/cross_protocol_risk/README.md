# Domain: Cross-Protocol Compound Risk

**Type:** Transaction analysis
**CROPS property:** S (Security)
**Access method:** APPLICATION
**Status:** Draft
**Schema:** `core/tx_profile.py`
**Source:** DeFi composability risk -- multi-protocol interaction analysis

## What this domain does

Detects compounding risks that emerge when a user holds positions across multiple DeFi protocols simultaneously. A swap on Uniswap can trigger a liquidation on Aave; a shared oracle failure can wipe positions across lending, derivatives, and staking; a forgotten approval can chain-react into collateral loss. These risks are invisible to any single protocol's risk engine.

## Heuristics

| # | Heuristic | Severity | Countermeasure |
|---|---|---|---|
| H1 | Cascading liquidation | critical | Add collateral before swap, partial swap, repay debt |
| H2 | Correlated oracle dependency | critical | Diversify oracle exposure, reduce correlated positions |
| H3 | Concentrated protocol exposure | high | Diversify across protocols, check insurance |
| H4 | Approval chain risk | critical | Revoke stale approvals, exact approvals, separate wallets |
| H5 | Flash loan attack surface | high | Increase health factor, use liquid collateral, monitor |

## Skills

- **portfolio_scanner** -- Aggregates positions across protocols for unified risk view
- **oracle_mapper** -- Maps oracle dependencies, detects shared feeds
- **position_simulator** -- Simulates transaction impact on all positions
- **flash_loan_detector** -- Estimates flash loan attack profitability

## What needs human effort

- [ ] Calibrate health factor thresholds against historical liquidation data
- [ ] Build oracle dependency graph for top 20 DeFi protocols
- [ ] Collect labeled dataset of cascading liquidation events for benchmark
- [ ] Validate flash loan profitability model against real attack transactions
- [ ] Integrate with protocol-specific ABIs for real-time position reading

## Improving this domain

See `docs/improving_a_domain.md`
