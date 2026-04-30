"""
Cross-Protocol Risk Analyzer — portfolio-level risk across DeFi positions.

Loads cross_protocol_risk/profile.json and evaluates a portfolio snapshot
against 5 heuristics (H1-H5) covering cascading liquidation, correlated oracle
dependency, concentrated protocol exposure, approval chain risk, and flash
loan attack surface.

Different shape from per-tx analyzers: takes a PortfolioSnapshot describing
all the user's positions, approvals, and oracle dependencies across protocols.

Production version would:
- Aggregate positions via DeFi Llama / Zapper / DeBank APIs
- Trace oracle dependency graph from each protocol
- Scan all outstanding approvals via Approval event logs
- Cross-reference flash loan provider exposure

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

CASCADE_HEALTH_FACTOR_THRESHOLD = 1.3      # H1: positions <1.3 with shared collateral
SHARED_COLLATERAL_FRACTION = 0.50          # H1: >50% of collateral in same asset
ORACLE_CONCENTRATION_THRESHOLD = 0.70      # H2: >70% of value depending on one oracle
PROTOCOL_CONCENTRATION_THRESHOLD = 0.50    # H3: >50% of portfolio in one protocol
APPROVAL_CHAIN_DEPTH_RISK = 3              # H4: >3 hops of unlimited approvals
FLASH_LOAN_VULNERABILITY_RATIO = 0.10      # H5: >10% of portfolio is flash-loan-attackable


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class LendingPosition:
    protocol: str               # "aave" | "compound" | "morpho" | etc.
    collateral_asset: str
    collateral_value_usd: float
    debt_asset: str
    debt_value_usd: float
    health_factor: float
    oracle_used: str            # which oracle prices the collateral


@dataclass
class TokenHolding:
    token: str
    amount: float
    value_usd: float
    protocol: str = ""          # if held inside a protocol (e.g., LP token)


@dataclass
class ApprovalChain:
    """Token approved to spender, who delegates to N downstream contracts."""
    token: str
    spender: str
    spender_protocol: str
    is_unlimited: bool
    chain_depth: int            # how many delegated contracts can ultimately move the token
    chain_protocols: list[str]  # protocols in the delegation chain


@dataclass
class FlashLoanExposure:
    """A position that could be exploited via flash loan amplification."""
    target_protocol: str
    vulnerability_type: str     # "oracle_manipulation" | "governance" | "amm_imbalance"
    affected_value_usd: float
    flash_loan_provider_available: bool


@dataclass
class PortfolioSnapshot:
    user_address: str
    total_portfolio_usd: float
    lending_positions: list[LendingPosition] = field(default_factory=list)
    token_holdings: list[TokenHolding] = field(default_factory=list)
    approval_chains: list[ApprovalChain] = field(default_factory=list)
    flash_loan_exposures: list[FlashLoanExposure] = field(default_factory=list)
    current_timestamp: int = 0


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
    portfolio: PortfolioSnapshot
    alerts: list[RiskAlert] = field(default_factory=list)
    overall_risk: str = "low"
    estimated_max_loss_usd: float = 0.0


# ---------------------------------------------------------------------------
# Profile loader
# ---------------------------------------------------------------------------

def load_profile(path: str | Path) -> dict:
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Heuristic checks
# ---------------------------------------------------------------------------

def check_h1_cascading_liquidation(p: PortfolioSnapshot, profile: dict) -> list[RiskAlert]:
    """H1: Multiple lending positions with shared collateral; one liquidation triggers others."""
    alerts: list[RiskAlert] = []
    h = profile["heuristics"]["H1_cascading_liquidation"]

    if len(p.lending_positions) < 2:
        return alerts

    # Group positions by collateral asset
    by_collateral: dict[str, list[LendingPosition]] = {}
    for pos in p.lending_positions:
        by_collateral.setdefault(pos.collateral_asset, []).append(pos)

    cascading_groups = []
    for asset, positions in by_collateral.items():
        if len(positions) < 2:
            continue
        total_collat = sum(pos.collateral_value_usd for pos in positions)
        share_of_portfolio = total_collat / max(p.total_portfolio_usd, 1.0)
        n_at_risk = sum(1 for pos in positions if pos.health_factor < CASCADE_HEALTH_FACTOR_THRESHOLD)
        if share_of_portfolio > SHARED_COLLATERAL_FRACTION and n_at_risk >= 2:
            cascading_groups.append((asset, positions, share_of_portfolio, n_at_risk))

    if cascading_groups:
        asset, positions, share, n_risk = cascading_groups[0]  # report worst
        total_value = sum(pos.collateral_value_usd + pos.debt_value_usd for pos in positions)
        alerts.append(RiskAlert(
            heuristic_id="H1",
            heuristic_name=h["name"],
            severity="critical",
            confidence=0.85,
            signal=(
                f"{n_risk} positions across {len(positions)} protocols share {asset} as collateral "
                f"({share:.0%} of portfolio). One liquidation triggers cascade."
            ),
            recommendation="Diversify collateral across asset types or reduce leverage on shared-collateral positions",
            skill="position_simulator",
            action="warn",
        ))
    return alerts


def check_h2_correlated_oracle(p: PortfolioSnapshot, profile: dict) -> list[RiskAlert]:
    """H2: Multiple positions depend on the same oracle — single point of failure."""
    alerts: list[RiskAlert] = []
    h = profile["heuristics"]["H2_correlated_oracle_dependency"]

    if not p.lending_positions:
        return alerts

    by_oracle: dict[str, float] = {}
    for pos in p.lending_positions:
        by_oracle[pos.oracle_used] = by_oracle.get(pos.oracle_used, 0.0) + pos.collateral_value_usd

    total_collat = sum(by_oracle.values())
    if total_collat <= 0:
        return alerts

    for oracle, value in by_oracle.items():
        share = value / total_collat
        if share > ORACLE_CONCENTRATION_THRESHOLD:
            alerts.append(RiskAlert(
                heuristic_id="H2",
                heuristic_name=h["name"],
                severity="critical",
                confidence=0.85,
                signal=(
                    f"{share:.0%} of lending collateral (${value:,.0f}) priced by single oracle "
                    f"'{oracle}' — oracle failure / manipulation = portfolio-wide event"
                ),
                recommendation="Diversify across protocols using independent oracles (Chainlink + Pyth + RedStone) or reduce exposure",
                skill="oracle_mapper",
                action="warn",
            ))
            break  # only report worst
    return alerts


def check_h3_concentrated_protocol(p: PortfolioSnapshot, profile: dict) -> list[RiskAlert]:
    """H3: >50% of portfolio in a single protocol — protocol exploit = personal disaster."""
    alerts: list[RiskAlert] = []
    h = profile["heuristics"]["H3_concentrated_protocol_exposure"]

    if p.total_portfolio_usd <= 0:
        return alerts

    by_protocol: dict[str, float] = {}
    for pos in p.lending_positions:
        by_protocol[pos.protocol] = by_protocol.get(pos.protocol, 0.0) + pos.collateral_value_usd
    for h_token in p.token_holdings:
        if h_token.protocol:
            by_protocol[h_token.protocol] = by_protocol.get(h_token.protocol, 0.0) + h_token.value_usd

    for proto, value in by_protocol.items():
        share = value / p.total_portfolio_usd
        if share > PROTOCOL_CONCENTRATION_THRESHOLD:
            severity = "critical" if share > 0.80 else "high"
            confidence = 0.85 if share > 0.80 else 0.75
            alerts.append(RiskAlert(
                heuristic_id="H3",
                heuristic_name=h["name"],
                severity=severity,
                confidence=confidence,
                signal=(
                    f"{share:.0%} of portfolio (${value:,.0f}) concentrated in protocol "
                    f"'{proto}' — exploit / pause / loss event = personal portfolio loss"
                ),
                recommendation="Diversify across protocols. Cap single-protocol exposure at 30-40% of net portfolio",
                skill="portfolio_scanner",
                action="warn",
            ))
            break
    return alerts


def check_h4_approval_chain(p: PortfolioSnapshot, profile: dict) -> list[RiskAlert]:
    """H4: Long chain of unlimited approvals — exploit at any link drains the user."""
    alerts: list[RiskAlert] = []
    h = profile["heuristics"]["H4_approval_chain_risk"]

    long_chains = [c for c in p.approval_chains
                   if c.is_unlimited and c.chain_depth > APPROVAL_CHAIN_DEPTH_RISK]

    if long_chains:
        worst = max(long_chains, key=lambda c: c.chain_depth)
        alerts.append(RiskAlert(
            heuristic_id="H4",
            heuristic_name=h["name"],
            severity="critical",
            confidence=0.85,
            signal=(
                f"Token {worst.token} has unlimited approval chain of depth {worst.chain_depth} "
                f"across protocols: {worst.chain_protocols[:4]}"
            ),
            recommendation=(
                f"Limit approval to exact amounts. Minimize chain depth — every protocol in the "
                f"chain is a possible exploit point."
            ),
            action="warn",
        ))
    return alerts


def check_h5_flash_loan_surface(p: PortfolioSnapshot, profile: dict) -> list[RiskAlert]:
    """H5: User holds positions vulnerable to flash-loan amplification."""
    alerts: list[RiskAlert] = []
    h = profile["heuristics"]["H5_flash_loan_attack_surface"]

    if not p.flash_loan_exposures or p.total_portfolio_usd <= 0:
        return alerts

    available_exposures = [e for e in p.flash_loan_exposures if e.flash_loan_provider_available]
    total_exposed = sum(e.affected_value_usd for e in available_exposures)
    fraction = total_exposed / p.total_portfolio_usd

    if fraction > FLASH_LOAN_VULNERABILITY_RATIO:
        types = [e.vulnerability_type for e in available_exposures]
        alerts.append(RiskAlert(
            heuristic_id="H5",
            heuristic_name=h["name"],
            severity=h["severity"],
            confidence=0.75,
            signal=(
                f"${total_exposed:,.0f} ({fraction:.0%}) of portfolio in flash-loan-attackable "
                f"positions: {set(types)}"
            ),
            recommendation=(
                "Avoid protocols with thin liquidity + price-oracle dependence (classic flash-loan "
                "exploit pattern). Prefer time-weighted oracles (TWAP, Chainlink stable) over spot."
            ),
            skill="flash_loan_detector",
            action="warn",
        ))
    return alerts


# ---------------------------------------------------------------------------
# Main analyzer
# ---------------------------------------------------------------------------

def analyze_portfolio(p: PortfolioSnapshot, profile: dict) -> AnalysisResult:
    result = AnalysisResult(portfolio=p)

    checks = [
        check_h1_cascading_liquidation(p, profile),
        check_h2_correlated_oracle(p, profile),
        check_h3_concentrated_protocol(p, profile),
        check_h4_approval_chain(p, profile),
        check_h5_flash_loan_surface(p, profile),
    ]
    for alerts in checks:
        result.alerts.extend(alerts)

    # Estimate max loss: sum of "critical" alerts' implicated value
    if result.alerts:
        # Heuristic: in worst case, all critical risks compound; cap at total portfolio
        critical_count = sum(1 for a in result.alerts if a.severity == "critical")
        result.estimated_max_loss_usd = min(
            p.total_portfolio_usd,
            p.total_portfolio_usd * (0.30 * critical_count + 0.10 * (len(result.alerts) - critical_count)),
        )

    if any(a.severity == "critical" and a.confidence >= 0.80 for a in result.alerts):
        result.overall_risk = "critical"
    elif any(a.severity == "critical" for a in result.alerts):
        result.overall_risk = "high"
    elif any(a.severity == "high" for a in result.alerts):
        result.overall_risk = "medium"
    elif result.alerts:
        result.overall_risk = "low"

    return result


def format_result(r: AnalysisResult) -> str:
    p = r.portfolio
    lines = [
        f"--- Portfolio Risk: {r.overall_risk.upper()} (max-loss est: ${r.estimated_max_loss_usd:,.0f}) ---",
        f"User: {p.user_address}",
        f"Portfolio: ${p.total_portfolio_usd:,.0f}",
        f"Lending positions: {len(p.lending_positions)}, Holdings: {len(p.token_holdings)}",
        f"Approval chains: {len(p.approval_chains)}, Flash-loan surfaces: {len(p.flash_loan_exposures)}",
        f"Alerts: {len(r.alerts)}",
    ]
    for a in r.alerts:
        lines.append(f"\n  [{a.heuristic_id}] {a.heuristic_name} ({a.severity}, conf {a.confidence:.0%}, action: {a.action})")
        lines.append(f"    Signal: {a.signal}")
        lines.append(f"    Action: {a.recommendation}")
        if a.skill:
            lines.append(f"    Skill: {a.skill}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Benchmark
# ---------------------------------------------------------------------------

def generate_synthetic_dataset(n: int = 100, seed: int = 42) -> list[PortfolioSnapshot]:
    rng = random.Random(seed)
    portfolios: list[PortfolioSnapshot] = []
    for i in range(n):
        is_risky = rng.random() < 0.40
        total = rng.uniform(5000, 5_000_000)
        n_lend = rng.randint(0, 4) if not is_risky else rng.randint(2, 6)

        # Cascading risk if multiple positions share collateral
        shared_collateral = is_risky and rng.random() < 0.50
        collat_pool = ["WETH"] * 3 + ["WBTC", "stETH", "DAI"] if shared_collateral else ["WETH", "WBTC", "DAI", "USDC", "stETH", "rETH", "LINK"]
        oracle_pool = ["chainlink_main"] * 4 if is_risky and rng.random() < 0.40 else ["chainlink_main", "pyth", "redstone"]

        positions = []
        for j in range(n_lend):
            collat = rng.choice(collat_pool)
            oracle = rng.choice(oracle_pool)
            cv = rng.uniform(1000, total * 0.4)
            hf = rng.uniform(1.0, 1.3) if is_risky else rng.uniform(1.5, 4.0)
            positions.append(LendingPosition(
                protocol=rng.choice(["aave", "compound", "morpho", "maker"]),
                collateral_asset=collat,
                collateral_value_usd=cv,
                debt_asset=rng.choice(["USDC", "DAI", "USDT"]),
                debt_value_usd=cv * rng.uniform(0.5, 0.85),
                health_factor=hf,
                oracle_used=oracle,
            ))

        # Token holdings
        holdings = []
        if is_risky and rng.random() < 0.40:
            # concentration in single protocol
            proto = rng.choice(["yearn_v3", "convex", "lido"])
            holdings.append(TokenHolding(token="LP_TOK", amount=1000, value_usd=total * 0.6, protocol=proto))
        else:
            for j in range(rng.randint(2, 6)):
                holdings.append(TokenHolding(
                    token=rng.choice(["USDC", "WETH", "WBTC", "DAI"]),
                    amount=rng.uniform(1, 1000),
                    value_usd=rng.uniform(100, total * 0.3),
                    protocol=rng.choice(["", "", "yearn", "convex"]),
                ))

        # Approval chains
        chains = []
        n_chains = rng.randint(0, 5)
        for j in range(n_chains):
            depth = rng.randint(1, 8) if is_risky else rng.randint(1, 3)
            chains.append(ApprovalChain(
                token=rng.choice(["USDC", "WETH", "DAI"]),
                spender=f"0xspender{j:02x}",
                spender_protocol=rng.choice(["uniswap", "1inch", "aave", "yearn"]),
                is_unlimited=rng.random() < 0.65,
                chain_depth=depth,
                chain_protocols=[rng.choice(["uniswap", "1inch", "yearn", "convex", "curve", "compound"]) for _ in range(depth)],
            ))

        # Flash loan exposures
        exposures = []
        if is_risky and rng.random() < 0.50:
            n_exp = rng.randint(1, 3)
            for j in range(n_exp):
                exposures.append(FlashLoanExposure(
                    target_protocol=rng.choice(["small_amm", "fork_protocol", "new_lend"]),
                    vulnerability_type=rng.choice(["oracle_manipulation", "amm_imbalance", "governance"]),
                    affected_value_usd=rng.uniform(1000, total * 0.30),
                    flash_loan_provider_available=True,
                ))

        portfolios.append(PortfolioSnapshot(
            user_address=f"0xuser{i:04x}",
            total_portfolio_usd=total,
            lending_positions=positions,
            token_holdings=holdings,
            approval_chains=chains,
            flash_loan_exposures=exposures,
            current_timestamp=1730000000,
        ))
    return portfolios


def run_benchmark(profile: dict, n: int = 1000) -> dict:
    portfolios = generate_synthetic_dataset(n)

    def is_risky(p: PortfolioSnapshot) -> bool:
        # Ground truth heuristic
        if len(p.lending_positions) >= 2:
            collat_groups: dict[str, int] = {}
            oracle_groups: dict[str, float] = {}
            for pos in p.lending_positions:
                if pos.health_factor < CASCADE_HEALTH_FACTOR_THRESHOLD:
                    collat_groups[pos.collateral_asset] = collat_groups.get(pos.collateral_asset, 0) + 1
                oracle_groups[pos.oracle_used] = oracle_groups.get(pos.oracle_used, 0.0) + pos.collateral_value_usd
            if any(c >= 2 for c in collat_groups.values()):
                return True
            total_oc = sum(oracle_groups.values())
            if total_oc and any(v / total_oc > ORACLE_CONCENTRATION_THRESHOLD for v in oracle_groups.values()):
                return True
        if any(c.is_unlimited and c.chain_depth > APPROVAL_CHAIN_DEPTH_RISK for c in p.approval_chains):
            return True
        if p.flash_loan_exposures and sum(e.affected_value_usd for e in p.flash_loan_exposures) / max(p.total_portfolio_usd, 1) > FLASH_LOAN_VULNERABILITY_RATIO:
            return True
        return False

    results = [(pp, analyze_portfolio(pp, profile)) for pp in portfolios]
    tp = fp = tn = fn = 0
    for pp, r in results:
        risky = is_risky(pp)
        flagged = r.overall_risk in ("critical", "high")
        if flagged and risky:
            tp += 1
        elif flagged and not risky:
            fp += 1
        elif not flagged and risky:
            fn += 1
        else:
            tn += 1
    total_r = tp + fn
    total_safe = tn + fp
    return {
        "n_portfolios": n,
        "risky_in_dataset": total_r,
        "true_positive": tp,
        "false_positive": fp,
        "true_negative": tn,
        "false_negative": fn,
        "true_positive_rate": f"{tp / total_r:.1%}" if total_r else "n/a",
        "false_positive_rate": f"{fp / total_safe:.1%}" if total_safe else "n/a",
    }


# ---------------------------------------------------------------------------
# Examples
# ---------------------------------------------------------------------------

def run_examples(profile: dict):
    examples = [
        ("Diversified portfolio: low risk", PortfolioSnapshot(
            user_address="0xsafe",
            total_portfolio_usd=100000,
            lending_positions=[
                LendingPosition("aave", "WETH", 30000, "USDC", 15000, 2.0, "chainlink_main"),
                LendingPosition("compound", "WBTC", 20000, "DAI", 8000, 2.5, "pyth"),
            ],
            token_holdings=[
                TokenHolding("USDC", 10000, 10000),
                TokenHolding("DAI", 10000, 10000),
            ],
        )),
        ("CRITICAL: cascading liquidation + oracle concentration", PortfolioSnapshot(
            user_address="0xrisky",
            total_portfolio_usd=200000,
            lending_positions=[
                LendingPosition("aave", "stETH", 80000, "USDC", 60000, 1.05, "chainlink_main"),
                LendingPosition("compound", "stETH", 50000, "DAI", 38000, 1.08, "chainlink_main"),
                LendingPosition("morpho", "stETH", 40000, "USDT", 30000, 1.1, "chainlink_main"),
            ],
        )),
        ("Concentration risk: 70% in one yield protocol", PortfolioSnapshot(
            user_address="0xconc",
            total_portfolio_usd=500000,
            lending_positions=[],
            token_holdings=[
                TokenHolding("yvUSDC", 350000, 350000, protocol="yearn_v3"),
                TokenHolding("USDC", 150000, 150000),
            ],
        )),
        ("Long approval chain risk", PortfolioSnapshot(
            user_address="0xchainy",
            total_portfolio_usd=50000,
            approval_chains=[
                ApprovalChain("USDC", "0xspender1", "1inch", True, 5,
                              ["1inch_router", "uniswap", "curve", "convex", "yearn"]),
            ],
        )),
        ("Flash loan exposure", PortfolioSnapshot(
            user_address="0xfl",
            total_portfolio_usd=100000,
            flash_loan_exposures=[
                FlashLoanExposure("small_amm", "oracle_manipulation", 30000, True),
                FlashLoanExposure("fork_protocol", "amm_imbalance", 15000, True),
            ],
        )),
    ]
    for name, p in examples:
        print(f"\n{'='*60}")
        print(f"Scenario: {name}")
        print(f"{'='*60}")
        print(format_result(analyze_portfolio(p, profile)))


def main():
    profile_path = Path(__file__).parent / "profile.json"
    profile = load_profile(profile_path)
    if "--benchmark" in sys.argv:
        print("Running cross-protocol risk benchmark (1000 synthetic portfolios)...")
        print(json.dumps(run_benchmark(profile), indent=2))
    else:
        print(f"Cross-Protocol Risk Analyzer v{profile['meta']['version']}")
        print(f"Profile: {profile['meta']['domain_name']}")
        run_examples(profile)


if __name__ == "__main__":
    main()
