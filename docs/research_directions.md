# Research Directions

Open problems and future work beyond the current prototype. Each direction includes the problem statement, why it matters, concrete approaches, and estimated effort.

---

## 1. NER-Based Quantity Filter

**Problem**: The regex sanitizer misses natural-language quantities ("three quarters of my portfolio," "roughly double what I started with," "a whale-sized position"). The fuzz test shows a ~1.2% leak rate from adversarial formatting; semantic quantities are an additional unquantified gap.

**Why it matters**: These are exactly the phrases privacy-conscious users might use instead of exact numbers — thinking they're being vague when they're actually leaking exploitable magnitude information.

**Approaches**:

A. **spaCy custom NER** — Train a small entity recognizer on DeFi-specific quantity expressions. Input: sanitized query text. Output: spans tagged as `QUANTITY`, `MAGNITUDE`, `DIRECTION`. Strip or replace with placeholders. ~12MB model, <10ms inference, runs in browser via WASM.

B. **Fine-tuned DistilBERT classifier** — Binary classifier: "does this text still contain quantity information?" Train on (original, sanitized, label: still_leaks?) pairs. Use as a second-pass filter after regex. Can leverage the existing classifier infrastructure.

C. **Rule-based number-word parser** — Extend the current cardinal/fraction patterns to a proper English number parser (handle "twenty-five thousand three hundred and forty-two"). Libraries exist: `text2num`, `word2number`. Limitation: English only.

**Recommended**: Start with C (lowest effort, immediate gain), then add A for semantic coverage.

**Effort**: C = 1-2 days. A = 1-2 weeks (data annotation + training). B = 3-5 days.

---

## 2. Formal ε-d-Privacy Proof

**Problem**: The current k-indistinguishability theorem (Section 2.3) is informal and its assumptions are stronger than what the implementation achieves. The DistilBERT classifier at AUC 0.507 provides empirical evidence but not a formal bound.

**Why it matters**: A formal proof would transform the paper from "empirical evidence that covers work" to "provable privacy under stated assumptions" — a much stronger claim for academic venues and regulatory compliance.

**Approaches**:

A. **Metric d-privacy framework** (Chatzikokolakis et al., CCS 2013) — Define a metric d(q, q') over the query space (e.g., embedding cosine distance). Show that the cover generation mechanism M satisfies: P(M(q) ∈ S) ≤ e^(ε·d(q,q')) · P(M(q') ∈ S) for all measurable S. The key challenge: calibrating the cover distribution so ε is small.

B. **Template-based proof** — Under the v5 algorithm's exact assumptions (identical template, uniform domain, independent vocabulary draws), prove P(correct identification) = 1/k exactly. Then bound the degradation when assumptions are relaxed (finite vocabulary, non-uniform domain priors, template extraction leakage). Express as ε = f(vocabulary_size, domain_imbalance, template_leakage).

C. **Empirical ε estimation** — Run a large-scale experiment (n=10,000+) with the strongest available adversary (fine-tuned RoBERTa-large). Compute the empirical advantage: ε_emp = ln(detection_rate / (1/k)). Report this as an upper bound on the mechanism's privacy loss.

**Recommended**: B for the formal result (publishable), C as a complement (practical bound).

**Effort**: B = 2-4 weeks (requires cryptographer collaboration). C = 3-5 days.

---

## 3. Real User Query Corpus

**Problem**: All evaluation uses synthetic data. Real DeFi queries are inherently private — we scanned 1M WildChat conversations and found only 38 DeFi-related queries (0.004% hit rate), almost all about coding, not personal positions.

**Why it matters**: Synthetic queries may not capture the distribution of phrasing, complexity, and implicit leakage patterns that real users produce. External validity of all benchmarks depends on this.

**Approaches**:

A. **Privacy-preserving local validation** — Users run the sanitizer on their actual queries locally and report only binary results (leaked/clean). The repo already includes this as a contribution pathway. Scale: aim for 500+ binary reports from DeFi community members.

B. **Wallet provider partnership** — Partner with a DeFi wallet or frontend (MetaMask, Zapper, DeBank) that already has AI chat features. Deploy the sanitizer as an opt-in middleware; collect only the sanitized outputs + user feedback on whether the sanitization was adequate. No raw queries leave the device.

C. **Simulated-real corpus** — Use a frontier LLM to role-play as DeFi users with different profiles (whale, degen, conservative LP, governance participant) and generate queries in their voice. Less authentic than real data but captures more diverse phrasing than hand-crafted synthetic queries.

D. **Bounty program** — Pay DeFi users to write "queries that sound like what you'd actually type" (not their real queries). $5-10 per realistic query. Target: 500 queries across 10 user profiles.

**Recommended**: A (zero cost, already set up) + D (fast, diverse) as immediate steps. B for long-term external validity.

**Effort**: A = ongoing (community). D = 1-2 weeks + $2,500-5,000 budget. B = months (partnership).

---

## 4. Cross-Provider Collusion Simulation

**Problem**: The current per-provider diversification ensures zero query intersection across providers. But a coalition of M providers could use statistical techniques (query timing, topic distribution, template similarity) to correlate sessions even without exact query matches.

**Why it matters**: The three-layer privacy stack (zk-promises + ZK API Credits + our work) assumes provider independence. If providers collude, the effective anonymity set shrinks.

**Approaches**:

A. **M-provider intersection attack** — Simulate M=2,3,5 colluding providers. Each receives a different cover set (via `generate_per_provider`). The coalition intersects topic distributions, template structures, and timing patterns. Measure: how much does the coalition's detection rate improve over a single provider?

B. **Timing correlation attack** — Add realistic timing to the simulation: query submission timestamps, response latencies, on-chain transaction timestamps. Measure: given timing alone, can the coalition link query sets to the same user across providers?

C. **Mitigation: per-provider template variation** — Already partially implemented (`generate_per_provider` ensures zero exact intersection). Extend to vary the template structure itself per provider, not just the vocabulary fill. Measure improvement in coalition resistance.

**Recommended**: A first (quantifies the threat), then C (builds the defense).

**Effort**: A = 1-2 weeks. B = 2-3 weeks. C = 1 week.

---

## 5. Cover-Traffic Pool

**Problem**: Individual users generating k=4 cover queries multiply their API costs by 4x and create distinctive traffic patterns (bursts of 4 queries). With many users, the aggregate traffic is more natural, but each user bears the full cost individually.

**Why it matters**: A shared cover-traffic pool would: (a) reduce per-user cost (covers are shared), (b) create natural-looking aggregate traffic, (c) increase the anonymity set for timing analysis.

**Approaches**:

A. **Centralized relay** — A privacy-focused relay service collects sanitized queries from multiple users, adds cover queries, and forwards batches to cloud providers at fixed intervals. Simple to build but introduces a trusted intermediary.

B. **Decentralized pool via smart contract** — Users deposit query credits into a pool contract. The pool generates and submits cover queries at a constant rate, independent of individual user activity. Real queries are mixed into the constant-rate stream. Implements the "dummy traffic at constant rate" defense from Section 2.4.

C. **P2P mixnet** — Users form a peer-to-peer network where each node's real queries serve as cover traffic for other nodes. No central point of failure. Requires a minimum number of active participants for the anonymity set to be meaningful.

**Recommended**: A as proof-of-concept, B as the production design.

**Effort**: A = 2-3 weeks. B = 2-3 months (smart contract + off-chain relay). C = 3-6 months.

---

## 6. ZK Proofs of Correct Sanitization

**Problem**: How can a user prove to a verifier (e.g., a DeFi protocol, a regulator) that their query was correctly sanitized WITHOUT revealing the original query?

**Why it matters**: Non-repudiability. If a user claims "I sanitized my query before sending," the provider currently has no way to verify this. ZK proofs would enable verifiable privacy compliance.

**Approaches**:

A. **ZK-SNARK over regex execution** — Prove that the sanitized output is the result of running the regex sanitizer on SOME input, without revealing the input. The regex sanitizer is deterministic, so this is a well-defined computation. Tools: circom (for regex circuits), Halo2, or Plonky2.

B. **Committed sanitization** — The user commits to hash(original_query) before sanitization, then reveals the sanitized output. A ZK proof shows: "the sanitized output was derived from an input whose hash matches the commitment, by running the sanitizer function." This provides non-repudiability without revealing the original.

C. **TEE-attested sanitization** — Run the sanitizer inside a TEE (e.g., Intel SGX enclave or WASM sandbox). The TEE attests: "this sanitized output was produced by running the verified sanitizer code on some input." Weaker than ZK (trusts hardware) but much simpler to implement.

**Recommended**: C for immediate practicality, A/B for the research contribution.

**Effort**: C = 2-4 weeks. A = 3-6 months (circuit design + optimization). B = 2-3 months.

---

## 7. Adversarial Fine-Tuning Resistance

**Problem**: A malicious cloud provider could fine-tune their model to recognize the sanitizer's "fingerprint" — the distinctive patterns that sanitized/genericized queries produce. For example, the model could learn that queries mentioning "lending protocols" (generic) instead of "Aave V3" (specific) are more likely to come from privacy-conscious users.

**Why it matters**: This is the long-term adversarial arms race. If the provider actively adapts to the privacy tool, the tool must adapt back.

**Approaches**:

A. **Adversarial training for the cover generator** — Train the cover generator against a discriminator that tries to distinguish sanitized/genericized queries from natural user queries. The generator adapts to minimize detectability. This is a GAN-style approach applied to query privacy.

B. **Style transfer for genericization** — Instead of regex-based protocol name stripping, use a small neural style-transfer model that rewrites queries into a "natural generic" style that is indistinguishable from how users naturally ask generic questions. Train on the contrast between specific ("Aave V3 health factor") and generic ("lending protocol health factor") phrasings.

C. **Red-team benchmark** — Fine-tune a BERT-large model on a dataset of (sanitized, original) query pairs, then measure detection rate. If detection is high, iterate on the sanitizer/genericizer. Publish the red-team model as a benchmark for future work.

**Recommended**: C first (quantifies the threat), then A/B (builds the defense).

**Effort**: C = 1-2 weeks. A = 2-3 months. B = 1-2 months.

---

## 8. Cross-Domain Generalization

**Problem**: The current architecture is specialized for DeFi. Can the same "sanitize + decompose + cover" pattern work for other high-value query domains?

**Why it matters**: If the technique generalizes, the contribution becomes a reusable privacy primitive for all LLM-backed services, not just DeFi.

**Candidate domains**:

| Domain | Private data at risk | Cover-generation challenge |
|---|---|---|
| **Medical** | Symptoms, diagnoses, medications, test results | Medical ontology is much larger; domain priors are harder to balance |
| **Legal** | Case details, contract terms, liability exposure | Legal queries are longer and more context-dependent |
| **Corporate finance** | M&A targets, revenue figures, strategic plans | Fewer public "cover" topics; insider information is harder to genericize |
| **Military/intelligence** | Operational details, targets, capabilities | Extreme sensitivity; local-only is the only viable tier |
| **Personal finance** | Income, debts, investment portfolio | Similar to DeFi but with traditional finance vocabulary |

**Approach**: Port the v5 algorithm to one other domain (e.g., medical), build a domain-specific ontology, run Benchmark C equivalent, compare indistinguishability.

**Effort**: 2-4 weeks per domain.

---

## 9. Optimal k Selection

**Problem**: The current system uses a fixed k=4 (1 real + 3 covers). Larger k reduces detection probability but increases cost and latency linearly.

**Why it matters**: Different users have different privacy/cost preferences. A whale with $10M in positions has a very different risk profile from a retail user with $1K.

**Approach**: Formulate as an optimization problem:

```
minimize: E[adversary_profit(k, detection_rate(k))] + cost(k) + latency_penalty(k)
subject to: detection_rate(k) ≤ threshold
            cost(k) ≤ budget
            latency(k) ≤ max_latency
```

Solve analytically for the template-filled case (detection = 1/k), and empirically for the genericized case (detection > 1/k). Publish lookup tables: given (position_size, budget, latency_tolerance), recommended k.

**Effort**: 1-2 weeks (analytical + simulation).

---

## 10. Shannon Capacity of the Paraphrase Channel

**Problem**: When a user paraphrases a numeric quantity in natural language ("about half a million"), how much information does the adversary recover? Can we bound this formally?

**Why it matters**: The regex sanitizer catches numeric formats but not semantic paraphrases. A formal bound on the information content of paraphrased quantities would quantify the residual privacy loss.

**Approach**: Model the user's paraphrasing as a noisy channel: input = exact amount, output = paraphrased text. Compute the channel capacity C using Shannon's theorem on a corpus of (amount, paraphrase) pairs. If C is low (e.g., <3 bits), the adversary can only distinguish ~8 magnitude buckets, not exact amounts — which may be acceptable for most attack scenarios.

**Effort**: 2-4 weeks (corpus construction + information-theoretic analysis).

---

## Priority Ranking

| Direction | Impact | Effort | Priority |
|---|---|---|---|
| 1. NER quantity filter | High (closes biggest sanitizer gap) | Low-Medium | **P0** |
| 3. Real user query corpus | High (external validity) | Low (bounty) to High (partnership) | **P0** |
| 7. Adversarial fine-tuning resistance (red-team) | High (quantifies long-term threat) | Low | **P1** |
| 2. Formal ε-d-privacy proof | High (academic credibility) | Medium | **P1** |
| 9. Optimal k selection | Medium (practical deployment) | Low | **P1** |
| 4. Cross-provider collusion simulation | Medium (quantifies threat) | Medium | **P2** |
| 10. Shannon capacity of paraphrase channel | Medium (theoretical interest) | Medium | **P2** |
| 5. Cover-traffic pool | Medium (cost reduction) | High | **P2** |
| 8. Cross-domain generalization | Medium (broadens impact) | Medium per domain | **P3** |
| 6. ZK proofs of sanitization | High (non-repudiability) | High | **P3** |
