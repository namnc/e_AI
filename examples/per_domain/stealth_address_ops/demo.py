"""stealth_address_ops demo — rule-based + LLM analysis on a sample stealth tx."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from core.llm_analyzer import LLMAnalyzer
from domains.stealth_address_ops.analyzer import (
    SteathTx,
    analyze_transaction,
    load_profile,
)

HERE = Path(__file__).parent
PROFILE_PATH = REPO_ROOT / "domains" / "stealth_address_ops" / "profile.json"
SAMPLE_PATH = HERE / "sample_tx.json"


def build_tx() -> SteathTx:
    raw = json.loads(SAMPLE_PATH.read_text())
    raw.pop("_scenario", None)
    raw["address_cluster"] = set(raw.get("address_cluster") or [])
    return SteathTx(**raw)


def print_result(result, llm_result):
    print("=" * 70)
    print("stealth_address_ops — pre-submission deanonymization risk")
    print("=" * 70)
    print(f"Deposit:    {result.tx.deposit_address}")
    print(f"Withdrawal: {result.tx.withdrawal_address}")
    print(f"Stealth:    {result.tx.stealth_address}")
    print(f"Amount:     {result.tx.amount_eth} ETH")
    print(f"Delta t:    {result.tx.spend_timestamp - result.tx.deposit_timestamp}s")
    print()
    print(f"OVERALL RISK: {result.overall_risk.upper()}")
    print(f"DEANONYMIZED: {result.deanonymized}")
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
    tx = build_tx()
    result = analyze_transaction(tx, profile)

    rule_alerts = [
        {"heuristic_id": a.heuristic_id, "severity": a.severity,
         "signal": a.signal, "recommendation": a.recommendation}
        for a in result.alerts
    ]
    llm = LLMAnalyzer(profile, backend="ollama", model="qwen2.5:7b")
    llm.connect()
    llm_result = llm.analyze(
        tx={"deposit": tx.deposit_address, "withdrawal": tx.withdrawal_address,
            "amount_eth": tx.amount_eth, "delta_t_s": tx.spend_timestamp - tx.deposit_timestamp,
            "gas_funding": tx.gas_funding_source},
        rule_based_alerts=rule_alerts,
    )

    print_result(result, llm_result)


if __name__ == "__main__":
    main()
