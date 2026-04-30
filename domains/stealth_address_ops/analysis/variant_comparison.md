# Stealth Address Ops Profile: Variant Comparison

## Overview

| | Hand-crafted | qwen2.5:7b | qwen2.5:14b |
|---|---|---|---|
| Heuristics | 6 (H1-H6) | 8 (H1-H8) | 7 (H1-H7) |
| Total signals | 17 | 22 | 27 |
| Avg signals/heuristic | 2.8 | 2.75 | 3.9 |
| Skills defined | 8 | 0 | 0 |
| Templates | 18 | 3 | 3 |
| Benchmark methodology | Detailed 6-step | Stub | Stub |
| Adversary model depth | 6 capabilities, 3 limitations | 3 capabilities, 1 limitation | 3 capabilities, 1 limitation |

## Heuristic Mapping

| Paper concept | Hand-crafted | 7b | 14b |
|---|---|---|---|
| Same-entity withdrawal | H1 (5 signals) | H1 (4 signals) | H1 (4 signals) |
| Gas fingerprinting | H2 (3 signals) | H2 (3) + H4 (3) | H3 (4 signals) |
| Timing correlation | H3 (3 signals) | H3 (4) + H5 (2) | H4 (4 signals) |
| Funding linkability | H4 (2 signals) | H6 (3 signals) | H5 (4 signals) |
| Self-transfer | H5 (3 signals) | H7 (3 signals) | H6 (5 signals) |
| Unique amounts | H6 (3 signals) | H8 (2 signals) | H7 (4 signals) |
| Clean address behavior | -- | -- | H2 (4 signals, novel) |
| Behavioral patterns | -- | H5 (2 signals, novel) | -- |

## What auto-generated found that hand-crafted missed

- **Cross-platform gas consistency** (14b H3): gas fingerprint persisting across different wallets/platforms, not just within a single wallet's history.
- **Consistent gas sender pattern** (14b H5): a single wallet repeatedly sending small gas amounts to multiple stealth addresses, which is a stronger signal than one-off direct funding.
- **Clean address behavior** (14b H2): withdrawal to fresh addresses as a distinct heuristic rather than a sub-signal. Debatable whether this is a separate heuristic or belongs under H1.
- **Behavioral deposit-withdrawal patterns** (7b H5): recurring timing intervals as a fingerprint. Hand-crafted captured "consistent dwell" as a signal under H3 but did not elevate the recurring-pattern angle to its own heuristic.
- **Fresh address as a signal itself** (both generated): both models flag withdrawals to fresh addresses as potentially suspicious (could be controlled by the same entity). Hand-crafted treats fresh addresses purely as a recommendation (use one), not as a detection signal.

## What hand-crafted had that auto-generated missed

- **Actionable skills**: 8 concrete skill definitions (paymaster, gas randomizer, timing delay, pool monitor, relay, amount normalizer, transfer splitter, activity monitor) with parameters. Both generated profiles have empty `skills: {}`.
- **ERC-4337 paymaster** as the primary mitigation for funding linkability. Neither generated profile mentions paymasters or account abstraction.
- **Relay/meta-transaction** pattern for hiding msg.sender. Generated profiles suggest "mixer services" generically instead.
- **Pool-aware amount matching**: checking the current deposit pool to choose blending amounts. Generated profiles suggest rounding but not pool-aware selection.
- **Fundamental limitations per heuristic**: each hand-crafted heuristic explains why the countermeasure is imperfect (e.g., "paymaster usage itself may become a fingerprint"). Generated profiles defer to a generic `failure_analysis.md`.
- **Severity calibration**: hand-crafted marks self-transfer and timing as "critical" with confidence 1.0 for self-send. Generated profiles use "high" or "medium" with lower confidence values.
- **Benchmark scenarios**: hand-crafted has per-heuristic test setups with expected baselines (48.5% from the paper). Generated profiles have placeholder stubs.
- **Rich template library**: 18 templates covering risk assessment, cover scoring, behavioral alerts, onboarding. Generated profiles have 3 generic templates.
- **Adversary model**: hand-crafted includes gas price distribution modeling, amount distribution modeling, and cross-protocol linkage. Generated profiles list only 3 generic capabilities.

## Quality of recommendations

Hand-crafted recommendations are protocol-specific and implementable (use ERC-4337 paymaster via Pimlico/StackUp, randomize gas within [p25,p75], delay 6-24h). Generated recommendations are generic security advice (use mixer services, enable 2FA, deploy cold storage, update wallets). The 7b profile is particularly noisy -- it recommends 2FA and cold storage for timing correlation, which are irrelevant to the deanonymization vector.

The 14b profile is moderately better than 7b: its recommendations are closer to relevant (e.g., "delay transactions", "randomize gas pricing", "use rounded amounts") but still lack protocol-specific detail.

## Verdict: which is best for production

**Hand-crafted, by a wide margin.** It is the only variant with implementable skills, protocol-aware mitigations, calibrated severity, and testable benchmarks. The generated profiles are useful as a checklist to audit coverage (they surfaced the cross-platform gas consistency angle and the fresh-address-as-signal idea), but their recommendations are too generic and their infrastructure (skills, templates, benchmarks) is empty. The 14b profile is meaningfully better than 7b in signal quality and recommendation relevance.

**Recommended path**: keep hand-crafted as the production profile. Cherry-pick from generated profiles: (1) add cross-platform gas consistency as a signal under H2, (2) add consistent-gas-sender as a signal under H4, (3) consider whether fresh-address withdrawal deserves a signal under H1.
