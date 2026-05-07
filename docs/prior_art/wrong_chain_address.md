# Prior art — wrong_chain_address

## What this guard catches (one line)
Operational mistakes around transaction routing — wrong chain selected, sending ERC-20 to a contract that can't receive it, EOA-vs-contract address mismatch, mismatched chain-ID in EIP-712 message.

## Existing tools that implement this (FULL or substantive coverage)

### Rabby Wallet
- URL: https://rabby.io/
- What it does: Auto-switches network when interacting with dApps — reduces user error from manual switching. Pre-tx scan also flags contract-vs-EOA mismatches and balance-change preview.
- Coverage of the heuristic set: Covers (a) auto-network-switching (eliminates the wrong-chain class), (b) contract-address detection, (c) preview before signing.
- Notable: Often cited as the wallet that solved this UX problem.

### MetaMask (with later improvements)
- URL: https://github.com/MetaMask/metamask-extension/issues/13486
- What it does: Now displays warning dialog when sending ERC-20 to a contract address; long-running issue (#13486) about improving "Known Contract Address" warning.
- Coverage: Partial — historically weaker than Rabby on auto-switch; now improving.
- Notable: The dominant wallet, so even partial coverage shapes user expectations.

### Coinbase Wallet, Rainbow, Block Wallet (similar warnings)
- What it does: Modern wallet UIs implement contract-address warnings when sending tokens.
- Coverage: Industry-standard warning surface.

### Chain-ID validation in EIP-712 (40+ wallet vendors fix, Coinspect)
- URL: https://www.coinspect.com/blog/chainid-eip-712-implementation-issue/
- What it does: Documented widespread chainId-mismatch vulnerability across 40+ wallets; led to fixes in major wallet codebases.
- Coverage: Vulnerability documentation + remediation tracking — defines what proper chain-ID validation looks like.

## Existing tools that implement this PARTIALLY

### Address-format checker (mixed)
- What it does: Generic checks (EIP-55 checksum, length).
- Coverage: Trivially built into most wallets; doesn't catch contract-vs-EOA semantics.

### Bridge frontends (Across, Hop, Stargate)
- What it does: Bridge UIs validate destination chain at the application layer.
- Coverage: Application-specific, not wallet-level.

## Adjacent / not-quite-this-guard

### Tenderly tx simulation
- URL: https://tenderly.co/
- What it does: Simulates a tx before broadcast.
- Why adjacent: Catches reverts, including wrong-chain reverts, but not as a dedicated guard.

### EIP-3770 (chain-specific addresses, like `eth:0x...`)
- Why adjacent: Standardization to make cross-chain address handling unambiguous; not yet broadly adopted.

## Where e_AI wrong_chain_address differs

This is the most-solved domain in the v2 set. Rabby has effectively closed the wrong-chain UX gap; MetaMask is catching up. Contract-vs-EOA warnings are industry-standard. The only durable angle for e_AI: (1) profile-driven cross-chain reasoning (e.g., "you usually use this dApp on Arbitrum, but this tx is on Optimism — confirm intent?"), (2) historical-context warnings ("you've never sent to this address on this chain — destination might not exist or might not be controlled by recipient on this chain"). Honest: heuristics here are mostly commodity; the post should probably treat this as a "completeness" guard, not a novelty claim.

## Open positioning question for the post

This domain is largely solved by Rabby and modern MetaMask. Is it worth publishing as a separate guard, or should it fold into a broader "operational hygiene" guard that combines wrong-chain + approval + signature mistakes?

## Sources

- [Rabby Wallet](https://rabby.io/)
- [Rabby vs MetaMask comparison](https://gottagamble.com/guide/rabby-wallet-vs-metamask/)
- [MetaMask issue #13486 — contract warnings](https://github.com/MetaMask/metamask-extension/issues/13486)
- [Coinspect — chainId EIP-712 issue (40+ wallets)](https://www.coinspect.com/blog/chainid-eip-712-implementation-issue/)
- [Stackup — What is an EOA?](https://www.stackup.fi/resources/what-is-an-eoa)
- [Ambire — EOA vs Smart Contract Account](https://blog.ambire.com/eoas-vs-smart-contract-accounts/)
