<!-- AI-assisted, human-reviewed before publication. -->

# From DeFi Sanitization to Pre-Submission Transaction Guards

**Where the access-layer privacy/safety problem sits, and what its
composition surface looks like.**

This is a standalone post; it references prior work in the e_AI series
(Parts 1, 2, 3) as background but does not assume it.

---

## TL;DR

- Privacy and safety at Ethereum's access layer is currently microscopic
  in mainnet activity — Privacy Pools + Railgun + Tornado Cash combined
  ≈ 0.0055 sustained tx/s, ~0.025% of mainnet (per [soispoke's 2026-05-07
  Dune dashboard](https://dune.com/soispoke/privacy-pools-nullifier-state-growth)).
- Yet operational mistakes at the access layer have measured impact in
  the hundreds of millions: 48.5% Umbra deanon (Wahrstätter, ACM Web Conf
  2024); 42,852 of 97,331 Tornado Cash deposits compromised by behavioral
  heuristics (Tutela); ~$40.65M revenue / ~$6.3M net profit extracted by
  one sandwich bot over 238K attacks against 106K victims in 3 months of
  2023 ([The Block](https://www.theblock.co/post/230218/jaredfromsubway-mev-bot));
  ~$494M lost to wallet drainers in 2024 across 332K addresses
  ([ScamSniffer](https://drops.scamsniffer.io/scam-sniffer-2024-web3-phishing-attacks-wallet-drainers-drain-494-million/)).
- Protocol-level work is converging on a coherent set of enabling
  primitives — EIP-8141 frame transactions, 2D nonces / specialized
  nullifier storage, encrypted frame transactions, FOCIL forced-inclusion
  — per [Vitalik's recent post](https://x.com/VitalikButerin/status/2051675198068330996),
  soispoke's Mar 19 thread, and [Nero_eth's *Three Gates* analysis](https://ethresear.ch/t/frame-transactions-and-the-three-gates-to-privacy/24666).
- Even after every protocol primitive lands, the access layer is
  **permanently** necessary: IP exposure, post-execution traces, and
  heuristic ops-mistake detection cannot be solved at the protocol level.
- The access-layer composition surface comprises three parts: centralized
  SaaS scanners, local-first profile-driven complements, and wallet/agent
  integration surfaces. All three are needed.
- We open-source one such local-first complement: 16 profile-driven guards
  across the 4 access methods to Ethereum, runnable end-to-end with a
  local LLM behavioral layer. Source: https://github.com/namnc/e_AI
  (`v2` branch). Offered as a **potential tooling direction**, not a
  finished defense.

---

## 1. The access-layer problem, in measured numbers

Ethereum's access layer is the surface where users actually interact
with the chain through wallets, agents, DApps, and L2s. It is also where
most operational privacy and safety losses happen.

A few documented data points:

- **48.5%** of Umbra stealth-address users on Ethereum are deanonymized
  by operational mistakes — same-entity withdrawal, gas-price reuse,
  timing correlation, funding linkability (Wahrstätter, Ernstberger,
  Soleimanian, Smaragdakis, [arXiv 2308.01703](https://arxiv.org/abs/2308.01703),
  ACM Web Conf 2024). The same paper measures 65.7% on Arbitrum, 52.6%
  on Optimism, 25.8% on Polygon.
- **42,852 of 97,331** Tornado Cash deposits compromised by post-deposit
  behavioral heuristics that survive the mixing step
  ([Tutela / Pareto-xyz](https://github.com/pareto-xyz/tutela-app), 7
  heuristics).
- One MEV bot ([jaredfromsubway.eth](https://etherscan.io/address/0x1f2f10d1c40777ae1da742455c65828ff36df387))
  ran ~238,000 sandwich attacks against ~106,000 victims in 3 months of
  2023, taking ~$40.65M revenue / ~$6.3M net profit per
  [The Block's reporting on EigenPhi analysis](https://www.theblock.co/post/230218/jaredfromsubway-mev-bot)
  (the net-profit figure is disputed by some MEV researchers).
  [EigenPhi's 2025 data](https://x.com/EigenPhi/status/1998090234442215671)
  shows sandwich extraction has compressed since — ~$60M total Nov
  2024 - Oct 2025 across Ethereum, monthly extraction falling from
  ~$10M to ~$2.5M as MEV-protection routes have become better known.
- **~$494M** lost to wallet drainers in 2024 across 332,000 addresses,
  85.3% on Ethereum
  ([ScamSniffer 2024 annual report](https://drops.scamsniffer.io/scam-sniffer-2024-web3-phishing-attacks-wallet-drainers-drain-494-million/)).
  ScamSniffer's 2025 follow-up shows losses fell ~83% to ~$84M as
  wallet-side warnings (Blockaid + integrators) became standard.
  [Blockaid's reporting](https://www.blockaid.io/blog/putting-inferno-drainer-group-out-of-business)
  on the dominant Inferno/Angelferno drainer family states the
  platform detected and blocked 40K+ Angelferno attempts in June 2025
  alone.

The asymmetry is striking: privacy and safety usage at the access layer
is a microscopic share of Ethereum activity (combined Privacy Pools +
Railgun + Tornado Cash throughput ~0.025% of mainnet per soispoke's data)
while measured operational losses are hundreds of millions of dollars.
**Privacy at the access layer is under-deployed, not over-deployed.**

---

## 2. The protocol-level roadmap is converging

A coherent set of enabling primitives is being designed at the protocol
layer, and the contours are clearer than they were six months ago:

| Primitive | What it provides | Primary source |
|---|---|---|
| **Native AA + paymaster (EIP-8141)** | Wallet-side construction of frame transactions; a paymaster contract in a VERIFY frame covers gas; user submits directly without a relayer broadcasting on her behalf | [EIP-8141](https://eips.ethereum.org/EIPS/eip-8141); [Vitalik on FOCIL + EIP-8141 synergy](https://x.com/VitalikButerin/status/2024523896360464791) |
| **2D nonces + specialized nullifier storage** | Privacy contracts use validation-phase-only storage to hold nullifiers as independent nonce keys; restricted-use storage scales differently from fully-dynamic state | [Vitalik on keyed nonces and restricted state types](https://x.com/VitalikButerin/status/2051675198068330996) and the [linked Fileverse bloom-filter proposal](https://docs.fileverse.io/d/020001fc0012#k=UT7Btd6tyqHgOj47t-TX06F8D6OpcpM_2PKdf7s4tGE) |
| **Encrypted frame transactions** | Public VERIFY frame + hidden encrypted execution params (`target`, `calldata`, `priority_fee`); execution payload only decrypts after inclusion | soispoke Mar 19 2026 thread (LUCID-class encrypted-mempool design pattern) |
| **FOCIL** | Rotating committee of inclusion-list publishers; builders that omit listed transactions without valid excuse lose attestations | soispoke Mar 19 2026 thread; [Nero_eth's *Three Gates*](https://ethresear.ch/t/frame-transactions-and-the-three-gates-to-privacy/24666) on the consensus-rule blockers |

Nero_eth's *Three Gates* post catalogues the consensus-rule changes that
need to land for these primitives to function (Groth16 100k gas cap,
FOCIL eligibility constraints, partial-state node validation), recommends
five specific changes, and argues the architecture is feasible.

---

## 3. What the protocol roadmap leaves on the access layer

After all four protocol primitives ship, two structural gaps remain (per
the closing of soispoke's Mar 19 thread):

1. **IP exposure** — Alice's network peers see her IP on first
   transaction submission. Wallet must route initial submission through
   Tor or a mixnet so the IP never touches the gossip network in the
   clear. *No protocol upgrade addresses this.*

2. **Post-execution traces** — after the encrypted frame decrypts, the
   on-chain trace is permanent. Repeated trades from the same shielded
   balance with recognizable patterns enable behavioral fingerprinting;
   pre-execution metadata (fee fields, gas amounts, key-releaser
   identity, timing) helps classify. *Removing this requires private
   execution state, which is not on the L1 short-term roadmap.*

A third class belongs to the same gap: **heuristic detection of
operational mistakes**. The user signs an EIP-712 typed-data with a
malicious permit; sets an unlimited approval to a phishing contract;
withdraws from a stealth address with timing-too-tight; monitors five
wallets every six hours through a single RPC provider. None of these is
a protocol-design failure; all of them are user-experience choices a
wallet UI can catch pre-submission with a profile of known-bad patterns
plus behavioral heuristics.

These three gaps — IP exposure, post-execution traces, ops-mistake
detection — are not interim work waiting on protocol completion. They
are **permanently access-layer responsibility**, because the protocol
layer cannot solve them without taking on far more than its appropriate
scope.

---

## 4. The access-layer composition surface

The access layer composes three things.

**Centralized SaaS scanners.** Blockaid, Pocket Universe, Scam Sniffer,
Wallet Guard, Veritas, Revoke.cash and others run continuously-updated
threat-intel feeds and integrate into mainstream wallets. For approval
phishing, EIP-712 phishing, and known-scam-DB lookups, these tools'
update cadence and integration footprint are genuinely better than any
local-first system can match. They are part of the access-layer answer.

**Local-first profile-driven complements.** Centralized SaaS sees every
transaction the user is about to sign — that's a metadata surface. Some
user populations (privacy-focused users, sovereignty-conscious users,
jurisdictions where SaaS is constrained, integrators avoiding vendor
lock-in) want a local layer. Specifically: there are several heuristic
classes that no centralized SaaS scanner currently covers — stealth-
address operational mistakes (the Wahrstätter 48.5% problem),
RPC-pattern leakage at the application layer (transport-layer tools
like Helios / RPCh / Nym don't catch sustained-query patterns),
post-mixer behavioral linkage as pre-withdrawal warning (Tutela is a
post-hoc auditor), defensive runtime against cross-chain forensics
(Chainalysis-class tools operate the offensive side; the user-side
defensive runtime is unfilled). For these, local-first is not a
complement; it's the only available defensive position.

**Wallet, DApp, and agent integration surfaces.** These are the channels
through which the SaaS and local-first layers actually reach the end
user — pre-sign hooks in a wallet (EIP-1193 wrapper, MetaMask plugin),
browser SDKs in a DApp, pre-action checklists in an AI agent, RPC
proxies for query-pattern monitoring, L2 monitors for cross-chain
awareness.

The access-layer composition is all three working together. Saying
"Blockaid covers approval phishing" is true; saying "the access layer
needs only Blockaid" misses the niches that local-first fills and the
integration work that wallets, DApps, and agents must do regardless.

---

## 5. A concrete local-first complement: e_AI v2

We open-source one such substrate at https://github.com/namnc/e_AI
(`v2` branch).

The architecture is profile-driven. Each guard is a JSON profile listing
heuristics, signals, severities, recommendations, fundamental
limitations, and benchmark scenarios. An 11-check validation engine
enforces structural integrity. A rule-based analyzer fires per-heuristic
where detection is algorithmic. A local LLM behavioral layer (Ollama /
`qwen2.5:7b` by default; graceful degradation if the LLM is unavailable)
augments with natural-language reasoning. The same profile schema +
validation engine + bootstrap pipeline came from the meta-framework we
built for DeFi query sanitization (Part 3), generalized to this new
task with bounded modifications.

Sixteen profile-validated guards organize around the four access methods
to Ethereum:

- **Wallet** (8 guards): `approval_phishing`, `backup_security`,
  `behavioral_drift`, `mev_vulnerability`, `offchain_signature`,
  `pq_readiness`, `stealth_address_ops`, `wrong_chain_address`
- **Application** (3 guards): `cross_protocol_risk`,
  `governance_proposal`, `mixing_behavioral`
- **AI agent** (1 guard): `rpc_leakage`
- **L2** (4 guards): `builder_censorship`, `l2_anonymity_set`,
  `l2_bridge_linkage`, `sequencer_privacy`

`builder_censorship` was added in one week using only the documented
extension walkthrough — but with the substrate work already in place;
first-time contributors should expect longer. The exercise was a
deliberate test of whether the framework supports new domains without
internal hand-holding.

Five integration surfaces ship as runnable demos: AI-agent guard
(Python), wallet EIP-1193 wrapper (TypeScript), DApp frontend SDK
(JavaScript), L2 monitor (Python), Kohaku-style middleware (TypeScript),
plus an RPC proxy for query-pattern monitoring. Each guard ships its own
demo at `examples/per_domain/<name>/`.

Per-guard prior-art research lives in `docs/prior_art/<name>.md` (16
files); composition across the transaction lifecycle is in
`docs/composition.md`; concrete end-user scenarios in
`docs/scenarios.md`.

---

## 6. Honest scope — where this complements vs where it doesn't

Reading the prior-art for each guard gives an uncomfortable but honest
picture. We organize the 16 guards into clusters:

**Strong-novelty (4 guards): genuinely under-served niches.**

- `stealth_address_ops` operationalizes Wahrstätter's heuristics into a
  runtime, pre-submission guard. The academic paper named and measured
  the problem (48.5% deanon); to our knowledge, no production runtime
  defense ships with current Umbra integrations.
- `rpc_leakage` does pattern detection at the application layer
  (sustained query sequences revealing strategy), where Helios / RPCh /
  Nym solve the transport layer but the application-layer pattern
  problem is unfilled.
- `mixing_behavioral` operationalizes Tutela's seven post-deposit
  heuristics as pre-withdrawal warning. Tutela itself is a post-hoc
  auditor.
- `l2_bridge_linkage` is defensive runtime against cross-chain
  forensics; Chainalysis / Elliptic / TRM Labs operate the offensive
  side commercially, the user-side defensive runtime is unfilled.

**Mature-coverage (5 guards): we ship a local-first complement, not a
replacement.** Blockaid + 4 dominate `approval_phishing`,
`offchain_signature`, `mev_vulnerability`, and the observation side of
`builder_censorship`; Rabby Wallet has comprehensively solved the
`wrong_chain_address` UX. e_AI's contribution in this cluster is local
execution + auditable JSON heuristics + framework integration. Honest
read: not novelty, completeness coverage. A wallet team running e_AI
locally might also call out to Blockaid for known-bad lists; the
substrate composes.

**Operationalization-niche (7 guards): turning empirical research into
runtime UX.** `l2_anonymity_set` calibrated against soispoke's measured
0xbow per-pool thinness (~1.5 nullifier-events per pool per day across
14 pools — H1's <20-depositor threshold fires correctly on the live
distribution). `cross_protocol_risk` and `governance_proposal` are
voter-side / user-side surfaces where operations-side tools (Gauntlet,
Chaos Labs, Guardrail) don't reach. `pq_readiness` is a behavioral
angle on quantum migration before NIST-PQC wallet integrations broadly
ship. `backup_security` audits guardian set + KEM scheme + deniability
posture across three usually-separate axes. `behavioral_drift`
surfaces concentration / leverage drift relative to a user-supplied
baseline. `sequencer_privacy` is largely informational until L2
encrypted mempools ship (LUCID-class), but the registry-of-known-
sequencers + censorship-signal model is wired and runnable today.

**All 16 guards now ship rule-based analyzers** (`domains/<name>/analyzer.py`).
Each `examples/per_domain/<name>/demo.py` runs the rule-based analyzer
and adds local-LLM behavioral context with graceful Ollama degradation.
Several heuristics are not fully algorithmic (e.g., address-book
lookalike detection takes a boolean input flag rather than computing
similarity scores; deniable-encryption scheme correctness is not
verifiable from the analyzer side; `behavioral_drift` cannot
distinguish deliberate strategy from drift). Where a heuristic's
algorithmic core is incomplete, the analyzer accepts an explicit input
field and documents the responsibility in its docstring.

**Brittle: hard-coded registries.** `builder_censorship`'s censoring-
relay set (`bloxroute_regulated`, `manifold`, `eden_compliance`) and
`sequencer_privacy`'s L2 sequencer registry (10 L2s with operator +
encrypted-mempool flags) are sourced from the analyzer source code.
Both will be wrong as the landscape changes. Production deployment
should reconcile against maintained registries (mevwatch / relayscan
for relays; L2Beat for sequencer state) on a cadence.

**Synthetic-data caveat applies throughout.** All 16 guards calibrated
on synthetic per-guard incidents (≥5 per domain). Production deployment
requires real-incident corpora; the meta-framework's bootstrap is
designed to ingest exactly that. False-positive and false-negative
rates against real corpora are unknown.

---

## 7. What we learned applying the meta-framework to a new task

Five observations from the exercise — these are the lessons that
surfaced when applying the Part 3 framework (originally for DeFi query
sanitization) to the structurally different task of pre-submission
transaction analysis:

1. **The profile schema generalized cleanly** with parallel structure
   for the new input class (transaction objects vs text queries). The
   11-check validation engine carried over with eight checks identical
   to the sanitization-task version and three new checks for severity /
   recommendation calibration.

2. **The bootstrap pipeline carried over but the ingestion contract
   changed** — the Part 3 framework took JSONL datasets of queries; the
   v2 task takes labeled-incident JSONL. Same shape; different semantic
   content.

3. **Algorithmic detection scaled across all 16 guards.** Initial
   iterations had several guards in an LLM-only state where rule-based
   analyzers seemed harder to write than they were. With consistent
   templates, all 16 now ship rule-based analyzers. The cases where
   detection genuinely cannot be made fully algorithmic (deniable-
   encryption soundness, deliberate-strategy-vs-drift, address-book
   lookalike scoring) are surfaced explicitly as input fields the
   analyzer trusts the caller to source.

4. **The local-LLM behavioral layer is useful but not load-bearing.**
   `qwen2.5:7b` produces plausible recommendations but the heavy
   lifting is rule-based detection. The LLM is decoration on top of an
   algorithmic core, not a substitute for it.

5. **Real-data calibration is the bottleneck.** Profile validation
   enforces *spread* across heuristics, not *correctness*. False-positive
   and false-negative rates are unknown until labeled real-incident
   corpora are wired in. This is the load-bearing future-work item; the
   framework is designed to ingest exactly this.

The framework generalized to a second task we tried; further tasks
(medical / legal compliance / on-chain agent safety / cross-chain
incident response) would strengthen any task-agnosticism claim. Today's
evidence supports "the framework extended to a second task" rather
than "the framework generalizes broadly."

---

## 8. Open questions and invitations

- **Real-incident corpora for the 16 guards** — Forta event archives,
  Blockaid public reports, ScamSniffer's wallet-drainer corpus,
  Wahrstätter's dataset, Tutela's compromised-deposit set, MEV Watch /
  Censorship.pics archives. The substrate is designed to ingest these;
  the meta-framework's bootstrap would re-calibrate confidence values
  and enable real ROC-curve benchmarks.
- **Real-incident corpora to calibrate the analyzers.** All 16 guards
  ship rule-based analyzers but calibrated against synthetic samples
  (≥5 per domain). Wiring real-incident data is the highest-leverage
  contribution.
- **New domains in adjacent space** — sybil multi-wallet linkability;
  frontend phishing / URL verification (different architecture than
  transaction analysis); post-mixer chain-bridging fingerprints with
  new 2025 cross-chain heuristics.
- **Integration surfaces** — mobile wallets, hardware-wallet pre-sign
  hooks, sequencer-side guards for L2 operators, policy-driven CI
  guards for institutional users.
- **Composition with adjacent tooling** — Blockaid (known-bad
  threat-intel via API alongside local heuristics), Helios / RPCh
  (transport-layer privacy), CoW Protocol / Flashbots Protect
  (execution-path privacy), Kohaku (wallet substrate target).

Discussion welcome on whether the strong-novelty / mature-coverage
cluster cut is the right honest read; whether the access-layer-
composition framing as a permanently-necessary layer (not interim)
holds up under scrutiny; whether any of the 16 guards should be
dropped or merged.

If you want to add a guard, see [`CONTRIBUTING.md`](CONTRIBUTING.md). If
you want to push back on the positioning — particularly the mature-
coverage cluster — that conversation is welcome.

---

## References

**e_AI series**:
- Part 1 — *The Private Query Problem: Privacy-Preserving AI Query Orchestration for DeFi* — [`ethresearch_post.md`](ethresearch_post.md)
- Part 2 — *Active Adversaries and Verifiable Inference* — [`companion_post_active_adversary.md`](companion_post_active_adversary.md)
- Part 3 — *A Meta-Framework for Domain-Agnostic Privacy Protection* — [`ethresearch_meta_framework_draft.md`](ethresearch_meta_framework_draft.md)

**Protocol-level primary sources**:
- Vitalik Buterin — [*keyed nonces and restricted state types*](https://x.com/VitalikButerin/status/2051675198068330996), May 2026
- *Bloom filters to shrink the VOPS for privacy protocol nullifiers* — [Fileverse proposal](https://docs.fileverse.io/d/020001fc0012#k=UT7Btd6tyqHgOj47t-TX06F8D6OpcpM_2PKdf7s4tGE) linked from the above (concrete numbers: ~1 byte per nullifier; 277 GiB at 1000 TPS × 8 years; 3% per-node false-rejection acceptable due to FOCIL+mempool redundancy)
- soispoke ([@soispoke on X](https://x.com/soispoke)) — Mar 19 2026 thread on EIP-8141 + 2D nonces + encrypted frame transactions + FOCIL composition (specific thread anchor not embedded; locate via author profile)
- Nero_eth — [*Frame Transactions and the Three Gates to Privacy*](https://ethresear.ch/t/frame-transactions-and-the-three-gates-to-privacy/24666), April 16 2026
- [EIP-8141 — Frame Transaction](https://eips.ethereum.org/EIPS/eip-8141)

**Empirical sources**:
- Wahrstätter, Ernstberger, Soleimanian, Smaragdakis — *Anonymity Analysis of the Umbra Stealth Address Scheme* — [arXiv 2308.01703](https://arxiv.org/abs/2308.01703), ACM Web Conf 2024 (48.5% Ethereum deanon rate)
- [The Block on jaredfromsubway.eth's MEV bot](https://www.theblock.co/post/230218/jaredfromsubway-mev-bot) (May 2023) — ~238K attacks against ~106K victims in 3 months, ~$40.65M revenue / ~$6.3M net profit per EigenPhi analysis (net-profit figure disputed by some MEV researchers); jaredfromsubway.eth [Etherscan profile](https://etherscan.io/address/0x1f2f10d1c40777ae1da742455c65828ff36df387)
- [EigenPhi 2025 sandwich data](https://x.com/EigenPhi/status/1998090234442215671) — ~$60M sandwich extraction Nov 2024 – Oct 2025 across Ethereum; declining trend
- [ScamSniffer 2024 annual phishing report](https://drops.scamsniffer.io/scam-sniffer-2024-web3-phishing-attacks-wallet-drainers-drain-494-million/) — ~$494M lost to wallet drainers in 2024 across 332K addresses, 85.3% on Ethereum; [2025 follow-up](https://drops.scamsniffer.io/scam-sniffer-2025-crypto-phishing-losses-fall-83-to-84-million/) shows losses fell to ~$84M
- Tutela / Pareto-xyz — [tutela-app](https://github.com/pareto-xyz/tutela-app) — 42,852 of 97,331 Tornado Cash deposits compromised
- [Blockaid Inferno/Angelferno drainer report](https://www.blockaid.io/blog/putting-inferno-drainer-group-out-of-business) — 40K+ Angelferno attack attempts blocked in June 2025
- [Cyberhaven shadow-AI report](https://www.cyberhaven.com/blog/4-2-of-workers-have-pasted-company-data-into-chatgpt) — ~4.7% of enterprise users pasted confidential data into ChatGPT
- [404 Media on archived LLM conversations](https://www.404media.co/more-than-130-000-claude-grok-chatgpt-and-other-llm-chats-readable-on-archive-org/) — 130K+ AI conversations indexed on Wayback Machine across Claude, Grok, ChatGPT
- soispoke — [Privacy Pools nullifier-state-growth Dune dashboard](https://dune.com/soispoke/privacy-pools-nullifier-state-growth) (read 2026-05-07)
- [MEV Watch](https://www.mevwatch.info) and [Censorship.pics](https://censorship.pics) — relay-level censorship rates post-OFAC

**Code**:
- Repository: https://github.com/namnc/e_AI (`v2` branch)
- 16 per-domain demos: [`examples/per_domain/`](examples/per_domain/)
- Five access-method integration demos: [`examples/`](examples/)
- Validation engine: [`meta/tx_validation_engine.py`](meta/tx_validation_engine.py) (11 checks)
- Profile schema reference: [`docs/profile_schema.md`](docs/profile_schema.md)
- Lifecycle composition: [`docs/composition.md`](docs/composition.md)
- End-user scenarios: [`docs/scenarios.md`](docs/scenarios.md)
- Architecture context (this post's framing in detail): [`docs/access_layer_context.md`](docs/access_layer_context.md)
- Per-guard prior art: [`docs/prior_art/`](docs/prior_art/) (16 files)
- Long-form substrate overview: [`docs/v2_substrate_overview.md`](docs/v2_substrate_overview.md)
- Contributor entry: [`CONTRIBUTING.md`](CONTRIBUTING.md)
