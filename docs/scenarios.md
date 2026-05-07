# Scenarios — what e_AI catches, in real cases

Each scenario below references a documented real-world incident or measured
empirical result. The "Run it" command points to a runnable demo on
synthetic data structurally matching the cited incident; the demo loads
the domain's profile, fires the rule-based analyzer, and adds local-LLM
behavioral context.

Sources are linked per-scenario; per-guard prior-art and full source list at
[`docs/prior_art/<guard>.md`](prior_art/).

---

## 1. Stealth-address deanonymization (Wahrstätter et al., ACM Web Conf 2024)

**Documented**: Wahrstätter, Ernstberger, Soleimanian, Smaragdakis (arXiv
[2308.01703](https://arxiv.org/abs/2308.01703)) measured the actual
deanonymization rate on the Umbra stealth-address protocol over its full
on-chain history:

| Network | Deanonymization rate |
|---|---|
| Ethereum | **48.5%** |
| Arbitrum | **65.7%** |
| Optimism | **52.6%** |
| Polygon | **25.8%** |

The four heuristics they identified — same-entity withdrawal, gas-price
fingerprinting, timing correlation, funding linkability — are exactly the
ops mistakes a typical user makes without realizing.

**What e_AI catches**: the `stealth_address_ops` guard implements all six
heuristics from the paper (the four above + self-transfer, unique amounts).
Pre-submission, before a stealth-address user signs a withdrawal, the guard
flags timing-too-tight, amount-fingerprint, or paymaster-vs-direct funding
patterns and recommends specific countermeasures.

**Run it**:
```sh
python3 examples/per_domain/stealth_address_ops/demo.py
```

The demo's sample triggers H1 + H3 + H4 + H6 — four critical alerts on a
configuration that would land in the ~48.5% deanon population. The LLM
behavioral layer adds: "Generate a new stealth address... use ERC-4337
paymaster... wait 6-24 hours... round to a standard denomination."

This guard is the **strongest novelty claim** across the substrate. The
academic paper named and measured the problem; to our knowledge, no
production pre-submission runtime defense currently ships with Umbra
integrations covering all four heuristic classes. If you know of one, the
post is the place to push back.

Full prior-art comparison: [`docs/prior_art/stealth_address_ops.md`](prior_art/stealth_address_ops.md)

---

## 2. Approval phishing (Blockaid/SlowMist/Scam Sniffer, 2024-2025 incident class)

**Documented**: per [ScamSniffer's 2024 annual phishing report](https://drops.scamsniffer.io/scam-sniffer-2024-web3-phishing-attacks-wallet-drainers-drain-494-million/),
wallet drainers stole approximately **$494M from 332,000 wallet
addresses in 2024**, with ~85.3% of losses on Ethereum. [Blockaid's
public reporting](https://www.blockaid.io/blog/putting-inferno-drainer-group-out-of-business)
on the dominant Inferno/Angelferno drainer family states the platform
detected and blocked 40K+ Angelferno attack attempts in June 2025 alone.
ScamSniffer's [2025 follow-up](https://drops.scamsniffer.io/scam-sniffer-2025-crypto-phishing-losses-fall-83-to-84-million/)
shows phishing losses fell by ~83% to ~$84M in 2025 — partly as wallet
warnings (Blockaid + integrators) became standard.

The pattern: a user is tricked into signing `approve(spender, MAX_UINT256)`
to a contract whose bytecode matches a known drainer template. The drainer
later drains the user's full token balance.

**What e_AI catches**: the `approval_phishing` guard fires on five
heuristics — unlimited approval, unverified spender contract, scam-DB or
bytecode-template match, suspicious selectors (Permit2 patterns), stale
approvals carrying live exposure.

**Run it**:
```sh
python3 examples/per_domain/approval_phishing/demo.py
```

The demo's sample is structurally a USDC `approve()` for `MAX_UINT256` to a
freshly-deployed unverified contract whose bytecode matches a known drainer
template. The guard fires H1 + H2 + H3, OVERALL CRITICAL, `should_block: true`.
The LLM layer adds context on the combined risk and recommends explicit
revocation.

This is a **mature-coverage cluster** guard. Blockaid, Pocket Universe,
Scam Sniffer, and Revoke.cash all cover the surface comprehensively. e_AI's
contribution here is local execution + profile-driven completeness for a
unified guard set, not novelty in detection.

Full prior-art comparison: [`docs/prior_art/approval_phishing.md`](prior_art/approval_phishing.md)

---

## 3. Pre-submission MEV (jaredfromsubway.eth, 2023; Flashbots MEV-Share data)

**Documented**: per [The Block's May 2023 reporting](https://www.theblock.co/post/230218/jaredfromsubway-mev-bot)
on EigenPhi analysis, a single sandwich bot
([jaredfromsubway.eth](https://etherscan.io/address/0x1f2f10d1c40777ae1da742455c65828ff36df387))
ran approximately **238,000 attacks against 106,000 victims** over a
3-month window in 2023, taking ~$40.65M in revenue / ~$6.3M net profit
after gas. (The net-profit figure is disputed by some pseudonymous MEV
researchers, who estimate proceeds in the $3.5-4.5M range.) Flashbots'
research on [MEV-Share](https://writings.flashbots.net/mev-share-programmably-private-orderflow)
showed that even partial transaction hints are enough for searchers to
profitably extract — the information bar is low, and routine
wallet-broadcast txs already cross it.

[EigenPhi's 2025 data](https://x.com/EigenPhi/status/1998090234442215671)
shows sandwich extraction has compressed: ~$60M total across Ethereum
in the Nov 2024 - Oct 2025 window, with monthly extraction falling from
~$10M to ~$2.5M even as DEX volumes climbed from ~$65B to >$100B
quarterly. The threat class persists; the relative magnitude has eased
as MEV-protection routes (Flashbots Protect, MEV Blocker, CoW) have
become better known.

**What e_AI catches**: the `mev_vulnerability` guard flags pre-submission
risk — high slippage in a public mempool, large swap relative to pool
liquidity, no MEV-protection route configured.

**Run it**:
```sh
python3 examples/per_domain/mev_vulnerability/demo.py
```

The demo's sample triggers H1 + H2 + H4 + H5 on a 3.5%-slippage, public-
mempool, large-swap-relative-to-pool transaction. The LLM layer
recommends: "Submit via Flashbots Protect or MEV Blocker... use CoW Swap,
1inch Fusion, or UniswapX for MEV-protected execution."

**Mature-coverage** cluster. Flashbots Protect, MEV Blocker, CoW Protocol,
1inch Fusion, UniswapX all ship MEV-protection routes. e_AI here is a
*router-recommender* — useful as part of a unified guard set, not a novel
detection.

Full prior-art comparison: [`docs/prior_art/mev_vulnerability.md`](prior_art/mev_vulnerability.md)

---

## 4. Builder/relay censorship — Tornado Cash post-OFAC

**Documented**: After [August 2022 OFAC sanctions on Tornado
Cash](https://home.treasury.gov/news/press-releases/jy0916), several
mev-boost relays added compliance lists. By early 2023, relays such as
**bloXroute Regulated** and **Manifold** systematically censored OFAC-flagged
transactions. [MEV Watch](https://www.mevwatch.info) and
[Censorship.pics](https://censorship.pics) made the censorship rates
publicly visible.

Per the soispoke Dune dashboard
[`privacy-pools-nullifier-state-growth`](https://dune.com/soispoke/privacy-pools-nullifier-state-growth)
(read 2026-05-07), the protocol still saw ~10,781 transactions in the most
recent 90-day window. The framing here is descriptive, not prescriptive: a
substrate that warns users about silent-drop relay behavior helps them make
informed routing choices regardless of jurisdiction or whether they choose
to interact with sanctioned destinations.

**What e_AI catches**: the `builder_censorship` guard flags routing through
known censoring relays, OFAC SDN destination addresses, missing forced-
inclusion fallback on L2, builder monoculture, and the compound
no-circumvention case.

**Run it**:
```sh
python3 examples/per_domain/builder_censorship/demo.py
```

The demo's sample is a worst-case configuration — only `bloxroute_regulated`
+ `manifold` selected, no private mempool, sanctioned-address destination,
narrow recent builder set. All five heuristics fire; OVERALL CRITICAL;
`should_block: true`. The LLM layer recommends adding Flashbots / Ultrasound
to the relay set or routing through a private mempool.

**Mature-coverage** with extension-framework alignment: MEV Watch and
Censorship.pics provide the analysis surface; e_AI is "MEV Watch in your
wallet" — pre-submission rather than retrospective. This guard was added
in a week using only [`adding_a_domain.md`](adding_a_domain.md) — with the
substrate work already in place; first-time contributors should expect
longer.

Full prior-art comparison: [`docs/prior_art/builder_censorship.md`](prior_art/builder_censorship.md)

---

## 5. AI-assistant query leakage (Cyberhaven 2024; ChatGPT history exposure)

**Documented**: [Cyberhaven](https://www.cyberhaven.com/blog/4-2-of-workers-have-pasted-company-data-into-chatgpt)
reports ~4.7% of enterprise users have pasted confidential data into
ChatGPT (with ~8.6% having pasted any company data); the average
company "leaks confidential material to ChatGPT hundreds of times per
week." [404 Media documented 130K+ conversations](https://www.404media.co/more-than-130-000-claude-grok-chatgpt-and-other-llm-chats-readable-on-archive-org/)
across Claude, Grok, ChatGPT, and other LLM products archived on the
Internet Archive's Wayback Machine — users who clicked "Share" without
realizing the link was public created a permanent searchable record.
Even though OpenAI later disabled public link sharing, the Wayback
Machine archives are not retroactively purged.

This is the threat model of the original e_AI Part 1: *cloud LLM queries
leak intent before the user has even submitted a transaction*. The same
pattern at the **RPC layer** is `rpc_leakage`'s domain.

**What e_AI catches**: the `rpc_leakage` guard flags query patterns that
reveal user strategy or portfolio to an RPC provider — balance-check
sequences, log scans on monitored addresses, eth_getStorageAt sweeps,
multi-address balance polling.

**Run it**:
```sh
python3 examples/per_domain/rpc_leakage/demo.py
```

The demo's sample is a sustained RPC-monitoring session that reveals an
arbitrage-hunting pattern. H1 + H2 + H3 fire. The LLM layer recommends
batching, randomizing query timing, or routing through a privacy-preserving
RPC service.

**Strong-novelty cluster.** RPCh, Helios, and Nym handle the *transport
layer* (route queries through privacy-preserving networks). No tool
detects *pattern-level* leakage at the application layer. This guard is in
a genuinely under-served niche.

Full prior-art comparison: [`docs/prior_art/rpc_leakage.md`](prior_art/rpc_leakage.md)

---

## 6. Post-mixer behavioral linkage (Tutela / Pareto-xyz)

**Documented**: Tutela ([github.com/pareto-xyz/tutela-app](https://github.com/pareto-xyz/tutela-app))
applied seven heuristics — address match, gas-price reveal, denomination
reveal, timing correlation, etc. — to Tornado Cash deposit-withdrawal pairs.
The result: **42,852 out of 97,331 deposits compromised** (~44%) by
behavioral mistakes that survived the mixer.

The 2025 cross-chain heuristics work extended this to bridge usage,
DEX-swap sequence patterns, and post-mixer denomination correlations
across L1↔L2.

**What e_AI catches**: the `mixing_behavioral` guard fires pre-withdrawal
on patterns that would survive the mixing step — recently used same gas
price, denomination matching upstream deposit, timing-too-tight.

**Run it**:
```sh
python3 examples/per_domain/mixing_behavioral/demo.py
```

The demo runs the rule-based analyzer (`domains/mixing_behavioral/analyzer.py`,
covering all five heuristics algorithmically against a `MixerWithdrawal`
input dataclass) and adds LLM behavioral context. The analyzer accepts
chain-data inputs the production deployment must wire — pool deposit-
count windows, address-cluster behavioral matching, gas-price block
stats, planned-post-withdrawal-action prediction.

**Strong-novelty cluster.** Tutela and the 2025 cross-chain work define
the heuristic set; both are post-hoc auditors. To our knowledge, no
production pre-withdrawal runtime guard ships against this heuristic
family today. e_AI's contribution is the framing + a runnable
rule-based analyzer; the load-bearing remaining item is real-incident
calibration.

Full prior-art comparison: [`docs/prior_art/mixing_behavioral.md`](prior_art/mixing_behavioral.md)

---

## A note on data and limitations

Each scenario above cites a real incident or measured study. The
`sample_tx.json` files in the per-domain demos are **synthetic**
transactions structurally matching the cited threat — not captured
real-incident transactions. False-positive and false-negative rates
against real corpora are unknown. A production deployment would replace
synthetic samples with labeled real-incident corpora; the meta-framework's
bootstrap and validation engine are designed to ingest exactly that.
Real-incident corpora is the load-bearing future-work item.

For the full set of guards (16 production domains) and per-guard prior-art:
- Index: [README.md](../README.md#whats-available)
- Per-guard: [`domains/<name>/README.md`](../domains/) and [`docs/prior_art/<name>.md`](prior_art/)
