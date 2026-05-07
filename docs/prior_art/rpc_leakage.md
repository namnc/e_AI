# Prior art — rpc_leakage

## What this guard catches (one line)
Wallet RPC query patterns that reveal user identity, portfolio composition, or strategy to a centralized RPC provider (Infura, Alchemy, Quicknode) — including correlated balance polls, dApp-specific call sequences, and IP-linkable request timing.

## Existing tools that implement this (FULL or substantive coverage)

### RPCh (HOPR)
- URL: https://rpch.net/, https://github.com/hoprnet/RPCh, https://medium.com/hoprnet/privacy-matters-comparing-rpch-to-other-rpc-providers-75420aa5b2a1
- What it does: Routes RPC requests through HOPR mixnet — multiple intermediary nodes between entry/exit, obscuring metadata from the RPC provider. Combined with Kevlar/Helios light-client verification.
- Coverage: Provides the *mitigation* (routing privacy), not the *detection* (which queries are leaky).
- Notable: Development paused as of 2024-2025 per the project; HOPR redirected effort to Gnosis VPN.

### Helios light client
- URL: https://github.com/a16z/helios
- What it does: Trustless RPC via light-client verification — minimizes trust in any single RPC provider by validating consensus locally.
- Coverage: Trust mitigation, not query-pattern leakage detection.
- Notable: Vitalik recommends; integrated into Kohaku.

### Kevlar
- URL: https://github.com/lightclients/kevlar
- What it does: Light-client RPC proxy for Ethereum — verifies RPC responses against the consensus layer.
- Coverage: Same family as Helios — trust minimization for RPC.

### Nym
- URL: https://nym.com/
- What it does: General-purpose mixnet; supports anonymizing arbitrary network traffic including RPC.
- Coverage: Mitigation infrastructure; not Ethereum-specific.

## Existing tools that implement this PARTIALLY

### Cover queries (e_AI v1)
- What it does: Generates plausible decoy RPC queries to obscure real ones.
- Coverage: e_AI v1 already addresses this for query patterns; v2 extends to transactions.
- Notable: This is the parent project's existing function being extended.

### dRPC (decentralized RPC)
- URL: https://drpc.org/blog/alchemy-vs-infura/
- What it does: Decentralized RPC routing across multiple providers — reduces single-provider linkability.
- Coverage: Distributes trust; doesn't hide query patterns from individual nodes.

### Privacy-focused RPC providers (e.g., Pocket Network)
- URL: https://pokt.network/
- What it does: Decentralized infrastructure layer that disperses RPC across many nodes.
- Coverage: Dispersion, not pattern obfuscation.

## Adjacent / not-quite-this-guard

### HOPR Sebastian Bürgel comparison post
- URL: https://medium.com/hoprnet/privacy-matters-comparing-rpch-to-other-rpc-providers-75420aa5b2a1
- What it does: Rigorous comparison of privacy postures of Infura/Alchemy/Quicknode/RPCh.
- Why adjacent: Analysis, not a runtime guard.

### Local node (geth, reth, nethermind)
- Why adjacent: Running a full node entirely sidesteps the RPC-provider trust problem, but doesn't help users who can't run one.

## Where e_AI rpc_leakage differs

RPCh / Nym / Helios cover *infrastructure-level* mitigation. e_AI's slot is **application-level pattern detection** — "your wallet's polling pattern is fingerprinting you to your RPC provider" or "this dApp is making an unusual query that reveals your full DeFi position." None of the existing tools surface the leakiness of *specific query patterns*; they only obfuscate transport. e_AI's profile-driven detection of leaky patterns + recommendation (route this query through a mixnet, batch this poll) is the wedge. Honest: the local-LLM angle is strong here — the analysis itself can't leak via cloud, which is the entire point. This is the second-strongest novelty claim across the 16 guards (after stealth_address_ops).

## Open positioning question for the post

Most users don't run Helios / RPCh. Is the right framing "local guard that warns + recommends RPCh/Helios when needed" (router-style)? And does e_AI v1's "cover queries" subsume this domain such that v2's contribution is just the profile?

## Sources

- [RPCh project](https://rpch.net/)
- [HOPR — Privacy Matters comparison](https://medium.com/hoprnet/privacy-matters-comparing-rpch-to-other-rpc-providers-75420aa5b2a1)
- [Helios light client](https://github.com/a16z/helios)
- [Kevlar](https://github.com/lightclients/kevlar)
- [Nym](https://nym.com/)
- [dRPC](https://drpc.org/blog/alchemy-vs-infura/)
- [CoW Fi — RPC endpoints explainer](https://cow.fi/learn/understanding-rpc-endpoints-for-ethereum)
