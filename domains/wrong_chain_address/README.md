# Domain: Wrong Chain / Address Prevention

**Type:** Transaction analysis
**CROPS property:** S (Security)
**Status:** Draft
**Schema:** `core/tx_profile.py`
**Source:** Address poisoning attacks (SlowMist reports), EIP-155 chain ID specification

## What this domain does

Pre-submission validation to prevent irreversible fund loss from wrong-chain sends, wrong-address sends, address poisoning attacks, and transfers to non-functional contracts. Wallet guard that catches common transfer mistakes before broadcast.

## Heuristics

| # | Heuristic | Severity | Countermeasure |
|---|---|---|---|
| H1 | Address has no activity on target chain | High | Verify chain, test transfer |
| H2 | Contract cannot receive tokens | Critical | Block transfer, suggest deposit function |
| H3 | Address poisoning | Critical | Block and compare with legitimate address |
| H4 | Chain ID mismatch | Critical | Block submission, auto-correct chain |
| H5 | Deprecated contract | High | Check migration, warn user |

## Skills

- **address_validator** -- visual similarity detection for address poisoning
- **chain_checker** -- multi-chain address activity lookup
- **contract_status_checker** -- pause status, migration, and activity analysis

## What needs human effort

- [ ] Build labeled dataset of confirmed address poisoning incidents
- [ ] Validate contract receivability checker against proxy patterns (EIP-1967, UUPS)
- [ ] Calibrate abandoned contract threshold (90 days may be too aggressive for some protocols)
- [ ] Test chain ID detection against L2/L3 edge cases (custom chain IDs)

## Improving this domain

See `docs/improving_a_domain.md`
