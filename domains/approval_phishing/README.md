# Domain: Token Approval Phishing (v2)

**Type:** Transaction analysis
**CROPS property:** S (Security)
**Status:** Draft, validated 11/11
**Schema:** `core/tx_profile.py` (TransactionProfile)
**Source:** Forta/Scam Sniffer 2025 Phishing Report

## What this domain does

Detects approval phishing patterns that led to $713M in losses in 2025. Analyzes approval transactions and off-chain signatures pre-submission.

## The 5 heuristics

| # | Heuristic | Severity | Countermeasure |
|---|---|---|---|
| H1 | Unlimited approval | High | Limit to exact amount needed |
| H2 | Unverified spender | Critical | Block until verified |
| H3 | Known scam address | Critical | Block immediately |
| H4 | Suspicious function selector | High | Decode and show effects |
| H5 | Stale approval | Medium | Periodic revocation audit |

## What needs human effort

- [ ] Collect labeled phishing transaction dataset (Forta alerts, Scam Sniffer)
- [ ] Build domain-specific analyzer (currently uses generic checks)
- [ ] Real data benchmark against known phishing txs
- [ ] Coordinate with Blockaid/Rabby for coverage comparison

## Improving this domain

1. Run: `python -m meta.tx_validation_engine domains/approval_phishing/profile.json`
2. Add labeled phishing transactions to `data/`
3. See `docs/improving_a_domain.md`
