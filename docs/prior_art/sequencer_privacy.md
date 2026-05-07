# Prior art — sequencer_privacy

## What this guard catches (one line)
Transaction visibility to a centralized L2 sequencer (Arbitrum, Optimism, Base) — the sequencer sees pre-confirmation tx content, can reorder for MEV, and constitutes a single trust point that can deanonymize, censor, or extract value from the user.

## Existing tools that implement this (FULL or substantive coverage)

### L2BEAT (sequencer trust posture per L2)
- URL: https://l2beat.com/
- What it does: Tracks per-L2 sequencer model — single sequencer, decentralized, escape-hatch latency, ability to force-include via L1.
- Coverage of the heuristic set: Provides the input data (which L2s have which sequencer trust posture). Doesn't compute per-tx risk.
- Notable: Canonical source of L2 risk metadata.

### Aztec (decentralized sequencing as the alternative)
- URL: https://aztec.network/
- What it does: Operates ~617 decentralized PoS sequencer nodes; sequencers cannot see private tx contents (zk).
- Coverage: Architectural escape route — not a guard for users on centralized-sequencer L2s.

### Arbitrum sequencer + delayed-inbox docs
- URL: https://docs.arbitrum.io/how-arbitrum-works/deep-dives/sequencer
- What it does: Documents the Arbitrum sequencer model + the delayed-inbox forced-inclusion fallback.
- Coverage: Reference; defines the trust surface that needs to be guarded.

### Espresso, Astria, Radius (shared/decentralized sequencer networks)
- URL: https://www.espressosys.com/, https://www.astria.org/, https://radiustech.xyz/
- What it does: Build decentralized / shared sequencing networks; Radius specifically uses encrypted mempool + PVDE.
- Coverage: Infrastructure-level mitigation. Out of user-wallet scope, but represents the protocol direction.
- Notable: Radius's encrypted-mempool approach maps to the same threat model.

## Existing tools that implement this PARTIALLY

### MEV Watch / Censorship.pics (L1 focus)
- URL: https://www.mevwatch.info/, https://censorship.pics/
- What it does: L1 builder-censorship monitoring. Conceptually parallel to L2-sequencer monitoring.
- Coverage: Wrong layer — L1 only.

### L2 Security Framework (Quantstamp)
- URL: https://github.com/quantstamp/l2-security-framework
- What it does: Posture assessment.
- Coverage: Static framework, not runtime.

## Adjacent / not-quite-this-guard

### Encrypted mempool EIP (EIP-7805)
- URL: https://en.cryptonomist.ch/2025/12/17/encrypted-mempool-eip/
- Why adjacent: L1 fix; analogous design at L2 would address sequencer-visibility concerns at the protocol layer.

### Shutter Network (threshold-encrypted mempool)
- URL: https://www.shutter.network/
- What it does: Threshold-encrypted mempool (deployed on Gnosis Chain).
- Why adjacent: Protocol-level mitigation; a future L2 deployment could subsume the guard.

## Where e_AI sequencer_privacy differs

L2BEAT publishes the static sequencer-trust posture. Aztec / Espresso / Radius solve it at the protocol level. No existing tool surfaces, at the moment a user is about to submit an L2 tx: "this sequencer can see your tx contents, has X% MEV-extraction history, and will hold your tx in a private mempool for ~Y seconds before commit — consider [Aztec / submit via L1 forced-include / delay]." e_AI's wedge: per-tx, per-L2 sequencer-trust risk surfacing in the wallet. Honest: most users currently have no good mitigation (Aztec is small; L1 forced-include is high-latency); the guard is mostly *informational* until protocol-level encrypted mempools land.

## Open positioning question for the post

If the only realistic mitigation is "use Aztec" or "wait for encrypted mempools," is the guard actionable enough to publish, or does it just surface a problem the user can't fix today?

## Sources

- [L2BEAT](https://l2beat.com/)
- [Aztec Network](https://aztec.network/)
- [Arbitrum sequencer + censorship resistance](https://docs.arbitrum.io/how-arbitrum-works/deep-dives/sequencer)
- [Unchained — What are sequencers](https://unchainedcrypto.com/what-are-sequencers-in-layer-2-protocols-such-as-optimism-arbitrum-and-base/)
- [Encrypted mempool EIP](https://en.cryptonomist.ch/2025/12/17/encrypted-mempool-eip/)
- [Shutter Network](https://www.shutter.network/)
