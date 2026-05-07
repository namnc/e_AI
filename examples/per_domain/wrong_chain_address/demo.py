"""
wrong_chain_address demo — runs the rule-based + LLM analyzers on a sample transfer.

Run:
    python examples/per_domain/wrong_chain_address/demo.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from core.llm_analyzer import LLMAnalyzer
from domains.wrong_chain_address.analyzer import (
    TransferIntent,
    analyze_transfer,
    load_profile,
)


HERE = Path(__file__).parent
PROFILE_PATH = REPO_ROOT / "domains" / "wrong_chain_address" / "profile.json"
SAMPLE_PATH = HERE / "sample_tx.json"


def build_transfer() -> TransferIntent:
    raw = json.loads(SAMPLE_PATH.read_text())
    return TransferIntent(
        tx_hash=raw.get("tx_hash", "0xdemo"),
        user_address=raw["user_address"],
        recipient_address=raw["recipient_address"],
        intended_target_chain_id=raw["intended_target_chain_id"],
        intended_target_chain_name=raw["intended_target_chain_name"],
        signing_chain_id=raw["signing_chain_id"],
        recipient_tx_count_on_target_chain=raw.get("recipient_tx_count_on_target_chain", 0),
        recipient_tx_count_on_other_chains=raw.get("recipient_tx_count_on_other_chains", {}),
        recipient_is_contract=raw.get("recipient_is_contract", False),
        recipient_implements_receive=raw.get("recipient_implements_receive", True),
        recipient_implements_erc20_receiver=raw.get("recipient_implements_erc20_receiver", True),
        recipient_lookalike_in_history=raw.get("recipient_lookalike_in_history"),
        recipient_address_distance=raw.get("recipient_address_distance"),
        recent_dust_from_lookalike=raw.get("recent_dust_from_lookalike", False),
        recipient_paused=raw.get("recipient_paused", False),
        recipient_migrated_to=raw.get("recipient_migrated_to"),
        recipient_last_activity_age_days=raw.get("recipient_last_activity_age_days", 0),
        token_being_sent=raw.get("token_being_sent", ""),
        amount_value_usd=raw.get("amount_value_usd", 0.0),
        current_timestamp=raw.get("current_timestamp", 0),
    )


def print_result(result, llm_result):
    t = result.transfer
    print("=" * 70)
    print("wrong_chain_address — pre-send recipient validation")
    print("=" * 70)
    print(f"User: {t.user_address}")
    print(f"Recipient: {t.recipient_address}")
    print(f"Token / value: {t.token_being_sent} ${t.amount_value_usd:,.0f}")
    print(f"Intended chain: {t.intended_target_chain_name} (id {t.intended_target_chain_id}); signing chain id {t.signing_chain_id}")
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
    transfer = build_transfer()
    result = analyze_transfer(transfer, profile)

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
            "recipient": transfer.recipient_address,
            "intended_chain": transfer.intended_target_chain_name,
            "signing_chain_id": transfer.signing_chain_id,
            "recipient_is_contract": transfer.recipient_is_contract,
            "lookalike": transfer.recipient_lookalike_in_history,
        },
        rule_based_alerts=rule_alerts_dicts,
    )

    print_result(result, llm_result)


if __name__ == "__main__":
    main()
