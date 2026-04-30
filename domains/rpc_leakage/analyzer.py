"""
RPC Leakage Analyzer — privacy heuristics for RPC query patterns.

Loads rpc_leakage/profile.json and evaluates a sequence of RPC queries (or
a single query) against 5 heuristics covering balance check linkage,
position monitoring, pre-trade intent, stealth address scanning, and price
check correlation.

This complements e_AI v1's defi_query analyzer (which deals with LLM-style
queries to a knowledge agent) by focusing on the RPC layer itself.

Privacy property: every JSON-RPC call to a non-local node leaks the user's
intent, position, and addresses to the RPC provider (Infura/Alchemy/etc.).

Production version would:
- Hook into wallet RPC client to intercept eth_call / eth_getBalance
- Track query rate per address pair (proxy for monitoring)
- Recognize protocol-specific patterns (Aave/Compound view functions)

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

POSITION_MONITORING_RATE_THRESHOLD = 12   # H2: >12 calls / hour to same address pair
PRICE_CHECK_CORRELATION_WINDOW_SECS = 300  # H5: price check within 5 min of swap
STEALTH_SCAN_PATTERN_LENGTH = 10           # H4: many sequential getLogs in narrow range

KNOWN_LENDING_VIEW_SELECTORS = {
    "0x4be21afe": "getUserAccountData(address)",      # Aave v3
    "0xbf92857c": "getAccountSnapshot(address)",      # Compound v2
    "0x35faa416": "getHealthFactor(address)",
}

KNOWN_PROTOCOL_PRICE_SELECTORS = {
    "0x33d6f8d2": "getReserves()",         # Uniswap V2 pair
    "0xddca3f43": "getReserves(address)",  # Uniswap V3
    "0x50d25bcd": "latestAnswer()",        # Chainlink
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class RPCQuery:
    timestamp: int
    method: str                  # "eth_call" | "eth_getBalance" | "eth_getLogs" | etc.
    target_address: str          # contract called or address checked
    function_selector: str = ""  # for eth_call
    args_addresses: list[str] = field(default_factory=list)  # addresses appearing in args
    block_range_size: int = 0    # for eth_getLogs
    user_originating_address: str = ""  # the wallet making the query


@dataclass
class RPCSession:
    """A user's RPC query session — typically one wallet's queries to a provider."""
    user_address: str
    queries: list[RPCQuery] = field(default_factory=list)
    rpc_provider: str = ""       # "infura" | "alchemy" | "self_hosted" | "helios" | etc.
    uses_local_node: bool = False
    uses_helios_or_light_client: bool = False
    uses_query_batching: bool = False
    uses_cover_queries: bool = False
    uses_tor: bool = False
    swap_or_action_timestamp: int = 0  # if there's an upcoming/recent swap to check intent against


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
    session: RPCSession
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

def check_h1_balance_check_linkage(s: RPCSession, profile: dict) -> list[RiskAlert]:
    """H1: Balance checks correlating multiple addresses owned by same user."""
    alerts: list[RiskAlert] = []
    h = profile["heuristics"]["H1_balance_check_linkage"]

    if s.uses_local_node or s.uses_helios_or_light_client:
        return alerts

    balance_queries = [q for q in s.queries if q.method == "eth_getBalance"]
    unique_targets = {q.target_address.lower() for q in balance_queries}

    if len(unique_targets) >= 3:
        # Multiple distinct addresses checked from same RPC connection — provider links them
        alerts.append(RiskAlert(
            heuristic_id="H1",
            heuristic_name=h["name"],
            severity="critical",
            confidence=0.90,
            signal=(
                f"User checked balances of {len(unique_targets)} distinct addresses through "
                f"{s.rpc_provider} — provider links these addresses to one identity"
            ),
            recommendation=(
                "Use a local light client (Helios) for balance checks. If using a hosted RPC, "
                "rotate providers or route through Tor."
            ),
            skill="helios_local",
            action="warn",
        ))
    return alerts


def check_h2_position_monitoring(s: RPCSession, profile: dict) -> list[RiskAlert]:
    """H2: High-rate eth_call to same lending position view function = monitoring leverage."""
    alerts: list[RiskAlert] = []
    h = profile["heuristics"]["H2_position_monitoring"]

    if s.uses_local_node:
        return alerts

    # Group eth_call to known lending view selectors
    monitoring_pairs: dict[tuple, list[int]] = {}
    for q in s.queries:
        if q.method == "eth_call" and q.function_selector in KNOWN_LENDING_VIEW_SELECTORS:
            for arg_addr in q.args_addresses:
                monitoring_pairs.setdefault((q.target_address, arg_addr), []).append(q.timestamp)

    for (contract, addr), timestamps in monitoring_pairs.items():
        if not timestamps:
            continue
        timestamps.sort()
        # Compute rate: queries per hour
        if len(timestamps) >= POSITION_MONITORING_RATE_THRESHOLD:
            duration_h = max((timestamps[-1] - timestamps[0]) / 3600, 0.1)
            rate = len(timestamps) / duration_h
            if rate > POSITION_MONITORING_RATE_THRESHOLD:
                alerts.append(RiskAlert(
                    heuristic_id="H2",
                    heuristic_name=h["name"],
                    severity=h["severity"],
                    confidence=0.85,
                    signal=(
                        f"High-rate monitoring of position {addr} on {contract} "
                        f"({len(timestamps)} queries / {duration_h:.1f}h = {rate:.0f}/h) — "
                        f"reveals leverage / health factor strategy to RPC provider"
                    ),
                    recommendation=(
                        "Use Helios or local node for position monitoring. If hosted RPC required, "
                        "batch queries (query_batching skill) or add cover queries."
                    ),
                    skill="helios_local",
                    action="warn",
                ))
                break  # one alert per session is enough
    return alerts


def check_h3_pretrade_intent(s: RPCSession, profile: dict) -> list[RiskAlert]:
    """H3: Pre-trade simulations / price checks correlated with imminent swap."""
    alerts: list[RiskAlert] = []
    h = profile["heuristics"]["H3_pretrade_intent"]

    if s.uses_local_node or s.swap_or_action_timestamp == 0:
        return alerts

    swap_ts = s.swap_or_action_timestamp
    pre_swap = [q for q in s.queries
                if q.timestamp < swap_ts and (swap_ts - q.timestamp) < PRICE_CHECK_CORRELATION_WINDOW_SECS
                and (q.function_selector in KNOWN_PROTOCOL_PRICE_SELECTORS or q.method == "eth_call")]

    if len(pre_swap) >= 3:
        alerts.append(RiskAlert(
            heuristic_id="H3",
            heuristic_name=h["name"],
            severity="critical",
            confidence=0.85,
            signal=(
                f"{len(pre_swap)} simulation/price queries within {PRICE_CHECK_CORRELATION_WINDOW_SECS}s "
                f"before swap (at {swap_ts}) — pre-trade intent revealed to RPC provider"
            ),
            recommendation=(
                "Use Helios for pre-trade simulation (no leak). If hosted RPC, generate "
                "cover_queries that simulate unrelated swaps to obscure intent."
            ),
            skill="cover_queries",
            action="warn",
        ))
    return alerts


def check_h4_stealth_scanning(s: RPCSession, profile: dict) -> list[RiskAlert]:
    """H4: Many sequential getLogs over narrow block ranges — stealth scan pattern."""
    alerts: list[RiskAlert] = []
    h = profile["heuristics"]["H4_stealth_address_scanning"]

    if s.uses_local_node:
        return alerts

    getLogs_queries = [q for q in s.queries if q.method == "eth_getLogs"]

    if len(getLogs_queries) >= STEALTH_SCAN_PATTERN_LENGTH:
        # Average block range — narrow ranges with high volume = scanning
        avg_range = sum(q.block_range_size for q in getLogs_queries) / len(getLogs_queries)
        if avg_range < 10000 and len(getLogs_queries) >= STEALTH_SCAN_PATTERN_LENGTH:
            alerts.append(RiskAlert(
                heuristic_id="H4",
                heuristic_name=h["name"],
                severity=h["severity"],
                confidence=0.80,
                signal=(
                    f"{len(getLogs_queries)} eth_getLogs queries with avg range {avg_range:.0f} blocks "
                    f"— matches stealth address scanner pattern (provider can identify Umbra/Fluidkey user)"
                ),
                recommendation=(
                    "Run a local Umbra scanner on a Helios light client. If using hosted RPC, this "
                    "reveals you are an SA recipient (and which collection)."
                ),
                skill="helios_local",
                action="warn",
            ))
    return alerts


def check_h5_price_check_correlation(s: RPCSession, profile: dict) -> list[RiskAlert]:
    """H5: Price-feed queries correlated with token holdings reveal portfolio."""
    alerts: list[RiskAlert] = []
    h = profile["heuristics"]["H5_price_check_correlation"]

    if s.uses_local_node:
        return alerts

    price_queries = [q for q in s.queries
                     if q.method == "eth_call" and q.function_selector in KNOWN_PROTOCOL_PRICE_SELECTORS]
    unique_price_targets = {q.target_address.lower() for q in price_queries}

    if len(unique_price_targets) >= 5:
        alerts.append(RiskAlert(
            heuristic_id="H5",
            heuristic_name=h["name"],
            severity=h["severity"],
            confidence=0.65,
            signal=(
                f"User checked prices on {len(unique_price_targets)} distinct pools/oracles — "
                f"signal of portfolio composition to RPC provider"
            ),
            recommendation=(
                "Use cover_queries to ask about prices the user does NOT hold, or batch price "
                "queries via a single multicall."
            ),
            skill="query_batching",
            action="inform",
        ))
    return alerts


# ---------------------------------------------------------------------------
# Main analyzer
# ---------------------------------------------------------------------------

def analyze_session(s: RPCSession, profile: dict) -> AnalysisResult:
    result = AnalysisResult(session=s)
    checks = [
        check_h1_balance_check_linkage(s, profile),
        check_h2_position_monitoring(s, profile),
        check_h3_pretrade_intent(s, profile),
        check_h4_stealth_scanning(s, profile),
        check_h5_price_check_correlation(s, profile),
    ]
    for alerts in checks:
        result.alerts.extend(alerts)

    if any(a.severity == "critical" and a.confidence >= 0.85 for a in result.alerts):
        result.overall_risk = "critical"
    elif any(a.severity == "critical" for a in result.alerts):
        result.overall_risk = "high"
    elif any(a.severity == "high" for a in result.alerts):
        result.overall_risk = "medium"
    elif result.alerts:
        result.overall_risk = "low"

    return result


def format_result(r: AnalysisResult) -> str:
    s = r.session
    lines = [
        f"--- RPC Leakage Risk: {r.overall_risk.upper()} ---",
        f"User: {s.user_address}",
        f"Provider: {s.rpc_provider} (local: {s.uses_local_node}, helios: {s.uses_helios_or_light_client})",
        f"Queries: {len(s.queries)}, batched: {s.uses_query_batching}, cover: {s.uses_cover_queries}",
        f"Alerts: {len(r.alerts)}",
    ]
    for a in r.alerts:
        lines.append(f"\n  [{a.heuristic_id}] {a.heuristic_name} ({a.severity}, conf {a.confidence:.0%}, action: {a.action})")
        lines.append(f"    Signal: {a.signal}")
        lines.append(f"    Action: {a.recommendation}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Benchmark
# ---------------------------------------------------------------------------

def generate_synthetic_dataset(n: int = 100, seed: int = 42) -> list[RPCSession]:
    rng = random.Random(seed)
    sessions: list[RPCSession] = []
    for i in range(n):
        leaks = rng.random() < 0.55
        local = (not leaks) and rng.random() < 0.30
        helios = (not leaks) and rng.random() < 0.20

        n_queries = rng.randint(5, 100) if leaks else rng.randint(0, 20)
        ts = 1730000000
        queries: list[RPCQuery] = []

        # Position monitoring pattern
        if leaks and rng.random() < 0.40:
            for j in range(rng.randint(15, 30)):
                queries.append(RPCQuery(
                    timestamp=ts + j * 60,
                    method="eth_call",
                    target_address="0xaave_v3_pool",
                    function_selector="0x4be21afe",
                    args_addresses=[f"0xuser{i:038x}"],
                    user_originating_address=f"0xuser{i:038x}",
                ))

        # Pre-trade intent
        swap_ts = 0
        if leaks and rng.random() < 0.30:
            swap_ts = ts + 1000
            for j in range(rng.randint(3, 6)):
                queries.append(RPCQuery(
                    timestamp=swap_ts - rng.randint(10, PRICE_CHECK_CORRELATION_WINDOW_SECS - 10),
                    method="eth_call",
                    target_address="0xunipool",
                    function_selector="0x33d6f8d2",
                    user_originating_address=f"0xuser{i:038x}",
                ))

        # Balance checks
        if leaks and rng.random() < 0.40:
            for j in range(rng.randint(3, 8)):
                queries.append(RPCQuery(
                    timestamp=ts + rng.randint(0, 3600),
                    method="eth_getBalance",
                    target_address=f"0xaddr{i:034x}{j:01x}",
                    user_originating_address=f"0xuser{i:038x}",
                ))

        # Stealth scanning
        if leaks and rng.random() < 0.30:
            for j in range(rng.randint(STEALTH_SCAN_PATTERN_LENGTH, 30)):
                queries.append(RPCQuery(
                    timestamp=ts + j * 12,
                    method="eth_getLogs",
                    target_address="0xumbra_announcer",
                    block_range_size=rng.randint(100, 5000),
                    user_originating_address=f"0xuser{i:038x}",
                ))

        # Price queries
        if leaks and rng.random() < 0.30:
            for j in range(rng.randint(5, 12)):
                queries.append(RPCQuery(
                    timestamp=ts + rng.randint(0, 3600),
                    method="eth_call",
                    target_address=f"0xpool{j:02x}",
                    function_selector=rng.choice(list(KNOWN_PROTOCOL_PRICE_SELECTORS.keys())),
                    user_originating_address=f"0xuser{i:038x}",
                ))

        sessions.append(RPCSession(
            user_address=f"0xuser{i:038x}",
            queries=queries,
            rpc_provider=rng.choice(["infura", "alchemy", "quicknode", "self_hosted"]),
            uses_local_node=local,
            uses_helios_or_light_client=helios,
            uses_query_batching=(not leaks) and rng.random() < 0.40,
            uses_cover_queries=(not leaks) and rng.random() < 0.20,
            uses_tor=False,
            swap_or_action_timestamp=swap_ts,
        ))
    return sessions


def run_benchmark(profile: dict, n: int = 1000) -> dict:
    sessions = generate_synthetic_dataset(n)

    def is_leaky(s: RPCSession) -> bool:
        if s.uses_local_node or s.uses_helios_or_light_client:
            return False
        balance_targets = {q.target_address.lower() for q in s.queries if q.method == "eth_getBalance"}
        if len(balance_targets) >= 3:
            return True
        getLogs_n = sum(1 for q in s.queries if q.method == "eth_getLogs")
        if getLogs_n >= STEALTH_SCAN_PATTERN_LENGTH:
            return True
        # high-rate monitoring
        monitoring_count = sum(1 for q in s.queries
                                if q.method == "eth_call" and q.function_selector in KNOWN_LENDING_VIEW_SELECTORS)
        if monitoring_count >= POSITION_MONITORING_RATE_THRESHOLD:
            return True
        if s.swap_or_action_timestamp:
            pre_swap = sum(1 for q in s.queries if q.timestamp < s.swap_or_action_timestamp
                           and (s.swap_or_action_timestamp - q.timestamp) < PRICE_CHECK_CORRELATION_WINDOW_SECS)
            if pre_swap >= 3:
                return True
        return False

    results = [(s, analyze_session(s, profile)) for s in sessions]
    tp = fp = tn = fn = 0
    for s, r in results:
        leaky = is_leaky(s)
        flagged = r.overall_risk in ("critical", "high")
        if flagged and leaky:
            tp += 1
        elif flagged and not leaky:
            fp += 1
        elif not flagged and leaky:
            fn += 1
        else:
            tn += 1
    total_l = tp + fn
    total_safe = tn + fp
    return {
        "n_sessions": n,
        "leaky_in_dataset": total_l,
        "true_positive": tp,
        "false_positive": fp,
        "true_negative": tn,
        "false_negative": fn,
        "true_positive_rate": f"{tp / total_l:.1%}" if total_l else "n/a",
        "false_positive_rate": f"{fp / total_safe:.1%}" if total_safe else "n/a",
    }


def run_examples(profile: dict):
    examples = [
        ("Privacy-preserving: Helios local, batched queries", RPCSession(
            user_address="0xprivate",
            rpc_provider="self_hosted",
            uses_local_node=True,
            uses_helios_or_light_client=True,
            uses_query_batching=True,
            queries=[],
        )),
        ("LEAK: balance checks across 5 addresses on Infura", RPCSession(
            user_address="0xleak1",
            rpc_provider="infura",
            queries=[
                RPCQuery(1730000000 + i*60, "eth_getBalance", f"0xaddr{i:01x}")
                for i in range(5)
            ],
        )),
        ("LEAK: position monitoring 30 queries/hour", RPCSession(
            user_address="0xleak2",
            rpc_provider="alchemy",
            queries=[
                RPCQuery(1730000000 + i*120, "eth_call", "0xaave_pool",
                         "0x4be21afe", ["0xleak2"]) for i in range(30)
            ],
        )),
        ("LEAK: pre-trade simulation burst before swap", RPCSession(
            user_address="0xleak3",
            rpc_provider="infura",
            swap_or_action_timestamp=1730003600,
            queries=[
                RPCQuery(1730003600 - 60 - i*30, "eth_call", "0xunipool",
                         "0x33d6f8d2") for i in range(5)
            ],
        )),
    ]
    for name, s in examples:
        print(f"\n{'='*60}")
        print(f"Scenario: {name}")
        print(f"{'='*60}")
        print(format_result(analyze_session(s, profile)))


def main():
    profile_path = Path(__file__).parent / "profile.json"
    profile = load_profile(profile_path)
    if "--benchmark" in sys.argv:
        print("Running RPC leakage benchmark (1000 synthetic sessions)...")
        print(json.dumps(run_benchmark(profile), indent=2))
    else:
        print(f"RPC Leakage Analyzer v{profile['meta']['version']}")
        print(f"Profile: {profile['meta']['domain_name']}")
        run_examples(profile)


if __name__ == "__main__":
    main()
