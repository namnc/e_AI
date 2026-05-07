"""rpc_leakage demo — rule-based + LLM analysis on a sample RPC session."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from core.llm_analyzer import LLMAnalyzer
from domains.rpc_leakage.analyzer import (
    RPCQuery,
    RPCSession,
    analyze_session,
    load_profile,
)

HERE = Path(__file__).parent
PROFILE_PATH = REPO_ROOT / "domains" / "rpc_leakage" / "profile.json"
SAMPLE_PATH = HERE / "sample_tx.json"


def build_session() -> RPCSession:
    raw = json.loads(SAMPLE_PATH.read_text())
    raw.pop("_scenario", None)
    queries = [RPCQuery(**q) for q in raw.pop("queries", [])]
    return RPCSession(queries=queries, **raw)


def print_result(result, llm_result):
    print("=" * 70)
    print("rpc_leakage — RPC-provider deanonymization risk")
    print("=" * 70)
    s = result.session
    print(f"User:     {s.user_address}")
    print(f"Provider: {s.rpc_provider}")
    print(f"Local node: {s.uses_local_node} | Helios: {s.uses_helios_or_light_client} | "
          f"Tor: {s.uses_tor} | Cover: {s.uses_cover_queries}")
    print(f"Queries:  {len(s.queries)}  (swap at {s.swap_or_action_timestamp})")
    print()
    print(f"OVERALL RISK: {result.overall_risk.upper()}")
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
    s = build_session()
    result = analyze_session(s, profile)

    rule_alerts = [
        {"heuristic_id": a.heuristic_id, "severity": a.severity,
         "signal": a.signal, "recommendation": a.recommendation}
        for a in result.alerts
    ]
    llm = LLMAnalyzer(profile, backend="ollama", model="qwen2.5:7b")
    llm.connect()
    llm_result = llm.analyze(
        tx={"provider": s.rpc_provider, "n_queries": len(s.queries),
            "uses_local_node": s.uses_local_node,
            "uses_helios": s.uses_helios_or_light_client,
            "swap_ts": s.swap_or_action_timestamp},
        rule_based_alerts=rule_alerts,
    )

    print_result(result, llm_result)


if __name__ == "__main__":
    main()
