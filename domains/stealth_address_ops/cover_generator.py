"""
Cover generator for stealth address transactions.

Adapts e_AI v1's cover query generator for transaction analysis.
Instead of generating fake queries, adjusts the real transaction's
parameters to be maximally indistinguishable from the background population.

The cover generator jointly optimizes: amount, timing, gas, and funding
against the current deposit pool state.

Usage:
    from domains.stealth_address_ops.cover_generator import CoverGenerator

    cg = CoverGenerator(profile, pool_state)
    cover_params = cg.generate(user_intent)
    # cover_params.amount, cover_params.timing, cover_params.gas, ...
"""

from __future__ import annotations

import json
import math
import random
import statistics
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PoolState:
    """Current state of the stealth address deposit pool."""
    deposits: list[dict] = field(default_factory=list)
    # Each deposit: {amount_eth, timestamp, gas_price_gwei}

    @property
    def amounts(self) -> list[float]:
        return [d["amount_eth"] for d in self.deposits if d.get("amount_eth")]

    @property
    def timestamps(self) -> list[int]:
        return [d["timestamp"] for d in self.deposits if d.get("timestamp")]

    @property
    def gas_prices(self) -> list[float]:
        return [d["gas_price_gwei"] for d in self.deposits if d.get("gas_price_gwei")]

    def amount_histogram(self) -> dict[float, int]:
        """Count occurrences of each standard denomination."""
        standard = [0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 50.0, 100.0]
        hist = {s: 0 for s in standard}
        for amt in self.amounts:
            nearest = min(standard, key=lambda s: abs(s - amt))
            if abs(nearest - amt) < 0.001:
                hist[nearest] += 1
        return hist

    def hourly_activity(self) -> dict[int, int]:
        """Count deposits per hour of day (UTC)."""
        import datetime
        hours = {h: 0 for h in range(24)}
        for ts in self.timestamps:
            dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
            hours[dt.hour] += 1
        return hours


@dataclass
class UserIntent:
    """What the user wants to do."""
    amount_eth: float
    recipient: str
    urgency: str = "normal"  # "immediate" | "normal" | "flexible"


@dataclass
class CoverParams:
    """Optimized transaction parameters that maximize indistinguishability."""
    amount_eth: float
    amount_reason: str
    delay_seconds: int
    delay_reason: str
    gas_price_gwei: float
    gas_reason: str
    funding_method: str
    funding_reason: str
    anonymity_set_estimate: int
    overall_cover_score: float  # 0.0 (exposed) to 1.0 (maximally covered)
    warnings: list[str] = field(default_factory=list)


class CoverGenerator:
    """Generates optimal cover parameters for stealth address transactions."""

    def __init__(self, profile: dict, pool_state: PoolState):
        self.profile = profile
        self.pool = pool_state
        self.standard_denoms = profile.get("skills", {}).get(
            "amount_normalizer", {}
        ).get("parameters", {}).get("denominations_eth", [0.1, 0.5, 1.0, 5.0, 10.0])

    def generate(self, intent: UserIntent) -> CoverParams:
        """Generate optimal cover parameters given user intent and pool state."""
        amount, amount_reason = self._optimize_amount(intent.amount_eth)
        delay, delay_reason = self._optimize_timing(intent.urgency)
        gas, gas_reason = self._optimize_gas()
        funding, funding_reason = self._optimize_funding()

        anon_set = self._estimate_anonymity_set(amount, delay)
        cover_score = self._compute_cover_score(amount, intent.amount_eth, delay, gas, funding, anon_set)
        warnings = self._generate_warnings(anon_set, intent, amount, delay)

        return CoverParams(
            amount_eth=amount,
            amount_reason=amount_reason,
            delay_seconds=delay,
            delay_reason=delay_reason,
            gas_price_gwei=gas,
            gas_reason=gas_reason,
            funding_method=funding,
            funding_reason=funding_reason,
            anonymity_set_estimate=anon_set,
            overall_cover_score=cover_score,
            warnings=warnings,
        )

    # -------------------------------------------------------------------
    # Amount optimization (H6)
    # -------------------------------------------------------------------

    def _optimize_amount(self, desired: float) -> tuple[float, str]:
        """Find the amount that maximizes anonymity set in current pool."""
        if not self.pool.amounts:
            nearest = min(self.standard_denoms, key=lambda d: abs(d - desired))
            return nearest, f"No pool data. Rounded to nearest standard denomination ({nearest} ETH)."

        hist = self.pool.amount_histogram()

        # Strategy 1: match the most popular amount in the pool
        if hist:
            best_amount = max(hist, key=hist.get)
            best_count = hist[best_amount]

            # Strategy 2: match nearest standard that has pool coverage
            nearest = min(self.standard_denoms, key=lambda d: abs(d - desired))
            nearest_count = hist.get(nearest, 0)

            # Prefer nearest to desired if it has reasonable cover
            if nearest_count >= best_count * 0.5 and nearest_count >= 3:
                return nearest, (
                    f"Rounded to {nearest} ETH ({nearest_count} matches in pool). "
                    f"Most popular is {best_amount} ETH ({best_count} matches)."
                )

            # Otherwise use the most popular
            if best_count >= 3:
                return best_amount, (
                    f"Using most popular amount {best_amount} ETH ({best_count} matches in pool). "
                    f"Your desired {desired} ETH would have ~0 matches."
                )

        # Fallback: simple rounding
        nearest = min(self.standard_denoms, key=lambda d: abs(d - desired))
        return nearest, f"Pool too sparse. Rounded to {nearest} ETH."

    # -------------------------------------------------------------------
    # Timing optimization (H3)
    # -------------------------------------------------------------------

    def _optimize_timing(self, urgency: str) -> tuple[int, str]:
        """Find the optimal delay to maximize anonymity set."""
        if urgency == "immediate":
            return 0, "User requested immediate execution. WARNING: timing correlation risk is high."

        if not self.pool.timestamps:
            # Default: random 6-24 hours
            delay = random.randint(6 * 3600, 24 * 3600)
            hours = delay / 3600
            return delay, f"No pool data. Random delay of {hours:.1f} hours."

        # Find peak activity hours
        hourly = self.pool.hourly_activity()
        peak_hour = max(hourly, key=hourly.get)
        peak_count = hourly[peak_hour]

        # Find second-best for variety
        sorted_hours = sorted(hourly.items(), key=lambda x: -x[1])
        top_3_hours = [h for h, c in sorted_hours[:3] if c >= peak_count * 0.5]

        import datetime
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        current_hour = now.hour

        # Find next peak hour that's at least 6 hours away
        target_hour = None
        for h in top_3_hours:
            hours_until = (h - current_hour) % 24
            if hours_until >= 6:
                target_hour = h
                break

        if target_hour is None:
            # All peak hours are within 6h, use random 6-24h
            delay = random.randint(6 * 3600, 24 * 3600)
            hours = delay / 3600
            return delay, f"Peak hours too close. Random delay of {hours:.1f} hours."

        hours_until = (target_hour - current_hour) % 24
        # Add random jitter (±30 min)
        jitter = random.randint(-1800, 1800)
        delay = hours_until * 3600 + jitter
        delay = max(6 * 3600, delay)  # minimum 6h

        return delay, (
            f"Targeting peak hour {target_hour}:00 UTC ({hourly[target_hour]} deposits/hr). "
            f"Delay: {delay / 3600:.1f} hours. "
            f"Current activity at {current_hour}:00: {hourly[current_hour]} deposits/hr."
        )

    # -------------------------------------------------------------------
    # Gas optimization (H2)
    # -------------------------------------------------------------------

    def _optimize_gas(self) -> tuple[float, str]:
        """Set gas to be indistinguishable from the population."""
        if not self.pool.gas_prices:
            # Use 30 gwei ± small random
            gas = round(random.gauss(30.0, 2.0), 1)
            return gas, "No pool gas data. Using default range (30 ± 2 gwei)."

        prices = self.pool.gas_prices
        median = statistics.median(prices)
        stdev = statistics.stdev(prices) if len(prices) > 1 else 2.0

        # Sample from [25th, 75th] percentile
        sorted_prices = sorted(prices)
        p25 = sorted_prices[len(sorted_prices) // 4]
        p75 = sorted_prices[3 * len(sorted_prices) // 4]

        gas = round(random.uniform(p25, p75), 1)
        return gas, (
            f"Sampled from pool IQR [{p25:.1f}, {p75:.1f}] gwei. "
            f"Median: {median:.1f}, Std: {stdev:.1f}. "
            f"Selected: {gas:.1f} gwei."
        )

    # -------------------------------------------------------------------
    # Funding optimization (H4)
    # -------------------------------------------------------------------

    def _optimize_funding(self) -> tuple[str, str]:
        """Always recommend paymaster -- deterministic best choice for H4."""
        return "paymaster", (
            "ERC-4337 paymaster eliminates gas funding link entirely. "
            "No ETH transfer to stealth address needed."
        )

    # -------------------------------------------------------------------
    # Anonymity set estimation
    # -------------------------------------------------------------------

    def _estimate_anonymity_set(self, amount: float, delay_seconds: int) -> int:
        """Estimate effective anonymity set given cover parameters."""
        if not self.pool.deposits:
            return 1  # worst case

        # Count deposits matching the amount within the time window
        delay_hours = delay_seconds / 3600
        window_hours = max(delay_hours, 6)  # minimum 6h window

        import datetime
        now_ts = int(datetime.datetime.now(tz=datetime.timezone.utc).timestamp())
        window_start = now_ts - int(window_hours * 3600)

        matching = 0
        for d in self.pool.deposits:
            ts = d.get("timestamp", 0)
            amt = d.get("amount_eth", 0)
            if ts >= window_start and abs(amt - amount) < 0.001:
                matching += 1

        return max(matching, 1)

    # -------------------------------------------------------------------
    # Cover score
    # -------------------------------------------------------------------

    def _compute_cover_score(
        self,
        amount: float,
        desired_amount: float,
        delay: int,
        gas: float,
        funding: str,
        anon_set: int,
    ) -> float:
        """Compute overall cover score (0.0 = exposed, 1.0 = maximally covered).

        Weighted combination of per-heuristic scores:
        - H1 (cluster): not controllable here, assume clean address (1.0)
        - H2 (gas): how close to population median
        - H3 (timing): delay length + activity in window
        - H4 (funding): paymaster = 1.0, known address = 0.0
        - H5 (self-send): not controllable here, assume not self-send (1.0)
        - H6 (amount): pool matches for chosen amount
        """
        scores = {}

        # H2: gas score
        if self.pool.gas_prices:
            median = statistics.median(self.pool.gas_prices)
            stdev = statistics.stdev(self.pool.gas_prices) if len(self.pool.gas_prices) > 1 else 5.0
            z = abs(gas - median) / max(stdev, 0.1)
            scores["H2"] = max(0, 1.0 - z * 0.3)
        else:
            scores["H2"] = 0.7

        # H3: timing score
        if delay >= 24 * 3600:
            scores["H3"] = 1.0
        elif delay >= 6 * 3600:
            scores["H3"] = 0.7 + 0.3 * ((delay - 6 * 3600) / (18 * 3600))
        elif delay >= 3600:
            scores["H3"] = 0.3
        else:
            scores["H3"] = 0.0

        # H4: funding score
        scores["H4"] = 1.0 if funding == "paymaster" else (0.5 if funding == "relay" else 0.0)

        # H6: amount score
        if self.pool.amounts:
            matches = sum(1 for a in self.pool.amounts if abs(a - amount) < 0.001)
            scores["H6"] = min(1.0, matches / 10)
        else:
            scores["H6"] = 0.5 if amount in self.standard_denoms else 0.1

        # Anonymity set multiplier
        anon_mult = min(1.0, math.log2(max(anon_set, 1)) / 5)  # log2(32) = 5 → full score

        # Weighted average (H3 and H4 are most impactful per the paper)
        weights = {"H2": 0.15, "H3": 0.35, "H4": 0.30, "H6": 0.20}
        raw_score = sum(scores[h] * weights[h] for h in weights)

        # Apply anonymity set multiplier
        final = raw_score * (0.5 + 0.5 * anon_mult)

        return round(final, 3)

    # -------------------------------------------------------------------
    # Warnings
    # -------------------------------------------------------------------

    def _generate_warnings(
        self,
        anon_set: int,
        intent: UserIntent,
        amount: float,
        delay: int,
    ) -> list[str]:
        """Generate human-readable warnings about remaining risks."""
        warnings = []

        if anon_set < 5:
            warnings.append(
                f"Anonymity set is only {anon_set}. Even with all countermeasures, "
                f"an adversary can narrow you to 1-of-{anon_set}. "
                f"Consider waiting for more pool activity."
            )

        if abs(amount - intent.amount_eth) > 0.01:
            diff = amount - intent.amount_eth
            warnings.append(
                f"Amount adjusted from {intent.amount_eth} to {amount} ETH "
                f"({'+' if diff > 0 else ''}{diff:.4f} difference). "
                f"Dust of {abs(diff):.4f} ETH remains in source wallet."
            )

        if delay == 0:
            warnings.append(
                "No delay applied (immediate urgency). "
                "Timing correlation risk remains critical."
            )

        if not self.pool.deposits:
            warnings.append(
                "No pool state data available. Cover parameters are based on "
                "defaults, not actual pool activity. Run with real data for "
                "accurate cover optimization."
            )

        return warnings


# ---------------------------------------------------------------------------
# Adversary simulation for cover quality measurement
# ---------------------------------------------------------------------------

def measure_cover_quality(
    cover_params: CoverParams,
    pool_state: PoolState,
    n_simulations: int = 1000,
) -> dict:
    """Simulate an adversary trying to identify the covered transaction.

    Returns detection rate (lower = better cover).
    """
    if not pool_state.deposits:
        return {"detection_rate": 1.0, "reason": "empty pool"}

    # The adversary sees: all deposits in the pool + the covered withdrawal
    # They try to match the withdrawal to a deposit using:
    # - amount matching (H6)
    # - timing proximity (H3)
    # - gas similarity (H2)

    pool_amounts = pool_state.amounts
    pool_times = pool_state.timestamps
    pool_gas = pool_state.gas_prices

    # For each simulation, place the covered tx among real deposits
    # and see if the adversary can pick it out
    correct_identifications = 0

    for _ in range(n_simulations):
        # Adversary's strategy: rank deposits by combined distance
        if not pool_amounts:
            correct_identifications += 1
            continue

        # Pick a random "true" deposit to be the matching one
        true_idx = random.randint(0, len(pool_state.deposits) - 1)
        true_deposit = pool_state.deposits[true_idx]

        # Score each deposit against the withdrawal
        scores = []
        for i, dep in enumerate(pool_state.deposits):
            # Amount distance (normalized)
            amt_dist = abs(dep.get("amount_eth", 0) - cover_params.amount_eth) / max(cover_params.amount_eth, 0.01)

            # Time distance (hours, normalized to 24h)
            time_dist = abs(dep.get("timestamp", 0) - (dep.get("timestamp", 0) + cover_params.delay_seconds)) / 86400

            # Gas distance (normalized)
            gas_dist = abs(dep.get("gas_price_gwei", 30) - cover_params.gas_price_gwei) / 30

            combined = amt_dist * 0.4 + time_dist * 0.4 + gas_dist * 0.2
            scores.append((i, combined))

        # Adversary picks the closest match
        scores.sort(key=lambda x: x[1])
        if scores[0][0] == true_idx:
            correct_identifications += 1

    detection_rate = correct_identifications / n_simulations
    return {
        "detection_rate": round(detection_rate, 3),
        "n_simulations": n_simulations,
        "random_baseline": round(1.0 / max(len(pool_state.deposits), 1), 3),
        "improvement_over_random": "none" if not pool_state.deposits else
            f"{(1.0 / len(pool_state.deposits)) / max(detection_rate, 0.001):.1f}x",
    }


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

def demo():
    """Run cover generator demo with synthetic pool."""
    import datetime

    # Load profile
    from pathlib import Path
    profile_path = Path(__file__).parent / "profile.json"
    with open(profile_path) as f:
        profile = json.load(f)

    # Generate synthetic pool
    now = int(datetime.datetime.now(tz=datetime.timezone.utc).timestamp())
    rng = random.Random(42)
    deposits = []
    for i in range(50):
        amounts = [0.1, 0.5, 1.0, 1.0, 1.0, 5.0, 5.0, 10.0]
        deposits.append({
            "amount_eth": rng.choice(amounts) if rng.random() > 0.3 else round(rng.uniform(0.1, 50), 4),
            "timestamp": now - rng.randint(0, 86400),
            "gas_price_gwei": round(rng.gauss(30, 4), 1),
        })

    pool = PoolState(deposits=deposits)
    cg = CoverGenerator(profile, pool)

    # Test scenarios
    scenarios = [
        ("Normal: 3.847 ETH, flexible timing", UserIntent(amount_eth=3.847, recipient="0xstealth", urgency="flexible")),
        ("Urgent: 1.0 ETH, immediate", UserIntent(amount_eth=1.0, recipient="0xstealth", urgency="immediate")),
        ("Large: 47.5 ETH, normal timing", UserIntent(amount_eth=47.5, recipient="0xstealth", urgency="normal")),
        ("Small: 0.05 ETH, flexible", UserIntent(amount_eth=0.05, recipient="0xstealth", urgency="flexible")),
    ]

    for name, intent in scenarios:
        print(f"\n{'=' * 60}")
        print(f"Scenario: {name}")
        print(f"{'=' * 60}")

        params = cg.generate(intent)

        print(f"  Amount: {params.amount_eth} ETH ({params.amount_reason})")
        print(f"  Delay:  {params.delay_seconds / 3600:.1f}h ({params.delay_reason})")
        print(f"  Gas:    {params.gas_price_gwei} gwei ({params.gas_reason})")
        print(f"  Fund:   {params.funding_method} ({params.funding_reason})")
        print(f"  Anon set: ~{params.anonymity_set_estimate}")
        print(f"  Cover score: {params.overall_cover_score}")

        if params.warnings:
            print(f"  Warnings:")
            for w in params.warnings:
                print(f"    - {w}")

        # Measure cover quality
        quality = measure_cover_quality(params, pool)
        print(f"  Adversary detection rate: {quality['detection_rate']:.1%} (random baseline: {quality['random_baseline']:.1%})")


if __name__ == "__main__":
    demo()
