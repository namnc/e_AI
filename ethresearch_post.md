# The Private Query Problem: Privacy-Preserving Orchestration of AI Queries for DeFi

## Abstract

When DeFi users consult cloud LLMs before transacting, they leak **intent, strategy, portfolio context, and decision rationale** — information strictly richer than the "private reads" already on Ethereum's privacy roadmap, leaked two steps earlier. We call this the **Private Query Problem**.

We present a tiered architecture: a **regex sanitizer** (deployable as a browser extension at zero cost) deterministically removes numerically-formatted private parameters — the data most directly exploitable for MEV. An optional **local LLM orchestrator** adds query decomposition and cover queries for topic hiding, but only under strong transport assumptions (per-query-set unlinkability via independent Tor circuits). Experimental results: regex sanitization catches all tested numeric parameter patterns (0% false negatives on a 2,600-case synthetic audit using 14 base token symbols; coverage for novel tokens depends on the broad pattern matcher and curated known-token list; natural language paraphrases and implicit leakage are not caught). Template + distribution matched cover queries reduce adversary detection to 25-29%, at the 25% random baseline, but degrade answer quality to 2.3/5 without LLM-based decomposition — covers are viable only in the full pipeline ($200-500/yr).

> **Scope note**: This is orthogonal to AI safety. We assume the LLM works correctly. The threat is the provider's observation of the query, not the model's behavior. A perfectly aligned LLM still creates the private query problem, just as a perfectly correct RPC still creates the private read problem.

## 1. Motivation

### 1.1 Users Are Already Querying LLMs Before Transacting

- **5% of US adults** already use AI for financial decisions (FINRA Investor Education Foundation, May 2024, N=1,033) [1], with **20% expressing interest** — a figure that is growing rapidly as AI tools improve
- Industry surveys (which skew toward engaged users) report much higher adoption: **19% of retail investors globally** use AI tools (eToro, August 2025, n=11,000 across 13 countries), with **30% among US retail investors** specifically (eToro US survey, n=1,000) [2], suggesting that among active traders — the DeFi-relevant population — adoption is substantially higher than the general public
- The **#16 most popular Custom GPT** is a finance/crypto trading assistant with **5M+ conversations** (per GPTsHunter, a third-party tracker; official OpenAI rankings are not published) [3]
- Anthropic launched "Claude for Financial Services" with FactSet/PitchBook integrations [4]. OpenAI released financial-services tools in March 2026 [5]. **The AI industry is building the pipeline that routes financial intent through their servers.**

### 1.2 The Information Leaked Is Economically Exploitable

**Intent data has a known market price.** US market makers paid **$1.19 billion in Q1 2025 alone** (~$4.9B annualized) for payment for order flow — the right to see retail trading intent before executing it, with Citadel Securities accounting for ~33% (SEC Rule 606 data) [6]. LLM conversation data contains a strictly richer signal: not just the trade, but the reasoning, portfolio context, and contingency plan.

**Partial information suffices.** Flashbots' MEV-Share research shows searchers profitably extract MEV even with partial transaction hints [7]. The study "How Informative Are MEV-Share Hints?" found minimal metadata is "far more strategy relevant than a naive parse suggests" [8]. An LLM conversation reveals far more.

**The MEV market is large.** Over **$1 billion** in MEV extracted post-Merge [9]. Sandwich attacks — pure information-asymmetry exploitation — constituted **51.56% of total MEV volume ($290M of $562M)** in 2025 [10]. A single bot (jaredfromsubway.eth) extracted **$40.65M in revenue** ($6.3M net profit) in ~2.5 months [11].

**Intent extraction is a solved problem.** Modern LLMs parse financial intent with >95% accuracy [12]. Financial intent classification achieves 90%+ accuracy on fine-grained taxonomies (demonstrated on the BANKING77 general banking intent benchmark, not DeFi-specific) [13]. Building an intent extraction pipeline over conversation logs requires only standard NLP tooling.

### 1.3 The Data Is Already Leaking

- **130,000+ AI conversations** from ChatGPT, Claude, Copilot, and others found publicly accessible on Archive.org via the Wayback Machine (discovered by researchers Henk van Ess and Nicolas Deleur; confirmed by 404 Media and Washington Post analysis of 93,000+ sessions) [14]. SafetyDetectives' analysis of a 1,000-session sample found insider trading plans and crypto wallet hacking attempts [15].
- **4.7% of enterprise employees** who use AI chatbots have pasted confidential company data (Cyberhaven analysis of 1.6M workers' activity) [16] — a figure likely underestimated as it only counts what their DLP product intercepted
- Samsung employees leaked source code to ChatGPT on **3 occasions within 20 days** (confirmed by Bloomberg) [17]
- OpenAI's 2024 revenue was **$3.7B projected** (NYT, September 2024), later revised to **$6B actual** (OpenAI CFO, January 2026), against operating costs significantly exceeding revenue. OpenAI began **testing ads in ChatGPT** in February 2026 [18].

### 1.4 The Private Read Problem and Its AI Extension

Vitalik's privacy roadmap [19] identifies four tracks, the third being **privacy of reads**. The PSE team notes this is "almost entirely unsolved" [20]. We identify the cloud LLM query as a **strictly more informative leakage**:

| Semantic Content Leaked | RPC Query | LLM Query |
|---|---|---|
| State accessed (address, slot) | Yes | Yes |
| **Intent** (buy/sell/provide liquidity) | No | **Yes** |
| **Strategy** (why, under what conditions) | No | **Yes** |
| **Portfolio context** (holdings, size) | No | **Yes** |
| **Risk tolerance / Contingency plans** | No | **Yes** |

The transaction lifecycle has three privacy layers:

```
Intent formation (private)
  → LLM query (leaks to provider)     ← THE PRIVATE QUERY PROBLEM (this work)
    → Transaction construction
      → RPC query (leaks to provider)  ← The private read problem (PSE/PIR)
        → Mempool (leaks to validators) ← Mempool privacy (Flashbots)
          → On-chain execution (public)
```

The private query problem sits **two steps earlier** than private reads, with **orders of magnitude richer information**, and has **no deployed solutions**. Notably, Vitalik's own blog post on local LLM privacy [21] frames cloud LLM use as a general infosec concern but does **not** connect it to Ethereum's privacy roadmap. Our paper bridges this gap.

### 1.5 Why Encryption Is Not the Answer

- **FHE-based inference**: 100-1000x overhead [22]. Impractical for real-time use.
- **MPC-based inference**: ~20 seconds for Llama 3 1B [23]. Not interactive.
- **TEE-based inference**: <7% overhead [24] but trusts hardware vendors, and stored conversation logs remain targets even with TEEs.

**We need to minimize what the cloud learns in the first place.**

## 2. Privacy-Preserving Query Orchestration

### 2.1 Architecture

A key design insight: **sanitization and cover generation do not require an LLM.** Sanitization is pattern matching (regex strips amounts, addresses, percentages). Cover generation is template filling (extract sentence structure, swap domain vocabulary). Both are deterministic, auditable, and run in microseconds with zero hardware. Only decomposition (breaking complex queries into sub-queries) and answer synthesis (combining cloud responses with private parameters) require a local LLM.

This yields a **tiered architecture** where the minimum viable deployment is a browser extension, not a $1,400 Mac:

```
┌──────────────────────────────────────────────────────────┐
│  User Device (browser extension — no GPU needed)          │
│                                                           │
│  User ──query──→ [Regex Sanitizer]  ← hard security      │
│                     1. Strip amounts, addresses,    boundary│
│                        percentages, leverage, timing       │
│                  [Template Cover Generator]  ← pure Python │
│                     2. Extract template from sanitized query│
│                     3. Fill template with k-1 cover domains │
│                     4. Shuffle real + covers                │
│                             │                             │
│                    send k queries via Tor (unlinkable)     │
└─────────────────────────────┼─────────────────────────────┘
                              ▼
              ┌───────┐  ┌───────┐  ┌───────┐
              │Cloud A│  │Cloud B│  │Cloud C│
              └───┬───┘  └───┬───┘  └───┬───┘
                  └──────────┼──────────┘
┌─────────────────────────────┼─────────────────────────────┐
│  User Device                ▼                              │
│                  [Discard cover responses]                  │
│                  User reads real response +                 │
│                  applies private parameters manually        │
│                                                            │
│  (Optional: Local LLM for decomposition + synthesis)       │
│                  Decomposes complex queries before cloud    │
│                  Synthesizes final answer with private params│
└────────────────────────────────────────────────────────────┘
```
*Figure 1: Tiered privacy orchestration. The regex sanitizer and cover generator form a hard security boundary that requires no LLM and no GPU — deployable as a browser extension. The optional local LLM adds decomposition (for complex queries) and automated synthesis (combining cloud answers with private parameters).*

### 2.2 Deployment Tiers

| Tier | Components | Hardware | Annual Cost | Protection |
|---|---|---|---|---|
| **0: Sanitize only** | Regex sanitizer | None (browser) | **$0** | Deterministic removal of numeric parameters |
| **1: Full pipeline** | + local LLM (14B+) + covers | Mac Mini ($200-467/yr) | **$200-500** | + topic hiding, decomposition, synthesis |

**Tier 0** eliminates the most economically exploitable data (trade size, liquidation threshold, wallet identity) at zero cost. Since the economic damage from intent leakage requires knowing *specific parameters* to profitably attack, sanitization alone eliminates direct parameter leakage for numerically-formatted values in all modeled parameter-dependent attack scenarios (Section 6.6, Benchmark F). The topic remains visible (the cloud knows the user is asking about lending), but without parameters the adversary cannot size or target an attack. **Deployable as a browser extension today.** UX caveat: regex stripping may produce garbled output (e.g., "My Aave V3 position has collateral and debt. health factor."). Users may need to rephrase sanitized queries before sending, or the extension can include a simple template-based rephrasing step (no LLM required).

**Tier 1** adds a local LLM that decomposes queries into generic sub-queries, generates template-matched cover queries, and synthesizes the final answer using private parameters. Cover queries require the local LLM because template rewriting without decomposition degrades answer quality to 2.3/5 — essentially useless (Section 6.5). With LLM-based decomposition, sub-queries are already generic enough that template rewriting preserves utility. This tier provides parameter hiding, topic hiding, and session protection. Cost: $200-500/year (hardware amortization + API).

Note: we initially proposed an intermediate tier (covers without a local LLM, $4-23/year). Benchmark D (Section 6.5) showed this is not viable — template rewriting of original queries destroys answer quality. Covers are only useful when combined with LLM-based decomposition.

### 2.3 Three Mechanisms

**Mechanism 1: Intent Sanitization (regex, no LLM)** — A deterministic pattern-matching layer strips private parameters (amounts, health factors, wallet addresses, percentages, leverage ratios, timing references) from queries. The cloud sees: *"How does adding collateral affect an Aave V3 position's health factor?"* — not the user's specific HF, collateral size, or debt amount. Because this is regex-based, it is deterministic, auditable, and produces **0% parameter leakage** for numerically-formatted values (2,600 synthetic variations tested) — compared to 30% leakage when a 7B LLM attempts the same task (Section 6.3). **Limitation**: The information-theoretic guarantee holds only for pattern-matchable parameters. Natural language paraphrases ("half a million USDC," "roughly two thousand ETH," "my six-figure position") bypass the regex. A secondary NLP-based filter (small classifier or entity recognizer) is recommended for production deployment. **Despite this gap, the regex layer catches the most common and most dangerous patterns — the specific numbers that enable an adversary to size and target an attack.**

**Mechanism 2: Cover Queries (template algorithm, no LLM)** — For each sanitized query, a deterministic algorithm extracts the sentence template and fills it with vocabulary from k-1 other DeFi domains, producing k indistinguishable queries. The cloud receives all k queries (via separate Tor circuits) and cannot determine which reflects the user's real interest. Unlike TrackMeNot (whose covers were detected with 99.98% accuracy [25]), our template + distribution matched covers reduce adversary detection to 25-29%, at the 25% random baseline, validated against both LLM adversaries and a trained DistilBERT classifier (Section 6.4).

**Mechanism 3: Query Decomposition (requires local LLM)** — Break complex queries into independent sub-queries about generic DeFi primitives. The strategy (the specific *combination* of primitives) exists only in the local context. This is the only mechanism that requires a local LLM, and is needed primarily for complex multi-step queries.

### 2.3 Privacy Guarantee

Our mechanism provides two distinct privacy properties with different guarantee strengths:

**Property 1: Parameter hiding** (via sanitization) — **Deterministic removal of pattern-matchable parameters.** The regex sanitizer strips numerically-formatted private parameters (dollar amounts, token quantities, addresses, percentages, leverage ratios) before they reach the cloud. What is stripped cannot be recovered. However, this is a guarantee about a *subset of string patterns*, not about the user's full sensitive state. Natural language paraphrases ("half a million," "roughly two thousand ETH"), qualitative descriptors ("underwater," "close to liquidation"), and implicit position signals ("What's a good health factor to maintain?") are not caught. The guarantee is: *pattern-matchable parameters are deterministically removed*. It is not: *all economically exploitable information is hidden*.

**Property 2: Topic hiding** (via cover queries) — **k-plausible deniability.** The adversary observes k queries per sub-query and cannot determine which reflects the user's real interest. The guarantee strength depends on cover quality:

- **If covers are indistinguishable from real queries**: Adversary success probability ≤ 1/k. With k=4, the adversary is correct at most 25% of the time. (This bound holds under the theorem's assumptions — see Section 6.4 for empirical validation and caveats.)
- **If covers have detectable patterns**: The bound degrades. TrackMeNot achieved ~0% plausible deniability because its covers were trivially classifiable [25].

**Formal guarantee for template-matched covers**: Under the v5 algorithm, we can state the following:

> **Theorem (k-indistinguishability).** Let T be a template, S = {D₁, ..., Dₖ} be k domains drawn from a set of equal-probability domains, and V_D denote the vocabulary distribution for domain D. The mechanism M(q) generates k queries {T(V_{D₁}), ..., T(V_{Dₖ})} where one domain corresponds to the real query's domain D_real ∈ S. If (i) the template T is identical for all k queries, (ii) domains are assigned uniformly at random, and (iii) vocabulary draws V_{Dᵢ} are independent of the real query's identity, then for any observation O and any two candidate real queries q, q' mapping to different domains: P(M(q) = O) = P(M(q') = O). The adversary's success probability is exactly 1/k.

*Proof sketch*: The observable output O = {T(V_{D₁}), ..., T(V_{Dₖ})} (shuffled) contains one query per domain in S. Since all k domains are present regardless of which is real, and the vocabulary draws are independent of the "real" label, O is identically distributed under q and q'. The adversary cannot distinguish which domain's query is real, yielding P(correct) = 1/k. ∎

*Conditions*: This holds when (1) the template is shared across all k queries, (2) domains are equiprobable, and (3) vocabulary fills within each domain use independent randomness (our implementation uses a local RNG instance to ensure this). **Assumption (3) is the weakest**: the template is extracted from the real query and may structurally favor the real domain's vocabulary — e.g., a template derived from a lending query may compose more naturally with lending terms than with derivatives terms. A classifier trained on naturalness could exploit this. The guarantee also degrades if: the vocabulary pools are too small (enabling memorization — our DistilBERT classifier detects this at 34% vs. 25% random, Section 6.4), or the adversary has per-user priors from metadata correlation.

**Connection to d-privacy** [26]: The above is a special case of d-privacy with ε = 0 for queries within the domain set S (perfect indistinguishability), and undefined for queries outside S (the mechanism does not cover rare domains). Extending to a formal ε·d-privacy bound over arbitrary query pairs, where d is semantic distance, requires calibrating the cover generation distribution against a reference query distribution — this remains future work. Our experimental results (Section 6.4) provide evidence that the v5 algorithm approaches this: adversary detection at 25-29% vs. 25% random baseline.

**Session-level composition**: Multiple queries in a session can jointly reveal information even if individually safe (Asif & Amiri [27] proved this formally). However, session composition depends on **metadata linkability**: if each query set is routed over independent Tor circuits with no identity link, the adversary cannot correlate queries across rounds and the session attack has no signal. Session composition is therefore reducible to the metadata privacy problem, which has known solutions (Section 2.4). When metadata linkability cannot be fully prevented, we propose (not yet implemented) a **privacy budget accountant** that:
- Tracks the cumulative topic correlation across queries sent to the cloud
- Increases k (more covers) when the session becomes topically focused
- Switches to **local-only mode** when the accumulated leakage estimate exceeds a configurable threshold
- Resets the budget on a new session or topic change

### 2.4 Threat Model

**Scope: Query content privacy.** Metadata privacy (IP, timing, linkability) is a separate concern but **load-bearing for the cover query mechanism**. The following table makes explicit which assumptions each tier requires:

| Assumption | Tier 0 (sanitize) | Tier 1 (full pipeline) |
|---|---|---|
| Regex covers all private param formats | Required (partial — numeric only) | Required |
| Per-query-set unlinkability (independent Tor circuits) | Not required | **Required** for cover and session protection |
| No timing correlation (query → on-chain action) | Not required | **Required** for session protection |
| Local model does not leak params during decomposition | Not required | Required (14B+ model, regex pre-filter) |
| Cover query templates compose naturally across domains | Not required | Required for answer quality |

**Tier 0's privacy claim is unconditional** — regex stripping works regardless of transport. **Tier 1's privacy claims are conditional on transport assumptions** that are achievable with known tools but operationally non-trivial. If per-set unlinkability fails, session composition and topic inference become significantly stronger. We state this as a first-class constraint, not a scoped-out detail.

While metadata privacy is out of scope for this work, the required mitigations are well-understood and achievable with existing tools: (1) each query in a cover set should be routed over an independent Tor circuit, preventing the exit node from observing query co-occurrence; (2) random delay injection (0-30 seconds) between query submission and any subsequent on-chain transaction breaks timing correlation; (3) query batching — accumulating queries and submitting them in fixed-interval batches (e.g., every 5 minutes) — prevents an observer from linking query rate to transaction timing; and (4) dummy traffic at regular intervals, even when the user is not querying, ensures a constant query rate that leaks no activity signal. These are standard anonymity techniques (Tor, mix networks, traffic shaping) applied to the query orchestration context, not novel contributions.

**Network effects strengthen all of the above.** Privacy tools have positive externalities — each additional user makes all existing users more private. If N users each send k=4 queries per real question, the cloud receives N×k queries per time window. An adversary attempting timing correlation between a specific query and a specific on-chain transaction must distinguish among N×k candidates, not just k. With wallet-level deployment (e.g., embedded in MetaMask), N could be tens of thousands of concurrent users. Additionally, other users' real queries serve as natural cover traffic: Alice's cover query about staking is indistinguishable from Bob's real query about staking. The domain distribution, which required artificial balancing in our experiments (Section 6.4), balances naturally in a multi-user population. **This argues strongly for wallet integration over standalone deployment** — the wider the adoption, the stronger the privacy for everyone, analogous to Tor's anonymity set or Flashbots Protect's adoption curve.

**Semi-honest adversary**: Observes query content, responds correctly. We protect against: extracting intent from individual queries, distinguishing real from cover queries, reconstructing strategy from decomposed sub-queries.

**Actively malicious adversary**: The cloud could manipulate responses to extract data (prompt injection via response, watermarking, canary queries, poisoned advice). The key defense is **statelessness between phases**: the query generation phase must NEVER be influenced by cloud responses. Each query batch is generated from the user's original query only; cloud responses feed only into the final local answer.

For correctness against active adversaries, we can use: TEE attestation (practical today, <7%), cross-provider verification (3x cost), or zkML (impractical but on trajectory). The local LLM acts as a verifier — it can detect gross factual errors, prompt injection attempts, and response uniformity violations. The human user is the final verifier, possessing the **private witness** (their actual position parameters) that makes verification easier than attack.

## 3. Anatomy of an Attack: A Concrete Walkthrough

### The Setup

**Alice** holds a leveraged Aave V3 position:
- Collateral: 1,000 ETH (~$2,500,000 at $2,500/ETH)
- Debt: 1,800,000 USDC
- Health factor: 1.15 (liquidation at ~$2,169/ETH)
- Uses Flashbots Protect (Layer 1 ✓) and TEE RPC (Layer 2 ✓)
- Uses ChatGPT for DeFi analysis (Layer 3: **unprotected**)

### The Query

Alice types:

> *"I have an Aave V3 position with 1,000 ETH collateral and 1.8M USDC debt. My health factor is 1.15. ETH is at $2,500. If ETH drops 10% to $2,250, my HF drops to about 1.035 — dangerously close to liquidation. Should I add 200 ETH more collateral now, or wait and close the position if ETH hits $2,250? Also, I want to hedge by buying put options on Lyra on Optimism."*

### What the Provider Records

```json
{
  "extracted_intent": {
    "protocol": "Aave V3",
    "collateral": "1000 ETH ($2.5M)",
    "debt": "1.8M USDC",
    "health_factor": 1.15,
    "liquidation_price": 2169,
    "plan_a": "add 200 ETH collateral",
    "plan_b": "close if ETH hits $2,250",
    "hedge": "put options on Lyra (Optimism)",
    "emotional_state": "anxious, indecisive"
  }
}
```

This extraction is trivial with >95% accuracy [12]. Stored for 30+ days, subpoenable, breachable, monetizable.

### The Exploitation Path

**Combined with chain analytics** (Chainalysis: 1B+ addresses clustered, 107K+ entities [28]):

1. Query mentions ~1,000 ETH collateral on Aave V3 at HF ~1.15
2. Chainalysis scans Aave V3: ~50 positions match these parameters
3. Timestamp correlation narrows to ~3 addresses
4. Alice is identified. Her Flashbots Protect and TEE RPC are irrelevant.

**Three attack vectors:**
- **Liquidation setup** ($45,000-$90,000): Pre-position as liquidator with exact threshold knowledge
- **Front-running the hedge** ($5,000-$25,000): Buy the same Lyra puts before Alice
- **Strategic shorting** ($10,000-$100,000): Open short position knowing a $2.5M leveraged position is in distress

**Total potential damage: $60,000-$215,000+**

### With the Privacy Orchestrator

The local 32B model decomposes Alice's query into:

| Sub-query (to cloud) | Cover 1 | Cover 2 | Cover 3 |
|---|---|---|---|
| "How does Aave V3 HF change when collateral is added?" | "How does Compound V3 calculate borrow APY?" | "What are MakerDAO's stability fee params?" | "How does Morpho Blue rate optimization work?" |
| "Gas costs: Aave collateral add vs. closure?" | "Gas costs: Uniswap v4 hook deployment?" | "Gas costs: bridging via LayerZero?" | "Gas costs: Gnosis Safe multisig?" |
| "ETH put premiums on Lyra?" | "How do Squeeth options on Opyn work?" | "dYdX ETH perps funding rate?" | "Panoptic concentrated liquidity options?" |

12 queries sent via separate Tor circuits. The cloud sees 12 anonymous, unlinkable DeFi questions. No position parameters, no wallet addresses, no strategy.

**The synthesized answer** (local, ~22 seconds): Combines cloud responses with Alice's private parameters to produce the same quality advice — but the cloud never saw the private parameters.

| | Without Protection | Tier 0 (regex, $0) | Tier 1 (+ covers, ~$0.003) |
|---|---|---|---|
| Adversary knows position size | **Yes** | No | No |
| Adversary knows liquidation threshold | **Yes** | No | No |
| Adversary knows topic (lending) | **Yes** | **Yes** | No (1/k) |
| Adversary can identify Alice on-chain | **Yes** | No | No |
| **Total damage** | **$60,000-$215,000+** | **~$0** | **~$0** |
| **Cost of protection** | $0 | **$0** | **~$0.003** |

## 4. Three Privacy Layers Compared

| Metric | Mempool (Layer 1) | RPC (Layer 2) | AI Query (Layer 3) |
|---|---|---|---|
| **What leaks** | Full signed transaction | State access pattern | Intent + strategy + portfolio |
| **Advance notice** | Seconds | Real-time | **Minutes to hours** |
| **Information richness** | Exact trade | Indirect | **Explicit, contextualized** |
| **Solutions deployed** | Flashbots Protect, MEV Blocker (~30% adoption) | TEE RPC (Automata), PIR (research) | **None** |
| **Cost to user** | Free | Free (TEE) | $0–$500/year (this work, tiered) |
| **Maturity** | Production | Early research | **Unaddressed** |

**The layers are complementary, not substitutes.** Alice using Flashbots Protect + TEE RPC but asking Claude about her position has **negated both protections**. The AI query layer is the weakest link — it leaks strictly more, earlier, with zero protection.

## 5. How Useful Is This? An Honest Analysis

### What Each Mechanism Buys

**Sanitization (Mechanism 1, regex, no LLM)** [measured]: Eliminates the most exploitable information — position parameters. Without knowing trade size, direction, or position specifics, the adversary cannot profitably attack. **Cost: $0. No hardware. Deployable as a browser extension today. This alone eliminates direct parameter leakage for numerically-formatted values in all modeled parameter-dependent attack scenarios.**

**Cover queries (Mechanism 2, template algorithm)** [measured]: Reduces adversary's topic identification from p=1.0 to ≤1/k. With k=4 and template+distribution matching, adversary detection rate drops to 25-29% (random baseline: 25%), validated by a trained DistilBERT classifier. **However, template rewriting degrades answer quality to 2.3/5 without LLM-based decomposition (Section 6.5). Covers are only viable when combined with Mechanism 3.**

**Decomposition (Mechanism 3, requires local LLM)** [measured]: Breaks complex queries into generic sub-queries, enabling cover queries that preserve answer quality. Also prevents strategy reconstruction from multi-turn conversations. **Cost: $200-500/year (local hardware amortization + API).**

**What does topic hiding (Mechanism 2) actually prevent beyond sanitization?** For the three main parameter-dependent attacks (front-running, liquidation hunting, strategy theft), sanitization alone reduces adversary profit to $0 because these attacks require specific parameters to execute. Topic-only knowledge (e.g., "someone asked about Aave health factors") has near-zero marginal value because: (1) liquidation bots already monitor all positions regardless of LLM queries; (2) swap front-running requires trade size and direction, not just the topic; (3) strategy theft requires the full multi-step plan, not just the domain. The exception is **unique position identification**: if only 3-5 positions match a narrow topic, the topic alone can deanonymize the user, enabling targeted attacks. This affects <1% of users (those with rare or very large positions) but the potential damage is high. **Covers protect this tail risk** — they prevent the adversary from learning even the topic, at the cost of requiring a local LLM ($200-500/year).

**The minimum viable product is a $0 browser extension** running Mechanism 1 (regex sanitization). For >99% of users, this is sufficient. Adding topic hiding via covers (Mechanisms 2+3, ~$200-500/year) protects the <1% with unique positions and prevents session-level strategy reconstruction.

### Latency Profile

We measured each pipeline stage on commodity hardware (Apple M-series, Qwen 2.5 7B via Ollama):

| Stage | Latency (M1 Pro, warm) | Notes |
|---|---|---|
| Regex sanitization | **4 ms** | Zero perceptible delay |
| Cover generation (k=4) | **0.2 ms** | Deterministic Python, no LLM |
| Local 7B decomposition | **~23 s** | Bottleneck; hardware-dependent (see below) |
| Cloud calls (k=4, parallel) | **~2 s** (API) / **~18 s** (local) | Parallel via independent circuits |
| Local 7B synthesis | **~19 s** | Second local inference call |
| **Total (cloud API, parallel)** | **~44 s** | Decompose + 2s cloud + synthesize |

**Tier 0** (regex only) adds zero perceptible latency — the sanitizer runs in milliseconds. The user types a query, the extension strips params instantly, and the sanitized query goes to the cloud at normal speed. **No UX penalty.**

**Tier 1** (full pipeline) is dominated by local inference speed. On an M1 Pro with Qwen 7B, total latency is **~44 s** (with cloud API) to **~60 s** (local only). This scales with hardware: an M4 Max at ~80 tok/s would reduce total to **~12 s** — approaching interactive. Local inference speed roughly doubles each Apple Silicon generation, so Tier 1 latency is on a clear improvement trajectory.

Inference speed scales with hardware and quantization: a 7B Q4 model runs at ~10-15 tok/s on M4 base, ~25-40 tok/s on M4 Pro, ~50-80 tok/s on M4 Max. A 32B Q4 model on M4 Pro achieves ~10-20 tok/s. Users prioritizing latency should use a 7B model for decomposition/synthesis (faster, but 30% param leakage — mitigated by the regex pre-filter) and cloud API (Haiku at ~1-3 s) for the knowledge queries.

**Optimization roadmap** to bring Tier 1 latency below 30 s: (1) Run the local LLM as a background service with pre-warmed context, eliminating cold-start overhead. (2) Cache decomposition templates for recurring query patterns — a user who repeatedly asks about health factors reuses the same sub-query structure. (3) Parallelize all k cloud calls via independent Tor circuits (already in the design, reduces cloud latency from k× to 1×). (4) Pre-generate cover queries while the user is typing, using partial input to predict the domain. (5) Use a distilled 7B model for decomposition (where the regex pre-filter catches any parameter leakage) and reserve larger models for synthesis only.

### Deployment Guide

**Tier 0** (zero cost): Implement the regex sanitizer as a browser extension or wallet plugin. The `sanitize_query()` function in `cover_generator.py` is ~50 lines of regex, portable to JavaScript. No model, no GPU, no server.

**Tier 1** (local LLM): Run a quantized open-weight model via [Ollama](https://ollama.com/) or [llama.cpp](https://github.com/ggerganov/llama.cpp):
- **Minimum hardware**: Mac Mini M4 base ($599) or equivalent with ≥16 GB unified memory. Runs 7B Q4 models.
- **Recommended**: Mac Mini M4 Pro ($1,399) with 24 GB. Runs 32B Q4 models at interactive speed.
- **Models**: Qwen 2.5 32B Q4 (`ollama pull qwen2.5:32b`), Llama 3 8B (`ollama pull llama3:8b`), or any GGUF checkpoint from HuggingFace.
- **Setup**: `brew install ollama && ollama serve && ollama pull qwen2.5:7b` — the benchmark suite then works with `--backend ollama`.

### Prior Work Validates the Architecture

| Approach | Utility Retained | Source |
|---|---|---|
| ConfusionPrompt | 93-95% | Mai et al. [29] |
| PPMI (1B local + cloud) | 109% on LoCoMo (outperforms cloud alone) | Bae et al. [30] |
| Minions (8B local + cloud) | 97.9% on FinanceBench | Stanford [31] |

### Where This Fails

1. **Uniquely identifying queries**: If Alice is the *only* Aave V3 user with ~1,000 ETH collateral near liquidation, the sanitized topic alone identifies her. How common is this? On-chain data suggests Aave V3 typically has hundreds to low thousands of active positions per major asset — but positions with very large collateral (>$1M) or extreme health factors (<1.1) may number only in the dozens. The orchestrator should estimate the on-chain anonymity set for the query's topic and route to local-only when the set is small.

2. **Session composition**: After ~10 topically correlated DeFi queries, accumulated topic signal can reconstruct strategy even if each query is individually safe (Section 6.7). However, this attack depends on **metadata linkability** — the adversary must know that queries across rounds came from the same user. Under the v5 design, each query set contains one query per top-4 domain regardless of which is real, so a single set reveals nothing about the user's topic. Session composition only works when the adversary can link sets over time, which is a metadata problem reducible to standard anonymity techniques (Section 2.4). The proposed privacy budget accountant (Section 2.3) provides an additional safeguard when metadata linkability cannot be fully prevented.

3. **Cover quality**: If covers are distinguishable from real queries (the TrackMeNot failure mode — 99.98% detection [25]), the guarantee collapses entirely. Our Benchmark C results (Section 6.4) show template + distribution matching solves this — detection dropped from 95% (naive) to 25-29% (at random baseline), validated against both LLM adversaries and a trained DistilBERT classifier. The critical requirement is balanced domain sampling: an unbalanced source pool leaked a domain distribution signal that a classifier exploited (64% detection), but balancing eliminated it.

4. **Cross-provider correlation**: An adversary controlling multiple cloud providers could compare query content, timing, or cover-query distribution patterns across providers to improve inference. Even with independent Tor circuits, if the cover generation strategy is uniform across providers (same style, same topic distribution), the correlation may be detectable. Diversifying cover generation per-provider mitigates but does not eliminate this risk.

    To quantify: suppose the adversary controls M of N providers and each provider receives the same set of k queries per sub-query. In the worst case (no per-provider diversification), all M providers see the identical k queries — the intersection is trivially the full set, and the adversary gains nothing beyond what a single provider already sees. The real threat is per-provider diversification done naively: if each provider receives a different set of k queries but the real query appears unchanged in all sets, the adversary intersects M sets of size k and recovers a 1-query intersection — the real query, identified with certainty. With k=4 and M=2, this reduces the adversary's uncertainty from 1/4 to 1/1. The fix is straightforward: the real query must also be template-varied per provider (not just the cover queries), so that each provider sees a semantically equivalent but lexically distinct version of the real query. With per-provider template variation, the intersection across M providers yields 0 exact matches, forcing the adversary back to semantic similarity analysis with no guaranteed advantage over single-provider observation. This is achievable with the existing template machinery but is not yet implemented.

5. **Metadata correlation**: If timing correlation links queries to on-chain transactions despite Tor/mixnet protections, the adversary can identify the real query by its temporal proximity to subsequent on-chain actions, rendering covers irrelevant. This is an orthogonal layer failure, not a content-privacy failure, but critical to acknowledge.

The orchestrator should be transparent about its limits: route to local-only when it detects edge case conditions (small anonymity set, exhausted session budget, high-value position).

## 6. Experimental Results

We ran benchmarks A-F using both a frontier model (Claude) and a local 7B model (Qwen 2.5) as generator and adversarial evaluator, plus a DistilBERT classifier for independent validation of cover indistinguishability. Sample sizes vary (A: n=40-100, B: n=10, C: n=20 LLM + 4,000 classifier examples, D: n=15, E: n=5 sessions × 10 queries, F: n=13 scenarios). Code, data, and all prompts (see `docs/`) are available at the companion repository.

### 6.1 Overview

| Benchmark | What It Tests | Target | Result | Verdict |
|---|---|---|---|---|
| **A: Sensitivity Classification** | Can a model detect private info in DeFi queries? | >90% F1 | **96-100% F1** (n=40-100, two models) | PASS |
| **B: Decomposition Quality** | Do sub-queries preserve utility without leaking params? | >85% coverage, 0% leakage | **100% / 0%** (frontier, n=5), **70% / 30%** (7B, n=10) | PASS / MARGINAL |
| **C: Cover Indistinguishability** | Template-filled queries: can adversary detect? | <55% detection | **27%** (LLM), **25-29%** (DistilBERT) | PASS |
| **C2: Deployed Pipeline** | Genericized sub-queries mixed with covers | <55% detection | **35%** (n=20) | PASS |
| **D: Answer Quality** | Does template rewriting preserve answer utility? | >80% scoring ≥4/5 | **20% scoring ≥4/5** (avg 2.3/5, n=15) | FAIL |
| **D2: Full Pipeline** | Decompose → genericize → synthesize (blinded A/B) | >80% quality retained | **3.8/5** (133% retained vs direct, n=5) | PASS |
| **E: Session Composition** | Do multi-query sessions leak strategy? | <40% recovery at 5 queries | **40% with covers** vs **100% without** | PASS |
| **F: Damage Model** | Illustrative economic model (not empirical) | — | Sanitization → $0 profit in modeled attacks | Illustrative |

### 6.2 Benchmark A: Sensitivity Classification

Both a frontier model (Claude) and a local 7B model (Qwen 2.5 7B) classified DeFi queries as sensitive vs. non-sensitive. At n=40 (20+20), both achieved **100% F1**. At n=100 (50+50), the 7B model achieved **98% F1** — two false negatives on borderline queries. Sensitive queries contained obvious lexical markers: dollar amounts, wallet addresses, position parameters, intent verbs ("buy," "sell," "swap"). Sensitivity classification is pattern matching, not hard reasoning.

**Caveat**: The two false negatives at scale suggest that borderline cases (e.g., "What's a good health factor to maintain on Aave?" — sounds generic but implies the user has an Aave position) remain challenging for smaller models. A regex pre-filter for known sensitive patterns (amounts, addresses) provides a deterministic fallback.

### 6.3 Benchmark B: Decomposition Quality

Ten complex DeFi queries were decomposed into sanitized sub-queries. Results depend on model capability:

| Model | Clean (0% leakage) | Leaked params | Notes |
|---|---|---|---|
| Frontier (Claude) | **100%** (5/5) | 0% | One near-miss ("underwater") caught on review |
| Local 7B (Qwen 2.5) | **70%** (7/10) | 30% | Leaked specific amounts, percentages, protocol names |

DeFi knowledge is naturally separable into (1) protocol mechanics (safe for cloud), (2) specific parameters (kept local), and (3) market data (fetchable via private RPC). Frontier models decompose cleanly; **smaller local models leak parameters**, revealing a deployment-critical capability gap. Production deployment requires at minimum a 14B+ model for sanitization, or a dedicated fine-tuned sanitization module.

**Near-miss detected** (frontier model): One sub-query used the word "underwater" to describe a losing position — qualitatively leaking PnL direction without stating numbers. This reveals a class of **implicit parameter leakage** through qualitative descriptors ("underwater," "about to be liquidated," "significantly imbalanced") that the orchestrator must strip in a second sanitization pass.

### 6.4 Benchmark C: Cover Indistinguishability

This is the linchpin benchmark. We ran five iterations with progressively stronger cover generation and adversarial detection:

| Version | Cover Strategy | Adversary | Detection Rate | vs. Random (25%) |
|---|---|---|---|---|
| v1 | Naive (different topic/tone) | Single-strategy | **95%** | 3.8x above |
| v2 | Tone-matched (operational framing) | Single-strategy | **60%** | 2.4x above |
| v3 | Template-matched (same sentence structure) | Single-strategy | **10%** | Below random |
| v4 | Template-matched | Multi-strategy (intuitive + structural + topical) | **60%** | 2.4x above |
| v5 | Template + domain-distribution matched | Multi-strategy | **0%** | Below random |

**The failure modes and their fixes**:

1. **Actionability signal** (v1→v2): Real queries sounded like "someone about to do something." Covers sounded educational. Fix: match operational framing. Detection: 95% → 60%.

2. **Template signal** (v2→v3): Real and cover queries had different sentence structures. Fix: extract the real query's syntactic template and fill with different domain nouns. Detection: 60% → 10%.

3. **Domain prior signal** (v3→v4→v5): A stronger multi-strategy adversary (v4) recovered to 60% detection by exploiting the fact that some DeFi topics (lending, DEXes) are more commonly queried, making them more likely to be real. Fix: draw all k queries (real + covers) from the top-N most common DeFi categories with equal base-rate probability. Detection: 60% → 0%.

**The algorithm that works**:

```
COVER_GENERATION(real_query):
  1. SANITIZE: Strip private params, qualitative descriptors, emotional language
  2. TEMPLATE: Extract sentence structure as template with domain-specific slots
  3. DOMAINS: Select k-1 cover domains from top-N DeFi categories
     (ensuring all k domains have roughly equal base-rate probability)
  4. FILL: Generate covers by filling template with cover domain vocabulary
  5. VERIFY: Length ±20%, valid question, no cross-domain leakage
  6. SHUFFLE: Randomize position
```

**Root cause**: Cover indistinguishability is not a fundamental impossibility but an engineering problem. When template and domain distribution are matched, the adversary has zero content-based signal. This directly contrasts with TrackMeNot, whose static word-list covers were detected with 99.98% accuracy [25].

**External classifier validation**: To address same-model bias (the LLM adversary may miss what it generated), we trained a DistilBERT classifier on 4,000 labeled (real, cover) query pairs:

| Classifier Test | Set-Level Detection | ROC-AUC | Signal Source |
|---|---|---|---|
| Unbalanced source pool | **64%** | 0.78 | Domain distribution leak |
| Balanced source pool (n=500) | **25%** | 0.52 | None detectable |
| Balanced source pool (n=1000, pre-fix) | **34%** | 0.58 | Non-deterministic dedup artifact |
| Balanced source pool (n=2000, deterministic) | **25-29%** | 0.52-0.54 | At random baseline |
| Random baseline | **25%** | 0.50 | — |

The initial classifier result (64%) was alarming — but the signal was entirely from domain distribution imbalance in the source query pool (lending queries were overrepresented as "real"). When source queries are balanced across the top-4 domains, the classifier drops to 25-29%, marginally above the random baseline. The residual signal at n=1000 appears to come from vocabulary repetition in small domain pools (only 12-13 unique source queries for derivatives/staking), not from any structural difference between real and cover queries. Per-domain ROC-AUC is near random (0.46-0.65) across all domains.

**What we can claim**:

| Claim | Confidence |
|---|---|
| Template + distribution matching eliminates structural and topical signals | **High** — verified across v1-v5 |
| A prompted LLM adversary cannot distinguish real from covers | **High** (n=20, two models) |
| A trained DistilBERT classifier cannot distinguish (balanced domains) | **High** (n=1000, AUC=0.58, set-level 34% vs. 25% random) |
| Domain distribution balance is critical | **High** — unbalanced pool → 64% detection, balanced → 25-29% |
| A sophisticated adversary with auxiliary data cannot distinguish | **Unknown** — metadata layer, out of scope |

### 6.5 Benchmark D: Answer Quality Under Template Rewriting

Template-matched covers achieve indistinguishability by rewriting the real query into the same template as covers — but this changes the question the cloud receives. We measured the impact by comparing the original sanitized query to its template-rewritten version (n=15, Qwen 2.5 7B as both answerer and judge):

| Score | Meaning | Count |
|---|---|---|
| 5 | Directly answers the original question | 0 (0%) |
| 4 | Mostly relevant | 3 (20%) |
| 3 | Partially relevant | 0 (0%) |
| 2 | Tangentially related | 10 (67%) |
| 1 | Irrelevant | 2 (13%) |
| **Average** | | **2.3/5** |

**This is a critical finding.** Template rewriting achieves privacy by making the query indistinguishable from covers, but the rewritten query often asks a different question than the user intended. Example: *"How does Aave V3 health factor change when collateral is added?"* becomes *"How does the utilization rate respond to market volatility in lending protocols?"* — a different mechanism, a different trigger, a different answer.

**Implication for the tiered architecture**: Cover queries without a local LLM (the proposed Tier 1 browser extension) have a severe utility problem. The privacy-utility tradeoff is sharper than anticipated:

| Approach | Privacy (detection rate) | Utility (answer quality) |
|---|---|---|
| No protection | 100% | 5/5 |
| Tier 0: Sanitize only (send original) | Topic exposed, params hidden | ~5/5 |
| Template covers, no LLM | 25-29% | **2.3/5** (FAIL) |
| **Full pipeline: decompose → genericize → covers → synthesize** | **35%** (C2, deployed config) | **3.8/5** (7B), quality retained |

The full pipeline (Benchmark D2, n=5, Qwen 7B) scores **3.6/5 with 60% scoring ≥4** — a substantial improvement over template-rewriting alone (2.3/5, 20%). The local LLM first decomposes the query into generic sub-queries (*"Would adding more collateral increase the health factor?"*), which are specific enough to get useful answers while being generic enough for cover generation. The 7B model's decomposition is imperfect (sometimes too vague); a 14B+ model would likely reach 4-5/5 based on the decomposition quality observed in Benchmark B with frontier models. **Covers are viable only when combined with LLM-based decomposition.**

### 6.6 Economic Damage Model (Illustrative, Not Empirical)

To illustrate the economic stakes, we modeled adversary profit across attack types and position sizes using MEV extraction formulas from Section 1.2. **This is an economic model, not an empirical benchmark** — it shows what happens *if* the sanitizer works perfectly *and* the adversary's only exploitable signal is the stripped parameters:

| Attack Type | Position Size | Damage (Unprotected) | Damage (Sanitized) | Reduction |
|---|---|---|---|---|
| Swap front-running | $50K–$5M | $50–$100,000 | **$0** | 100% |
| Liquidation hunting | $100K–$10M | $1,500–$175,000 | **$0** | 100% |
| Strategy theft | Any | $10K–$1M | **$0** | 100% |

In this model, sanitization reduces adversary profit to zero for parameter-dependent attacks, because the adversary cannot size or target an attack without knowing trade size, direction, or position specifics. **This is conditional on the sanitizer catching all relevant parameters** — which it does for numeric formats but not for natural language paraphrases or implicit signals (Section 2.3). The model does not account for topic-only attacks (narrowing on-chain search by domain) or metadata correlation. It illustrates the *ceiling* of sanitization's value, not the floor of the adversary's residual capability.

### 6.7 Benchmark E: Session Composition

We simulated 5 realistic DeFi sessions (10 queries each) where a user follows a coherent strategy (e.g., leveraged ETH accumulation, stablecoin yield rotation, options hedging). **Metric**: at each checkpoint, the adversary is given the accumulated queries and must select the user's true strategy from 5 options (1 correct + 4 plausible decoys). "Recovery rate" = probability of exact correct identification. Random baseline: 20% (1/5).

| Queries Observed | Without Covers | With Covers (k=4) |
|---|---|---|
| 1 | **100%** | **20%** |
| 3 | **100%** | **40%** |
| 5 | **100%** | **40%** |
| 10 | **100%** | **60%** |

Without covers, the adversary identifies the user's strategy from the **very first query** — 100% recovery at every checkpoint. With k=4 cover queries per step, recovery stays at or near random baseline through 5 queries and only reaches 60% after 10 queries.

**Implications**: (1) Even a single unprotected query reveals strategy — confirming the threat model. (2) Cover queries provide substantial session-level protection, delaying strategy reconstruction by 5-10x. (3) The privacy budget accountant (Section 2.3) should trigger local-only mode or increase k after approximately 5-7 topically correlated queries, when the adversary begins to accumulate meaningful signal.

### 6.8 Remaining Work and Caveats

- **Same-model bias — addressed**: We trained an independent DistilBERT classifier on 4,000 labeled examples (Section 6.4). With balanced domain sampling, the classifier achieves 25-29% set-level detection (random baseline: 25%), confirming that the LLM adversary result is not an artifact of same-model bias.
- **Local model capability gap — quantified**: A 7B local model (Qwen 2.5) achieves 100% on sensitivity classification but leaks private parameters 30% of the time during decomposition (Section 6.3). Production deployment requires a 14B+ model for sanitization.
- **Session composition — tested and analyzed**: Benchmark E (Section 6.7) shows covers delay strategy reconstruction from 1 query to 5-10 queries under worst-case metadata linkability (adversary knows all sets are from the same user). However, session composition is reducible to metadata linkability — with per-set unlinkability (independent Tor circuits), the attack has no signal. The proposed privacy budget accountant provides defense when perfect unlinkability cannot be guaranteed.
- **Benchmark D/D2 — template rewriting alone FAILS (2.3/5), genericized pipeline PASSES (3.8/5)**: Template rewriting destroys answers. The full pipeline (decompose → genericize sub-queries by stripping protocol names → synthesize) scores 3.8/5 in blinded A/B, matching or exceeding direct queries. Genericized queries are detected at 35% (Benchmark C2) — between the template baseline (27%) and raw sub-queries (~67%). **Protocol name removal is the key signal elimination: it preserves the mechanism question while removing the adversary's main detection heuristic.**
- **No real user queries**: We use realistic synthetic queries — real user queries are privacy-sensitive by definition.
- **Vocabulary diversity**: The residual classifier signal at n=1000 (34% vs. 25%) likely stems from small domain vocabulary pools. Expanding the DeFi ontology (more protocols, mechanisms, operations per domain) would reduce this further.

## 7. Related Work

**Ethereum privacy**: Vitalik's privacy roadmap [19] identifies read privacy as critical but does not mention AI/LLMs. The Sharded PIR proposal [32] notes that "leaking what is being read can lead to frontrunning and other extractive MEV" — our work extends this observation to the AI query layer. While at least one ethresear.ch post has explored differential privacy in a DeFi context (e.g., "Differentially Private Uniswap in ETH2"), **no ethresear.ch posts address AI query privacy** — the leakage from user-to-LLM conversations before transacting.


**PII/DLP sanitization for LLMs**: Enterprise tools already use regex + ML to strip personally identifiable information before LLM queries — Strac, LLM Guard, PrivacyScrubber, Nightfall, and Microsoft Azure Language Service all offer this pattern. The technique (regex as fast first pass, NER as second pass, pseudonymization with placeholders) is well-established. Our contribution is not the regex technique itself but its **domain-specific specialization for DeFi**: a pattern set targeting health factors, token quantities, leverage ratios, and wallet addresses — parameters whose leakage enables MEV extraction, not just identity theft. No existing DLP tool models DeFi-specific exploitability or generates cover queries for topic hiding.

**Query obfuscation**: TrackMeNot [25] failed because cover queries were trivially distinguishable. We use a deterministic template-matching algorithm — the same structural indistinguishability that makes AI-generated text hard to detect works in our favor.

**Local LLM for privacy**: Vitalik's local LLM setup [21] advocates running models locally for general privacy. ConfusionPrompt [29], PPMI [30], and Minions [31] demonstrate that local-cloud hybrid architectures can preserve utility while keeping private data on-device (97.9% quality retention on FinanceBench). Our architecture follows this pattern but adds two elements: (1) a deterministic regex pre-filter that provides a hard security boundary independent of the local model's capability, and (2) cover queries for topic hiding beyond what local-only inference provides.

**Anonymous API payments**: Crapis & Buterin [36] propose ZK API Usage Credits — a protocol using Rate-Limit Nullifiers and ZK-STARKs to enable anonymous, metered payment for LLM inference. Users deposit once on-chain and make thousands of unlinkable API calls. Their work solves **sender anonymity** (who is querying), while ours solves **content privacy** (what is being queried). The two compose: ZK API credits prevent the provider from linking queries to a wallet, while our sanitization + covers prevent the provider from learning intent from query content. Notably, discussion of their proposal by `omarespejel` identified that inference metadata (output token counts, latency patterns, speculative decoding rates) can re-link anonymous sessions with ~96% accuracy — reinforcing our argument that metadata privacy is load-bearing (Section 2.4). Their dual staking mechanism (RLN stake for double-spend, policy stake for ToS violations) is a concrete instantiation of the on-chain accountability we sketch in Part 2.

**Stateful anonymous credentials**: Shih et al. [37] propose zk-promises — anonymous credentials with asynchronous callbacks that allow a server to update a client's private state (reputation, bans, rate limits) without learning the client's identity. This composes with our architecture and Crapis & Buterin's ZK API Credits [36] to form a three-layer privacy stack: zk-promises for anonymous identity and moderation, ZK API Credits for anonymous payment, and our work for anonymous query content. Together, the server knows neither who asked, nor how much they paid, nor what they asked — but can still moderate abuse, enforce rate limits, and get paid. Their callback mechanism is also a more rigorous primitive for the privacy budget accountant we propose in Section 2.3: the server could increment a user's topic-correlation counter via a callback without learning which topics were queried.

**Differential privacy in blockchain**: Essentially absent. One paper applies verifiable DP to transaction amounts [33]. Dandelion++ [34] provides DP-like network anonymity. Our application to AI query privacy is novel.

**Agent communication privacy**: Firewalled Agentic Networks [35] applies information flow control between collaborating AI agents (data firewalls, trajectory firewalls, input firewalls), analogous to our sanitization mechanism but targeting inter-agent coordination rather than user-to-cloud query privacy.

**Regulatory context**: Existing data protection regulations create legal incentives for privacy-preserving query architectures. GDPR Article 17 ("right to be forgotten") and CCPA give users theoretical rights over data held by LLM providers, but enforcement is impractical for conversational data. The EU AI Act classifies AI systems used for financial advisory purposes as "high-risk" (Annex III), imposing transparency and data governance requirements. Each tier maps to specific obligations:

| Regulation | Tier 0 (sanitize) | Tier 1 (full pipeline) |
|---|---|---|
| GDPR Art. 25 (data minimization) | Params never transmitted — satisfied by design | + topic hidden — stronger compliance |
| GDPR Art. 32 (security of processing) | Regex pre-filter as technical safeguard | + covers as additional safeguard |
| EU AI Act Annex III (high-risk) | Provider never sees private financial data | + provider cannot determine query topic |
| CCPA §1798.100 (right to know) | Nothing to disclose — params not collected | + topic not identifiable in logs |

Providers adopting the orchestrator pattern could materially reduce their regulatory surface. Note that even when data never leaves the user device (Tier 0), a Data Protection Impact Assessment (DPIA) may still be required under GDPR Art. 35 for high-risk processing contexts — the sanitizer reduces *what* is processed, but does not eliminate the obligation to assess *how* it is processed. We note this as context for adoption incentives, not as legal analysis.

## 8. Conclusion

The Ethereum community has identified and is solving privacy at the mempool layer (Flashbots) and the RPC layer (PIR, TEEs). But a new, more informative leakage channel has emerged: users querying cloud LLMs about their DeFi positions before transacting. This channel leaks intent, strategy, portfolio context, and reasoning — two steps earlier than RPC reads, with orders of magnitude richer information — and has zero deployed protection.

We propose privacy-preserving query orchestration with a tiered architecture. **The core contribution is narrow and concrete**: client-side regex sanitization deterministically removes numerically-formatted private parameters — the data most directly exploitable for MEV, liquidation hunting, and front-running — at zero cost, with no LLM and no hardware. This is deployable as a browser extension today.

Cover queries for topic hiding are promising but conditional: they require a local LLM for decomposition and a genericization step (stripping protocol names from sub-queries). Template rewriting alone degrades answers to 2.3/5; genericization preserves utility (3.8/5) while reducing detection from 67% (raw sub-queries) to 35% (Benchmark C2). The residual 10-point gap between C2 (35%) and C (27%) reflects the phrasing difference between genericized natural language and mechanical template fills — an engineering gap, not a fundamental one.

**What we have shown**: (1) The private query problem is real, quantifiable, and unaddressed in the Ethereum privacy roadmap. (2) Regex sanitization materially reduces the most economically exploitable leakage at zero cost. (3) Cover queries achieve near-random indistinguishability but are viable only with LLM decomposition and transport unlinkability. (4) Naive covers fail as badly as TrackMeNot (95% detection), confirming that indistinguishability is an engineering problem requiring careful design.

**What we have not shown**: (1) That all economically exploitable information is hidden (natural language paraphrases and implicit signals bypass the regex). (2) That the full pipeline preserves answer quality at frontier-model levels (3.6/5 with a 7B model, untested with 14B+). (3) That the transport assumptions hold in practice (Tor unlinkability is achievable but operationally non-trivial).

The Ethereum privacy roadmap should include AI query privacy as a concern alongside mempool privacy and read privacy.

---

*A companion post covering practical defenses against active providers (response manipulation, fingerprinting, GPU TEEs, and a research agenda for cryptoeconomic accountability) is available as Part 2.*

## References

[1] FINRA Investor Education Foundation, "Financial Professional or Artificial Intelligence?" May 2024. N=1,033 US adults. 5% use AI for financial decisions, 20% interested. https://www.finrafoundation.org/sites/finrafoundation/files/2024-10/the-machines-are-coming.pdf (accessed April 2026).
[2] eToro, "Retail Investor Beat," August 2025. Global: 19% AI usage, n=11,000 across 13 countries. US: 30% AI usage, n=1,000. https://www.etoro.com/news-and-analysis/etoro-updates/retail-investors-flock-to-ai-tools-with-usage-up-46-in-one-year/ (accessed April 2026).
[3] GPTsHunter, "Finance & Crypto GPT Usage Data," GPTsHunter (third-party Custom GPT tracker; not an official OpenAI source), 2025. https://www.gptshunter.com/ (accessed April 2026).
[4] Anthropic, "Claude for Financial Services," July 2025. https://www.anthropic.com/news/claude-for-financial-services (accessed April 2026).
[5] Bloomberg, "OpenAI Releases New Financial Services Tools," March 5, 2026. https://www.bloomberg.com/news/articles/2026-03-05/openai-releases-new-financial-services-tools-rivaling-anthropic (accessed April 2026).
[6] SEC Rule 606(a) data aggregated by Global Trading. Q1 2025: $1.19B total PFOF, Citadel ~33%. https://www.globaltrading.net/payment-for-us-retail-flow-reaches-record-high-led-by-citadel-securities-imc/ (accessed April 2026). See also: SEC DERA, "How Does Payment for Order Flow Influence Markets?" https://www.sec.gov/files/dera_wp_payment-order-flow-2501.pdf (accessed April 2026); CRS IF12594.
[7] Flashbots, "Searching on MEV-Share," 2023. https://writings.flashbots.net/searching-on-mev-share (accessed April 2026).
[8] Flashbots Collective, "How Informative Are MEV-Share Hints?" 2026. https://collective.flashbots.net/t/how-informative-are-mev-share-hints-searcher-route-choice-blind-bidding-and-retained-surplus-on-flashbots-surfaces/5632 (accessed April 2026).
[9] Flashbots, "MEV-Explore," post-Merge data. >330,000 ETH extracted. https://explore.flashbots.net/ (accessed April 2026).
[10] EigenPhi, "Sandwich Overview," EigenPhi MEV Dashboard, March 4, 2025 snapshot (sandwich attacks: $289.76M of $561.92M total MEV volume, 51.56%). https://eigenphi.io/mev/ethereum/sandwich (accessed April 2026). See also: CoinTelegraph Research / EigenPhi, "Exclusive Data from EigenPhi Reveals That Sandwich Attacks on Ethereum Have Waned," 2025. https://cointelegraph.com/research/exclusive-data-from-eigenphi-reveals-that-sandwich-attacks-on-ethereum-have-waned (accessed April 2026).
[11] EigenPhi, "Performance Appraisal of jaredfromsubway.eth," EigenPhi Substack, 2023. $40.65M revenue, $6.3M net profit, ~2.5 months. https://eigenphi.substack.com/p/performance-appraisal-of-jaredfromsubway-eth (accessed April 2026).
[12] Lopez-Lira & Tang, "Can ChatGPT Forecast Stock Price Movements? Return Predictability and Large Language Models," arXiv, 2023. https://arxiv.org/abs/2304.07619 (accessed April 2026).
[13] Casanueva et al., "Efficient Intent Detection with Dual Sentence Encoders," arXiv, 2020. Introduces the BANKING77 dataset (77 general banking intent categories, 90%+ accuracy); note: this is a banking domain benchmark, not DeFi-specific. https://arxiv.org/abs/2003.04807 (accessed April 2026).
[14] 404 Media, "More than 130,000 Claude, Grok, ChatGPT, and Other LLM Chats Readable on Archive.org," August 2025. Original researcher: Henk van Ess. Washington Post independently analyzed 93,000+ sessions. https://www.404media.co/more-than-130-000-claude-grok-chatgpt-and-other-llm-chats-readable-on-archive-org/ (accessed April 2026).
[15] SafetyDetectives, "Analysis of 1,000 Leaked ChatGPT Sessions," 2025. https://www.safetydetectives.com/blog/chatgpt-leaks/ (accessed April 2026).
[16] Cyberhaven, "11% of Data Employees Paste into ChatGPT Is Confidential," February 2023. Analysis of 1.6M workers. (Note: vendor data, not independently verified.) https://www.cyberhaven.com/blog/4-2-of-workers-have-pasted-company-data-into-chatgpt (accessed April 2026).
[17] Bloomberg, "Samsung Bans ChatGPT and Other Generative AI Use by Staff After Leak," May 2023. https://www.bloomberg.com/news/articles/2023-05-02/samsung-bans-chatgpt-and-other-generative-ai-use-by-staff-after-leak (accessed April 2026).
[18] NYT (September 2024): OpenAI projected $3.7B revenue, ~$8.7B costs. OpenAI CFO (January 2026): actual 2024 revenue $6B. OpenAI, "Testing Ads in ChatGPT," February 9, 2026. https://openai.com/index/testing-ads-in-chatgpt/ (accessed April 2026).
[19] Vitalik Buterin, "A Maximally Simple L1 Privacy Roadmap," Ethereum Magicians, April 2025. https://ethereum-magicians.org/t/a-maximally-simple-l1-privacy-roadmap/23459 (accessed April 2026).
[20] PSE Team, "Ethereum's Privacy Stack: What Leaks, What's Fixed, What's Missing," HackMD, February 2026. https://hackmd.io/lcrJeeKyR-ujW50zcWZcbg (accessed April 2026).
[21] Vitalik Buterin, "My Self-Sovereign / Local / Private / Secure LLM Setup," April 2, 2026. https://vitalik.eth.limo/general/2026/04/02/secure_llms.html (accessed April 2026).
[22] De Castro et al., "EncryptedLLM: Privacy-Preserving Large Language Model Inference via GPU-Accelerated Fully Homomorphic Encryption," ICML 2025. GPU-accelerated FHE forward passes on GPT-2. https://proceedings.mlr.press/v267/de-castro25a.html (accessed April 2026).
[23] Nillion, "Fission: Distributed Privacy-Preserving LLM Inference," IEEE S&P, 2025. https://eprint.iacr.org/2025/653 (accessed April 2026).
[24] "Confidential Computing on NVIDIA Hopper GPUs," arXiv:2409.03992, 2024. https://arxiv.org/abs/2409.03992 (accessed April 2026).
[25] Peddinti & Saxena, "On the Privacy of Web Search Based on Query Obfuscation: A Case Study of TrackMeNot," PETS, 2010. https://link.springer.com/chapter/10.1007/978-3-642-14527-8_2 (accessed April 2026).
[26] Chatzikokolakis et al., "Geo-Indistinguishability: Differential Privacy for Location-Based Systems," CCS, 2013. https://arxiv.org/abs/1212.1984 (accessed April 2026).
[27] Asif & Amiri, "Information-Theoretic Privacy Control for Sequential Multi-Agent LLM Systems," arXiv, 2026. https://arxiv.org/abs/2603.05520 (accessed April 2026).
[28] Chainalysis, "Blockchain Intelligence," Chainalysis, 2025. 1B+ addresses clustered, 107K+ entities. https://www.chainalysis.com/blockchain-intelligence/ (accessed April 2026).
[29] Mai et al., "ConfusionPrompt: Practical Private Inference for Online Large Language Models," arXiv, 2024. https://arxiv.org/abs/2401.00870 (accessed April 2026).
[30] Bae et al., "PPMI: Privacy-Preserving LLM Interaction," arXiv, 2025. https://arxiv.org/abs/2506.17336 (accessed April 2026).
[31] Narayan et al., "Minions: Cost-efficient Collaboration Between On-device and Cloud Language Models," Stanford, arXiv, 2025. https://arxiv.org/abs/2502.15964 (accessed April 2026).
[32] Atiia & Lee, "Sharded PIR Design for the Ethereum State," ethresear.ch, March 2026. https://ethresear.ch/t/sharded-pir-design-for-the-ethereum-state/24552 (accessed April 2026).
[33] Movsowitz Davidow et al., "Privacy-Preserving Transactions with Verifiable Local DP," AFT, 2023. https://eprint.iacr.org/2023/126 (accessed April 2026).
[34] Fanti et al., "Dandelion++: Lightweight Cryptocurrency Networking with Formal Anonymity Guarantees," ACM SIGMETRICS, 2018. https://arxiv.org/abs/1805.11060 (accessed April 2026).
[35] Abdelnabi et al., "Firewalls to Secure Dynamic LLM Agentic Networks," arXiv, 2025. https://arxiv.org/abs/2502.01822 (accessed April 2026).
[36] Crapis & Buterin, "ZK API Usage Credits: LLMs and Beyond," ethresear.ch, February 2026. https://ethresear.ch/t/zk-api-usage-credits-llms-and-beyond/24104 (accessed April 2026).
[37] Shih, Rosenberg, Kailad & Miers, "zk-promises: Anonymous Moderation, Reputation, and Blocking from Anonymous Credentials with Callbacks," IACR ePrint 2024/1260. https://eprint.iacr.org/2024/1260 (accessed April 2026).
