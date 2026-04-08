"""
Privacy Orchestration Benchmarks for "The Private Query Problem"

Usage:
  export ANTHROPIC_API_KEY=sk-ant-...
  python run_benchmarks.py --benchmark all
  python run_benchmarks.py --benchmark C --cover-version v5 --samples 50
  python run_benchmarks.py --benchmark E --backend ollama --model qwen2.5:32b

Benchmarks:
  A: Sensitivity Classification
  B: Decomposition Quality
  C: Cover Query Indistinguishability (v1 naive or v5 template+distribution)
  E: Session Composition Attack
  F: Damage Reduction (pure math, no LLM)
"""

import argparse
import json
import random
import re
import time
from pathlib import Path

from llm_backend import init_backend, call_llm
from cover_generator import generate_cover_set, generate_cover_set_raw, sanitize_query
from dataset import (
    SENSITIVE_QUERIES, NON_SENSITIVE_QUERIES, COMPLEX_QUERIES,
    MEV_SCENARIOS, SANITIZED_QUERIES, SESSION_SCENARIOS,
)


RESULTS_DIR = Path(__file__).parent / "results"


def extract_json(text: str) -> dict | list:
    """Extract JSON from LLM response that may contain surrounding text or markdown."""
    # Try direct parse first
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code block
    m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try finding first { or [ and matching
    for start_char, end_char in [('{', '}'), ('[', ']')]:
        start = text.find(start_char)
        if start == -1:
            continue
        # Find matching closing bracket
        depth = 0
        for i in range(start, len(text)):
            if text[i] == start_char:
                depth += 1
            elif text[i] == end_char:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i+1])
                    except json.JSONDecodeError:
                        break

    raise ValueError(f"No valid JSON found in response: {text[:200]}")


# ─────────────────────────────────────────────
# Benchmark A: Sensitivity Classification
# ─────────────────────────────────────────────

CLASSIFY_SYSTEM = """You are a DeFi privacy sensitivity classifier. Given a user query about DeFi/crypto,
classify whether it contains EXPLOITABLE PRIVATE INFORMATION that could be used for MEV extraction,
front-running, liquidation hunting, or deanonymization.

SENSITIVE means the query contains ANY of:
- Specific token amounts or portfolio values
- Wallet addresses
- Trading intent with parameters (buy/sell X amount of Y)
- Position details (health factor, collateral ratio, leverage)
- Time-sensitive trading plans
- Strategy details that could be front-run

NON-SENSITIVE means the query is generic DeFi knowledge that reveals nothing exploitable about the user's positions or intent.

Respond with ONLY a JSON object: {"classification": "SENSITIVE" or "NON_SENSITIVE", "reason": "brief explanation"}"""


def benchmark_a(n_samples: int = 20):
    """Test if the model can classify DeFi queries as sensitive vs non-sensitive."""
    print("\n" + "=" * 60)
    print("BENCHMARK A: Sensitivity Classification")
    print("=" * 60)

    sens_sample = random.sample(SENSITIVE_QUERIES, min(n_samples, len(SENSITIVE_QUERIES)))
    safe_sample = random.sample(NON_SENSITIVE_QUERIES, min(n_samples, len(NON_SENSITIVE_QUERIES)))

    results = {"tp": 0, "fp": 0, "tn": 0, "fn": 0, "errors": 0}

    print(f"\nTesting {len(sens_sample)} sensitive + {len(safe_sample)} non-sensitive queries...")

    for i, q in enumerate(sens_sample):
        try:
            resp = call_llm(f"Classify this query:\n\n{q}", system=CLASSIFY_SYSTEM, max_tokens=200)
            parsed = extract_json(resp)
            if parsed["classification"] == "SENSITIVE":
                results["tp"] += 1
            else:
                results["fn"] += 1
                print(f"  FALSE NEGATIVE [{i}]: {q[:80]}...")
                print(f"    Reason: {parsed.get('reason', 'N/A')}")
        except Exception as e:
            results["errors"] += 1
            print(f"  ERROR [{i}]: {e}")

    for i, q in enumerate(safe_sample):
        try:
            resp = call_llm(f"Classify this query:\n\n{q}", system=CLASSIFY_SYSTEM, max_tokens=200)
            parsed = extract_json(resp)
            if parsed["classification"] == "NON_SENSITIVE":
                results["tn"] += 1
            else:
                results["fp"] += 1
                print(f"  FALSE POSITIVE [{i}]: {q[:80]}...")
                print(f"    Reason: {parsed.get('reason', 'N/A')}")
        except Exception as e:
            results["errors"] += 1
            print(f"  ERROR [{i}]: {e}")

    total = results["tp"] + results["fp"] + results["tn"] + results["fn"]
    accuracy = (results["tp"] + results["tn"]) / total if total > 0 else 0
    precision = results["tp"] / (results["tp"] + results["fp"]) if (results["tp"] + results["fp"]) > 0 else 0
    recall = results["tp"] / (results["tp"] + results["fn"]) if (results["tp"] + results["fn"]) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    print(f"\nResults (n={total}):")
    print(f"  Accuracy:  {accuracy:.1%}")
    print(f"  Precision: {precision:.1%}")
    print(f"  Recall:    {recall:.1%}")
    print(f"  F1:        {f1:.1%}")
    print(f"  Errors:    {results['errors']}")

    return {**results, "accuracy": accuracy, "precision": precision, "recall": recall, "f1": f1}


# ─────────────────────────────────────────────
# Benchmark B: Decomposition Quality
# ─────────────────────────────────────────────

DECOMPOSE_SYSTEM = """You are a DeFi privacy orchestrator. Given a user query containing private financial information,
decompose it into generic sub-queries that:
1. Individually reveal NO private parameters (amounts, addresses, health factors, specific positions)
2. Collectively contain enough information to reconstruct a useful answer when combined with the private parameters locally

Rules:
- NEVER include specific dollar amounts, token quantities, wallet addresses, or health factor values in sub-queries
- NEVER include the user's specific trading direction or timing
- Each sub-query should ask about a GENERIC DeFi mechanism that any user could ask about
- Aim for 2-4 sub-queries

Respond with ONLY a JSON object:
{"sub_queries": ["query1", "query2", ...], "local_reasoning": "what the local model computes using private params + cloud answers"}"""


def benchmark_b(n_samples: int = 10):
    """Test decomposition quality: do sub-queries leak private params?"""
    print("\n" + "=" * 60)
    print("BENCHMARK B: Decomposition Quality")
    print("=" * 60)

    samples = COMPLEX_QUERIES[:n_samples]
    results = {"total": 0, "no_leak": 0, "leaked": 0, "errors": 0, "details": []}

    for i, item in enumerate(samples):
        q = item["query"]
        private_params = item["private_params"]
        print(f"\n--- Query {i+1}/{len(samples)} ---")
        print(f"  Original: {q[:100]}...")
        print(f"  Private params to protect: {private_params}")

        try:
            resp = call_llm(f"Decompose this query:\n\n{q}", system=DECOMPOSE_SYSTEM, max_tokens=500)
            parsed = extract_json(resp)
            sub_queries = parsed.get("sub_queries", [])
            local_reasoning = parsed.get("local_reasoning", "")

            leaked = []
            for param in private_params:
                for sq in sub_queries:
                    param_variants = [param, param.replace(",", ""), param.replace("$", "")]
                    for pv in param_variants:
                        if pv.lower() in sq.lower() and len(pv) > 2:
                            leaked.append(f"'{pv}' found in sub-query: '{sq[:80]}'")

            results["total"] += 1
            if leaked:
                results["leaked"] += 1
                print(f"  LEAKED: {leaked[:3]}")
            else:
                results["no_leak"] += 1
                print(f"  CLEAN: {len(sub_queries)} sub-queries, no param leakage")

            for j, sq in enumerate(sub_queries):
                print(f"    Sub-query {j+1}: {sq}")

            results["details"].append({
                "query_idx": i,
                "sub_queries": sub_queries,
                "leaked": leaked,
                "local_reasoning": local_reasoning,
            })

        except Exception as e:
            results["errors"] += 1
            print(f"  ERROR: {e}")

    leak_rate = results["leaked"] / results["total"] if results["total"] > 0 else 0
    print(f"\nResults (n={results['total']}):")
    print(f"  Clean decompositions: {results['no_leak']}/{results['total']} ({1-leak_rate:.0%})")
    print(f"  Leaked params:        {results['leaked']}/{results['total']} ({leak_rate:.0%})")
    print(f"  Target: 0% leakage")

    return results


# ─────────────────────────────────────────────
# Benchmark C: Cover Query Indistinguishability
# ─────────────────────────────────────────────

# v1 naive cover generation (for comparison)
COVER_SYSTEM_V1 = """You are a DeFi privacy orchestrator generating cover queries.
Given a REAL sanitized DeFi query, generate 3 plausible COVER queries that:
1. Are about DIFFERENT DeFi topics (not the same protocol/concept)
2. Have similar length, complexity, and style as the real query
3. Sound like genuine questions a DeFi user would ask
4. Are NOT obviously generated or template-based

Respond with ONLY a JSON array of 3 cover queries: ["cover1", "cover2", "cover3"]"""

DETECT_SYSTEM = """You are analyzing a set of 4 DeFi queries. One of them is a "real" query that a user actually
wants answered. The other 3 are "cover" queries generated to hide the real one.

Your task: identify which query is MOST LIKELY the real one.

Consider:
- Does one query seem more specific or urgent than the others?
- Does one query have a different writing style?
- Are there subtle patterns suggesting generation (too uniform, too diverse)?
- Does one query seem more "purposeful" vs "generic"?

Respond with ONLY a JSON object: {"guess": 0-3, "confidence": "low/medium/high", "reason": "brief explanation"}"""

# Multi-strategy adversary (v4/v5 style)
DETECT_SYSTEM_MULTI = """You are a sophisticated adversary analyzing a set of 4 DeFi queries. One is "real" (a user's
actual question), the other 3 are cover queries designed to hide it.

Apply THREE detection strategies independently, then give your final answer:

Strategy A (Intuitive): Which query "feels" most like a real user question?
Strategy B (Structural): Compare lengths, complexity, specificity levels. Any outlier?
Strategy C (Topical Prior): Which DeFi topic is most commonly asked about in practice?
  (Lending ~25%, DEX/trading ~30%, Staking ~15%, Derivatives ~10%, other ~20%)

Respond with ONLY a JSON object:
{
  "strategy_a": {"guess": 0-3, "reason": "..."},
  "strategy_b": {"guess": 0-3, "reason": "..."},
  "strategy_c": {"guess": 0-3, "reason": "..."},
  "final_guess": 0-3,
  "confidence": "low/medium/high"
}"""


def benchmark_c(n_samples: int = 20, cover_version: str = "v5", adversary: str = "multi"):
    """Test if an adversary can distinguish real DeFi queries from generated covers."""
    print("\n" + "=" * 60)
    print(f"BENCHMARK C: Cover Indistinguishability (covers={cover_version}, adversary={adversary})")
    print("=" * 60)

    real_sample = random.sample(SANITIZED_QUERIES, min(n_samples, len(SANITIZED_QUERIES)))
    correct_guesses = 0
    total_tests = 0
    domain_results = {}  # track detection per domain

    detect_system = DETECT_SYSTEM_MULTI if adversary == "multi" else DETECT_SYSTEM

    print(f"\nTesting {len(real_sample)} query sets...\n")

    for i, real_q in enumerate(real_sample):
        try:
            # Generate covers
            if cover_version == "v5":
                shuffled, real_pos, domain, template, cover_domains = generate_cover_set_raw(
                    real_q, k=4, seed=42 + i, presanitized=True
                )
            elif cover_version == "v4":
                shuffled, real_pos, domain, template, cover_domains = generate_cover_set_raw(
                    real_q, k=4, seed=42 + i, domain_strategy="weighted", presanitized=True
                )
            elif cover_version == "v1":
                # Naive: ask LLM to generate covers
                cover_resp = call_llm(
                    f"Generate 3 cover queries for this real query:\n\n{real_q}",
                    system=COVER_SYSTEM_V1, max_tokens=500
                )
                covers = extract_json(cover_resp)
                if not isinstance(covers, list) or len(covers) != 3:
                    print(f"  [{i}] Bad cover format, skipping")
                    continue
                all_queries = [real_q] + covers
                indices = list(range(4))
                random.shuffle(indices)
                shuffled = [all_queries[j] for j in indices]
                real_pos = indices.index(0)
                domain = "unknown"
                template = "N/A"
                cover_domains = []
            else:
                raise ValueError(f"Unknown cover version: {cover_version}")

            # Present to adversary
            query_list = "\n".join([f"Query {j}: {shuffled[j]}" for j in range(4)])
            detect_resp = call_llm(
                f"Which of these 4 queries is the real one?\n\n{query_list}",
                system=detect_system, max_tokens=300
            )
            parsed = extract_json(detect_resp)

            if adversary == "multi":
                guess = parsed.get("final_guess", -1)
                confidence = parsed.get("confidence", "?")
            else:
                guess = parsed.get("guess", -1)
                confidence = parsed.get("confidence", "?")

            total_tests += 1
            detected = guess == real_pos
            if detected:
                correct_guesses += 1

            # Track per-domain
            if domain not in domain_results:
                domain_results[domain] = {"total": 0, "detected": 0}
            domain_results[domain]["total"] += 1
            if detected:
                domain_results[domain]["detected"] += 1

            status = "DETECTED" if detected else "FOOLED"
            print(f"  [{i}] {status} (real={real_pos}, guess={guess}, conf={confidence}, domain={domain})")

        except Exception as e:
            print(f"  [{i}] ERROR: {e}")

    detection_rate = correct_guesses / total_tests if total_tests > 0 else 0

    print(f"\n{'='*40}")
    print(f"Results (n={total_tests}, covers={cover_version}, adversary={adversary}):")
    print(f"  Detection rate:  {detection_rate:.1%} ({correct_guesses}/{total_tests})")
    print(f"  Random baseline: 25.0%")
    print(f"  Target:          <40%")

    if domain_results:
        print(f"\n  Per-domain breakdown:")
        for d, r in sorted(domain_results.items()):
            rate = r["detected"] / r["total"] if r["total"] > 0 else 0
            print(f"    {d}: {rate:.0%} ({r['detected']}/{r['total']})")

    if detection_rate <= 0.25:
        print(f"\n  PASS: At or below random baseline")
    elif detection_rate <= 0.40:
        print(f"\n  PASS: Below target threshold")
    elif detection_rate <= 0.60:
        print(f"\n  MARGINAL: Some detection ability, covers need improvement")
    else:
        print(f"\n  FAIL: Covers too distinguishable")

    return {
        "detection_rate": detection_rate,
        "total": total_tests,
        "correct": correct_guesses,
        "cover_version": cover_version,
        "adversary": adversary,
        "per_domain": domain_results,
    }


# ─────────────────────────────────────────────
# Benchmark D: End-to-End Answer Quality
# ─────────────────────────────────────────────

QUALITY_JUDGE_SYSTEM = """You are evaluating whether a DeFi answer is useful. You will see:
1. A user's ORIGINAL QUESTION (sanitized — no specific amounts, but retains the specific topic)
2. An ANSWER generated from a rewritten version of that question

Rate the answer's usefulness for the original question on a 1-5 scale:
5 = Directly answers the original question with relevant, specific information
4 = Mostly relevant, covers the core topic but misses some specifics
3 = Partially relevant, provides related DeFi knowledge but doesn't fully address the question
2 = Tangentially related, mostly about a different topic
1 = Irrelevant, about a completely different topic

Respond with ONLY a JSON object: {"score": 1-5, "reason": "brief explanation"}"""


def benchmark_d(n_samples: int = 15):
    """Compare answer quality: original sanitized query vs template-rewritten query."""
    print("\n" + "=" * 60)
    print("BENCHMARK D: Answer Quality (sanitized vs template-rewritten)")
    print("=" * 60)

    sample = random.sample(SANITIZED_QUERIES, min(n_samples, len(SANITIZED_QUERIES)))
    results_list = []

    for i, original_q in enumerate(sample):
        try:
            # Generate template-rewritten version (what Tier 1 sends to cloud)
            from cover_generator import _generate
            _, _, domain, template, _ = _generate(original_q, k=4, seed=42 + i, domain_strategy="top4", presanitized=True)
            # The real query in the cover set is template-rewritten
            # Regenerate just the real fill
            rng = random.Random(42 + i)
            from cover_generator import DOMAIN_ONTOLOGY, extract_template
            tmpl = extract_template(original_q, rng=rng)
            onto = DOMAIN_ONTOLOGY[domain]
            rewritten = tmpl
            for slot, key in [("{MECHANISM}", "mechanisms"), ("{OPERATION}", "operations"),
                              ("{TRIGGER}", "triggers"), ("{METRIC}", "metrics"),
                              ("{ACTOR}", "actors"), ("{GENERIC_REF}", "generic_refs"),
                              ("{RISK_CONCEPT}", "risk_concepts"),
                              ("{OPERATION_A}", "operations"), ("{OPERATION_B}", "operations")]:
                if slot in rewritten:
                    rewritten = rewritten.replace(slot, rng.choice(onto[key]), 1)

            print(f"\n--- Query {i+1}/{len(sample)} ---")
            print(f"  Original:  {original_q[:90]}")
            print(f"  Rewritten: {rewritten[:90]}")

            # Get answer to the template-rewritten query (what the cloud sees)
            answer = call_llm(rewritten, max_tokens=300)

            # Judge: is this answer useful for the ORIGINAL question?
            judge_prompt = (
                f"ORIGINAL QUESTION: {original_q}\n\n"
                f"ANSWER (from rewritten query): {answer[:500]}\n\n"
                f"How useful is this answer for the original question?"
            )
            judge_resp = call_llm(judge_prompt, system=QUALITY_JUDGE_SYSTEM, max_tokens=150)
            parsed = extract_json(judge_resp)
            score = parsed.get("score", 0)
            reason = parsed.get("reason", "")

            results_list.append({
                "original": original_q,
                "rewritten": rewritten,
                "score": score,
                "reason": reason,
                "domain": domain,
            })
            print(f"  Score: {score}/5 — {reason[:60]}")

        except Exception as e:
            print(f"  [{i}] ERROR: {e}")

    if not results_list:
        print("\nNo results")
        return {}

    scores = [r["score"] for r in results_list]
    avg = sum(scores) / len(scores)
    dist = {s: scores.count(s) for s in range(1, 6)}

    print(f"\n{'='*40}")
    print(f"Results (n={len(scores)}):")
    print(f"  Average score: {avg:.2f}/5")
    print(f"  Distribution: {dist}")
    print(f"  Score >=4 (useful): {sum(1 for s in scores if s >= 4)}/{len(scores)} ({sum(1 for s in scores if s >= 4)/len(scores):.0%})")
    print(f"  Score >=3 (partially useful): {sum(1 for s in scores if s >= 3)}/{len(scores)} ({sum(1 for s in scores if s >= 3)/len(scores):.0%})")
    print(f"\n  Target: >80% scoring >=4")

    return {
        "avg_score": avg,
        "distribution": dist,
        "n": len(scores),
        "pct_useful": sum(1 for s in scores if s >= 4) / len(scores),
        "pct_partial": sum(1 for s in scores if s >= 3) / len(scores),
        "details": results_list,
    }


# ─────────────────────────────────────────────
# Benchmark D2: Full Pipeline End-to-End Quality
# (decompose → covers → cloud → synthesize)
# ─────────────────────────────────────────────

DECOMPOSE_FOR_PIPELINE = """You are a DeFi privacy orchestrator. Given a user query, decompose it into 2-3 generic sub-queries that:
1. Reveal NO private parameters
2. Each ask about a generic DeFi mechanism
3. Together provide enough information to answer the original question

Respond with ONLY a JSON array of sub-queries: ["query1", "query2"]"""

SYNTHESIZE_SYSTEM = """You are a DeFi advisor. You have received answers to several generic sub-queries about DeFi mechanics.
Using these answers AND the user's specific parameters (provided below), synthesize a concrete, actionable answer.

Respond naturally as if answering the user's original question directly."""


def benchmark_d2(n_samples: int = 5):
    """Full pipeline: decompose → cover → cloud → synthesize. Compare to direct query."""
    print("\n" + "=" * 60)
    print("BENCHMARK D2: Full Pipeline End-to-End Quality")
    print("=" * 60)
    print("  (decompose → covers → cloud answers → synthesize with private params)")

    # Use complex queries that have both the full query and known private params
    samples = COMPLEX_QUERIES[:n_samples]
    results_list = []

    for i, item in enumerate(samples):
        original_q = item["query"]
        private_params = item["private_params"]

        print(f"\n--- Query {i+1}/{len(samples)} ---")
        print(f"  Original: {original_q[:90]}...")

        try:
            # Step 1: Get direct answer (baseline — no privacy)
            direct_answer = call_llm(original_q, max_tokens=400)

            # Step 2: Decompose into sub-queries (what the local LLM does)
            decomp_resp = call_llm(
                f"Decompose this query:\n\n{sanitize_query(original_q)}",
                system=DECOMPOSE_FOR_PIPELINE, max_tokens=300
            )
            sub_queries = extract_json(decomp_resp)
            if not isinstance(sub_queries, list):
                sub_queries = sub_queries.get("sub_queries", [])

            print(f"  Sub-queries: {len(sub_queries)}")
            for j, sq in enumerate(sub_queries):
                print(f"    {j+1}. {sq[:80]}")

            # Step 3: Generate covers for each sub-query and get cloud answers
            sub_answers = []
            for sq in sub_queries:
                # In the real pipeline, covers would be sent too; here we just answer the real sub-query
                answer = call_llm(sq, max_tokens=300)
                sub_answers.append(answer)

            # Step 4: Synthesize using sub-answers + private params
            synthesis_prompt = (
                f"The user's original question: {original_q}\n\n"
                f"Their private parameters: {', '.join(private_params)}\n\n"
                f"Sub-query answers:\n" +
                "\n".join(f"Q: {sq}\nA: {sa[:200]}" for sq, sa in zip(sub_queries, sub_answers)) +
                f"\n\nSynthesize a complete answer for the user."
            )
            pipeline_answer = call_llm(synthesis_prompt, system=SYNTHESIZE_SYSTEM, max_tokens=400)

            # Step 5: Blinded A/B — judge BOTH answers, randomized order
            answers = [
                ("direct", direct_answer),
                ("pipeline", pipeline_answer),
            ]
            rng_ab = random.Random(42 + i)
            rng_ab.shuffle(answers)

            scores = {}
            for label, answer in answers:
                judge_prompt = (
                    f"ORIGINAL QUESTION: {original_q}\n\n"
                    f"ANSWER: {answer[:500]}\n\n"
                    f"How useful is this answer for the original question?"
                )
                judge_resp = call_llm(judge_prompt, system=QUALITY_JUDGE_SYSTEM, max_tokens=150)
                parsed = extract_json(judge_resp)
                scores[label] = parsed.get("score", 0)

            results_list.append({
                "direct_score": scores["direct"],
                "pipeline_score": scores["pipeline"],
                "quality_retained": scores["pipeline"] / max(scores["direct"], 1),
            })
            print(f"  Direct: {scores['direct']}/5 | Pipeline: {scores['pipeline']}/5 | Retained: {scores['pipeline']/max(scores['direct'],1):.0%}")

        except Exception as e:
            print(f"  ERROR: {e}")

    if not results_list:
        return {}

    direct_scores = [r["direct_score"] for r in results_list]
    pipeline_scores = [r["pipeline_score"] for r in results_list]
    retained = [r["quality_retained"] for r in results_list]
    avg_direct = sum(direct_scores) / len(direct_scores)
    avg_pipeline = sum(pipeline_scores) / len(pipeline_scores)
    avg_retained = sum(retained) / len(retained)

    print(f"\n{'='*40}")
    print(f"Full Pipeline A/B Results (n={len(results_list)}):")
    print(f"  Direct avg:   {avg_direct:.2f}/5")
    print(f"  Pipeline avg: {avg_pipeline:.2f}/5")
    print(f"  Quality retained: {avg_retained:.0%}")
    print(f"  Pipeline >=4: {sum(1 for s in pipeline_scores if s >= 4)}/{len(pipeline_scores)}")

    return {
        "avg_direct": avg_direct,
        "avg_pipeline": avg_pipeline,
        "avg_retained": avg_retained,
        "n": len(results_list),
        "details": results_list,
    }


# ─────────────────────────────────────────────
# Benchmark E: Session Composition Attack
# ─────────────────────────────────────────────

SESSION_DETECT_SYSTEM = """You are an adversary analyzing a sequence of DeFi queries observed over a user session.
Each query was one of 4 sent to the cloud (the real query mixed with 3 covers). You see one query per round
— it may be the real one or a cover.

Based on the accumulated queries, infer the user's underlying DeFi strategy.

Choose from the following options:
{strategies}

Respond with ONLY a JSON object: {{"guess": "exact strategy name", "confidence": "low/medium/high", "reasoning": "brief explanation"}}"""


def benchmark_e(n_scenarios: int = 5, max_queries: int = 10, use_covers: bool = True):
    """Test if multi-query sessions leak strategy even when individual queries are safe."""
    print("\n" + "=" * 60)
    print(f"SIMULATION E: Session Composition (covers={'on' if use_covers else 'off'})")
    print("  (Best-case: assumes per-set unlinkability via independent Tor circuits)")
    print("=" * 60)

    scenarios = SESSION_SCENARIOS[:n_scenarios]
    # Track recovery rate at different query counts
    checkpoints = [1, 3, 5, 7, 10]
    checkpoint_results = {cp: {"total": 0, "correct": 0} for cp in checkpoints}

    for s_idx, scenario in enumerate(scenarios):
        true_strategy = scenario["strategy"]
        all_strategies = [true_strategy] + scenario["decoy_strategies"]
        random.shuffle(all_strategies)
        strategies_str = "\n".join(f"- {s}" for s in all_strategies)

        queries = scenario["queries"][:max_queries]
        observed = []

        print(f"\n--- Scenario {s_idx+1}: {true_strategy} ---")

        for q_idx, query in enumerate(queries):
            if use_covers:
                # Generate cover set, adversary sees a random one
                cover_set, real_pos = generate_cover_set(query, k=4, seed=100 + s_idx * 20 + q_idx, presanitized=True)
                # Adversary intercepts one query at random (simulating k independent circuits)
                observed_query = random.choice(cover_set)
            else:
                # No covers — adversary sees the real query directly
                observed_query = query

            observed.append(observed_query)

            # Check at each checkpoint
            if (q_idx + 1) in checkpoints:
                observed_text = "\n".join(f"  Query {j+1}: {q}" for j, q in enumerate(observed))
                system = SESSION_DETECT_SYSTEM.format(strategies=strategies_str)

                try:
                    resp = call_llm(
                        f"After observing {len(observed)} queries from this session:\n{observed_text}\n\nWhat is the user's strategy?",
                        system=system, max_tokens=200
                    )
                    parsed = extract_json(resp)
                    guess = parsed.get("guess", "")
                    correct = guess.strip().lower() == true_strategy.lower()

                    checkpoint_results[q_idx + 1]["total"] += 1
                    if correct:
                        checkpoint_results[q_idx + 1]["correct"] += 1

                    status = "IDENTIFIED" if correct else "wrong"
                    print(f"    After {q_idx+1} queries: {status} (guess: {guess[:50]})")

                except Exception as e:
                    print(f"    After {q_idx+1} queries: ERROR ({e})")

    random_baseline = 1.0 / 5  # 5 choices
    print(f"\n{'='*40}")
    print(f"Results (covers={'on' if use_covers else 'off'}):")
    print(f"  Random baseline: {random_baseline:.0%}")
    print(f"\n  {'Queries':>8} | {'Recovery Rate':>14} | {'n':>4}")
    print(f"  {'-'*8}-+-{'-'*14}-+-{'-'*4}")
    for cp in checkpoints:
        r = checkpoint_results[cp]
        if r["total"] > 0:
            rate = r["correct"] / r["total"]
            print(f"  {cp:>8} | {rate:>13.0%} | {r['total']:>4}")

    return {
        "use_covers": use_covers,
        "checkpoints": {
            str(cp): {
                "recovery_rate": r["correct"] / r["total"] if r["total"] > 0 else 0,
                **r
            }
            for cp, r in checkpoint_results.items()
        },
    }


# ─────────────────────────────────────────────
# Benchmark F: Damage Reduction (pure math)
# ─────────────────────────────────────────────

def benchmark_f():
    """Simulate economic damage with and without protection. No LLM needed."""
    print("\n" + "=" * 60)
    print("SIMULATION F: Economic Damage Model (Illustrative, not empirical)")
    print("  (Assumes sanitizer catches all params; models parameter-dependent attacks only)")
    print("=" * 60)

    results = []

    for s in MEV_SCENARIOS:
        if s["type"] == "swap_frontrun":
            damage_low = s["trade_size_usd"] * s["extraction_rate_low"]
            damage_high = s["trade_size_usd"] * s["extraction_rate_high"]
            damage_sanitized = 0
            damage_covered = damage_high * 0.25  # k=4
            defense_cost = 0.012

            results.append({
                "type": "swap_frontrun",
                "trade_size": f"${s['trade_size_usd']:,.0f}",
                "damage_no_protection": f"${damage_low:,.0f}-${damage_high:,.0f}",
                "damage_sanitized": f"${damage_sanitized:,.0f}",
                "damage_with_covers": f"${damage_covered:,.0f}",
                "defense_cost": f"${defense_cost:.3f}",
                "reduction": "100% (sanitization), ~75% (covers alone)",
            })

        elif s["type"] == "liquidation":
            close_factor = 0.5
            profit = s["debt_usd"] * close_factor * s["bonus_rate"]
            damage_sanitized = 0
            damage_covered = profit * 0.25
            defense_cost = 0.012

            results.append({
                "type": "liquidation",
                "position": f"${s['position_usd']:,.0f}",
                "damage_no_protection": f"${profit:,.0f}",
                "damage_sanitized": f"${damage_sanitized:,.0f}",
                "damage_with_covers": f"${damage_covered:,.0f}",
                "defense_cost": f"${defense_cost:.3f}",
                "reduction": "100% (sanitization)",
            })

        elif s["type"] == "strategy_theft":
            low = s["estimated_lifetime_value_low"]
            high = s["estimated_lifetime_value_high"]
            results.append({
                "type": "strategy_theft",
                "damage_no_protection": f"${low:,.0f}-${high:,.0f}",
                "damage_decomposed": f"$0",
                "defense_cost": f"$0.012",
                "reduction": "100% (decomposition keeps strategy local)",
            })

    print(f"\n{'Type':<20} {'Without Protection':<25} {'With Sanitization':<20} {'With Covers(k=4)':<20}")
    print("-" * 85)
    for r in results:
        if r["type"] == "swap_frontrun":
            print(f"{'Swap '+r['trade_size']:<20} {r['damage_no_protection']:<25} {r['damage_sanitized']:<20} {r['damage_with_covers']:<20}")
        elif r["type"] == "liquidation":
            print(f"{'Liq '+r['position']:<20} {r['damage_no_protection']:<25} {r['damage_sanitized']:<20} {r['damage_with_covers']:<20}")
        elif r["type"] == "strategy_theft":
            print(f"{'Strategy':<20} {r['damage_no_protection']:<25} {r['damage_decomposed']:<20} {'N/A':<20}")

    return results


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Privacy Orchestration Benchmarks")
    parser.add_argument("--benchmark", "-b",
                        choices=["A", "B", "C", "D", "D2", "E", "F", "all"],
                        default="all")
    parser.add_argument("--backend", choices=["anthropic", "ollama"],
                        default="anthropic")
    parser.add_argument("--model", "-m", default=None,
                        help="Model name (default: claude-haiku-4-5-20251001 for anthropic, qwen2.5:32b for ollama)")
    parser.add_argument("--samples", "-n", type=int, default=20,
                        help="Samples per benchmark")
    parser.add_argument("--cover-version", choices=["v1", "v4", "v5"],
                        default="v5", help="Cover generation strategy for Benchmark C")
    parser.add_argument("--adversary", choices=["single", "multi"],
                        default="multi", help="Adversary strategy for Benchmark C")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed")
    args = parser.parse_args()

    random.seed(args.seed)

    # Init LLM backend (skip for F-only since it doesn't need LLM)
    if args.benchmark != "F":
        init_backend(args.backend, args.model)

    results = {}

    if args.benchmark in ("F", "all"):
        results["F"] = benchmark_f()

    if args.benchmark in ("A", "all"):
        results["A"] = benchmark_a(args.samples)

    if args.benchmark in ("B", "all"):
        results["B"] = benchmark_b(min(args.samples, len(COMPLEX_QUERIES)))

    if args.benchmark in ("C", "all"):
        results["C"] = benchmark_c(args.samples, args.cover_version, args.adversary)

    if args.benchmark in ("D", "all"):
        results["D"] = benchmark_d(args.samples)

    if args.benchmark in ("D2", "all"):
        results["D2"] = benchmark_d2(min(args.samples, len(COMPLEX_QUERIES)))

    if args.benchmark in ("E", "all"):
        results["E_covers"] = benchmark_e(use_covers=True)
        results["E_no_covers"] = benchmark_e(use_covers=False)

    # Save results
    RESULTS_DIR.mkdir(exist_ok=True)
    out_path = RESULTS_DIR / "results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
