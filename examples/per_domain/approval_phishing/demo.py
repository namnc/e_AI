"""
approval_phishing demo — runs the rule-based + LLM analyzers on a sample tx.

Run:
    python examples/per_domain/approval_phishing/demo.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Make the repo root importable regardless of where Python is invoked from.
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from core.llm_analyzer import LLMAnalyzer
from domains.approval_phishing.analyzer import (
    MAX_UINT256,
    ApprovalTx,
    analyze_transaction,
    load_profile,
)


HERE = Path(__file__).parent
PROFILE_PATH = REPO_ROOT / "domains" / "approval_phishing" / "profile.json"
SAMPLE_PATH = HERE / "sample_tx.json"


def build_tx() -> ApprovalTx:
    raw = json.loads(SAMPLE_PATH.read_text())
    return ApprovalTx(
        tx_hash=raw["tx_hash"],
        user_address=raw["user_address"],
        spender_address=raw["spender_address"],
        token_address=raw["token_address"],
        function_selector=raw["function_selector"],
        approval_amount=int(raw["approval_amount_hex"], 16),
        is_permit=raw["is_permit"],
        permit_expiry_seconds=raw["permit_expiry_seconds"],
        spender_verified=raw["spender_verified"],
        spender_creation_timestamp=raw["spender_creation_timestamp"],
        spender_in_scam_db=raw["spender_in_scam_db"],
        spender_in_protocol_registry=raw["spender_in_protocol_registry"],
        spender_bytecode_match_scam=raw["spender_bytecode_match_scam"],
        is_multicall_with_approval=raw["is_multicall_with_approval"],
        nested_calls=raw["nested_calls"],
        last_interaction_with_spender_days=raw["last_interaction_with_spender_days"],
        exposed_value_usd=raw["exposed_value_usd"],
        current_timestamp=raw["current_timestamp"],
    )


def print_result(result, llm_result):
    print("=" * 70)
    print("approval_phishing — pre-submission risk analysis")
    print("=" * 70)
    print(f"Tx: {result.tx.tx_hash}")
    print(f"Spender: {result.tx.spender_address}")
    print(f"Token: {result.tx.token_address}")
    print(f"Approval amount: {result.tx.approval_amount} "
          f"({'UNLIMITED' if result.tx.approval_amount >= MAX_UINT256 // 2 else 'bounded'})")
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
    llm.connect()  # graceful: returns False if Ollama unavailable
    llm_result = llm.analyze(
        tx={
            "spender": tx.spender_address,
            "token": tx.token_address,
            "amount": tx.approval_amount,
            "selector": tx.function_selector,
        },
        rule_based_alerts=rule_alerts_dicts,
    )

    print_result(result, llm_result)


if __name__ == "__main__":
    main()
