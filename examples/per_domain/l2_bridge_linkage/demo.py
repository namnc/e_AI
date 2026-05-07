"""l2_bridge_linkage demo — rule-based + LLM analysis on a sample bridge sequence."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from core.llm_analyzer import LLMAnalyzer
from domains.l2_bridge_linkage.analyzer import (
    BridgeSequence,
    BridgeTx,
    analyze_sequence,
    load_profile,
)

HERE = Path(__file__).parent
PROFILE_PATH = REPO_ROOT / "domains" / "l2_bridge_linkage" / "profile.json"
SAMPLE_PATH = HERE / "sample_tx.json"


def build_sequence() -> BridgeSequence:
    raw = json.loads(SAMPLE_PATH.read_text())
    raw.pop("_scenario", None)
    txs = [BridgeTx(**t) for t in raw.pop("txs", [])]
    return BridgeSequence(txs=txs, **raw)


def print_result(result, llm_result):
    print("=" * 70)
    print("l2_bridge_linkage — bridge-sequence linkage risk")
    print("=" * 70)
    seq = result.sequence
    print(f"User: {seq.user_address}")
    print(f"Bridges: {len(seq.txs)} txs")
    for t in seq.txs:
        print(f"  {t.bridge_protocol}: {t.source_chain} -> {t.dest_chain} "
              f"${t.amount_usd:,.0f} (NFT={t.bundles_nft})")
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
    seq = build_sequence()
    result = analyze_sequence(seq, profile)

    rule_alerts = [
        {"heuristic_id": a.heuristic_id, "severity": a.severity,
         "signal": a.signal, "recommendation": a.recommendation}
        for a in result.alerts
    ]
    llm = LLMAnalyzer(profile, backend="ollama", model="qwen2.5:7b")
    llm.connect()
    llm_result = llm.analyze(
        tx={"user": seq.user_address, "n_bridges": len(seq.txs),
            "bridges": [{"protocol": t.bridge_protocol, "src": t.source_chain,
                         "dst": t.dest_chain, "amount_usd": t.amount_usd,
                         "bundles_nft": t.bundles_nft}
                        for t in seq.txs]},
        rule_based_alerts=rule_alerts,
    )

    print_result(result, llm_result)


if __name__ == "__main__":
    main()
