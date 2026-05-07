<!-- AI-assisted, human-reviewed before publication. -->

# From DeFi Sanitization to Pre-Submission Transaction Guards

**A tooling substrate for Access-Layer privacy and safety.**

This is a standalone post. It references and builds on prior work in the
e_AI series:
- *The Private Query Problem* (Part 1) — the original DeFi sanitization paper.
- *Active Adversaries and Verifiable Inference* (Part 2).
- *A Meta-Framework for Domain-Agnostic Privacy Protection* (Part 3, draft).

Readers who want the substrate without the journey can skip to §3.

---

## 0. Abstract

In *The Private Query Problem* we identified cloud LLM queries leaking
DeFi intent and built a tiered sanitization pipeline. In the *Meta-Framework*
post we generalized to auto-generation: same pipeline applied to arbitrary
text-query domains, validated on DeFi via six generation strategies. This
post takes the next step — applying the same meta-framework to a
**different task entirely**: pre-submission transaction analysis. The
substrate produces profile-driven guards across Ethereum's four access
methods (wallet, application, AI agent, L2), plus one fresh CR-aligned
domain demonstrating extensibility. Each guard ships profile + tests +
analyzer (where rule-based detection applies) + a runnable demo. The result
is not a finished product. It is a **potential tooling direction**: minimal,
runnable, with a documented upgradability path. We are honest about which
guards live in already-occupied space (a substantial fraction) and which
fill genuine gaps, and we frame what we have NOT shown.

**Empirical motivation, one number**: per soispoke's 2026-05-07 Dune dashboard,
Privacy Pools + Railgun + Tornado Cash combined process ~0.0055 transactions
per second sustained — five orders of magnitude below Vitalik's
recently-discussed state-bloat thresholds, and ~0.025% of Ethereum mainnet
activity. Privacy at the Access Layer is currently *under-deployed*, not
over-deployed. That asymmetry shapes the framing: the substrate is offered
as a way to lower the cost of building access-layer privacy/safety guards,
not as a finished defense.

---

## 1. Origin — Why we started with DeFi sanitization

(2-3 paragraphs. Recap from Part 1 in the user's voice. Pull motivation
threads:)

- 5% of US adults already use AI for financial decisions; intent leakage to
  LLM providers is a strictly richer signal than RPC reads (Part 1 §1)
- The hand-crafted DeFi sanitization pipeline (Part 1): regex + cover queries
  + local-LLM decomposition + genericization
- It worked, but it was DeFi-specific — weeks of iteration; non-portable to
  medical / legal / TradFi without re-doing the hand-crafting

**Framing tag:** this section is FRAMING (analytical lens that organizes
thinking, not a formal claim).

---

## 2. First generalization — Part 3's meta-framework (one-page recap)

(Quick recap; refer to Part 3 for full validation:)

- 13 property checks, 11 programmatic
- 6 generation strategies on a 216-query DeFi benchmark
- Local 14B + web search achieves ACCEPTED (matches hand-crafted)
- Cloud Claude achieves 97% vocabulary recall, 3.8/5 Tier 1 quality
- The quality gap is in the generating model, not the framework

**Honest reading**: Part 3 demonstrated **domain-agnosticism within the
sanitization task** (DeFi vs hypothetical medical / legal / TradFi). It
did not demonstrate **task-agnosticism** (sanitization vs other privacy
tasks). That's where this Part 4 picks up.

**Framing tag:** sentences in this section that recap Part 3 are CLAIM
(evidence-grounded by Part 3 measurements). The "honest reading" sentence is
FRAMING.

---

## 3. Second generalization — Same framework, different task

### 3.1 The new task: pre-submission transaction analysis

Instead of: "given a query about DeFi, sanitize sensitive parameters before
sending to cloud LLM," we now ask: "given a transaction the user is about to
submit, flag privacy/safety/CR risks pre-submission and suggest
countermeasures."

The threat model is different. The detection target is different. The
intervention point is different. But the **profile + LLM + validation
engine + meta-framework** is the same. That's the claim being tested in this
section.

### 3.2 Architectural reuse

Show side-by-side:

| Component | Part 3 (sanitization) | Part 4 (tx analysis) |
|---|---|---|
| Profile schema | `domain_profile.py` | `tx_profile.py` (parallel structure) |
| LLM analyzer | local 14B for cover gen | local 7B for behavioral analysis |
| Validation engine | 13 property checks | 11 property checks (shared 8) |
| Bootstrap | `meta.bootstrap_domain` | same module, different schema |
| Cover generator | regex + ontology | not applicable for tx guards |
| Tests | per-heuristic structure | per-heuristic structure (same shape) |

**Claim**: the meta-framework's core artifacts (profile schema, validation
engine, bootstrap pipeline) carry across tasks with bounded modifications.

**Evidence**: 15 v2 production tx-analysis guards built on the same engine,
all passing the 11-check `tx_validation_engine`. Plus 1 fresh domain
(`builder_censorship`) added in 1 week using only the documented extension
guide.

---

## 4. Four access methods to Ethereum

The 15 v2 guards organize around how a user actually touches Ethereum.

### 4.1 Wallet method (7 guards in this post + 1 hygiene-only)

Direct user-signed transactions from a wallet UI.

| Guard | What it catches | Detection | Has analyzer.py |
|---|---|---|---|
| `approval_phishing` | Unlimited / scam-DB / unverified-spender approvals | rule-based | yes |
| `backup_security` | Risky guardian sets, coercion-vulnerable / quantum-exposed backups | LLM-only currently | no |
| `behavioral_drift` | Concentration / leverage creep relative to user baseline | LLM-only | no |
| `mev_vulnerability` | Pre-submission sandwich/front-running risk | rule-based | yes |
| `offchain_signature` | Malicious EIP-712 / Permit2 signatures | rule-based | yes |
| `pq_readiness` | Operations leaking quantum-vulnerable secrets | rule-based | yes |
| `stealth_address_ops` ⭐ | Deanonymization via timing / amounts / gas / address reuse | rule-based | yes |

The repo also ships `wrong_chain_address` (chain-ID and contract-vs-EOA
mismatch detection). We do not give it a flagship section here because
Rabby Wallet has comprehensively solved this UX. It belongs to the
"wallet hygiene completeness" set the framework will absorb in future
iterations.

### 4.2 Application method (3 guards)

DApp / governance / cross-protocol surfaces.

| Guard | What it catches | Has analyzer.py |
|---|---|---|
| `cross_protocol_risk` | Cascading liquidation / correlated exposure | yes |
| `governance_proposal` | Treasury drain / parameter manipulation / proxy upgrade | yes |
| `mixing_behavioral` | Post-mixer linkability across chains | LLM-only |

### 4.3 AI method (1 guard)

Where an agent (or RPC-driven monitor) acts on behalf of the user.

| Guard | What it catches | Has analyzer.py |
|---|---|---|
| `rpc_leakage` | Query patterns revealing user strategy / portfolio | yes |

### 4.4 L2 method (3 guards)

Layer-2 specific risk classes that don't appear at L1.

**Real-data calibration note for `l2_anonymity_set` H1** (to insert into per-guard
section 5): soispoke's Dune dashboard `privacy-pools-nullifier-state-growth`
(90-day window through 2026-05-07) shows 0xbow Privacy Pools running ~1.5
nullifier-events per pool per day across 14 pools. The H1 threshold (<20
depositors/24h → WARN, <5 → BLOCK) would fire on the majority of 0xbow pools
at current activity — this is real-data validation that the heuristic was
calibrated against actual access-layer thinness, not synthetic worst-case.
[shared/feed.jsonl entries 2026-05-07]


| Guard | What it catches | Has analyzer.py |
|---|---|---|
| `l2_anonymity_set` | Thin pools, sequencer visibility, forced-inclusion deanon | yes |
| `l2_bridge_linkage` | Cross-chain identity correlation via bridge usage | yes |
| `sequencer_privacy` | Tx visibility to centralized L2 sequencer | LLM-only |

### 4.5 Plus one fresh CR-aligned domain

| Guard | What it catches | Has analyzer.py |
|---|---|---|
| `builder_censorship` | Routes through censoring builders/relays; missing forced-inclusion fallback; builder monoculture | yes |

`builder_censorship` was added to validate the extension framework: profile
+ analyzer + tests + per-domain demo, built in 1 week using
`docs/adding_a_domain.md`. It thread-connects an access-layer thesis we
work to: protocol provides bounded enabling primitives; the access layer
composes;
when all submission paths gate on operator policy, CR collapses to
operator-trust. The guard surfaces this pre-submission so the user can
reconfigure or use a forced-inclusion escape hatch.

**Honest scope**: 5 of 15 guards are LLM-only currently. Their detection
mechanism is profile-driven LLM analysis without a bespoke rule-based
analyzer; some of these are inherently subjective (behavioral_drift,
mixing_behavioral) while others have algorithmic structure that should get
an analyzer in future iterations (wrong_chain_address, sequencer_privacy).
The framework supports both detection mechanisms transparently.

---

## 5. Per-guard demos and prior art

For each guard: a runnable demo, a one-line catch description, prior-art
positioning, and an honest where-it-differs note. Detailed prior-art per
guard at `docs/prior_art/<name>.md` in the repo (16 files).

### Strong-novelty cluster (4 guards) — lead with these

#### `stealth_address_ops` ⭐

**Catches**: ERC-5564 / Umbra stealth-address operational mistakes that allow
deanonymization — timing correlation, amount fingerprints, gas-price reuse,
address reuse, paymaster funding patterns. Profile is built directly on
Wahrstätter et al.'s 2023 Umbra anonymity-analysis heuristics (48.5% deanon
rate on Ethereum).

**Demo**: `python3 examples/per_domain/stealth_address_ops/demo.py` — sample
triggers 5 critical alerts (H1 + H3 + H4 + H6).

**Prior art**: Wahrstätter paper *named* and *measured* the problem; ScopeLift
Umbra ships passive guidance; Tutela addresses an analogous problem for
mixers but is post-hoc auditor, not pre-submission guard. **No deployed
runtime, pre-submission tool exists for stealth-address ops mistakes.**

**Where e_AI differs**: First runtime pre-submission guard turning Wahrstätter's
heuristics into prevention. Concrete benchmark question: *does it reduce the
48.5% deanon rate?*

#### `rpc_leakage` ⭐

**Catches**: RPC query patterns (balance checks, log scans, eth_getStorageAt
sweeps, multi-address monitoring) that reveal the user's strategy or
portfolio to an RPC provider — even when the underlying transactions are
private.

**Demo**: `python3 examples/per_domain/rpc_leakage/demo.py` — sample triggers
H1 + H2 + H3 from a sustained-monitoring session.

**Prior art**: RPCh / Helios / Nym handle the *transport layer* (route
queries through privacy-preserving network). No tool detects *pattern-level*
leakage at the application layer ("you've checked these 5 wallets every 6
hours for 3 weeks").

**Where e_AI differs**: Pattern detection at the app layer, locally, with an
LLM that can recognize the strategy-revealing semantics of a query sequence.
Genuinely under-served niche.

#### `mixing_behavioral` ⭐

**Catches**: Post-mixer linkability across chains via behavioral patterns
that survive the mixing step — bridge usage timing, DEX swap sequences,
denomination correlations.

**Demo**: `python3 examples/per_domain/mixing_behavioral/demo.py` —
LLM-mediated detection (5 stub alerts derived from sample).

**Prior art**: Tutela (Tornado Cash anonymity auditor — 7 heuristics, 42.8K
of 97.3K deposits compromised) is a *post-hoc auditor* for the operator. The
2025 cross-chain heuristics paper extends the heuristic set. **No
pre-withdrawal runtime tool exists.**

**Where e_AI differs**: Pre-emptive runtime against the same heuristic
family Tutela demonstrated. The user can act on the warning before the
linkable behavior happens.

#### `l2_bridge_linkage` ⭐

**Catches**: Cross-chain identity correlation through bridge usage —
deposit→withdrawal pair leakage, timing heuristics, denomination matching
across L1↔L2.

**Demo**: `python3 examples/per_domain/l2_bridge_linkage/demo.py` — sample
triggers all 5 heuristics.

**Prior art**: Chainalysis / Elliptic / TRM Labs operate the offensive
side commercially (cross-chain forensics for compliance/law enforcement).
**No defensive runtime tool exists for users.**

**Where e_AI differs**: Defensive-runtime gap is real. The asymmetry between
offensive forensics (well-funded, commercial) and defensive runtime (zero
shipped tools) is a clean motivation.

---

### Mature-coverage cluster (4 guards) — acknowledge, don't lead

These domains have substantial prior art. e_AI's contribution is
local-execution, framework-driven *completeness coverage* — not novel
detection. We include them so a unified guard set is plausibly deployable;
we do not claim novelty in this cluster.

The honest framing across this cluster is that e_AI is a
**privacy-preserving local complement to existing centralized SaaS
scanners** (Blockaid, Pocket Universe, Scam Sniffer, Flashbots Protect,
MEV Watch). It is not a replacement. The substrate runs locally, keeps
private data on-host by default, exposes its heuristics in JSON rather
than as opaque proprietary classifiers, and composes with the centralized
services (a wallet can run e_AI locally + query Blockaid for known-bad
lists, etc.). That positioning applies to all four guards below.

#### `approval_phishing`

**Catches**: Malicious ERC-20/721/Permit2 approvals — unlimited allowances,
scam-DB hits, unverified spenders, suspicious selectors, stale approvals
with live exposure.

**Demo**: `python3 examples/per_domain/approval_phishing/demo.py` — triggers
H1 + H2 + H3, OVERALL CRITICAL, should_block.

**Prior art (heavy)**: Blockaid (industry-leading, integrated into MetaMask /
Rainbow / Coinbase Wallet / Phantom / Zerion / OpenSea / Uniswap; blocked
40K+ Angelferno drainer attempts in June 2024 alone), Pocket Universe (browser
sim-first), Scam Sniffer (multi-layer Web3 anti-phishing), Revoke.cash
(hygiene + revocation).

**Where e_AI differs**: Local execution; profile-driven (heuristics + thresholds
documented in JSON, not opaque); fits the v2 framework. Honest framing:
*not* a novelty claim, *is* a completeness claim.

#### `offchain_signature`

**Catches**: Malicious EIP-712 / Permit / Permit2 signatures — typed-data
phishing payloads carrying token-spend authorization without an on-chain
tx that simulators would catch.

**Demo**: `python3 examples/per_domain/offchain_signature/demo.py` —
triggers H1 + H2 + H4.

**Prior art (heavy)**: Blockaid + Pocket Universe + Rabby Wallet (built-in
Permit2 warnings) + Veritas + Coinspect.

**Where e_AI differs**: Same framing as approval_phishing — local-execution
completeness, not novelty.

#### `mev_vulnerability`

**Catches**: Pre-submission sandwich / front-running risk — high-slippage
swaps in public mempool, large swap relative to pool, no MEV protection
configured.

**Demo**: `python3 examples/per_domain/mev_vulnerability/demo.py` — triggers
H1 + H2 + H4 + H5.

**Prior art (mature)**: Flashbots Protect, MEV Blocker, CoW Protocol (CoW Swap),
1inch Fusion, UniswapX — all production MEV-protection routes.

**Where e_AI differs**: Router-recommender (suggests the right protection
path) rather than novel detection. Useful as part of a unified guard set;
not a standalone contribution.

**Note on `wrong_chain_address`** (no flagship section, included in repo):
chain-ID mismatch and EOA-vs-contract address confusion. **Rabby Wallet has
solved this UX**; MetaMask and OneKey cover the basics. We keep the guard
in the repo as wallet-hygiene completeness but don't claim novelty.

#### `builder_censorship`

**Catches**: Submission paths through censoring builders/relays; missing
forced-inclusion fallback on L2; builder monoculture; the compound
no-circumvention case.

**Demo**: `python3 examples/per_domain/builder_censorship/demo.py` —
worst-case sample triggers all 5 heuristics, OVERALL CRITICAL, should_block.

**Prior art**: MEV Watch, Censorship.pics, Relayscan are dominant on the
*observation* side; no pre-submission guard wired into the wallet.

**Where e_AI differs**: "MEV Watch in your wallet" — pre-submission framing
is the contribution. Honest: this is a re-derivative cluster member, not a
novelty claim. We include it deliberately because it provided the
*extension-validation* exercise: built in one week using only the
documented `docs/adding_a_domain.md` walkthrough. The honest test of
"framework supports new domains" is doing it on a domain where you already
know the answer roughly looks like prior art — and seeing the framework
hold up.

---

### Operationalization cluster (4 guards) — niche-fill

Real gaps where existing tools are observers, not actors.

#### `l2_anonymity_set`

**Catches**: Thin L2 privacy pools, sequencer visibility, forced-inclusion
deanon vectors. **Real-data calibration** (soispoke Dune dashboard, 2026-05-07):
0xbow Privacy Pools running ~1.5 nullifier-events per pool per day across
14 pools — H1 (<20 depositors/24h → WARN, <5 → BLOCK) fires correctly on
the live thinness it was designed to detect.

**Demo**: `python3 examples/per_domain/l2_anonymity_set/demo.py` — triggers 5
alerts on a thin-pool sample.

**Prior art**: Wahrstätter's empirical L2 privacy work + L2BEAT data; no
runtime per-tx anonymity-set warning.

**Where e_AI differs**: Operationalization niche — turning empirical research
into pre-submission UX. Calibrated against real measured pool sizes.

#### `cross_protocol_risk`

**Catches**: Cascading liquidation / correlated exposure across DeFi
protocols (Aave + Compound positions sharing collateral; flash-loan attack
surface).

**Demo**: `python3 examples/per_domain/cross_protocol_risk/demo.py` —
triggers H1 + H2 + H4 + H5.

**Prior art**: Gauntlet / Chaos Labs operate at *protocol-governance* level
(set parameters for protocols). User-side composition reasoning is
under-served — but the user demand signal is unclear.

**Where e_AI differs**: User-side, not protocol-side. Open question: does
a user actually want this analysis pre-submission, or is it
implicit-advisor territory?

#### `governance_proposal`

**Catches**: Treasury drain / parameter manipulation / proxy upgrade
patterns in DAO governance proposals — voter-side scrutiny before voting.

**Demo**: `python3 examples/per_domain/governance_proposal/demo.py` —
triggers all 5 heuristics on an adversarial proposal.

**Prior art**: Guardrail.xyz + OpenZeppelin Defender at the operations side
(treasury controls, multisig review). Voter-side niche exists but is
under-tooled.

**Where e_AI differs**: Voter-side framing — surfaces risk before vote
submission, not after deployment.

#### `pq_readiness`

**Catches**: Operations exposing quantum-vulnerable secrets — re-using a
public key after first use, signing with an EOA whose pubkey is on-chain,
operations that prematurely reveal pq-vulnerable structure.

**Demo**: `python3 examples/per_domain/pq_readiness/demo.py` — triggers all
5 heuristics.

**Prior art**: QuantumShield, Quantum Canary cover *static scan*. The
behavioral angle ("when to rotate", pre-submission warning on first-use
exposure) is forward-looking.

**Where e_AI differs**: Behavioral pre-submission angle vs static audit.
Currently small population; will grow as PQ migration becomes practical.

---

### LLM-only cluster (3 guards) — detection mechanism is profile-driven LLM

These ship without a bespoke `analyzer.py`. Detection is via LLM with the
profile as prompt context. Documented honestly in the per-domain README.

#### `backup_security`

**Catches**: Risky guardian sets, weak password backups, ECDH-derived
encryption without PQ KEM (storage forever; future quantum break compromises
present backups), missing deniability for coercion resistance, non-deterministic
secrets not backed up.

**Demo**: `python3 examples/per_domain/backup_security/demo.py` — LLM-mediated
detection produces 5 stub alerts on a worst-case backup config.

**Prior art**: Argent guardian model + Safe (multisig) cover *guardian
configuration*; no tool composes guardian + cloud-backup + quantum axes
into a unified pre-submission guard.

**Where e_AI differs**: Synthesis-novelty across three usually-separate axes.
Thin novelty but real.

#### `behavioral_drift`

**Catches**: Concentration / leverage creep relative to a user's baseline —
the user's positions have drifted from their stated risk tolerance over weeks.

**Demo**: `python3 examples/per_domain/behavioral_drift/demo.py` — LLM-mediated.

**Prior art**: Nansen / Arkham observe at the analytics level. Forta /
Hypernative monitor *compromise*. No per-user-baseline drift detector — but
user-demand evidence is vague.

**Where e_AI differs**: User-baseline framing rather than absolute-position.
Useful if there's adoption signal; honest open question if there isn't.

#### `sequencer_privacy`

**Catches**: Tx visibility to a centralized L2 sequencer — the sequencer
sees the user's tx pre-batch.

**Demo**: `python3 examples/per_domain/sequencer_privacy/demo.py` —
LLM-mediated.

**Prior art**: Largely informational — rollup-team docs disclose the
trust-assumption; no runtime guard.

**Where e_AI differs**: Mostly informational until encrypted mempools land
at L2 (encrypted-mempool primitive class). Today the actionability is limited; this guard
is a placeholder for the architecture that will matter post-LUCID.

---

## 6. The upgradability framework

Reference: `CONTRIBUTING.md`, `docs/adding_a_domain.md`, `docs/profile_schema.md`.

### 6.1 Adding a new domain in N steps

(Pull from `docs/adding_a_domain.md` — 11 steps, ~1 day for a domain expert
who's done it once.)

### 6.2 What's NOT auto-magical

- Threat model still has to be authored by a domain expert
- Heuristic confidence calibration is hand-tuned for first iteration
- Real-incident labeled data must be collected; the framework's bootstrap
  generates synthetic samples, not ground truth
- Production integrations (block explorer APIs, scam DBs, oracle telemetry)
  must be wired by a contributor
- LLM behavioral analysis quality depends on local model capability

### 6.3 What IS auto-magical (with caveats)

- Profile validation (11-check engine) catches structural issues before runtime
- Per-domain demo template ensures any new guard has a runnable PoC
- CI runs all v2 domain tests on every push
- LLM step is local-first by default; no private data leaves the host unless
  explicitly opted into a cloud backend

---

## 7. Where this fits — Access Layer Privacy and Safety thesis

(2-3 paragraphs.)

This substrate sits at Ethereum's access layer — between the protocol and
the user, composing wallets, services, integrations, and AI agents. It
does not change protocol behavior. It augments the access path with
pre-submission analysis.

We work to an access-layer thesis: the protocol should provide bounded
enabling primitives (auth abstraction via EIP-8141; ordering via
LUCID-class encrypted mempool; specialized storage per Vitalik's recent
post on keyed nonces; forced inclusion via FOCIL), with everything else
composed off-chain at the access layer. This substrate is one such
composition: it does not require a new protocol mechanism to function.
It does benefit from emerging primitives but does not depend on them.

**Trust assumptions** (surfaced explicitly per guard): the substrate
trusts the user's local machine, the chosen LLM backend (Ollama by
default, local-only), block-explorer verification status, scam-DB lookups
(where wired), and any external registries the user opts into. None of
these are protocol-grade trust assumptions; they are operator-grade. Each
guard's README states its specific trust set.

---

## 8. Limitations — what we have NOT shown

- **Real-incident labeled data**: synthetic samples per domain (≥5 each).
  No ROC curves over captured-incident corpora.
- **Production integrations**: scam DBs, block explorers, OFAC live lists,
  builder-diversity feeds — all referenced as inputs, not wired live.
- **End-to-end UX**: no shipped wallet integration; the Kohaku middleware
  demo is a working PoC but not a deployed feature.
- **Confidence calibration at scale**: the `F4_confidence_calibration` check
  enforces *spread* across heuristics, not absolute correctness; that
  requires real-incident-grounded training.
- **Sybil and frontend-phishing**: the v2 problem brief enumerates these as
  future-work items; not in v2 production set.
- **Adversarial robustness**: no red-team has actively probed the heuristics
  yet.

---

## 9. Decisions and tradeoffs in scoping this post

A note on what this post deliberately does and does not do, written down
because the choices affect how the rest reads.

**Cluster the guards, lead with novelty, fold the weakest.** The prior-art
audit (Section 5 + per-guard files in `docs/prior_art/`) was uncomfortable
in places. Five guards live in already-occupied space — Blockaid, Pocket
Universe, Flashbots Protect, Rabby, MEV Watch are real, deployed, and
covering most of the surface. We organize the section by cluster
(strong-novelty / mature-coverage / operationalization / LLM-only) so the
reader can see what is being claimed. We fold `wrong_chain_address` out of
flagship treatment because Rabby Wallet has solved that UX comprehensively
— including it as a flagship would weaken the rest of the post by
proximity.

**Include `builder_censorship` and surface the tension.** This was a
test — built in one week using only the `docs/adding_a_domain.md`
walkthrough — to check whether the framework supports new domains. The
prior-art finding ("MEV Watch in your wallet") is honest and we say so.
The point is not to claim novelty for `builder_censorship` itself; it is to
show the framework holds up on a domain whose prior art is dense.

**"Potential tooling direction" is the framing, not hedging.** Given the
prior-art density, anything stronger ("we built a defense", "this replaces
X") would be overclaiming. The phrase reflects the actual state: a
substrate that lowers the cost of building access-layer guards, with
concrete extension docs, calibrated against real-world data where
available.

**Standalone post, references for prior work.** The earlier posts in the
series exist; we cite them as background reading, not prerequisites. A
reader who comes via search engine or social link should be able to follow
this post without having read the earlier ones.

**Real-data calibration is motivation + sidebar, not centerpiece.** The
soispoke Dune dashboard (2026-05-07) shows access-layer privacy is microscopic
in current Ethereum activity — that motivates the substrate's existence.
The 0xbow per-pool thinness datapoint validates `l2_anonymity_set` H1; we
cite it in that guard's section as a calibration fact, not as the post's
main claim.

---

## 10. References

**e_AI series**:
- Part 1 — *The Private Query Problem: Privacy-Preserving AI Query Orchestration for DeFi* — [`ethresearch_post.md`](ethresearch_post.md)
- Part 2 — *Active Adversaries and Verifiable Inference* — [`companion_post_active_adversary.md`](companion_post_active_adversary.md)
- Part 3 — *Meta-Framework for Domain-Agnostic Privacy Protection* — [`ethresearch_meta_framework_draft.md`](ethresearch_meta_framework_draft.md)

**Architecture context** (in-repo): [`docs/access_layer_context.md`](docs/access_layer_context.md)
places this substrate within the broader 2026 Ethereum privacy roadmap and
cites the protocol-level work below.

**Protocol-level primary sources**:
- Vitalik Buterin — [*keyed nonces and restricted state types*](https://x.com/VitalikButerin/status/2051675198068330996), May 2026 — core thesis on specialized state types as a new state-scaling strategy
- *Bloom filters to shrink the VOPS for privacy protocol nullifiers* — Fileverse proposal linked from the above; concrete numbers (~1 byte / nullifier; 277 GiB at 1000 TPS × 8 years; 3% per-node false-rejection acceptable due to FOCIL+mempool redundancy)
- soispoke ([@soispoke on X](https://x.com/soispoke)) — Mar 19 2026 thread on EIP-8141 + 2D nonces + encrypted frame transactions + FOCIL composition (specific thread anchor not embedded; locate via author profile)
- Nero_eth — [*Frame Transactions and the Three Gates to Privacy*](https://ethresear.ch/t/frame-transactions-and-the-three-gates-to-privacy/24666), April 16 2026
- [EIP-8141 — Frame Transaction](https://eips.ethereum.org/EIPS/eip-8141)

**Empirical data cited**:
- Wahrstätter, Ernstberger, Soleimanian, Smaragdakis — *Anonymity Analysis of the Umbra Stealth Address Scheme* — [arXiv 2308.01703](https://arxiv.org/abs/2308.01703), ACM Web Conf 2024 (48.5% Ethereum deanon rate)
- jaredfromsubway.eth — [Etherscan profile](https://etherscan.io/address/0x1f2f10d1c40777ae1da742455c65828ff36df387) — single MEV bot, $40.65M revenue / $6.3M net profit in ~2.5 months of 2023
- Tutela / Pareto-xyz — [tutela-app](https://github.com/pareto-xyz/tutela-app) — 42,852 of 97,331 Tornado Cash deposits compromised
- Blockaid — [token-scanning + threat-intel platform](https://www.blockaid.io); 40K+ Angelferno drainer attempts blocked in June 2024 alone
- soispoke — [Privacy Pools nullifier-state-growth Dune dashboard](https://dune.com/soispoke/privacy-pools-nullifier-state-growth) — 0xbow ~1.5 nullifiers/pool/day; combined Privacy Pools throughput 0.0055 tx/s sustained
- [MEV Watch](https://www.mevwatch.info) and [Censorship.pics](https://censorship.pics) — relay-level censorship rates post-OFAC

**External tooling (per-guard prior-art positioning)**:
- `stealth_address_ops` — Umbra (ScopeLift), Wahrstätter et al.
- `mixing_behavioral` — Tutela; cross-chain post-mixer heuristics work (2025)
- `approval_phishing` — Blockaid, Pocket Universe, Scam Sniffer, Revoke.cash
- `offchain_signature` — Blockaid, Rabby Wallet, Pocket Universe, Veritas, Coinspect
- `mev_vulnerability` — Flashbots Protect, MEV Blocker, CoW Protocol, 1inch Fusion, UniswapX
- `builder_censorship` — MEV Watch, Censorship.pics, Relayscan
- `governance_proposal` — Guardrail.xyz, OpenZeppelin Defender
- `cross_protocol_risk` — Gauntlet, Chaos Labs
- `l2_anonymity_set` — L2BEAT, Wahrstätter L2 work
- `l2_bridge_linkage` — Chainalysis, Elliptic, TRM Labs (offensive side; defensive runtime gap)
- `pq_readiness` — QuantumShield, Quantum Canary; NIST PQC (ML-KEM, ML-DSA, SLH-DSA)
- `rpc_leakage` — Helios, RPCh, Nym (transport-layer)
- `backup_security` — Argent guardians, Safe multisig, OpenZeppelin Guardian (Miden PSM)
- `wrong_chain_address` — Rabby Wallet, MetaMask network detection
- `sequencer_privacy` — rollup-team disclosure docs; LUCID-class encrypted mempool
- `behavioral_drift` — Nansen, Arkham, Forta, Hypernative

Full per-guard prior-art: [`docs/prior_art/<name>.md`](docs/prior_art/) (16 files in the repo).

**Code**:
- Repository: https://github.com/namnc/e_AI (`v2` branch)
- 16 per-domain demos under [`examples/per_domain/`](examples/per_domain/)
- Five access-method integration demos under [`examples/`](examples/)
- Validation engine: [`meta/tx_validation_engine.py`](meta/tx_validation_engine.py) (11 checks)
- Profile schema reference: [`docs/profile_schema.md`](docs/profile_schema.md)
- Lifecycle composition: [`docs/composition.md`](docs/composition.md)
- End-user scenarios: [`docs/scenarios.md`](docs/scenarios.md)
- Contributor entry: [`CONTRIBUTING.md`](CONTRIBUTING.md)

---

## 11. Conclusion

We started with one specific privacy threat in DeFi — query leakage to cloud
LLMs — and built a hand-crafted sanitization pipeline (Part 1). The
hand-crafting was painful enough that we generalized: a meta-framework that
auto-generates equivalent privacy profiles for any text-query domain,
validated on DeFi via six generation strategies (Part 3). That step
demonstrated **domain-agnosticism within the sanitization task**.

This post takes the next step. The same meta-framework — same profile
schema, same validation engine, same bootstrap pipeline, same local-LLM
analyzer pattern — generates pre-submission **transaction-analysis** guards
across Ethereum's four access methods. Fifteen v2 production guards plus a
fresh `builder_censorship` domain built in one week using only the
documented extension guide. **Domain-agnosticism within the sanitization
task** has become **task-agnosticism** of the meta-framework itself.

We are not claiming this is finished. The honest reading of the prior-art
audit (Section 5) is that several guards live in already-occupied tooling
space and contribute *completeness coverage* rather than novelty. Four
guards (`stealth_address_ops`, `rpc_leakage`, `mixing_behavioral`,
`l2_bridge_linkage`) sit in genuinely under-served niches. Five (`approval_phishing`,
`offchain_signature`, `mev_vulnerability`, `wrong_chain_address`,
`builder_censorship`) overlap heavily with existing centralized SaaS
scanners — e_AI's contribution there is local execution and framework
integration, not a novel detection.

We offer this as a **potential tooling direction** with a documented
upgradability path: profile schema reference, validation engine, extension
guide, contributor doc. The substrate sits at Ethereum's Access Layer —
between the protocol and the user — and composes alongside the keystone
enabling primitives (auth abstraction + encrypted mempool) without
requiring protocol changes.

The framework still extends. New domains take ~1 day for an expert who has
read the docs once. The 11-check validation engine catches structural
failures before runtime. The local-first LLM analyzer keeps private data on
the host by default. The trust assumptions per guard are surfaced
explicitly, not buried.

If you want to add a guard, see [`CONTRIBUTING.md`](CONTRIBUTING.md). If
you want to discuss positioning — particularly the strong-novelty /
mature-coverage cut, or which guards belong in scope at all — that
conversation is welcome.
