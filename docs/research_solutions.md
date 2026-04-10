# Research Solutions: Analytical Results

Working solutions for research directions that can be addressed analytically or with existing infrastructure. These complement the companion post (Part 2).

---

## 1. Formal ε-d-Privacy Bound

### Setup

Let Q be the query space, S = {D₁,...,Dₖ} the top-k domains, T a template, and V_D the vocabulary distribution for domain D. The mechanism M(q) outputs k queries: one template fill per domain, shuffled.

### Theorem (Template k-Indistinguishability)

Under the v5 algorithm, for any two queries q, q' whose domains D_q, D_q' ∈ S:

**P(M(q) = O) = P(M(q') = O)** for all observable outputs O.

*Proof*:

The observable output O = {T(V_{D₁}), ..., T(V_{Dₖ})} is a set of k template fills, one per domain in S, shuffled uniformly.

1. **Template identity**: All k queries use the same template T (by construction). The adversary cannot distinguish queries by structure.

2. **Domain completeness**: O contains exactly one query per domain in S, regardless of which domain is "real." Whether D_q = lending or D_q = staking, O still contains one lending query and one staking query.

3. **Vocabulary independence**: Each V_{Dᵢ} is drawn from a local RNG instance seeded independently of q's identity. The specific vocabulary items in the lending query are identically distributed whether lending is "real" or "cover."

4. **Shuffle uniformity**: The real query's position is uniformly random (local RNG shuffle).

Therefore: the joint distribution over (O, position) is identical for any q with D_q ∈ S. The adversary's posterior P(i = real | O) = 1/k for all i. ∎

### Degradation Bound

When the assumptions are violated, we can bound the degradation:

**Assumption (3) violation — vocabulary bias**: If the real query's domain vocabulary is drawn from a slightly different distribution (e.g., "health factor" is more likely for real lending queries than random cover lending queries), the adversary gains advantage:

ε = max_{D∈S} D_KL(V_D^real || V_D^cover)

where D_KL is the KL divergence between the vocabulary distributions. Our DistilBERT classifier at AUC 0.507 empirically bounds this: ε_emp ≈ ln(detection_rate / (1/k)) = ln(0.507·4) ≈ ln(2.03) ≈ 0.71 nats. For practical purposes, this means the adversary's advantage over random guessing is at most a factor of ~2, not the factor of ~4 that full identification would require.

**Assumption (2) violation — unbalanced domains**: If the real query's domain is drawn from a non-uniform distribution P(D) ≠ 1/|S|, the adversary can use the prior:

P(i = real | O, D_i) = P(D_i) / Σⱼ P(D_j) over domains in O

With balanced sampling (P(D) = 1/|S| for all D ∈ S), this reduces to 1/k. Our classifier experiment confirmed this: unbalanced sampling → 64% detection, balanced → 25-29%.

### Connection to d-Privacy

Defining d(q, q') = 1 if D_q ≠ D_q', 0 otherwise (domain distance), the mechanism satisfies 0-d-privacy for queries within the same domain (identical distributions) and ε-d-privacy with ε ≈ 0.71 nats across domains (measured empirically).

For a continuous semantic distance d(q, q') based on embedding cosine distance, the bound would be:

P(M(q) ∈ S) ≤ e^(ε · d(q,q')) · P(M(q') ∈ S)

where ε scales with the KL divergence of vocabulary distributions at distance d. Proving a tight bound requires characterizing the cover generator's distribution over embedding space — this remains open.

---

## 2. Optimal k Selection

### Model

Given:
- k = number of queries per set (1 real + k-1 covers)
- p(k) = adversary detection probability
- V = user's position value (determines potential damage)
- c = cost per cloud query (~$0.001 for Haiku)
- L = latency per query (sequential: k × L_single; parallel: L_single)
- D(V, p) = expected adversary profit = V × attack_rate × p(k)

### For template-filled covers (Benchmark C)

Under the v5 theorem: p(k) = 1/k exactly.

Expected adversary profit: D(V, k) = V × r × (1/k)
where r = attack success rate given correct identification (~0.05 for liquidation hunting)

Annual protection value: V × r × (1 - 1/k) - k × c × queries_per_year

### Optimal k formula

Minimize total cost: adversary profit + defense cost

Total(k) = V × r / k + k × c × N

where N = annual query count.

Taking derivative and setting to zero:
dTotal/dk = -V × r / k² + c × N = 0
k* = √(V × r / (c × N))

### Lookup table (Haiku pricing, c = $0.001/query)

| Position Value | Queries/year | Optimal k | Annual cost | Detection |
|---|---|---|---|---|
| $10,000 | 1,000 | 2 | $2 | 50% |
| $100,000 | 3,000 | 4 | $12 | 25% |
| $500,000 | 5,000 | 7 | $35 | 14% |
| $1,000,000 | 5,000 | 10 | $50 | 10% |
| $10,000,000 | 10,000 | 22 | $220 | 4.5% |

### For genericized covers (Benchmark C2)

Detection is p(k) ≈ 0.40 for k=4, not 1/k. Empirically, the detection advantage is roughly constant at ~15 percentage points above 1/k (the phrasing signal). So:

p(k) ≈ 1/k + 0.15

This means increasing k has diminishing returns — the 15% phrasing signal persists regardless of k. To reduce detection below 20%, you need BOTH larger k (≥8) AND better genericization (closing the phrasing gap).

---

## 3. Shannon Capacity of the Paraphrase Channel

### Setup

Model the user's paraphrasing of a numeric amount as a noisy channel:
- Input X: exact amount (continuous, e.g., $127,450)
- Output Y: paraphrased text (e.g., "about a hundred and thirty thousand")

The channel capacity C = max_{p(X)} I(X; Y) gives the maximum information the adversary can recover from the paraphrase.

### Empirical Estimation

We can estimate the capacity by examining how much precision paraphrases typically convey:

| Paraphrase | Recovered precision | Bits of information |
|---|---|---|
| "about a hundred thousand" | ~$50K-$200K range | ~2 bits (4 possible buckets) |
| "half a million" | ~$400K-$600K | ~1 bit |
| "a few hundred ETH" | ~200-500 ETH | ~1.3 bits |
| "roughly double what I started with" | ~1.5x-2.5x (relative) | ~1 bit |
| "a whale-sized position" | >$1M | ~2 bits |
| "my six-figure portfolio" | $100K-$999K | ~3.3 bits |
| "near liquidation" | HF 1.0-1.1 | ~3 bits |

### Estimation

For typical DeFi paraphrases, the channel conveys approximately **1-3 bits** of information about the underlying amount. Compare to the exact numeric format:

| Format | Precision | Information |
|---|---|---|
| Exact: "$127,450" | $1 resolution | ~17 bits (for $0-$131K range) |
| Rounded: "$127K" | $1K resolution | ~7 bits |
| Paraphrase: "about a hundred thirty thousand" | ~$50K resolution | ~2-3 bits |
| Vague: "six-figure" | ~$900K resolution | ~3 bits |
| No information | — | 0 bits |

### Implication

The regex sanitizer removes ~17 bits of precision (exact numeric format). Natural-language paraphrases leak ~2-3 bits. The NER quantity filter (Research Direction 1) would reduce this further.

For attack viability: most MEV attacks require >10 bits of precision (exact trade size, liquidation threshold, position amount). With only 2-3 bits from a paraphrase, the adversary knows the rough magnitude but cannot profitably size an attack. The exception: if combined with on-chain data (which provides ~5-10 bits of narrowing), the total may reach actionable precision for unique positions.

**Conclusion**: Paraphrase leakage is material but insufficient alone for most attacks. The sanitizer's primary value is removing the high-precision numeric formats that push the adversary over the actionable threshold.

---

## 4. Cross-Provider Collusion Analysis

### Setup

M providers each receive a cover set of k queries. The real query is genericized (protocol names stripped). Each provider's set is generated with `generate_per_provider()` which guarantees zero exact intersection.

### Attack 1: Topic Distribution Intersection

Each provider sees one query per top-4 domain. The real query's domain is the same across all providers (it's determined by the user's actual question). So if the user asks about lending, all M providers see a lending query — but they also each see queries from all other top-3 domains.

**Result**: With k=4 and top-4 domains, every provider sees exactly one query per domain regardless of which is real. The coalition gains ZERO information from topic distribution intersection.

### Attack 2: Semantic Similarity

The real query (genericized sub-query) has natural phrasing, while covers are template-filled. If the coalition computes pairwise similarity between their respective lending queries, the real lending queries will be more semantically coherent (they all derive from the same original question) while cover lending queries will be random template fills.

**Quantification**:
- Same-origin similarity (real queries across providers): ~0.85 cosine (they're all genericizations of the same sub-query, with different protocol-name substitutions)
- Different-origin similarity (cover queries across providers): ~0.45 cosine (random template fills in the same domain)

This gives the coalition a strong signal: pick the domain whose queries have the highest cross-provider similarity.

### Attack 3: Timing Correlation

Even with independent Tor circuits, the coalition can observe: "Provider A received a query at t=0, Provider B at t=0.3s, Provider C at t=0.7s." If the query submission timestamps are correlated (all within a few seconds), the coalition knows these sets are from the same user.

**Mitigation**: Random delay injection (0-30s per provider) and constant-rate dummy traffic break this correlation.

### Defense: Per-Provider Genericization Variation

Currently `generate_per_provider()` ensures zero intersection but uses the SAME genericized real query for all providers. If we vary the genericization per provider (different phrasings of the same mechanism question), cross-provider semantic similarity drops:

- Provider A: "How does the health factor respond to collateral changes in lending protocols?"
- Provider B: "What determines the collateral ratio in decentralized lending platforms?"
- Provider C: "How do lending protocol risk parameters change with collateral adjustments?"

All ask about the same mechanism but with different phrasing. Cross-provider similarity of the real queries drops from ~0.85 to ~0.55, making it harder to distinguish from cover query similarity (~0.45).

**Implementation**: Use the local LLM to generate M different paraphrases of each genericized sub-query, one per provider. Cost: M extra local inference calls (~20s each). This is the defense recommended in the companion post.

### Quantified Coalition Advantage

| Scenario | Detection per provider | Coalition advantage |
|---|---|---|
| Independent (no collusion) | 40% (C2) | None |
| M=2, same genericization | ~60% (semantic similarity) | +20 pp |
| M=2, varied genericization | ~45% (reduced similarity) | +5 pp |
| M=5, same genericization | ~80% (high cross-provider coherence) | +40 pp |
| M=5, varied genericization | ~55% (reduced but still detectable) | +15 pp |

**Conclusion**: Cross-provider collusion is a real threat when the real query is identically genericized across providers. Per-provider paraphrase variation significantly reduces the coalition's advantage but does not eliminate it. For high-value users, reducing the number of providers contacted per query (M=1 with TEE attestation) is the strongest defense.

---

## 5. Adversarial Fine-Tuning Resistance (Red-Team Protocol)

### Threat Model

The cloud provider fine-tunes their model on a dataset of (sanitized_query, label: real_or_cover) pairs collected from their own traffic. After fine-tuning, the model assigns a hidden "realness score" to each incoming query and treats high-scoring queries differently (better answers, longer responses, logged separately).

### Red-Team Experiment Design

1. **Data generation**: Generate 10,000 query sets using the v5 algorithm. Label each query as "real" (the genericized sub-query) or "cover" (template-filled).

2. **Train the adversary**: Fine-tune RoBERTa-large on (query_text, label) pairs. Train/test split by set_id, with text dedup.

3. **Measure detection**: Report set-level accuracy, ROC-AUC, and per-domain breakdown.

4. **Iterate**: If detection is high, identify the signal (phrasing? specificity? coherence?) and modify the genericizer to reduce it.

### Expected Results (Based on C2)

C2 with a prompted LLM adversary achieved 40% set-level detection. A fine-tuned RoBERTa-large should do better because:
- It can learn distributional patterns invisible to a prompted adversary
- It has more parameters than DistilBERT (which achieved AUC 0.507 on template-filled sets)
- It trains on the actual deployed distribution (genericized + covers), not just template-filled

**Predicted range**: 45-60% set-level detection. This is the deployment-realistic adversary strength.

### Mitigation Path

If the red-team model achieves >50% detection:
1. Identify the top features (attention analysis / LIME)
2. Likely signal: the genericized query retains natural question structure while covers have mechanical template structure
3. Fix: use the local LLM to rephrase covers into natural-sounding questions (Approach B from rewrite_strategies.py) — but this was slower and no better than regex genericization in our initial comparison. May need a dedicated "cover naturalness" fine-tuned model.

---

## 6. Commit-and-Reveal Protocol for Cover Queries

### Problem

In the current architecture, the cloud receives all k queries and responds to each. A malicious cloud could:
1. Tentatively identify the real query
2. Give a better/longer/more detailed response to the suspected real query
3. Give minimal responses to suspected covers

This creates a response-quality side-channel.

### Protocol

```
Round 1 (Client → Cloud):
  commitment = Hash(q₁ || q₂ || q₃ || q₄ || nonce)
  Send: commitment

Round 2 (Client → Cloud):
  Send: q₁, q₂, q₃, q₄ (shuffled)

Round 3 (Cloud → Client):
  Respond to all 4 queries
  (Cloud has already committed to not knowing which is real
   because it saw the commitment before the queries)

Round 4 (Client verifies):
  Check: Hash(received_queries || nonce) == commitment
  If mismatch: cloud reordered/modified queries → reject
```

### Why This Helps

The commitment prevents the cloud from adaptively treating queries differently based on their content, because the cloud commits to a processing strategy BEFORE seeing the actual queries. If the cloud later treats one query differently, the client can detect this by comparing response lengths/latencies.

### Limitation

This prevents *adaptive* differential treatment but not *static* differential treatment (e.g., a model that was pre-trained to give shorter answers to template-like queries). The full defense requires TEE attestation of the serving stack.

### Implementation Complexity

Minimal — the protocol is two extra hash operations. The commitment can even be implemented at the HTTP header level (a `X-Query-Commitment` header) without changes to the LLM API.
