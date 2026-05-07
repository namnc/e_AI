# Prior art — offchain_signature

## What this guard catches (one line)
Malicious EIP-712 / Permit / Permit2 / Seaport off-chain signatures that authorize spending or transfers without an on-chain approve, including signature-format injection (EIP-712 normalization abuse, chainId mismatches).

## Existing tools that implement this (FULL or substantive coverage)

### Blockaid
- URL: https://www.blockaid.io/, https://www.blockaid.io/blog/wallet-drainers-vitalik-metamask
- What it does: Pre-signature scanning of EIP-712 typed-data messages including Permit, Permit2, Seaport; simulates the resulting state changes and flags malicious signature payloads.
- Coverage of the heuristic set: Covers (a) Permit/Permit2 risk classification, (b) Seaport order classification, (c) drainer-signature DB. EIP-712 simulation is explicitly hard and Blockaid invests heavily here.
- Notable: Public posts from Blockaid acknowledge "EIP-712s are incredibly difficult to simulate and validate" — they treat this as a primary attack surface.

### Veritas Protocol — Permit Signature Risk Scanner
- URL: https://www.veritasprotocol.com/blog/permit-signature-risk-scanner-eip-2612-checks
- What it does: EIP-2612 / Permit-specific scanner that classifies the signed message and surfaces risk (spender reputation, amount sanity, expiry).
- Coverage: Permit-class only; deep on EIP-2612 specifics.
- Notable: Specialist tool in a domain Blockaid covers more broadly.

### Coinspect — EIP-712 vulnerability research
- URL: https://www.coinspect.com/blog/wallet-eip-712-injection-vulnerability/, https://www.coinspect.com/blog/chainid-eip-712-implementation-issue/
- What it does: Published research on EIP-712 injection vulnerabilities affecting 40+ wallet vendors; toolkit for testing wallet display correctness.
- Coverage: Wallet-display attack surface; not a runtime guard but documents what a guard should test.
- Notable: Foundation for any rigorous offchain_signature heuristic — defines the threat surface.

### Pocket Universe
- URL: https://pocketuniverse.app/
- What it does: Simulates EIP-712 typed-data signatures alongside transactions; flags Permit and Permit2 risks.
- Coverage: Permit / Permit2 / Seaport coverage; consumer-grade simulation.
- Notable: One of the few consumer extensions that explicitly handles offchain signatures, not just txs.

## Existing tools that implement this PARTIALLY

### Rabby Wallet
- URL: https://rabby.io/
- What it does: Pre-signature simulation and balance-change preview; surfaces what a Permit signature would actually authorize.
- Coverage: Decoded EIP-712 display + spender risk surfacing; less aggressive on signature-format attacks.
- Notable: Wallet-native rather than third-party extension.

### Wallet Guard / Web3 Antivirus
- URL: https://www.walletguard.app/, https://web3antivirus.io/
- What it does: Browser extensions that decode and warn on EIP-712 signatures during dApp interactions.
- Coverage: Surface-level decode + reputation; lighter than Blockaid.

### Ledger (clear-signing initiative)
- URL: https://www.ledger.com/academy/glossary/eip-712
- What it does: Pushes for "clear signing" — hardware wallet displays full EIP-712 message intent, not just an opaque hash.
- Coverage: Display-layer only; no automated risk classification.
- Notable: Core ecosystem-wide effort, complements but doesn't replace risk scanners.

## Adjacent / not-quite-this-guard

### Three Sigma — Wallet Drainers + EIP-7702 research
- URL: https://threesigma.xyz/blog/opsec/ai-phishing-wallet-drainers-eip7702-part-2
- What it does: Threat-research blog series on drainer evolution including EIP-7702 attack patterns.
- Why adjacent: Research, not a runtime tool — useful for heuristic design.

## Where e_AI offchain_signature differs

This is one of the most crowded surfaces in Web3 security. Blockaid + Pocket Universe + Rabby cover the consumer side; Veritas + Coinspect cover the specialist side. e_AI's natural angle: (1) local execution (no signature payload sent to a remote scanner — important when the signed message contains sensitive recipient/amount information), (2) reasoning about user-historical context (e.g. "you have never signed a Permit2 for this token before") which third-party scanners can't do without privacy cost, (3) integration with wallet history that a stateless scanner cannot see. Honest: pure detection lags Blockaid; context-aware framing is the wedge.

## Open positioning question for the post

Blockaid's EIP-712 detection is mature and broadly integrated. The differentiator can only be (a) local privacy or (b) historical-context reasoning. Is "I've never signed a Permit2 to this spender before" a strong-enough novelty to publish, given Blockaid likely tracks similar reputation server-side?

## Sources

- [Blockaid — Wallet Drainers blog](https://www.blockaid.io/blog/wallet-drainers-vitalik-metamask)
- [Veritas Protocol — Permit Signature Scanner](https://www.veritasprotocol.com/blog/permit-signature-risk-scanner-eip-2612-checks)
- [Coinspect — EIP-712 UI flaw](https://www.coinspect.com/blog/wallet-eip-712-injection-vulnerability/)
- [Coinspect — chainId implementation issue](https://www.coinspect.com/blog/chainid-eip-712-implementation-issue/)
- [EIP-712 normalization phishing](https://coinpaper.com/3546/wallet-drainers-can-bypass-security-by-exploiting-eip-712-normalization)
- [Three Sigma — EIP-7702 drainer research](https://threesigma.xyz/blog/opsec/ai-phishing-wallet-drainers-eip7702-part-2)
- [Ledger — EIP-712 explainer](https://www.ledger.com/academy/glossary/eip-712)
