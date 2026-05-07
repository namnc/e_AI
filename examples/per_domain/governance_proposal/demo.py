"""governance_proposal demo — rule-based + LLM analysis on a sample DAO proposal."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from core.llm_analyzer import LLMAnalyzer
from domains.governance_proposal.analyzer import (
    GovernanceProposal,
    ParameterChange,
    ProxyUpgrade,
    TreasuryTransfer,
    analyze_proposal,
    load_profile,
)

HERE = Path(__file__).parent
PROFILE_PATH = REPO_ROOT / "domains" / "governance_proposal" / "profile.json"
SAMPLE_PATH = HERE / "sample_tx.json"


def build_proposal() -> GovernanceProposal:
    raw = json.loads(SAMPLE_PATH.read_text())
    raw.pop("_scenario", None)
    transfers = [TreasuryTransfer(**t) for t in raw.pop("transfers", [])]
    params = [ParameterChange(**p) for p in raw.pop("parameter_changes", [])]
    upgrades = [ProxyUpgrade(**u) for u in raw.pop("proxy_upgrades", [])]
    return GovernanceProposal(
        transfers=transfers,
        parameter_changes=params,
        proxy_upgrades=upgrades,
        **raw,
    )


def print_result(result, llm_result):
    print("=" * 70)
    print("governance_proposal — pre-vote risk analysis")
    print("=" * 70)
    p = result.proposal
    print(f"Proposal: {p.proposal_id} ({p.dao_name})")
    print(f"Proposer: {p.proposer_address}")
    print(f"Treasury: ${p.treasury_balance_usd:,.0f}")
    print(f"Transfers: {len(p.transfers)} | "
          f"Param changes: {len(p.parameter_changes)} | "
          f"Proxy upgrades: {len(p.proxy_upgrades)}")
    print(f"Timelock: {p.current_timelock_hours}h → {p.proposed_timelock_hours}h "
          f"(min {p.minimum_timelock_hours}h)")
    print(f"Top voter share: {p.top_voter_share:.0%}")
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
    p = build_proposal()
    result = analyze_proposal(p, profile)

    rule_alerts = [
        {"heuristic_id": a.heuristic_id, "severity": a.severity,
         "signal": a.signal, "recommendation": a.recommendation}
        for a in result.alerts
    ]
    llm = LLMAnalyzer(profile, backend="ollama", model="qwen2.5:7b")
    llm.connect()
    llm_result = llm.analyze(
        tx={"dao": p.dao_name, "proposer": p.proposer_address,
            "treasury_usd": p.treasury_balance_usd,
            "total_transfer_usd": sum(t.value_usd for t in p.transfers),
            "n_proxy_upgrades": len(p.proxy_upgrades),
            "timelock_change_h": (p.current_timelock_hours, p.proposed_timelock_hours),
            "top_voter_share": p.top_voter_share},
        rule_based_alerts=rule_alerts,
    )

    print_result(result, llm_result)


if __name__ == "__main__":
    main()
