"""l2_anonymity_set demo — rule-based + LLM analysis on a sample L2 action."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from core.llm_analyzer import LLMAnalyzer
from domains.l2_anonymity_set.analyzer import (
    L2Action,
    analyze_action,
    load_profile,
)

HERE = Path(__file__).parent
PROFILE_PATH = REPO_ROOT / "domains" / "l2_anonymity_set" / "profile.json"
SAMPLE_PATH = HERE / "sample_tx.json"


def build_action() -> L2Action:
    raw = json.loads(SAMPLE_PATH.read_text())
    raw.pop("_scenario", None)
    return L2Action(**raw)


def print_result(result, llm_result):
    print("=" * 70)
    print("l2_anonymity_set — L2 anonymity-set risk")
    print("=" * 70)
    a = result.action
    print(f"L2: {a.l2_chain}")
    print(f"Tx: {a.tx_id}")
    print(f"Privacy tx: {a.is_privacy_tx} | Pool size: {a.privacy_pool_size}")
    print(f"Forced inclusion: {a.used_forced_inclusion} | Batch: {a.batch_index}")
    print()
    print(f"OVERALL RISK: {result.overall_risk.upper()}")
    print(f"ALERTS: {len(result.alerts)}")
    print()
    for alert in result.alerts:
        print(f"  [{alert.severity.upper():8s}] {alert.heuristic_id} {alert.heuristic_name} "
              f"(confidence {alert.confidence:.2f})")
        print(f"    signal: {alert.signal}")
        print(f"    recommend: {alert.recommendation}")
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
    a = build_action()
    result = analyze_action(a, profile)

    rule_alerts = [
        {"heuristic_id": al.heuristic_id, "severity": al.severity,
         "signal": al.signal, "recommendation": al.recommendation}
        for al in result.alerts
    ]
    llm = LLMAnalyzer(profile, backend="ollama", model="qwen2.5:7b")
    llm.connect()
    llm_result = llm.analyze(
        tx={"l2_chain": a.l2_chain, "is_privacy_tx": a.is_privacy_tx,
            "pool_size": a.privacy_pool_size,
            "forced_inclusion": a.used_forced_inclusion,
            "batch_index": a.batch_index},
        rule_based_alerts=rule_alerts,
    )

    print_result(result, llm_result)


if __name__ == "__main__":
    main()
