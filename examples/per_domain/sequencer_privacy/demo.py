"""
sequencer_privacy demo — runs the rule-based + LLM analyzers on an L2 submission scenario.

Run:
    python examples/per_domain/sequencer_privacy/demo.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from core.llm_analyzer import LLMAnalyzer
from domains.sequencer_privacy.analyzer import (
    SequencerSubmission,
    analyze_submission,
    load_profile,
)


HERE = Path(__file__).parent
PROFILE_PATH = REPO_ROOT / "domains" / "sequencer_privacy" / "profile.json"
SAMPLE_PATH = HERE / "sample_tx.json"


def build_submission() -> SequencerSubmission:
    raw = json.loads(SAMPLE_PATH.read_text())
    tx = raw.get("submitted_tx") or {}
    cens = raw.get("censorship_observed") or {}
    return SequencerSubmission(
        user_address=raw["user_address"],
        l2_chain=raw["l2_chain"],
        submitted_tx_id=tx.get("tx_id", ""),
        tx_value_usd=tx.get("value_usd", 0.0),
        tx_kind=tx.get("tx_kind", "transfer"),
        is_high_value=tx.get("is_high_value", False),
        is_privacy_relevant=tx.get("is_privacy_relevant", False),
        sequencer_model_override=raw.get("sequencer_model"),
        sequencer_operator_override=raw.get("sequencer_operator"),
        tx_submitted_at=cens.get("tx_submitted_at", 0),
        expected_inclusion_by=cens.get("expected_inclusion_by", 0),
        actually_included=cens.get("actually_included", True),
        valid_gas_and_nonce=cens.get("valid_gas_and_nonce", True),
        user_flagged_as_sanctioned=cens.get("user_flagged_as_sanctioned", False),
        consecutive_exclusions=cens.get("consecutive_exclusions", 0),
        sequencer_mev_extracted_usd_30d=raw.get("sequencer_mev_extracted_usd_30d", 0.0),
        sequencer_share_of_l2_mev_pct=raw.get("sequencer_share_of_l2_mev_pct", 0.0),
        shared_sequencer_other_rollups=raw.get("shared_sequencer_other_rollups", []),
        preconfirmation_published_before_batch=raw.get("preconfirmation_published_before_batch", False),
        preconfirmation_window_seconds=raw.get("preconfirmation_window_seconds", 0),
        preconfirmation_publicly_readable=raw.get("preconfirmation_publicly_readable", True),
    )


def print_result(result, llm_result):
    s = result.submission
    print("=" * 70)
    print("sequencer_privacy — L2 sequencer trust analysis")
    print("=" * 70)
    print(f"L2: {s.l2_chain} (override model={s.sequencer_model_override or 'registry'})")
    print(f"Tx: {s.submitted_tx_id} kind={s.tx_kind} value=${s.tx_value_usd:,.0f} "
          f"privacy_relevant={s.is_privacy_relevant}")
    if s.consecutive_exclusions:
        print(f"Exclusions: {s.consecutive_exclusions} consecutive")
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


def main():
    profile = load_profile(PROFILE_PATH)
    submission = build_submission()
    result = analyze_submission(submission, profile)

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
            "l2": submission.l2_chain,
            "kind": submission.tx_kind,
            "value_usd": submission.tx_value_usd,
            "privacy_relevant": submission.is_privacy_relevant,
            "included": submission.actually_included,
            "shared_sequencer_with": submission.shared_sequencer_other_rollups,
        },
        rule_based_alerts=rule_alerts_dicts,
    )

    print_result(result, llm_result)


if __name__ == "__main__":
    main()
