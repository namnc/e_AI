"""
Profile compiler for stealth address ops.

Composes analyzer + cover generator + LLM into a single analysis pipeline.
Mirrors e_AI v1's compiler/ module.

Usage:
    from domains.stealth_address_ops.compiler import compile_analysis

    result = compile_analysis(tx, profile, pool_state, llm=analyzer)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from domains.stealth_address_ops.analyzer import (
    SteathTx, AnalysisResult, analyze_transaction, format_result,
)
from domains.stealth_address_ops.cover_generator import (
    CoverGenerator, CoverParams, PoolState, UserIntent, measure_cover_quality,
)


@dataclass
class CompiledAnalysis:
    """Full analysis result: rule-based + cover + LLM."""
    rule_based: AnalysisResult
    cover: Optional[CoverParams] = None
    cover_quality: Optional[dict] = None
    llm_analysis: Optional[dict] = None
    summary: str = ""


def compile_analysis(
    tx: SteathTx,
    profile: dict,
    pool_state: Optional[PoolState] = None,
    llm_analyzer=None,
    user_history: Optional[list[dict]] = None,
    deposit_pool_amounts: Optional[list[float]] = None,
) -> CompiledAnalysis:
    """Run full analysis pipeline.

    1. Rule-based heuristic checks (always)
    2. Cover parameter generation (if pool state available)
    3. LLM behavioral analysis (if LLM available)
    4. Compile into unified result
    """
    result = CompiledAnalysis(
        rule_based=analyze_transaction(tx, profile, deposit_pool_amounts),
    )

    # Cover generation
    if pool_state:
        cg = CoverGenerator(profile, pool_state)
        intent = UserIntent(
            amount_eth=tx.amount_eth,
            recipient=tx.withdrawal_address,
            urgency="normal",
        )
        result.cover = cg.generate(intent)
        result.cover_quality = measure_cover_quality(result.cover, pool_state)

    # LLM analysis
    if llm_analyzer:
        tx_dict = {
            "amount_eth": tx.amount_eth,
            "dwell_hours": (tx.spend_timestamp - tx.deposit_timestamp) / 3600,
            "gas_price_gwei": tx.gas_price_gwei,
            "gas_funding_source": tx.gas_funding_source,
            "is_self_send": tx.is_self_send,
        }
        rule_alerts = [
            {"heuristic": a.heuristic_id, "signal": a.signal, "confidence": a.confidence}
            for a in result.rule_based.alerts
        ]
        result.llm_analysis = llm_analyzer.analyze(tx_dict, user_history, rule_alerts)

    # Summary
    result.summary = _build_summary(result)

    return result


def _build_summary(result: CompiledAnalysis) -> str:
    """Build human-readable summary from all analysis components."""
    parts = []

    # Rule-based
    rb = result.rule_based
    parts.append(f"Risk: {rb.overall_risk.upper()}")
    if rb.deanonymized:
        parts.append("LIKELY DEANONYMIZED")
    parts.append(f"Alerts: {len(rb.alerts)}")

    for alert in rb.alerts:
        parts.append(f"  [{alert.heuristic_id}] {alert.signal}")

    # Cover
    if result.cover:
        parts.append(f"\nCover recommendation:")
        parts.append(f"  Amount: {result.cover.amount_eth} ETH")
        parts.append(f"  Delay: {result.cover.delay_seconds / 3600:.1f}h")
        parts.append(f"  Gas: {result.cover.gas_price_gwei} gwei")
        parts.append(f"  Funding: {result.cover.funding_method}")
        parts.append(f"  Cover score: {result.cover.overall_cover_score}")
        parts.append(f"  Anonymity set: ~{result.cover.anonymity_set_estimate}")

    if result.cover_quality:
        parts.append(f"  Adversary detection: {result.cover_quality['detection_rate']:.1%}")

    # LLM
    if result.llm_analysis:
        llm = result.llm_analysis
        if llm.get("explanation"):
            parts.append(f"\nLLM analysis: {llm['explanation']}")
        if llm.get("behavioral_notes") and llm["behavioral_notes"] != "none":
            parts.append(f"Behavioral: {llm['behavioral_notes']}")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import random
    import datetime

    profile_path = Path(__file__).parent / "profile.json"
    with open(profile_path) as f:
        profile = json.load(f)

    # Synthetic pool
    now = int(datetime.datetime.now(tz=datetime.timezone.utc).timestamp())
    rng = random.Random(42)
    deposits = []
    for i in range(50):
        amounts = [0.1, 0.5, 1.0, 1.0, 1.0, 5.0, 5.0, 10.0]
        deposits.append({
            "amount_eth": rng.choice(amounts) if rng.random() > 0.3 else round(rng.uniform(0.1, 50), 4),
            "timestamp": now - rng.randint(0, 86400),
            "gas_price_gwei": round(rng.gauss(30, 4), 1),
        })
    pool = PoolState(deposits=deposits)

    # Test transaction
    tx = SteathTx(
        deposit_address="0xaaaa",
        withdrawal_address="0xbbbb",
        stealth_address="0xcccc",
        amount_eth=3.847,
        deposit_timestamp=now - 600,
        spend_timestamp=now,
        gas_price_gwei=45.0,
        gas_funding_source="0xaaaa",
        address_cluster={"0xaaaa"},
    )

    # Try with LLM if available
    llm = None
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from core.llm_analyzer import LLMAnalyzer
        llm = LLMAnalyzer(profile, backend="ollama", model="qwen2.5:7b")
        llm.connect()
        print("LLM connected.\n")
    except Exception as e:
        print(f"LLM not available ({e}). Running without.\n")

    result = compile_analysis(tx, profile, pool, llm)
    print(result.summary)
