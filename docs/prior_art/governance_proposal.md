# Prior art — governance_proposal

## What this guard catches (one line)
Malicious DAO governance proposals — treasury drains, parameter manipulation, hidden proxy upgrades, obfuscated calldata — flagged before vote-cast or execute.

## Existing tools that implement this (FULL or substantive coverage)

### Tally
- URL: https://www.tally.xyz/
- What it does: Governance-as-a-platform — proposal tracking, vote casting, treasury management for major DAOs (ENS, Uniswap, Compound, Arbitrum). Surfaces proposal calldata + parameter changes.
- Coverage of the heuristic set: Covers (a) proposal display + decoding, (b) treasury movement tracking, (c) governance-token concentration. Less explicit on automated "this is malicious" classification.
- Notable: De-facto governance UI for OpenZeppelin Governor-based DAOs.

### Boardroom
- URL: https://boardroom.io/
- What it does: Cross-DAO governance aggregator — votes, proposals, delegate analytics across many protocols; provides signals on voter participation and proposal context.
- Coverage: Proposal aggregation + delegate data; analytics surface, not active classifier.

### Guardrail
- URL: https://www.guardrail.ai/projects/dao-governance-platforms
- What it does: DAO governance security monitoring — claims to detect governance attacks, treasury anomalies, suspicious proposals.
- Coverage of the heuristic set: Most direct competitor — purpose-built for proposal-risk classification (treasury drain, parameter manipulation).
- Notable: Marketed specifically as an anti-governance-attack tool.

### OpenZeppelin Defender
- URL: https://www.openzeppelin.com/defender
- What it does: Operations and security platform with proposal-simulation, transaction simulation, and timelock monitoring.
- Coverage: Used by DAOs themselves to simulate and stage proposals before execution; covers the operator side of the heuristic.

## Existing tools that implement this PARTIALLY

### Tenderly (proposal simulation)
- URL: https://tenderly.co/
- What it does: Generic transaction simulator — DAOs use it to dry-run proposal execution and inspect state changes.
- Coverage: Simulation infrastructure; classification is up to the user.

### Snapshot
- URL: https://snapshot.org/
- What it does: Off-chain governance signaling; less relevant to on-chain treasury-drain detection but central to governance UX.
- Coverage: Off-chain only; the on-chain execution layer is where the risk lives.

### Karpatkey + Llama treasury reports
- URL: https://karpatkey.com/, https://llama.xyz/
- What it does: DAO treasury management and reporting services.
- Coverage: Operational risk + treasury hygiene reporting; not real-time proposal scanning.

## Adjacent / not-quite-this-guard

### MakerDAO Pause Proxy + delays
- Why adjacent: Protocol-level defense (governance delay) used by mature DAOs. Architectural mitigation, not a detection layer.

### Forta governance bots
- URL: https://forta.org/
- What it does: Decentralized detection-bot network has bots monitoring governance contracts.
- Why adjacent: Open framework with some governance bots, but not a unified "governance proposal scanner."

## Where e_AI governance_proposal differs

Guardrail and OpenZeppelin Defender are direct prior art. Tally and Boardroom dominate the UX surface but don't classify malicious intent. e_AI's wedge: (1) **voter-side** detection — Guardrail/Defender are operator-side; voters currently rely on raw Tally display. A wallet-resident scanner that surfaces "this proposal contains a delegatecall to an unverified contract" *as the user is about to cast a vote* is a thin gap. (2) Local execution means no leak of which proposals the user is reviewing. Honest: detection coverage will trail Guardrail unless the heuristic set is genuinely novel; positioning is "voter-side defense" not "DAO-ops defense."

## Open positioning question for the post

Guardrail covers the DAO-ops angle. Is "wallet-side voter defense" a meaningfully different surface, or is the right answer "publish the heuristics, let Tally integrate them"?

## Sources

- [Tally](https://www.tally.xyz/)
- [Boardroom DAO Tool Report](https://daotimes.com/boardroom-dao-tool-report-for-2025/)
- [Guardrail — DAO governance security](https://www.guardrail.ai/projects/dao-governance-platforms)
- [Gitcoin Treasury Protection update](https://gov.gitcoin.co/t/security-update-treasury-protection-governance-transition-what-we-did-and-why/25228)
- [Cube — Treasury Management for DAOs](https://www.cube.exchange/what-is/treasury-management-dao)
- [OpenZeppelin Defender](https://www.openzeppelin.com/defender)
