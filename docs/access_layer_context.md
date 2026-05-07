# Access-Layer Context — where e_AI fits

This substrate sits at Ethereum's **access layer** — the composition surface
between the protocol and the user. It does not change protocol behavior;
it augments how the user interacts with the chain. This document places
e_AI within the broader privacy/safety roadmap currently under active
discussion in 2026.

## The architecture map (concrete primitives, real authors, real URLs)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  END USER                                                                │
│  (a wallet user, an agent operator, a DApp visitor)                      │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────────┐
│  INTEGRATION SURFACES                                                    │
│  Wallets · DApps · Agents · RPC proxies · L2 monitors                    │
│                                                                          │
│  e_AI ships 5 reference surfaces under examples/                         │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────────┐
│  ACCESS LAYER                                ← this is where e_AI lives  │
│                                                                          │
│  Pre-submission guards · Trust-quorum services · Off-chain coordination  │
│  · Cover-query orchestration · Local LLM behavioral analysis             │
│                                                                          │
│  e_AI's 16 guards compose at this layer (see docs/composition.md)        │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────────┐
│  PROTOCOL ENABLING PRIMITIVES                                            │
│                                                                          │
│  • Auth abstraction         — EIP-8141 (Frame Transaction)               │
│  • Ordering / mempool       — Encrypted frame transactions, LUCID-class  │
│  • Specialized storage      — 2D nonces, dedicated nullifier store       │
│  • Forced inclusion         — FOCIL (Forced Inclusion Committee List)    │
│                                                                          │
│  All four are roadmap items as of May 2026 (see references below)        │
└──────────────────────────────────────────────────────────────────────────┘
```

## What each protocol-level primitive does

### 1. EIP-8141 — Frame Transactions (auth abstraction)

**Source**: [EIP-8141](https://eips.ethereum.org/EIPS/eip-8141);
[Vitalik on FOCIL + EIP-8141 synergy](https://x.com/VitalikButerin/status/2024523896360464791);
[Openfort: What EIP-8141 means for developers](https://www.openfort.io/blog/eip-8141-means-for-developers).

A new transaction type with multiple "frames" — VERIFY frame, EXECUTE
frame — that can define custom validation and payment logic. The
practical consequence: smart accounts (multisig, quantum-resistant
signatures, key changes, gas sponsorship) and **privacy protocols**
become first-class citizens.

For privacy specifically, soispoke ([Mar 19 2026 thread](https://x.com/soispoke/))
notes that with EIP-8141, "**Alice constructs a frame transaction. A
paymaster contract in a VERIFY frame covers her gas on-chain. She submits
directly to the mempool. No single party gets a preview of Alice's
calldata.**" This eliminates the broadcaster/relayer dependency that
current privacy protocols (Tornado Cash, Privacy Pools, Railgun) rely on.

**What e_AI does given this**: the `stealth_address_ops` H4 mitigation
("ERC-4337 paymaster funding") naturally migrates to a first-class
EIP-8141 paymaster. The `pq_stealth_address` Phase 1 spec includes a
migration path. The wallet-side guards (`approval_phishing`,
`offchain_signature`, `mev_vulnerability`) all benefit from the wallet
controlling its own pre-sign flow rather than handing off to a relayer.

### 2. 2D nonces — specialized nullifier storage

**Source**: [Vitalik on keyed nonces and restricted state types (X, May 2026)](https://x.com/VitalikButerin/status/2051675198068330996);
soispoke Mar 19 2026 thread.

Privacy contracts use **validation-phase-only storage** to hold nullifiers
as independent nonce keys. Each transaction gets its own nonce key derived
from its nullifier. Different users with different nullifiers use different
nonce keys, so transactions process **in parallel without broadcasters**.

Per Vitalik's framing, this is part of a broader thesis: "create new
types of storage that are more optimized for handling categories of use
cases that we care about, with restrictions on their use that make them
usable at extreme scale while preserving the protocol's decentralization."
At 2000 TPS privacy-preserving × 8 years = **500 billion nullifiers**;
feasible on a dedicated nullifier store (sharding + ~8-bit-per-nullifier
bloom filter compression both viable), infeasible on dynamic state (16 TB
viable-builder threshold, FOCIL-Merkle-branch problem).

**What e_AI does given this**: the access-layer guards stay agnostic to
the underlying storage class; a privacy-pool guard like `l2_anonymity_set`
still surfaces pool thinness regardless of whether the pool is implemented
on dynamic state or specialized nullifier storage. The framework should
absorb 2D-nonce-specific signals as the substrate matures.

### 3. Encrypted frame transactions — ordering / mempool privacy

**Source**: soispoke Mar 19 2026 thread; LUCID design discussions on
encrypted mempools; EIP-7732 (ePBS) as a substrate for separating
ordering from execution.

A frame transaction's execution phase can be **encrypted** — only the
VERIFY frame is public. Concretely:

```
exec_params = RLP(blinding_nonce, target, calldata, priority_fee, padding)
```

`target` (e.g., the Uniswap router via the privacy-protocol adapter),
`calldata` (the swap parameters), and `priority_fee` are all hidden
until the block decrypts.

**What e_AI does given this**: the wallet-side `mev_vulnerability` and
`offchain_signature` guards still inspect the local intent — that is, the
unencrypted execution parameters as the user sees them, before the
encrypted-frame envelope is constructed. The encryption protects against
mempool observers; the guards protect against the user signing a malicious
intent in the first place. These are complementary, not redundant.

### 4. FOCIL — Forced Inclusion Committee List

**Source**: [FOCIL + EIP-8141 design](https://www.thecoinrepublic.com/2026/02/22/vitalik-buterin-reveals-focil-eip-8141-design-that-could-guarantee-1-2-slot-transaction-inclusion/);
soispoke Mar 19 2026 thread.

A rotating committee of inclusion-list publishers. Each publishes the
transactions they have seen and validated. If a builder omits a listed
transaction without a valid excuse, it loses attestations. With EIP-8141
+ FOCIL together, privacy-protocol transactions get **guaranteed inclusion
within 1-2 slots through one of 17 randomly-selected actors**.

**What e_AI does given this**: the `builder_censorship` guard's H3 (L2
forced-inclusion path) and the recommendation set point at FOCIL as the
escape hatch. Once FOCIL ships, the guard's decision tree changes — but
the heuristics still apply (the user still needs to know whether their
chosen relay set is censoring before they hand a tx off).

### Why these four are insufficient — soispoke's residual gaps

After all four protocol upgrades land, two gaps remain (per soispoke's
final tweet in the Mar 19 thread):

1. **IP exposure** — Alice's network peers see her IP on first submission.
   Wallet should route initial submission through Tor or a mixnet.
   *No protocol upgrade addresses this.*

2. **Post-execution traces** — after the encrypted frame decrypts, the
   on-chain trace is permanent. Repeated trades from the same shielded
   balance with recognizable patterns enable behavioral fingerprinting.
   Pre-execution metadata (fee fields, gas amounts, key-releaser identity,
   timing) helps classify. *Removing this requires private execution
   state, which is not currently planned on L1 in the short term.*

**These two gaps are exactly the access-layer's responsibility.** e_AI's
`rpc_leakage` and `behavioral_drift` guards address parts of this; Tor /
mixnet routing is wallet-level UX (e_AI does not solve this directly).
The substrate is **persistently necessary** alongside the protocol
upgrades — not a temporary patch awaiting protocol perfection.

## What's blocking the architecture today (the "Three Gates" analysis)

Nero_eth's [*Frame Transactions and the Three Gates to
Privacy*](https://ethresear.ch/t/frame-transactions-and-the-three-gates-to-privacy/24666)
(April 2026) catalogues why current Ethereum consensus rules block privacy
transactions even where the protocol primitives above land:

| Gate | What it requires | Why privacy txs fail |
|---|---|---|
| 1. Public mempool admission | Validation under gas / opcode / storage caps | Groth16 pairing checks exceed `100k` `MAX_VERIFY_GAS` cap |
| 2. FOCIL eligibility | Verification within per-tx FOCIL gas budget | Privacy verification exceeds the budget; FOCIL excuses these txs |
| 3. Node validation capability | Sufficient state to validate the tx | VOPS / AA-VOPS partial-state nodes don't track pool-contract storage |

Nero_eth recommends five specific consensus changes — recognize canonical
privacy pools by code hash; raise per-tx VERIFY gas cap to ~400k for
canonical contracts; validation-index FOCIL enforcement (`O(k)` not
`O(k²)`); raise `MAX_VERIFY_GAS_PER_INCLUSION_LIST` to ~1M; relax bounded
state-access rules for canonical privacy contracts.

**What e_AI does given this**: the substrate is designed to compose with
whichever subset of these protocol changes ships and in whatever order.
The guards are thin enough that the access-layer composition does not need
to wait for a particular consensus outcome.

## Where this fits — a thesis statement

Three claims:

1. **The protocol layer should provide bounded enabling primitives**, not
   complete privacy/safety solutions. The four primitives above are the
   right scope for protocol; everything else composes on top.

2. **The access layer is permanently necessary.** Even with all four
   protocol primitives shipped, IP exposure + post-execution traces +
   user-experience composition + heuristic detection of operational
   mistakes all live at the access layer. e_AI is one such composition.

3. **The substrate is publishable now**, before the protocol primitives
   ship, because the access-layer composition is independent of the
   underlying primitives. Today's wallet users already face stealth-
   address deanon (Wahrstätter 48.5%), approval phishing (Blockaid 40K
   blocks/month), MEV (jaredfromsubway.eth $40.65M), builder censorship
   (Tornado Cash post-OFAC). The guards address these now and continue to
   address them after the protocol primitives land.

## How others can expand or upgrade

The substrate is intentionally small. Expansion paths visible from here:

### Add a new domain (existing capability)

Step-by-step in [`docs/adding_a_domain.md`](adding_a_domain.md). Concrete
examples: `builder_censorship` was added in one week using only that
walkthrough; the framework's claim of "task-agnosticism" was tested by
moving from query sanitization (Parts 1, 3) to transaction analysis (this
substrate). A future researcher adding a domain in adjacent space (e.g.,
**sybil multi-wallet linkability**, **frontend phishing / URL
verification**, **post-mixer chain-bridging fingerprints with new 2025
cross-chain heuristics**) follows the same pattern.

### Wire a real-data corpus (high-leverage future work)

All current per-domain `data/labeled_incidents.jsonl` files are synthetic
(≥5 entries each). Replacing them with real-incident corpora would
re-calibrate the heuristic confidence values + enable real ROC-curve
benchmarks. The validation engine's `F4_confidence_calibration` check
enforces *spread* across heuristics, not absolute correctness — that
ground truth requires data the substrate is designed to ingest. Concrete
candidates:

- **Approval phishing**: Forta event archives, Blockaid public reports,
  ScamSniffer wallet-drainer corpus
- **Stealth address ops**: Wahrstätter et al.'s analysis dataset
  (Umbra full on-chain history)
- **Mixing behavioral**: Tutela's compromised-deposit set (~42.8K records
  documented)
- **Builder censorship**: MEV Watch / Censorship.pics archives

### Tighten the rule-based analyzers

All 16 guards ship rule-based `analyzer.py`. Several heuristics still
take input flags from the caller rather than computing them
algorithmically (address-book lookalike detection, deniable-encryption
soundness, deliberate-strategy-vs-drift classification). Contributors
can replace these input flags with computed signals as the substrate
matures — the analyzer source documents which fields are meant to be
wired from a chain-data integration vs from a user-side configuration
or address book.

### Wire a new integration surface

Five surfaces ship today (RPC proxy, wallet EIP-1193, DApp frontend, AI
agent, L2 monitor) plus the Kohaku composition reference. Adjacent surfaces
that the framework supports cleanly:

- **Mobile wallet** (Android / iOS — pattern would mirror the EIP-1193
  guard but in native)
- **Hardware wallet** integration (pre-sign hook on the device)
- **Layer-2 sequencer-side guard** (operator-level analysis at submission)
- **Policy-driven CI guard** for institutional users (review every signed
  tx against a policy bundle)

### Compose with adjacent ecosystems

The substrate is local-first by design but composes naturally with:

- **Blockaid / Pocket Universe / Scam Sniffer** — e_AI provides local-
  execution complement to these centralized SaaS scanners. A wallet could
  run e_AI locally + query Blockaid for known-bad lists.
- **Helios light client / RPCh / Nym** — transport-layer privacy beneath
  e_AI's pattern-detection layer.
- **CoW Protocol / Flashbots Protect / MEV Blocker** — execution-path
  privacy beneath e_AI's pre-submission risk classification.
- **Kohaku** — the canonical wallet substrate the integration demo targets.

## References

### Primary sources cited above

- Vitalik Buterin — [*keyed nonces and restricted state types*](https://x.com/VitalikButerin/status/2051675198068330996) (X, May 2026); core thesis on specialized state types as a new state-scaling strategy
- soispoke — Mar 19 2026 thread on frame transactions, 2D nonces,
  encrypted frame, FOCIL composition. Author profile:
  [@soispoke on X](https://x.com/soispoke). The specific thread anchor
  is not embedded here; locate via the author profile.
- soispoke.eth — [Privacy Pools nullifier-state-growth Dune
  dashboard](https://dune.com/soispoke/privacy-pools-nullifier-state-growth)
- Nero_eth — [*Frame Transactions and the Three Gates to
  Privacy*](https://ethresear.ch/t/frame-transactions-and-the-three-gates-to-privacy/24666),
  ethresear.ch (April 16, 2026)
- [EIP-8141 — Frame Transaction](https://eips.ethereum.org/EIPS/eip-8141)
- Vitalik on [FOCIL + EIP-8141
  synergy](https://x.com/VitalikButerin/status/2024523896360464791)

### Empirical sources for the threat model

- Wahrstätter, Ernstberger, Soleimanian, Smaragdakis — *Anonymity Analysis
  of the Umbra Stealth Address Scheme* ([arXiv 2308.01703](https://arxiv.org/abs/2308.01703),
  ACM Web Conf 2024) — 48.5% Ethereum deanon rate
- Tutela / Pareto-xyz —
  [tutela-app](https://github.com/pareto-xyz/tutela-app) — 42.8K of 97.3K
  Tornado Cash deposits compromised
- jaredfromsubway.eth Etherscan profile — single MEV bot, $40.65M
  revenue / ~$6.3M net profit over ~3 months of 2023 (per [The Block's reporting on EigenPhi analysis](https://www.theblock.co/post/230218/jaredfromsubway-mev-bot); net-profit figure disputed by some MEV researchers)
- [MEV Watch](https://www.mevwatch.info) and
  [Censorship.pics](https://censorship.pics) — relay-level censorship rates
  post-OFAC
- Cyberhaven analysis (4.7% of enterprise users pasted confidential data
  into AI chat tools)
- 130,000+ AI conversations exposed via Wayback Machine (404 Media,
  Washington Post, SafetyDetectives)

### e_AI series

- *The Private Query Problem* (Part 1) — [`ethresearch_post.md`](../ethresearch_post.md)
- *Active Adversaries and Verifiable Inference* (Part 2) —
  [`companion_post_active_adversary.md`](../companion_post_active_adversary.md)
- *A Meta-Framework for Domain-Agnostic Privacy Protection* (Part 3) —
  [`ethresearch_meta_framework_draft.md`](../ethresearch_meta_framework_draft.md)
- *From DeFi Sanitization to Pre-Submission Transaction Guards* (this
  substrate) — [`ethresearch_v2_guards_draft.md`](../ethresearch_v2_guards_draft.md)
