"""pq_readiness demo — rule-based + LLM analysis on a sample wallet snapshot."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from core.llm_analyzer import LLMAnalyzer
from domains.pq_readiness.analyzer import (
    AccountSnapshot,
    analyze_account,
    load_profile,
)

HERE = Path(__file__).parent
PROFILE_PATH = REPO_ROOT / "domains" / "pq_readiness" / "profile.json"
SAMPLE_PATH = HERE / "sample_tx.json"


def build_acc() -> AccountSnapshot:
    raw = json.loads(SAMPLE_PATH.read_text())
    raw.pop("_scenario", None)
    return AccountSnapshot(**raw)


def print_result(result, llm_result):
    print("=" * 70)
    print("pq_readiness — post-quantum exposure assessment")
    print("=" * 70)
    print(f"Account: {result.account.address}")
    print(f"Smart account: {result.account.is_smart_account} "
          f"(validation={result.account.smart_account_validation})")
    print(f"Stealth meta-address: {result.account.has_stealth_meta_address} "
          f"(ML-KEM={result.account.meta_address_has_mlkem})")
    print(f"BLS deposits: {result.account.bls_deposit_count}")
    print(f"Lifetime: tx_count={result.account.tx_count}, value_usd=${result.account.total_value_usd:,.0f}")
    print()
    print(f"OVERALL RISK: {result.overall_risk.upper()}")
    print(f"PQ READINESS SCORE: {result.pq_readiness_score:.2f}  (1.0 = fully PQ-ready)")
    print(f"ALERTS: {len(result.alerts)}")
    print()
    for a in result.alerts:
        print(f"  [{a.severity.upper():8s}] {a.heuristic_id} {a.heuristic_name} "
              f"(confidence {a.confidence:.2f})")
        print(f"    signal: {a.signal}")
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
    acc = build_acc()
    result = analyze_account(acc, profile)

    rule_alerts = [
        {"heuristic_id": a.heuristic_id, "severity": a.severity,
         "signal": a.signal, "recommendation": a.recommendation}
        for a in result.alerts
    ]
    llm = LLMAnalyzer(profile, backend="ollama", model="qwen2.5:7b")
    llm.connect()
    llm_result = llm.analyze(
        tx={"address": acc.address, "is_smart_account": acc.is_smart_account,
            "smart_account_validation": acc.smart_account_validation,
            "stealth_meta_address": acc.has_stealth_meta_address,
            "mlkem": acc.meta_address_has_mlkem,
            "bls_deposits": acc.bls_deposit_count,
            "tx_count": acc.tx_count, "value_usd": acc.total_value_usd},
        rule_based_alerts=rule_alerts,
    )

    print_result(result, llm_result)


if __name__ == "__main__":
    main()
