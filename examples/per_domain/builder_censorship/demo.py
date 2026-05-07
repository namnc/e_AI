"""
builder_censorship demo — runs the rule-based + LLM analyzers on a sample tx.

Run:
    python examples/per_domain/builder_censorship/demo.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from core.llm_analyzer import LLMAnalyzer
from domains.builder_censorship.analyzer import (
    BuilderCensorshipTx,
    analyze_transaction,
    load_profile,
)


HERE = Path(__file__).parent
PROFILE_PATH = REPO_ROOT / "domains" / "builder_censorship" / "profile.json"
SAMPLE_PATH = HERE / "sample_tx.json"


def build_tx() -> BuilderCensorshipTx:
    raw = json.loads(SAMPLE_PATH.read_text())
    return BuilderCensorshipTx(
        tx_hash=raw["tx_hash"],
        user_address=raw["user_address"],
        to_address=raw["to_address"],
        selected_relays=raw["selected_relays"],
        has_private_mempool_configured=raw["has_private_mempool_configured"],
        destination_chain=raw["destination_chain"],
        interacts_with_sanctioned_addresses=raw["interacts_with_sanctioned_addresses"],
        recent_block_builder_count=raw["recent_block_builder_count"],
        dominant_builder_share=raw["dominant_builder_share"],
        wallet_exposes_l1_inbox_path=raw["wallet_exposes_l1_inbox_path"],
        mev_boost_enabled=raw["mev_boost_enabled"],
    )


def print_result(result, llm_result):
    print("=" * 70)
    print("builder_censorship — pre-submission CR routing audit")
    print("=" * 70)
    print(f"Tx: {result.tx.tx_hash}")
    print(f"To: {result.tx.to_address}  | Chain: {result.tx.destination_chain}")
    print(f"Relays: {', '.join(result.tx.selected_relays)}")
    print(f"Private mempool: {result.tx.has_private_mempool_configured}")
    print(f"Sanctioned touches: {len(result.tx.interacts_with_sanctioned_addresses)}")
    print()
    print(f"OVERALL RISK: {result.overall_risk.upper()}")
    print(f"SHOULD BLOCK: {result.should_block}")
    print(f"ALERTS: {len(result.alerts)}")
    print()
    for a in result.alerts:
        print(f"  [{a.severity.upper():8s}] {a.heuristic_id} {a.heuristic_name} "
              f"(confidence {a.confidence:.2f})")
        print(f"    signal: {a.signal}")
        print(f"    recommend: {a.recommendation}")
        if a.action:
            print(f"    action: {a.action}")
        print()
    print("-" * 70)
    print("LLM behavioral analysis")
    print("-" * 70)
    if llm_result.get("degraded_mode"):
        print(f"[degraded] {llm_result.get('degraded_reason')}")
        print(f"Synthesized result: {llm_result.get('explanation')}")
    else:
        print(f"Risk: {llm_result.get('risk_level')}")
        print(f"Explanation: {llm_result.get('explanation')}")
        if llm_result.get("recommendations"):
            print("Recommendations:")
            for r in llm_result["recommendations"]:
                print(f"  - {r}")
        notes = llm_result.get("behavioral_notes")
        if notes and notes != "none":
            print(f"Behavioral: {notes}")


def main():
    profile = load_profile(PROFILE_PATH)
    tx = build_tx()
    result = analyze_transaction(tx, profile)

    rule_alerts_dicts = [
        {
            "heuristic_id": a.heuristic_id,
            "severity": a.severity,
            "signal": a.signal,
            "recommendation": a.recommendation,
        }
        for a in result.alerts
    ]
    llm = LLMAnalyzer(profile, backend="ollama", model="qwen2.5:7b")
    llm.connect()
    llm_result = llm.analyze(
        tx={
            "to": tx.to_address,
            "chain": tx.destination_chain,
            "relays": tx.selected_relays,
            "private_mempool": tx.has_private_mempool_configured,
            "sanctioned_touches": tx.interacts_with_sanctioned_addresses,
        },
        rule_based_alerts=rule_alerts_dicts,
    )

    print_result(result, llm_result)


if __name__ == "__main__":
    main()
