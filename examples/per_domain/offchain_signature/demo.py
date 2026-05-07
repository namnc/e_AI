"""offchain_signature demo — rule-based + LLM analysis on a sample sign request."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from core.llm_analyzer import LLMAnalyzer
from domains.offchain_signature.analyzer import (
    SignatureRequest,
    analyze_signature,
    load_profile,
)

HERE = Path(__file__).parent
PROFILE_PATH = REPO_ROOT / "domains" / "offchain_signature" / "profile.json"
SAMPLE_PATH = HERE / "sample_tx.json"


def build_req() -> SignatureRequest:
    raw = json.loads(SAMPLE_PATH.read_text())
    raw.pop("_scenario", None)
    return SignatureRequest(**raw)


def print_result(result, llm_result):
    print("=" * 70)
    print("offchain_signature — pre-signing risk analysis")
    print("=" * 70)
    print(f"Request: {result.request.request_id}")
    print(f"dApp:   {result.request.dapp_origin}")
    print(f"Type:   {result.request.signature_type} (primary={result.request.primary_type})")
    print(f"UI says: {result.request.ui_description!r}  payload={result.request.payload_semantic!r}")
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
    req = build_req()
    result = analyze_signature(req, profile)

    rule_alerts = [
        {"heuristic_id": a.heuristic_id, "severity": a.severity,
         "signal": a.signal, "recommendation": a.recommendation}
        for a in result.alerts
    ]
    llm = LLMAnalyzer(profile, backend="ollama", model="qwen2.5:7b")
    llm.connect()
    llm_result = llm.analyze(
        tx={"signature_type": req.signature_type, "dapp": req.dapp_origin,
            "ui_description": req.ui_description, "payload_semantic": req.payload_semantic,
            "spender": req.spender_address, "spender_known": req.spender_in_protocol_registry,
            "is_homoglyph": req.is_homoglyph_of_known, "domain_age_days": req.domain_age_days},
        rule_based_alerts=rule_alerts,
    )

    print_result(result, llm_result)


if __name__ == "__main__":
    main()
