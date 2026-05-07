"""
mixing_behavioral demo — rule-based + LLM analysis on a sample mixer withdrawal.

Run:
    python examples/per_domain/mixing_behavioral/demo.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from core.llm_analyzer import LLMAnalyzer
from domains.mixing_behavioral.analyzer import (
    MixerWithdrawal,
    analyze_withdrawal,
    load_profile,
)


HERE = Path(__file__).parent
PROFILE_PATH = REPO_ROOT / "domains" / "mixing_behavioral" / "profile.json"
SAMPLE_PATH = HERE / "sample_tx.json"


def build_tx() -> MixerWithdrawal:
    raw = json.loads(SAMPLE_PATH.read_text())
    raw.pop("_scenario", None)
    return MixerWithdrawal(**{k: v for k, v in raw.items() if not k.startswith("_")})


def print_result(result, llm_result):
    print("=" * 70)
    print("mixing_behavioral — pre-withdrawal post-mixer linkability audit")
    print("=" * 70)
    print(f"Tx: {result.tx.tx_hash}")
    print(f"Pool: {result.tx.pool_id} ({result.tx.pool_denomination})")
    print(f"Withdrawal addr: {result.tx.withdrawal_address}")
    print(f"Dwell: {(result.tx.withdrawal_timestamp - result.tx.deposit_timestamp)/3600:.2f}h")
    print(f"Pool concurrent deposits: {result.tx.pool_concurrent_deposits_in_window}")
    print()
    print(f"OVERALL RISK: {result.overall_risk.upper()}")
    print(f"SHOULD BLOCK: {result.should_block}")
    print(f"ALERTS: {len(result.alerts)}")
    print()
    for a in result.alerts:
        print(f"  [{a.severity.upper():8s}] {a.heuristic_id} {a.heuristic_name}")
        print(f"    signal: {a.signal[:100]}")
        print(f"    recommend: {a.recommendation}")
        print()
    print("-" * 70)
    print("LLM behavioral analysis")
    print("-" * 70)
    if llm_result.get("degraded_mode"):
        print(f"[degraded] {llm_result.get('degraded_reason')}")
        print(f"Synthesized: {llm_result.get('explanation')}")
    else:
        print(f"Risk: {llm_result.get('risk_level')}")
        print(f"Explanation: {llm_result.get('explanation')}")
        if llm_result.get("recommendations"):
            print("Recommendations:")
            for r in llm_result["recommendations"]:
                print(f"  - {r}")


def main():
    profile = load_profile(PROFILE_PATH)
    tx = build_tx()
    result = analyze_withdrawal(tx, profile)

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
            "pool": tx.pool_id,
            "denomination": tx.pool_denomination,
            "dwell_hours": (tx.withdrawal_timestamp - tx.deposit_timestamp) / 3600,
            "is_variable_denom": tx.is_variable_denom_pool,
            "withdrawal_address_reuse": tx.withdrawal_address_prior_mixer_uses,
            "post_withdrawal_action": tx.expected_post_withdrawal_action,
        },
        rule_based_alerts=rule_alerts_dicts,
    )

    print_result(result, llm_result)


if __name__ == "__main__":
    main()
