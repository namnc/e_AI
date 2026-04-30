# Domain: Governance Proposal Risk Analysis

**Type:** Transaction analysis (APPLICATION access method)
**CROPS property:** S (Security)
**Status:** Draft
**Schema:** `core/tx_profile.py`
**Source:** Beanstalk, Tornado Cash, Compound governance attack post-mortems

## What this domain does

Detects malicious or high-risk governance proposals before execution. Analyzes proposal calldata, parameter changes, proxy upgrades, timelock modifications, and voter concentration to flag potential governance attacks.

## Heuristics

| # | Heuristic | Severity | Countermeasure |
|---|---|---|---|
| H1 | Treasury drain (>10% to unknown address) | critical | Simulate treasury impact, verify recipient |
| H2 | Parameter manipulation (out-of-range values) | high | Fork-simulate parameter changes |
| H3 | Proxy upgrade to unverified code | critical | Decode + diff bytecode, require verification |
| H4 | Timelocked bypass (shorten/remove timelock) | critical | Decode timelock changes, alert delegates |
| H5 | Voter concentration (<3 addresses >50% power) | high | Analyze voter distribution + token provenance |

## Skills

- **proposal_decoder** -- decode governance calldata into human-readable actions
- **parameter_simulator** -- fork mainnet and simulate protocol under proposed parameters
- **vote_analyzer** -- analyze voting power distribution and historical participation

## What needs human effort

- [ ] Label historical governance proposals (benign vs. suspicious vs. attack) for benchmark dataset
- [ ] Define protocol-specific parameter bounds for major DeFi protocols
- [ ] Curate list of known multisig/grant-program addresses for recipient verification
- [ ] Integrate with governance forum APIs for context enrichment
- [ ] Validate flash-loan detection window against real Beanstalk attack data

## Improving this domain

See `docs/improving_a_domain.md`
