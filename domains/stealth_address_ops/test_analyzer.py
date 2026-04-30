"""
Tests for stealth address ops analyzer.

Run: python -m pytest domains/stealth_address_ops/test_analyzer.py -v
  or: python domains/stealth_address_ops/test_analyzer.py
"""

import json
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from domains.stealth_address_ops.analyzer import (
    SteathTx, RiskAlert, AnalysisResult,
    analyze_transaction, load_profile,
    check_h1_same_entity, check_h2_gas_fingerprint,
    check_h3_timing, check_h4_funding,
    check_h5_self_send, check_h6_unique_amount,
    generate_synthetic_dataset, run_benchmark,
)

PROFILE_PATH = Path(__file__).parent / "profile.json"


def get_profile():
    return load_profile(PROFILE_PATH)


def make_tx(**overrides) -> SteathTx:
    """Create a default safe transaction, then apply overrides."""
    defaults = dict(
        deposit_address="0xaaaa",
        withdrawal_address="0xbbbb",
        stealth_address="0xcccc",
        amount_eth=1.0,
        deposit_timestamp=1700000000,
        spend_timestamp=1700000000 + 43200,  # 12h later
        gas_price_gwei=30.0,
        gas_funding_source="paymaster",
        is_self_send=False,
        address_cluster={"0xaaaa"},
    )
    defaults.update(overrides)
    return SteathTx(**defaults)


# ---------------------------------------------------------------------------
# Profile loading
# ---------------------------------------------------------------------------

def test_profile_loads():
    profile = get_profile()
    assert profile["meta"]["domain_name"] == "stealth_address_ops"
    assert len(profile["heuristics"]) == 6
    assert len(profile["skills"]) == 8


def test_profile_validation_passes():
    from meta.tx_validation_engine import validate_profile
    profile = get_profile()
    results = validate_profile(profile)
    assert results["overall"] == "PASS", f"Validation failed: {results}"


# ---------------------------------------------------------------------------
# H1: Same-entity withdrawal
# ---------------------------------------------------------------------------

def test_h1_clean():
    """No alert when withdrawal address NOT in cluster."""
    tx = make_tx()
    alerts = check_h1_same_entity(tx, get_profile())
    assert len(alerts) == 0


def test_h1_triggers():
    """Alert when withdrawal address IS in cluster."""
    tx = make_tx(address_cluster={"0xaaaa", "0xbbbb"})
    alerts = check_h1_same_entity(tx, get_profile())
    assert len(alerts) == 1
    assert alerts[0].heuristic_id == "H1"
    assert alerts[0].confidence >= 0.9


# ---------------------------------------------------------------------------
# H2: Gas price fingerprinting
# ---------------------------------------------------------------------------

def test_h2_clean():
    """No alert for normal gas price."""
    tx = make_tx(gas_price_gwei=30.0)
    alerts = check_h2_gas_fingerprint(tx, get_profile(), block_median_gas=30.0, block_std_gas=5.0)
    assert len(alerts) == 0


def test_h2_outlier():
    """Alert for gas price >2 std devs from median."""
    tx = make_tx(gas_price_gwei=50.0)
    alerts = check_h2_gas_fingerprint(tx, get_profile(), block_median_gas=30.0, block_std_gas=5.0)
    assert len(alerts) == 1
    assert alerts[0].heuristic_id == "H2"


# ---------------------------------------------------------------------------
# H3: Timing correlation
# ---------------------------------------------------------------------------

def test_h3_clean():
    """No alert when dwell time > 6 hours."""
    tx = make_tx(spend_timestamp=1700000000 + 43200)  # 12h
    alerts = check_h3_timing(tx, get_profile())
    assert len(alerts) == 0


def test_h3_short_dwell():
    """Critical alert when dwell time < 1 hour."""
    tx = make_tx(spend_timestamp=1700000000 + 600)  # 10 min
    alerts = check_h3_timing(tx, get_profile())
    assert len(alerts) == 1
    assert alerts[0].severity == "critical"
    assert alerts[0].confidence >= 0.9


def test_h3_medium_dwell():
    """Warning when dwell time 1-6 hours."""
    tx = make_tx(spend_timestamp=1700000000 + 10800)  # 3h
    alerts = check_h3_timing(tx, get_profile())
    assert len(alerts) == 1
    assert alerts[0].severity == "high"


# ---------------------------------------------------------------------------
# H4: Funding linkability
# ---------------------------------------------------------------------------

def test_h4_paymaster_clean():
    """No alert when gas from paymaster."""
    tx = make_tx(gas_funding_source="paymaster")
    alerts = check_h4_funding(tx, get_profile())
    assert len(alerts) == 0


def test_h4_relay_clean():
    """No alert when gas from relay."""
    tx = make_tx(gas_funding_source="relay")
    alerts = check_h4_funding(tx, get_profile())
    assert len(alerts) == 0


def test_h4_known_address():
    """Alert when gas from known address."""
    tx = make_tx(gas_funding_source="0xaaaa")
    alerts = check_h4_funding(tx, get_profile())
    assert len(alerts) == 1
    assert alerts[0].heuristic_id == "H4"
    assert alerts[0].confidence >= 0.9


# ---------------------------------------------------------------------------
# H5: Self-transfer
# ---------------------------------------------------------------------------

def test_h5_clean():
    """No alert for non-self-transfer."""
    tx = make_tx(is_self_send=False)
    alerts = check_h5_self_send(tx, get_profile())
    assert len(alerts) == 0


def test_h5_triggers():
    """Alert with 100% confidence for self-transfer."""
    tx = make_tx(is_self_send=True)
    alerts = check_h5_self_send(tx, get_profile())
    assert len(alerts) == 1
    assert alerts[0].confidence == 1.0


# ---------------------------------------------------------------------------
# H6: Unique amounts
# ---------------------------------------------------------------------------

def test_h6_round_amount():
    """No alert for standard denomination."""
    tx = make_tx(amount_eth=1.0)
    alerts = check_h6_unique_amount(tx, get_profile())
    assert len(alerts) == 0


def test_h6_unique_amount():
    """Alert for non-standard amount."""
    tx = make_tx(amount_eth=3.847)
    alerts = check_h6_unique_amount(tx, get_profile())
    assert len(alerts) == 1
    assert alerts[0].heuristic_id == "H6"


def test_h6_unique_in_pool():
    """High confidence when amount is unique in deposit pool."""
    tx = make_tx(amount_eth=7.3921)
    pool = [1.0, 5.0, 10.0, 0.5, 1.0]
    alerts = check_h6_unique_amount(tx, get_profile(), deposit_pool_amounts=pool)
    assert len(alerts) == 1
    assert alerts[0].confidence >= 0.9


def test_h6_common_in_pool():
    """No alert when amount has many matches in pool."""
    tx = make_tx(amount_eth=1.0)
    pool = [1.0, 1.0, 1.0, 1.0, 1.0, 5.0, 10.0]
    alerts = check_h6_unique_amount(tx, get_profile(), deposit_pool_amounts=pool)
    assert len(alerts) == 0


# ---------------------------------------------------------------------------
# Combined analysis
# ---------------------------------------------------------------------------

def test_good_practice_zero_alerts():
    """Good practice transaction should have zero alerts."""
    tx = make_tx()  # defaults are all safe
    result = analyze_transaction(tx, get_profile())
    assert result.overall_risk == "low"
    assert len(result.alerts) == 0
    assert not result.deanonymized


def test_bad_practice_multiple_alerts():
    """Bad practice should trigger multiple heuristics."""
    tx = make_tx(
        amount_eth=3.847,
        spend_timestamp=1700000000 + 600,
        gas_price_gwei=50.0,
        gas_funding_source="0xaaaa",
        address_cluster={"0xaaaa", "0xbbbb"},
    )
    result = analyze_transaction(tx, get_profile())
    assert result.overall_risk == "critical"
    assert result.deanonymized
    assert len(result.alerts) >= 3


def test_self_send_always_critical():
    """Self-send should always be critical regardless of other factors."""
    tx = make_tx(is_self_send=True)
    result = analyze_transaction(tx, get_profile())
    assert result.overall_risk == "critical"
    assert result.deanonymized


# ---------------------------------------------------------------------------
# Synthetic benchmark
# ---------------------------------------------------------------------------

def test_synthetic_dataset_generation():
    """Synthetic dataset should produce varied transactions."""
    txs = generate_synthetic_dataset(100)
    assert len(txs) == 100

    # Should have mix of self-sends and non-self-sends
    self_sends = sum(1 for tx in txs if tx.is_self_send)
    assert 0 < self_sends < 20  # ~5% expected

    # Should have mix of amounts
    amounts = set(tx.amount_eth for tx in txs)
    assert len(amounts) > 10


def test_benchmark_runs():
    """Benchmark should complete and show improvement."""
    profile = get_profile()
    results = run_benchmark(profile, n=100)
    assert results["n_transactions"] == 100
    baseline_rate = float(results["baseline"]["deanon_rate"].rstrip("%")) / 100
    mitigated_rate = float(results["mitigated"]["deanon_rate"].rstrip("%")) / 100
    assert mitigated_rate < baseline_rate


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  PASS  {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {test.__name__}: {e}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed out of {passed + failed}")
    sys.exit(1 if failed else 0)
