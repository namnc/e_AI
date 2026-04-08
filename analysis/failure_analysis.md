# Why Cover Queries Fail: A Systematic Analysis

## The Central Question

Is cover query indistinguishability **fundamentally hard** (information-theoretically impossible) or **an engineering problem** (solvable with better algorithms)?

Our answer: **it is an engineering problem, not a fundamental impossibility** — but it requires careful attention to multiple dimensions of query similarity that naive approaches miss.

## The Signal Hierarchy

We identified four independent signals that an adversary can use to distinguish real queries from covers, ordered by how hard they are to eliminate:

### Signal 1: Actionability Tone (easiest to exploit, easiest to fix)

**What it is**: Real queries sound like "I'm about to do something." Covers sound like "teach me about this concept."

**Example**:
- Real: "What are the gas costs for adding collateral vs closing a position on Aave V3?"
- Naive cover: "What is the difference between optimistic and zk rollups?"

The real query implies an imminent decision. The cover is purely educational. Any classifier — even keyword matching on words like "adding," "closing," "vs" (implying comparison for a decision) — would detect this.

**Fix**: Generate covers with the same actionability level. Both real and cover should be phrased as operational comparisons or both as educational explanations.

**Result**: Fixing this dropped detection from 95% → 60%.

**Is this fundamental?** No. It's a prompt engineering problem. The cover generation prompt simply needs to specify "generate queries that sound like someone about to take action, not someone studying."

### Signal 2: Specificity Level (medium difficulty)

**What it is**: Real queries tend to be more specific to a single protocol operation. Covers tend to be broader or about different categories of DeFi.

**Example**:
- Real: "How does Aave V3 health factor change when collateral is added?"
- Cover: "How do decentralized exchanges handle order matching?"

The real query is about a specific operation on a specific protocol type. The cover is about a general concept. Even with matched actionability, the specificity gradient is detectable.

**Fix**: Match specificity levels. Both real and cover should name specific protocol types and specific operations.

**Result**: Fixing this (combined with Signal 1 fix) dropped detection from 60% → ~40%.

**Is this fundamental?** No, but it's harder than Signal 1. The cover generator needs to understand what "equally specific" means in the DeFi domain — it needs enough domain knowledge to generate covers that are at the same abstraction level.

### Signal 3: Structural Template (the key insight)

**What it is**: Real queries have a particular sentence structure determined by the user's actual question. Covers generated freely may have different structures (different sentence patterns, different question types).

**Example**:
- Real: "How does [X mechanism] respond to [Y change] in [Z protocol type]?"
- Cover (freely generated): "What are the risks of [A] compared to [B]?"

Even if actionability and specificity match, the sentence template is different. The "How does X respond to Y" pattern vs. "What are the risks" pattern is a classifiable signal.

**Fix**: Template-matched generation. Extract the structural template from the real query, then fill it with different domain nouns.

**Result**: Fixing this dropped detection from ~40% → 10% (below random).

**Is this fundamental?** No, but it reveals an important insight: **the cover generation must be aware of the query's syntactic structure, not just its semantic content.** A template-based approach achieves this mechanically. A well-prompted LLM could also achieve it with instructions like "generate a query with the EXACT same sentence structure but about a different DeFi domain."

### Signal 4: Domain Prior (hardest — partially fundamental)

**What it is**: Some DeFi topics are more commonly asked about than others. If the adversary knows the base rate distribution of real queries, a cover topic that is rarely asked about (e.g., "How does Frax's algorithmic stability mechanism work?") is less likely to be real than a commonly asked topic (e.g., "How does Uniswap routing work?").

**Example**: If 30% of real DeFi queries are about lending, 25% about DEXes, 10% about bridges, 5% about governance, and 2% about insurance — then a query about insurance is less likely to be real than one about lending, regardless of tone/specificity/template.

**Fix**: Sample cover topics from the same distribution as real queries. If 30% of real queries are about lending, 30% of covers should be too.

**Is this fundamental?** Partially. Even with perfect distribution matching, the adversary can still use Bayesian reasoning:
- Prior: P(topic = lending) = 0.30 for real queries
- If covers are drawn from the same distribution: P(topic = lending) = 0.30 for covers too
- No distinguishing signal → adversary is at random baseline

But if the adversary has **per-user** priors (e.g., "this user has used lending protocols before, so lending queries are more likely real for THIS user"), distribution matching at the population level is insufficient. This is the **metadata correlation** problem and is partially fundamental — it requires not just good covers but also metadata protections (Tor, session unlinkability) to prevent per-user profiling.

## The Indistinguishability Ladder

| Level | Signals Eliminated | Detection Rate | Approach |
|-------|-------------------|---------------|----------|
| 0 | None (naive covers) | ~95% | Random topic, different tone |
| 1 | Actionability | ~60% | Matched operational framing |
| 2 | + Specificity | ~40% | Matched protocol-level detail |
| 3 | + Template | ~10% | Same sentence structure, different domain |
| 4 | + Domain prior | ~25% (random) | Cover topics drawn from real query distribution |

**Level 3 already achieves our target** (<40%). Level 4 would be ideal but requires knowledge of the real query distribution, which could be approximated from public datasets (LMSYS-Chat-1M filtered for DeFi, Reddit r/defi post categories).

## Is This Analogous to TrackMeNot's Failure?

TrackMeNot failed because:
1. Fake queries were drawn from a static word list — easily distinguishable from real search behavior
2. Real vs. fake queries had completely different statistical properties (length, word frequency, temporal patterns)
3. A simple ML classifier achieved 99.98% detection

Our v1 failure (95%) has the same root cause — different statistical properties (actionability). But our v3 success (10%) demonstrates that when statistical properties are matched, the approach works.

**Key difference from TrackMeNot**: We use an LLM to generate covers, not a word list. LLMs produce text with the same statistical properties as human text — this is the same reason AI-text detection is so hard. We exploit this property: if you can't tell AI-generated text from human text in general, you can't tell AI-generated DeFi queries from human DeFi queries when the template is matched.

## Is Indistinguishability Fundamentally Impossible?

**No, for the following reason:**

The information-theoretic argument for indistinguishability is:
1. The cloud sees a query q from the set {q_real, q_cover1, q_cover2, q_cover3}
2. If all four queries are drawn from the same distribution D (same template, same specificity, same domain distribution), then observing any single query gives the adversary zero bits of information about which is real
3. The mutual information I(real_index; observed_query) = 0 when the distributions are identical

The practical challenge is making the distributions identical across all dimensions simultaneously. Our v3 results suggest template matching gets close. A trained classifier on a larger dataset might find residual patterns (e.g., subtle word choice preferences), but these can be addressed with:
- Random synonym substitution
- Temperature variation in generation
- Fine-tuning the cover generator on real DeFi query distributions

**The fundamental limit** is not indistinguishability per se, but:
1. **Session composition** — multiple queries from one session can correlate
2. **Metadata correlation** — timing/IP linkage breaks content-level privacy
3. **Unique positions** — if only one user has a particular DeFi situation, the topic alone identifies them

These are acknowledged limitations of the architecture, not of the cover generation algorithm.

## Recommendations for Production Cover Generation

1. **Template extraction**: Parse the real query into a syntactic template. Use dependency parsing or a simpler regex-based approach.
2. **Domain swapping**: Replace the domain-specific nouns (protocol type, mechanism type) with alternatives from a curated ontology of DeFi domains.
3. **Distribution matching**: Sample replacement domains from the observed frequency distribution of real DeFi queries.
4. **Quality check**: Before sending, verify that each cover is a valid, answerable DeFi question (not gibberish from template filling).
5. **Diversity across sessions**: Don't use the same cover domains repeatedly — vary them across sessions.
6. **Fine-tuning**: Consider fine-tuning the local model on real DeFi conversations (LMSYS-Chat-1M, Reddit, Discord) to match the natural distribution of user queries.
