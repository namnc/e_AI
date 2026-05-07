# Prior art — approval_phishing

## What this guard catches (one line)
Malicious ERC-20 / ERC-721 / Permit2 approval transactions that grant a hostile spender access to user balances (unlimited allowances, unverified spenders, scam-DB hits, suspicious selector patterns, stale unrevoked approvals).

## Existing tools that implement this (FULL or substantive coverage)

### Blockaid
- URL: https://www.blockaid.io/token-scanning, https://www.blockaid.io/platform
- What it does: Real-time pre-signature transaction security engine; simulates and classifies token approvals against an internet-wide threat-intel feed of malicious tokens, drainer contracts, and phishing dApps. Integrated into MetaMask, Rainbow, Coinbase Wallet, Phantom, Zerion, OpenSea, Uniswap, World App.
- Coverage of the heuristic set: Covers (a) known-bad spender DB, (b) drainer/dApp scanning, (c) approval-as-action simulation, (d) Permit/Permit2/EIP-712 off-chain approval scanning. Less explicit on "stale approval hygiene."
- Notable: Blocked 40K+ Angelferno drainer attempts in a single month (June 2024); reported $200M+ in approval-attack losses in 2024-2025. Industry-leading in coverage and integration footprint.

### Pocket Universe
- URL: https://pocketuniverse.app/
- What it does: Browser extension that simulates each transaction on a forked chain before signing, with explicit warnings for "approval-for-all" patterns, honeypot NFTs, and counterfeit tokens.
- Coverage of the heuristic set: Covers (a) unlimited approval flag, (b) drainer signature simulation, (c) phishing-dApp blocklist. Less coverage of "stale approvals" — focuses on point-in-time signing.
- Notable: User-facing, simulation-first UX; popular with retail.

### Scam Sniffer
- URL: https://scamsniffer.io/
- What it does: Multi-layer Web3 anti-phishing — Web3 Safe Browsing for malicious sites + signature security checks + token-approval monitoring + drainer-signature DB.
- Coverage of the heuristic set: Covers (a) phishing-site DB, (b) malicious signature classifier, (c) approval risk surface. Strong on phishing-site detection, weaker on simulation.
- Notable: Publishes monthly phishing reports; widely cited as the public phishing-loss tracker.

### Revoke.cash
- URL: https://revoke.cash/, https://revoke.cash/learn/approvals/what-are-token-approvals
- What it does: Allowance-management tool for revoking past approvals + approval-warning browser extension that flags risky approvals at signing time.
- Coverage of the heuristic set: Covers (a) stale-approval hygiene (its origin function), (b) unlimited-approval flag, (c) known-bad spender warnings. Best-in-class for the "stale approval" heuristic specifically.
- Notable: The de-facto consumer tool for cleaning up old approvals.

## Existing tools that implement this PARTIALLY

### Wallet Guard
- URL: https://www.walletguard.app/
- What it does: Browser extension flagging malicious dApp connections + transaction simulation + approval warnings.
- Coverage: Approval phishing flagged as part of broader dApp security UX; not a deep approval-specific tool.
- Notable: Acquired by Consensys; integrated into MetaMask flows.

### Forta Scam Detector Bot
- URL: https://docs.forta.network/en/latest/scam-detector-bot/
- What it does: Decentralized network of detection bots; scam-detector bot uses heuristics + ML to flag phishing/drainer addresses.
- Coverage: Address-level flagging that downstream wallets can consume; not a UX surface itself.
- Notable: Open architecture — anyone can publish a detection bot.

### Rabby Wallet (built-in pre-tx scanner)
- URL: https://rabby.io/
- What it does: Pre-transaction risk scanning + balance-change preview; flags risky approvals natively.
- Coverage: Approval phishing covered as one risk class among many; integrated into wallet UI.
- Notable: Often cited as best wallet UX for approval-risk surfacing.

## Adjacent / not-quite-this-guard

### Token Sniffer
- URL: https://tokensniffer.com/
- What it does: Smart-contract scam scanner that audits token contracts for honeypot / rug indicators.
- Why adjacent: Scans the *token*, not the *approval*. Different surface.

### D'CENT Wallet (Blockaid-powered)
- URL: D'CENT integrates Blockaid downstream.
- Why adjacent: Wallet integrator, not an independent detector.

## Where e_AI approval_phishing differs

The dominant tools (Blockaid, Pocket Universe, Scam Sniffer) run as centralized SaaS or browser extensions that send transaction context to a remote server. e_AI runs entirely local — the analysis itself does not leak portfolio state. This is the privacy-preservation angle, not the detection-quality angle. e_AI's profile-driven framing is also more transparent (user can read the heuristic set), unlike Blockaid's proprietary model. Honest assessment: detection coverage is likely behind Blockaid; the differentiator is privacy + auditability + composability with other local guards.

## Open positioning question for the post

Detection quality almost certainly trails Blockaid (which has dedicated threat-intel and integration with most major wallets). Is the local-execution / privacy / auditability angle enough to publish — or should the framing be "privacy-preserving complement to Blockaid" rather than "alternative to Blockaid"?

## Sources

- [Blockaid Token Scanning](https://www.blockaid.io/token-scanning)
- [Blockaid Platform](https://www.blockaid.io/platform)
- [Pocket Universe](https://pocketuniverse.app/)
- [Scam Sniffer Chrome extension](https://chromewebstore.google.com/detail/scam-sniffer/mnkbccinkbalkmmnmbcicdobcmgggmfc)
- [Revoke.cash — What Are Token Approvals](https://revoke.cash/learn/approvals/what-are-token-approvals)
- [Wallet Drainers (Blockaid blog)](https://www.blockaid.io/blog/wallet-drainers-vitalik-metamask)
- [Forta Scam Detector Bot](https://docs.forta.network/en/latest/scam-detector-bot/)
- [Rabby Wallet](https://rabby.io/)
