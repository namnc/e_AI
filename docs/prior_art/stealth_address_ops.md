# Prior art — stealth_address_ops

## What this guard catches (one line)
Operational mistakes when using ERC-5564 / Umbra stealth addresses that allow third-party deanonymization (timing correlation, amount fingerprints, gas-price reuse, address reuse, sender = recipient self-sends, paymaster-vs-direct funding pattern).

## Existing tools that implement this (FULL or substantive coverage)

### "Anonymity Analysis of the Umbra Stealth Address Scheme" (Wahrstätter et al., 2023, ACM Web Conf 2024)
- URL: https://arxiv.org/pdf/2308.01703
- What it does: Empirical deanonymization study; defines four heuristics that recover real recipients of Umbra payments — recovery rates 48.5% Ethereum, 25.8% Polygon, 65.7% Arbitrum, 52.6% Optimism.
- Coverage of the heuristic set: Defines the canonical heuristic set (sender/recipient self-link, amount preservation, timing). This is the academic reference e_AI's profile is built against.
- Notable: Authors explicitly recommend "easily implementable countermeasures" — exactly the niche e_AI fills.

### Umbra protocol docs (ScopeLift)
- URL: https://github.com/ScopeLift/umbra-protocol
- What it does: Reference implementation of stealth-address payments; ships some user-facing privacy guidance.
- Coverage: Tooling without an automated guard; user is responsible for following the privacy-hygiene guidance.
- Notable: The protocol that Wahrstätter's deanon work targets.

### Nerolation stealth-utils
- URL: https://nerolation.github.io/stealth-utils/
- What it does: Educational + utility site for ERC-5564 stealth addresses.
- Coverage: Educational; helps with key management, not runtime ops-error detection.

## Existing tools that implement this PARTIALLY

### Tutela (Tornado Cash anonymity auditor) — adjacent heuristic set
- URL: https://github.com/pareto-xyz/tutela-app
- What it does: Anonymity-set auditor for Tornado Cash with seven heuristics (address-match, gas-price reveal, denomination reveal, etc.).
- Coverage: Same *family* of heuristics applied to a different surface (mixers, not stealth addresses). Same operational-mistake threat model.
- Notable: 42.8K of 97.3K Tornado deposits compromised by these heuristics — strong empirical motivation that operational mistakes are the dominant attack.

### Privacy & Scaling Explorations (PSE) educational content
- What it does: Stealth-address articles and prototypes from the EF privacy team.
- Coverage: Educational and research — no runtime guard.

## Adjacent / not-quite-this-guard

### More Efficient Stealth Address Protocol (arXiv 2504.06744, 2025)
- URL: https://arxiv.org/html/2504.06744v1
- Why adjacent: Protocol-level improvement, not an ops-error guard.

### RAILGUN / Privacy Pools privacy guidance
- URL: https://docs.railgun.org/wiki/learn/privacy-system
- What it does: Recommends gap between deposit and withdrawal, varying amounts, etc.
- Why adjacent: Same heuristic family applied to shielded pools, not stealth addresses.

## Where e_AI stealth_address_ops differs

This is the most defensible domain in e_AI v2 from a prior-art standpoint. The Wahrstätter paper *named* the problem and *measured* it (48.5% deanon rate) but did not ship a defensive runtime tool. Tutela addresses an analogous problem for mixers but is point-in-time auditor, not pre-submission guard. e_AI is the first runtime, pre-submission guard for ERC-5564 stealth-address operational mistakes — directly turning Wahrstätter's heuristics into a prevention layer. The benchmark question (does it reduce 48.5% deanon?) is concrete and measurable. Honest: this is the strongest novelty claim across the 16 guards.

## Open positioning question for the post

The novelty here is genuine — but adoption is gated by ERC-5564 itself reaching critical mass. Should the post frame this as "preparing for the stealth-address rollout" or "applies today to Umbra users (a small population)"?

## Sources

- [Anonymity Analysis of Umbra (Wahrstätter et al.)](https://arxiv.org/pdf/2308.01703)
- [Umbra Protocol — ScopeLift](https://github.com/ScopeLift/umbra-protocol)
- [Nerolation stealth-utils](https://nerolation.github.io/stealth-utils/)
- [Tutela App](https://github.com/pareto-xyz/tutela-app)
- [ERC-5564 spec](https://eips.ethereum.org/EIPS/eip-5564)
- [More Efficient Stealth Address Protocol](https://arxiv.org/html/2504.06744v1)
