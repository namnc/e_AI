"""
Three approaches to rewriting sub-queries for privacy while preserving utility.

The problem: template-filled queries are indistinguishable (27% detection) but
produce useless answers (2.3/5). Actual sub-queries produce useful answers (3.8/5)
but are distinguishable (~67% detection).

This module implements three middle-ground approaches and a benchmark to compare.

Usage:
  python rewrite_strategies.py --backend ollama --model qwen2.5:7b
"""

import argparse
import json
import random
import re

from cover_generator import (
    DOMAIN_ONTOLOGY, TOP_DOMAINS, TEMPLATES,
    sanitize_query, classify_domain, extract_template,
    generate_cover_set, _generate,
)
from llm_backend import init_backend, call_llm, is_local
from dataset import COMPLEX_QUERIES


# ─────────────────────────────────────────────
# Approach A: Regex-based genericization
# ─────────────────────────────────────────────

# Protocol names to strip (case-insensitive)
_PROTOCOL_NAMES = [
    "Aave V3", "Aave V2", "Aave", "Compound V3", "Compound V2", "Compound",
    "Uniswap V3", "Uniswap V2", "Uniswap", "Curve", "Balancer", "SushiSwap",
    "MakerDAO", "Maker", "dYdX", "GMX", "Synthetix", "Lyra", "Opyn",
    "Lido", "Rocket Pool", "Eigenlayer", "Pendle", "Yearn", "Convex",
    "Morpho", "Radiant", "Spark", "Frax", "Swell",
]

def approach_a_regex(sub_query: str) -> str:
    """Strip protocol names, replace with generic domain reference."""
    result = sub_query
    domain = classify_domain(sub_query)
    onto = DOMAIN_ONTOLOGY.get(domain, {})
    generic_ref = onto.get("generic_refs", ["DeFi protocols"])[0]

    # Sort by length (longest first) to avoid partial matches
    for proto in sorted(_PROTOCOL_NAMES, key=len, reverse=True):
        result = re.sub(rf'\b{re.escape(proto)}\b', generic_ref, result, flags=re.IGNORECASE)

    # Clean up "on lending protocols protocols" etc.
    result = re.sub(rf'({re.escape(generic_ref)})\s+\1', generic_ref, result)
    result = re.sub(r'\s+', ' ', result).strip()
    return result


# ─────────────────────────────────────────────
# Approach B: LLM-based rewriting
# ─────────────────────────────────────────────

REWRITE_SYSTEM = """Rewrite this DeFi query to remove all protocol-specific references
while preserving the mechanism question. Replace protocol names (Aave, Uniswap, Compound, etc.)
with generic terms like "lending protocol" or "decentralized exchange."
Keep the specific mechanism (health factor, slippage, funding rate, etc.) intact.

Output ONLY the rewritten query, nothing else."""

def approach_b_llm(sub_query: str) -> str:
    """Use the local LLM to genericize the sub-query."""
    return call_llm(sub_query, system=REWRITE_SYSTEM, max_tokens=100).strip()


# ─────────────────────────────────────────────
# Approach C: Template with real mechanism
# ─────────────────────────────────────────────

def _extract_mechanism_keywords(query: str, domain: str) -> dict:
    """Extract which ontology terms the query mentions."""
    onto = DOMAIN_ONTOLOGY.get(domain, {})
    q_lower = query.lower()
    found = {}
    for slot_key in ["mechanisms", "operations", "triggers", "metrics", "actors", "generic_refs"]:
        for term in onto.get(slot_key, []):
            if term.lower() in q_lower:
                slot_name = {
                    "mechanisms": "{MECHANISM}",
                    "operations": "{OPERATION}",
                    "triggers": "{TRIGGER}",
                    "metrics": "{METRIC}",
                    "actors": "{ACTOR}",
                    "generic_refs": "{GENERIC_REF}",
                }.get(slot_key)
                if slot_name and slot_name not in found:
                    found[slot_name] = term
    return found


def approach_c_template(sub_query: str, seed: int = 42) -> str:
    """Fill template with the sub-query's ACTUAL mechanism, not random."""
    rng = random.Random(seed)
    domain = classify_domain(sub_query)
    template = extract_template(sub_query, rng=rng)
    onto = DOMAIN_ONTOLOGY[domain]

    # Extract what the query is actually about
    real_slots = _extract_mechanism_keywords(sub_query, domain)

    # Fill template: use real mechanism where found, random for the rest
    def pick(slot_name, category):
        if slot_name in real_slots:
            return real_slots[slot_name]
        return rng.choice(onto[category])

    result = template
    replacements = {
        "{MECHANISM}": pick("{MECHANISM}", "mechanisms"),
        "{OPERATION}": pick("{OPERATION}", "operations"),
        "{TRIGGER}": pick("{TRIGGER}", "triggers"),
        "{METRIC}": pick("{METRIC}", "metrics"),
        "{ACTOR}": pick("{ACTOR}", "actors"),
        "{GENERIC_REF}": pick("{GENERIC_REF}", "generic_refs"),
        "{RISK_CONCEPT}": rng.choice(onto.get("risk_concepts", ["risk"])),
    }
    if "{OPERATION_A}" in result and "{OPERATION_B}" in result:
        ops = rng.sample(onto["operations"], min(2, len(onto["operations"])))
        replacements["{OPERATION_A}"] = ops[0]
        replacements["{OPERATION_B}"] = ops[1] if len(ops) > 1 else ops[0]

    for slot, value in replacements.items():
        result = result.replace(slot, value, 1)
    return result


# ─────────────────────────────────────────────
# Benchmark: compare all three
# ─────────────────────────────────────────────

JUDGE_SYSTEM = """Rate this answer's usefulness for the original question on a 1-5 scale:
5 = Directly answers the original question
4 = Mostly relevant
3 = Partially relevant
2 = Tangentially related
1 = Irrelevant
Respond with ONLY a JSON object: {"score": 1-5}"""

DETECT_SYSTEM = """You see 4 DeFi queries. One is a real user question, the other 3 are covers.
Which is most likely real? Consider: specificity, protocol references, actionability.
Respond with ONLY: {"guess": 0-3}"""


def benchmark_approaches(n_queries: int = 5):
    """Compare approaches A, B, C on privacy (detection rate) and utility (answer quality)."""

    # Use sanitized versions of complex queries as sub-queries
    sub_queries = [
        "How does Aave V3 health factor change when additional collateral is supplied?",
        "What are the gas costs for adding collateral vs full position closure on Aave V3?",
        "How does Uniswap V3 route large swaps across multiple fee tiers?",
        "How does the Aave safety module unstaking cooldown work?",
        "What are the mechanics of perpetual futures liquidation on dYdX?",
        "How does Eigenlayer slashing risk compare to native ETH staking risk?",
        "What is the relationship between ETH implied volatility and options premium on Lyra?",
        "How does Curve 3pool rebalancing work when the pool is imbalanced?",
        "What are the tradeoffs between different DEX aggregator routing algorithms?",
        "How does reward distribution work across different staking tiers?",
    ][:n_queries]

    approaches = {
        "original": lambda q, s: q,  # no rewriting (D2 baseline)
        "A_regex": lambda q, s: approach_a_regex(q),
        "B_llm": lambda q, s: approach_b_llm(q),
        "C_template": lambda q, s: approach_c_template(q, seed=s),
        "template_random": lambda q, s: _generate(q, k=4, seed=s, domain_strategy="top4", presanitized=True)[0][
            _generate(q, k=4, seed=s, domain_strategy="top4", presanitized=True)[1]
        ],  # pure template fill (C baseline)
    }

    results = {name: {"detection": 0, "detected": 0, "total": 0, "scores": []} for name in approaches}

    for i, sq in enumerate(sub_queries):
        print(f"\n--- Sub-query {i+1}/{len(sub_queries)} ---")
        print(f"  Original: {sq[:80]}")

        for name, rewriter in approaches.items():
            rewritten = rewriter(sq, 42 + i)
            print(f"  {name:>16}: {rewritten[:80]}")

            # --- Utility: get answer and judge ---
            answer = call_llm(rewritten, max_tokens=200)
            judge_resp = call_llm(
                f"ORIGINAL QUESTION: {sq}\n\nANSWER: {answer[:400]}\n\nRate usefulness.",
                system=JUDGE_SYSTEM, max_tokens=50
            )
            try:
                score = json.loads(judge_resp).get("score", 0)
            except (json.JSONDecodeError, ValueError):
                score = 0
            results[name]["scores"].append(score)

            # --- Privacy: mix with covers, try detection ---
            cover_set, _ = generate_cover_set(sq, k=4, seed=42 + i, presanitized=True)
            # Replace template-filled real with our rewritten version
            covers_only = [q for idx, q in enumerate(cover_set) if idx != _][:3]
            mixed = covers_only + [rewritten]
            rng = random.Random(42 + i)
            rng.shuffle(mixed)
            real_pos = mixed.index(rewritten)

            query_list = "\n".join(f"Query {j}: {mixed[j]}" for j in range(4))
            detect_resp = call_llm(
                f"Which is the real query?\n\n{query_list}",
                system=DETECT_SYSTEM, max_tokens=50
            )
            try:
                guess = json.loads(detect_resp).get("guess", -1)
            except (json.JSONDecodeError, ValueError):
                guess = -1

            results[name]["total"] += 1
            if guess == real_pos:
                results[name]["detected"] += 1

        print()

    # Summary
    print("\n" + "=" * 70)
    print(f"{'Approach':>16} | {'Avg Utility':>11} | {'Detection':>10} | {'Privacy-Utility Score':>20}")
    print("-" * 70)
    for name, r in results.items():
        avg_score = sum(r["scores"]) / len(r["scores"]) if r["scores"] else 0
        det_rate = r["detected"] / r["total"] if r["total"] > 0 else 0
        # Combined score: higher is better (utility/5 * (1 - detection))
        combined = (avg_score / 5) * (1 - det_rate)
        print(f"{name:>16} | {avg_score:>8.1f}/5  | {det_rate:>8.0%}   | {combined:>18.2f}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", default="ollama")
    parser.add_argument("--model", default="qwen2.5:7b")
    parser.add_argument("--n", type=int, default=5)
    args = parser.parse_args()

    init_backend(args.backend, args.model)
    benchmark_approaches(args.n)
