"""cross_protocol_risk demo — rule-based + LLM analysis on a sample portfolio."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from core.llm_analyzer import LLMAnalyzer
from domains.cross_protocol_risk.analyzer import (
    ApprovalChain,
    FlashLoanExposure,
    LendingPosition,
    PortfolioSnapshot,
    TokenHolding,
    analyze_portfolio,
    load_profile,
)

HERE = Path(__file__).parent
PROFILE_PATH = REPO_ROOT / "domains" / "cross_protocol_risk" / "profile.json"
SAMPLE_PATH = HERE / "sample_tx.json"


def build_portfolio() -> PortfolioSnapshot:
    raw = json.loads(SAMPLE_PATH.read_text())
    raw.pop("_scenario", None)
    lending = [LendingPosition(**lp) for lp in raw.pop("lending_positions", [])]
    holdings = [TokenHolding(**th) for th in raw.pop("token_holdings", [])]
    chains = [ApprovalChain(**ac) for ac in raw.pop("approval_chains", [])]
    flash = [FlashLoanExposure(**fl) for fl in raw.pop("flash_loan_exposures", [])]
    return PortfolioSnapshot(
        lending_positions=lending,
        token_holdings=holdings,
        approval_chains=chains,
        flash_loan_exposures=flash,
        **raw,
    )


def print_result(result, llm_result):
    print("=" * 70)
    print("cross_protocol_risk — portfolio cross-protocol exposure")
    print("=" * 70)
    p = result.portfolio
    print(f"User: {p.user_address}")
    print(f"Portfolio: ${p.total_portfolio_usd:,.0f}")
    print(f"Lending positions: {len(p.lending_positions)} | "
          f"Holdings: {len(p.token_holdings)} | "
          f"Approval chains: {len(p.approval_chains)} | "
          f"Flash exposures: {len(p.flash_loan_exposures)}")
    print()
    print(f"OVERALL RISK: {result.overall_risk.upper()}")
    print(f"EST. MAX LOSS: ${result.estimated_max_loss_usd:,.0f}")
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
    p = build_portfolio()
    result = analyze_portfolio(p, profile)

    rule_alerts = [
        {"heuristic_id": a.heuristic_id, "severity": a.severity,
         "signal": a.signal, "recommendation": a.recommendation}
        for a in result.alerts
    ]
    llm = LLMAnalyzer(profile, backend="ollama", model="qwen2.5:7b")
    llm.connect()
    llm_result = llm.analyze(
        tx={"user": p.user_address, "portfolio_usd": p.total_portfolio_usd,
            "lending_positions": [{"protocol": lp.protocol,
                                   "collateral": lp.collateral_asset,
                                   "hf": lp.health_factor,
                                   "oracle": lp.oracle_used}
                                  for lp in p.lending_positions],
            "approval_chain_depth": [ac.chain_depth for ac in p.approval_chains],
            "flash_loan_exposures": len(p.flash_loan_exposures)},
        rule_based_alerts=rule_alerts,
    )

    print_result(result, llm_result)


if __name__ == "__main__":
    main()
