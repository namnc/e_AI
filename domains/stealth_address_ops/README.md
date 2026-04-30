# Domain: Stealth Address Operational Privacy (v2)

**Type:** Transaction analysis
**CROPS property:** P (Privacy)
**Status:** Draft, validated 11/11
**Schema:** `core/tx_profile.py` (TransactionProfile)
**Source:** arxiv 2308.01703 (ACM Web Conference 2024)

## What this domain does

Detects the 6 operational heuristics that deanonymize 48.5% of stealth address transactions. Analyzes transactions pre-submission and recommends countermeasures.

## The 6 heuristics

| # | Heuristic | Severity | Countermeasure |
|---|---|---|---|
| H1 | Same-entity withdrawal | Critical | Fresh unlinked address |
| H2 | Gas price fingerprinting | High | Randomize within block distribution |
| H3 | Timing correlation | Critical | Delay 6-24 hours |
| H4 | Funding linkability | Critical | ERC-4337 paymaster |
| H5 | Self-transfer | Critical | Block the transaction |
| H6 | Unique amounts | High | Round to standard denomination |

## Benchmark

Synthetic: 1000 txs, 84.5% baseline → 0% with all countermeasures.
Real data: Script ready (`benchmarks/real_data.py`), needs RPC endpoint.

## What needs human effort

- [ ] Run real data benchmark against Umbra transactions
- [ ] Calibrate confidence scores against ground truth
- [ ] Test LLM behavioral analysis over transaction history (multi-tx patterns)
- [ ] Coordinate with Kohaku team for wallet integration

## Improving this domain

1. Run: `python -m meta.tx_validation_engine domains/stealth_address_ops/profile.json`
2. Add labeled deanonymization incidents to `data/`
3. Run analyzer: `python domains/stealth_address_ops/analyzer.py --benchmark`
4. See `docs/improving_a_domain.md`
