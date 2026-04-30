"""
L2 Anonymity Set Analyzer — privacy heuristics for L2 transaction visibility.

Loads l2_anonymity_set/profile.json and evaluates a transaction (or a set
of L2 interactions) against 5 heuristics covering thin pool, sequencer
visibility, forced inclusion deanon, L2 timing correlation, and rollup
batch linkage.

Privacy property: L2s have smaller anonymity sets than L1, single-operator
sequencers see all txs in plaintext, and rollup batches reveal sequence
metadata even when individual txs are private.

Production version would:
- Query L2 privacy pool sizes via on-chain getLogs
- Inspect sequencer endpoint behavior (is it MEV-protected?)
- Track batch posting timing on L1 to detect cross-batch correlation

Usage:
    python analyzer.py                     # examples
    python analyzer.py --benchmark         # benchmark
"""

from __future__ import annotations

import json
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIN_POOL_SIZE_SAFE = 1000        # H1: <1000 = thin
POOL_SIZE_DANGEROUS = 100        # H1: <100 = critically thin
SHORT_BATCH_DELAY_SECS = 60      # H4: txs within same batch close in time
SAME_BATCH_THRESHOLD_SECS = 12   # H5: <12s = likely same L2 block / same batch

# Sequencer trust labels per L2
L2_SEQUENCER_TRUST = {
    "arbitrum": {"single_operator": True, "decentralization_status": "BoLD live, sequencer still single", "encrypted_mempool": False},
    "optimism": {"single_operator": True, "decentralization_status": "single OP Labs sequencer", "encrypted_mempool": False},
    "base": {"single_operator": True, "decentralization_status": "single Coinbase sequencer", "encrypted_mempool": False},
    "polygon_zkevm": {"single_operator": True, "decentralization_status": "single Polygon sequencer", "encrypted_mempool": False},
    "zksync_era": {"single_operator": True, "decentralization_status": "single Matter Labs sequencer", "encrypted_mempool": False},
    "scroll": {"single_operator": True, "decentralization_status": "single Scroll sequencer", "encrypted_mempool": False},
    "linea": {"single_operator": True, "decentralization_status": "single Consensys sequencer", "encrypted_mempool": False},
    "starknet": {"single_operator": True, "decentralization_status": "single StarkWare sequencer", "encrypted_mempool": False},
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class L2Action:
    tx_id: str
    user_address: str
    l2_chain: str                  # "arbitrum" | "optimism" | etc.
    sequencer_address: str = ""
    submitted_at: int = 0          # L2 timestamp
    posted_to_l1_at: int = 0       # L1 timestamp when included in rollup batch
    batch_index: int = 0           # rollup batch number
    block_number_l2: int = 0
    block_number_l1: int = 0       # L1 block where batch was posted

    is_privacy_tx: bool = False    # interacting with privacy pool
    privacy_pool_address: str = ""
    privacy_pool_size: int = 0     # current set size of the pool used
    used_forced_inclusion: bool = False
    forced_inclusion_l1_tx: str = ""

    # Companion txs (for sequence/batch correlation)
    companion_txs: list[str] = field(default_factory=list)


@dataclass
class RiskAlert:
    heuristic_id: str
    heuristic_name: str
    severity: str
    confidence: float
    signal: str
    recommendation: str
    skill: Optional[str] = None
    action: Optional[str] = None


@dataclass
class AnalysisResult:
    action: L2Action
    alerts: list[RiskAlert] = field(default_factory=list)
    overall_risk: str = "low"


# ---------------------------------------------------------------------------
# Profile loader
# ---------------------------------------------------------------------------

def load_profile(path: str | Path) -> dict:
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Heuristic checks
# ---------------------------------------------------------------------------

def check_h1_thin_pool(a: L2Action, profile: dict) -> list[RiskAlert]:
    """H1: Privacy pool too thin — anonymity set insufficient."""
    alerts: list[RiskAlert] = []
    h = profile["heuristics"]["H1_thin_pool"]

    if not a.is_privacy_tx:
        return alerts

    if a.privacy_pool_size < POOL_SIZE_DANGEROUS:
        alerts.append(RiskAlert(
            heuristic_id="H1",
            heuristic_name=h["name"],
            severity="critical",
            confidence=0.95,
            signal=(
                f"Privacy pool {a.privacy_pool_address} on {a.l2_chain} has only "
                f"{a.privacy_pool_size} members — effective k-anonymity << safe threshold"
            ),
            recommendation=(
                "Wait for pool size to grow or use an L1 privacy pool with larger anonymity set "
                "(Privacy Pools, Railgun)."
            ),
            skill="pool_size_monitor",
            action="block",
        ))
    elif a.privacy_pool_size < MIN_POOL_SIZE_SAFE:
        alerts.append(RiskAlert(
            heuristic_id="H1",
            heuristic_name=h["name"],
            severity=h["severity"],
            confidence=0.85,
            signal=(
                f"Privacy pool size {a.privacy_pool_size} on {a.l2_chain} below "
                f"recommended {MIN_POOL_SIZE_SAFE}-member threshold"
            ),
            recommendation=(
                "Use a pool with more members; check pool size before deposit."
            ),
            skill="pool_size_monitor",
            action="warn",
        ))
    return alerts


def check_h2_sequencer_visibility(a: L2Action, profile: dict) -> list[RiskAlert]:
    """H2: Single-operator sequencer can see and reorder all txs in plaintext."""
    alerts: list[RiskAlert] = []
    h = profile["heuristics"]["H2_sequencer_visibility"]

    seq_info = L2_SEQUENCER_TRUST.get(a.l2_chain, {"single_operator": True, "decentralization_status": "unknown", "encrypted_mempool": False})

    if seq_info["single_operator"] and not seq_info["encrypted_mempool"] and a.is_privacy_tx:
        alerts.append(RiskAlert(
            heuristic_id="H2",
            heuristic_name=h["name"],
            severity="critical",
            confidence=0.90,
            signal=(
                f"L2 {a.l2_chain} has single operator sequencer ({seq_info['decentralization_status']}) "
                f"with no encrypted mempool — privacy pool deposit visible in plaintext to sequencer"
            ),
            recommendation=(
                "Use L1 privacy pool (sequencer-trust-free), or wait for the L2 to ship encrypted "
                "mempool / decentralized sequencing. Even k-anonymity in pool doesn't help if "
                "sequencer logs deposits."
            ),
            skill="sequencer_analyzer",
            action="warn",
        ))
    return alerts


def check_h3_forced_inclusion(a: L2Action, profile: dict) -> list[RiskAlert]:
    """H3: User used L1 forced-inclusion path — distinctive behavior, narrows anonymity."""
    alerts: list[RiskAlert] = []
    h = profile["heuristics"]["H3_forced_inclusion_deanon"]

    if a.used_forced_inclusion:
        alerts.append(RiskAlert(
            heuristic_id="H3",
            heuristic_name=h["name"],
            severity=h["severity"],
            confidence=0.85,
            signal=(
                f"Tx posted via L1 forced-inclusion path ({a.forced_inclusion_l1_tx}) — "
                f"distinctive behavior, shrinks anonymity to forced-inclusion users only "
                f"(very small set on most L2s)"
            ),
            recommendation=(
                "Only use forced inclusion for censorship resistance, not for privacy. "
                "If sequencer didn't censor, the regular path has a larger anonymity set."
            ),
            skill="sequencer_analyzer",
            action="warn",
        ))
    return alerts


def check_h4_l2_timing(a: L2Action, profile: dict) -> list[RiskAlert]:
    """H4: Multiple companion txs in close temporal proximity — sequencer correlation."""
    alerts: list[RiskAlert] = []
    h = profile["heuristics"]["H4_l2_timing_correlation"]

    if a.is_privacy_tx and a.companion_txs:
        # If companion txs exist within seconds, sequencer can correlate
        alerts.append(RiskAlert(
            heuristic_id="H4",
            heuristic_name=h["name"],
            severity=h["severity"],
            confidence=0.80,
            signal=(
                f"Privacy tx submitted alongside {len(a.companion_txs)} companion tx(s) — "
                f"sequencer can correlate via timing within batch"
            ),
            recommendation=(
                "Add random delay (minutes-hours) between privacy interaction and any other "
                "tx from any related address. Avoid bursts."
            ),
            skill="timing_advisor",
            action="warn",
        ))
    return alerts


def check_h5_rollup_batch(a: L2Action, profile: dict) -> list[RiskAlert]:
    """H5: Same rollup batch as related txs — batch posting timing links them."""
    alerts: list[RiskAlert] = []
    h = profile["heuristics"]["H5_rollup_batch_linkage"]

    # If we have batch_index AND companion txs in the same batch index, that's a strong link.
    # Synthetic models: if companion_txs exist and the action is privacy-bearing, treat as same batch.
    if a.is_privacy_tx and a.companion_txs and a.batch_index > 0:
        alerts.append(RiskAlert(
            heuristic_id="H5",
            heuristic_name=h["name"],
            severity=h["severity"],
            confidence=0.75,
            signal=(
                f"Privacy tx in rollup batch #{a.batch_index} alongside companion(s); batch posting "
                f"timestamp on L1 ({a.posted_to_l1_at}) creates a permanent correlation pin"
            ),
            recommendation=(
                "Wait for batch to close, then submit privacy tx in a NEW batch. Avoid co-batching "
                "with related activity."
            ),
            skill="batch_inspector",
            action="warn",
        ))
    return alerts


# ---------------------------------------------------------------------------
# Main analyzer
# ---------------------------------------------------------------------------

def analyze_action(a: L2Action, profile: dict) -> AnalysisResult:
    result = AnalysisResult(action=a)
    checks = [
        check_h1_thin_pool(a, profile),
        check_h2_sequencer_visibility(a, profile),
        check_h3_forced_inclusion(a, profile),
        check_h4_l2_timing(a, profile),
        check_h5_rollup_batch(a, profile),
    ]
    for alerts in checks:
        result.alerts.extend(alerts)

    if any(al.action == "block" and al.confidence >= 0.85 for al in result.alerts):
        result.overall_risk = "critical"
    elif any(al.severity == "critical" for al in result.alerts):
        result.overall_risk = "high"
    elif any(al.severity == "high" for al in result.alerts):
        result.overall_risk = "medium"
    elif result.alerts:
        result.overall_risk = "low"
    return result


def format_result(r: AnalysisResult) -> str:
    a = r.action
    lines = [
        f"--- L2 Anonymity Risk: {r.overall_risk.upper()} ---",
        f"User: {a.user_address}",
        f"L2: {a.l2_chain}, privacy tx: {a.is_privacy_tx}, pool size: {a.privacy_pool_size}",
        f"Forced inclusion: {a.used_forced_inclusion}, batch: {a.batch_index}",
        f"Companions: {len(a.companion_txs)}",
        f"Alerts: {len(r.alerts)}",
    ]
    for al in r.alerts:
        lines.append(f"\n  [{al.heuristic_id}] {al.heuristic_name} ({al.severity}, conf {al.confidence:.0%}, action: {al.action})")
        lines.append(f"    Signal: {al.signal}")
        lines.append(f"    Action: {al.recommendation}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Benchmark
# ---------------------------------------------------------------------------

def generate_synthetic_dataset(n: int = 100, seed: int = 42) -> list[L2Action]:
    rng = random.Random(seed)
    actions: list[L2Action] = []
    chains = list(L2_SEQUENCER_TRUST.keys())
    for i in range(n):
        is_privacy = rng.random() < 0.40
        leak = is_privacy and rng.random() < 0.60
        chain = rng.choice(chains)
        pool_size = rng.choice([20, 80, 200, 500, 2000, 10000]) if leak else rng.choice([2000, 10000, 50000])
        actions.append(L2Action(
            tx_id=f"tx{i:04d}",
            user_address=f"0xuser{i:038x}",
            l2_chain=chain,
            sequencer_address="0xseq",
            submitted_at=1730000000 + i * 60,
            posted_to_l1_at=1730000000 + i * 60 + rng.randint(60, 600),
            batch_index=i // 50,
            block_number_l2=12000000 + i,
            block_number_l1=20000000 + i // 50,
            is_privacy_tx=is_privacy,
            privacy_pool_address=f"0xpool{i % 10:01x}",
            privacy_pool_size=pool_size,
            used_forced_inclusion=leak and rng.random() < 0.10,
            forced_inclusion_l1_tx=f"0xforce{i:034x}" if rng.random() < 0.10 else "",
            companion_txs=[f"0xcomp{j:04d}" for j in range(rng.randint(0, 4) if leak else 0)],
        ))
    return actions


def run_benchmark(profile: dict, n: int = 1000) -> dict:
    actions = generate_synthetic_dataset(n)

    def is_at_risk(a: L2Action) -> bool:
        if a.is_privacy_tx and a.privacy_pool_size < MIN_POOL_SIZE_SAFE:
            return True
        if a.is_privacy_tx and L2_SEQUENCER_TRUST.get(a.l2_chain, {}).get("single_operator", True):
            return True
        if a.used_forced_inclusion:
            return True
        if a.is_privacy_tx and a.companion_txs:
            return True
        return False

    results = [(a, analyze_action(a, profile)) for a in actions]
    tp = fp = tn = fn = 0
    for a, r in results:
        risk = is_at_risk(a)
        flagged = r.overall_risk in ("critical", "high")
        if flagged and risk:
            tp += 1
        elif flagged and not risk:
            fp += 1
        elif not flagged and risk:
            fn += 1
        else:
            tn += 1
    total_r = tp + fn
    total_safe = tn + fp
    return {
        "n_actions": n,
        "at_risk_in_dataset": total_r,
        "true_positive": tp,
        "false_positive": fp,
        "true_negative": tn,
        "false_negative": fn,
        "true_positive_rate": f"{tp / total_r:.1%}" if total_r else "n/a",
        "false_positive_rate": f"{fp / total_safe:.1%}" if total_safe else "n/a",
    }


def run_examples(profile: dict):
    examples = [
        ("Safe: large pool, no companions, no forced inclusion", L2Action(
            tx_id="ok01", user_address="0xuser",
            l2_chain="arbitrum", is_privacy_tx=True,
            privacy_pool_size=10000, batch_index=0,
        )),
        ("CRITICAL: thin pool (50 members) + single-op sequencer", L2Action(
            tx_id="thin01", user_address="0xuser",
            l2_chain="optimism", is_privacy_tx=True,
            privacy_pool_size=50, batch_index=1,
        )),
        ("Forced inclusion (small subset deanon)", L2Action(
            tx_id="forced01", user_address="0xuser",
            l2_chain="arbitrum", is_privacy_tx=True,
            privacy_pool_size=2000,
            used_forced_inclusion=True,
            forced_inclusion_l1_tx="0xforced_l1_tx",
        )),
        ("Privacy + 3 companion txs in same batch", L2Action(
            tx_id="batch01", user_address="0xuser",
            l2_chain="base", is_privacy_tx=True,
            privacy_pool_size=2000, batch_index=42,
            companion_txs=["0xc1", "0xc2", "0xc3"],
        )),
    ]
    for name, a in examples:
        print(f"\n{'='*60}")
        print(f"Scenario: {name}")
        print(f"{'='*60}")
        print(format_result(analyze_action(a, profile)))


def main():
    profile_path = Path(__file__).parent / "profile.json"
    profile = load_profile(profile_path)
    if "--benchmark" in sys.argv:
        print("Running L2 anonymity set benchmark (1000 synthetic actions)...")
        print(json.dumps(run_benchmark(profile), indent=2))
    else:
        print(f"L2 Anonymity Set Analyzer v{profile['meta']['version']}")
        print(f"Profile: {profile['meta']['domain_name']}")
        run_examples(profile)


if __name__ == "__main__":
    main()
