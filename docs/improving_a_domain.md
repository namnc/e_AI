# Improving an Existing Domain

## Quick start

1. Read the domain's `README.md`
2. Run validation: `python -m meta.tx_validation_engine domains/<name>/profile.json`
3. Check "What needs human effort" in the README

## Common improvements

### Calibrate confidence scores

Confidence scores are initially estimated. To calibrate:

1. Collect labeled data (incidents where the heuristic should/shouldn't fire)
2. Run analyzer against labeled data
3. Measure true positive rate per signal
4. Update confidence to match measured detection rate

### Add detection signals

Each heuristic can have multiple signals. Adding signals improves detection:

1. Identify a new data pattern that indicates the risk
2. Add to the heuristic's `detection.signals` array
3. Re-run validation (F4 checks confidence calibration)

### Add recommendations

Good recommendations are:
- **Actionable**: "Round to 1.0 ETH" not "be careful with amounts"
- **Measurable**: effectiveness score reflects actual risk reduction
- **Costed**: user_cost reflects real UX impact

### Run real data benchmark

Most domains start with synthetic benchmarks. To validate against reality:

1. Obtain real transaction data (RPC, Etherscan API, labeled datasets)
2. Write benchmark script in `domains/<name>/benchmarks/`
3. Compare synthetic results with real results
4. Adjust confidence scores and thresholds

### Document fundamental limitations

Every heuristic should document what technology CANNOT fix. This prevents overselling. Validation check S3 flags missing limitations.

## Validation checks reference

| Check | What it verifies |
|---|---|
| F1 | Every heuristic has detection signals with data requirements |
| F2 | Every heuristic has recommendations with effectiveness > 0 |
| F3 | Every referenced skill is defined with parameters |
| F4 | Confidence scores are distributed (not all same value) |
| F5 | Every heuristic has a benchmark scenario |
| S1 | Adversary model has >= 3 capabilities and limitations |
| S2 | Critical heuristics have high-confidence signals (> 0.8) |
| S3 | Critical/high heuristics document fundamental limitations |
| Q1 | Descriptions are substantive (> 20 chars) |
| Q2 | Output templates exist for all types |
| Q3 | Heuristics balanced in depth (signal count) |
