# Prior art — builder_censorship

## What this guard catches (one line)
Transactions routed through builders or relays that censor sanctioned addresses (OFAC compliance), reducing user-visible censorship-resistance — and recommendation of non-censoring submission paths.

## Existing tools that implement this (FULL or substantive coverage)

### MEV Watch
- URL: https://www.mevwatch.info/
- What it does: Tracks the percentage of blocks built by OFAC-compliant MEV-Boost relays since the Merge; lists the seven major relays (Flashbots, BloXroute Max Profit/Ethical/Regulated, BlockNative, Manifold, Eden) and their compliance posture.
- Coverage of the heuristic set: Covers (a) relay census + classification, (b) historical OFAC-compliance %. Network-level monitoring, not per-transaction.
- Notable: The most-cited public dashboard for ETH censorship trends.

### Censorship.pics
- URL: https://censorship.pics/
- What it does: Visualizations on Ethereum block censorship and reorged blocks; comparative historical view.
- Coverage: Network-wide trend analysis; ~52% relay OFAC compliance over recent 60-day windows.
- Notable: Best public-facing visualization layer.

### Relayscan
- URL: https://www.relayscan.io/
- What it does: Per-relay liveness, latency, payload, and inclusion data for MEV-Boost relays.
- Coverage: Operational metrics on relay behavior; supports censorship analysis but doesn't directly flag censorship per relay.
- Notable: De-facto monitoring for relay operators and validators.

### Toni Wahrstätter (eth-censorship analysis)
- URL: https://toniwahrstaetter.com/, https://writings.flashbots.net/
- What it does: Ongoing research and writeups on Ethereum censorship dynamics, builder concentration, relay-level OFAC behavior.
- Coverage: Analytical, not a tool — but the heuristic foundation that MEV Watch / Censorship.pics build on.
- Notable: Most rigorous academic-grade tracking of the problem.

## Existing tools that implement this PARTIALLY

### Flashbots / Ultra Sound Relay (operator side)
- URL: https://ultrasound.money/, https://docs.flashbots.net/
- What it does: Run non-OFAC-compliant relays and publish their compliance position as a feature.
- Coverage: Provides the *alternative* — but doesn't help a user verify which relay their tx hit.

### Justin Drake / EF research notes on inclusion lists
- URL: https://notes.ethereum.org/@vbuterin/pbs_censorship_resistance, EIP-7547 / FOCIL
- What it does: Protocol-level work on Forced Inclusion Lists (FOCIL) and PBS-CR — designed to make censorship structurally hard rather than detectable.
- Coverage: Protocol fix, not a runtime guard.

### EthSplain / block explorer overlays
- Why adjacent: Some explorer overlays show which relay won a slot; informational only.

## Adjacent / not-quite-this-guard

### Helios light client
- URL: https://github.com/a16z/helios
- What it does: Trustless RPC via light-client verification.
- Why adjacent: Solves the *trust-the-RPC* problem orthogonally; can be paired with non-censoring tx submission.

### CR-MEV reports (Symbolic Capital, ChainSafe)
- URL: https://blog.chainsafe.io/censorship-resistance/
- What it does: Periodic reports on censorship-resistance state.
- Why adjacent: Research, not a runtime guard.

## Where e_AI builder_censorship differs

Network-level monitoring (MEV Watch, Censorship.pics, Relayscan) is solved. The gap is **wallet-side, per-transaction**: at signing time, surface "this tx will likely route through an OFAC-compliant relay; consider switching to Ultra Sound / Aestus / Manifold." None of the existing tools surface this in-wallet — they're all dashboards. e_AI's wedge: pre-submission classification + actionable recommendation. Honest: heuristic set is straightforward (mempool/RPC choice → expected relay distribution); the value is integration with the wallet flow, not novel detection.

## Open positioning question for the post

The detection is essentially a lookup against MEV Watch's data. Is the contribution (a) the wallet-integration UX, (b) the recommendation engine ("use this RPC instead"), or (c) something else? Without one of these being clearly novel, the post may read as "MEV Watch in your wallet."

## Sources

- [MEV Watch](https://www.mevwatch.info/)
- [Censorship.pics](https://censorship.pics/)
- [ChainSafe — Censorship Resistance](https://blog.chainsafe.io/censorship-resistance/)
- [Vitalik on PBS censorship resistance](https://notes.ethereum.org/@vbuterin/pbs_censorship_resistance)
- [Flashbots MEV-Boost risks](https://docs.flashbots.net/flashbots-mev-boost/architecture-overview/risks)
- [BeInCrypto — censorship trend](https://beincrypto.com/ethereum-transactions-no-longer-censorship-resistant/)
- [EigenPhi — relay public goods problem](https://eigenphi.substack.com/p/eth-relay-public-goods-problem)
