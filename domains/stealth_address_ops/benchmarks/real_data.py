"""
Real data benchmark — fetch actual Umbra stealth address transactions and
run the analyzer against them.

Requires an Ethereum RPC endpoint (Infura, Alchemy, or local node).

Usage:
    export RPC_URL=https://mainnet.infura.io/v3/YOUR_KEY
    python -m benchmarks.real_data --rpc $RPC_URL --limit 100
    python -m benchmarks.real_data --rpc $RPC_URL --full
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Umbra contract addresses (mainnet)
UMBRA_STEALTH_ADDRESS = "0xFb2dc580Eed955B528407b4d36FfaFe3da685401"  # Umbra v1
UMBRA_REGISTRY = "0x31fe56609C65Cd0C510E7125f051D440424D38f3"  # StealthKeyRegistry

# ERC-5564 singleton (if deployed)
ERC5564_ANNOUNCER = "0x55649E01B5Df198D18D95b5cc5051630cfD45564"

# Event signatures
ANNOUNCEMENT_TOPIC = "0x5f0016680bca4c37eec235b80e tried"  # Umbra Announcement event


@dataclass
class UmbraTx:
    """A real Umbra stealth address transaction."""
    tx_hash: str
    block_number: int
    timestamp: int
    sender: str
    receiver: str  # stealth address
    token: str
    amount: float
    amount_wei: int


def fetch_umbra_events(rpc_url: str, from_block: int, to_block: int | str = "latest") -> list[dict]:
    """Fetch Umbra Announcement events via eth_getLogs."""
    import httpx

    # Umbra Announcement event: event Announcement(...)
    # We fetch all logs from the Umbra contract
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_getLogs",
        "params": [{
            "fromBlock": hex(from_block),
            "toBlock": to_block if isinstance(to_block, str) else hex(to_block),
            "address": UMBRA_STEALTH_ADDRESS,
        }],
    }

    client = httpx.Client(timeout=30)
    resp = client.post(rpc_url, json=payload)
    resp.raise_for_status()
    result = resp.json()

    if "error" in result:
        raise RuntimeError(f"RPC error: {result['error']}")

    return result.get("result", [])


def fetch_block_timestamp(rpc_url: str, block_number: int) -> int:
    """Fetch block timestamp."""
    import httpx

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_getBlockByNumber",
        "params": [hex(block_number), False],
    }

    client = httpx.Client(timeout=10)
    resp = client.post(rpc_url, json=payload)
    resp.raise_for_status()
    block = resp.json().get("result", {})

    return int(block.get("timestamp", "0"), 16)


def fetch_tx_details(rpc_url: str, tx_hash: str) -> dict:
    """Fetch transaction details."""
    import httpx

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_getTransactionByHash",
        "params": [tx_hash],
    }

    client = httpx.Client(timeout=10)
    resp = client.post(rpc_url, json=payload)
    resp.raise_for_status()

    return resp.json().get("result", {})


def build_umbra_dataset(
    rpc_url: str,
    limit: int = 100,
    from_block: int = 14000000,  # Umbra deployed ~block 14M
) -> list[dict]:
    """Build a dataset of real Umbra transactions for benchmarking.

    Returns list of dicts with: tx_hash, block, timestamp, sender,
    stealth_address, amount_eth, gas_price_gwei, funding_source.
    """
    print(f"Fetching Umbra events from block {from_block}...")

    # Fetch in chunks to handle large ranges
    chunk_size = 10000
    all_logs = []
    current_block = from_block

    while len(all_logs) < limit:
        end_block = current_block + chunk_size
        try:
            logs = fetch_umbra_events(rpc_url, current_block, end_block)
            all_logs.extend(logs)
            print(f"  Block {current_block}-{end_block}: {len(logs)} events (total: {len(all_logs)})")
        except Exception as e:
            print(f"  Block {current_block}-{end_block}: error {e}")

        current_block = end_block + 1

        if len(all_logs) >= limit:
            break

        time.sleep(0.1)  # rate limit

    # Process logs into structured dataset
    dataset = []
    for log in all_logs[:limit]:
        tx_hash = log.get("transactionHash", "")
        block_num = int(log.get("blockNumber", "0"), 16)

        # Fetch tx details for gas info
        try:
            tx = fetch_tx_details(rpc_url, tx_hash)
            timestamp = fetch_block_timestamp(rpc_url, block_num)
        except Exception:
            continue

        gas_price = int(tx.get("gasPrice", "0"), 16) / 1e9  # gwei
        sender = tx.get("from", "")
        value_wei = int(tx.get("value", "0"), 16)
        value_eth = value_wei / 1e18

        dataset.append({
            "tx_hash": tx_hash,
            "block_number": block_num,
            "timestamp": timestamp,
            "sender": sender,
            "value_eth": round(value_eth, 6),
            "gas_price_gwei": round(gas_price, 2),
            "topics": log.get("topics", []),
            "data": log.get("data", ""),
        })

    return dataset


def run_real_benchmark(rpc_url: str, limit: int = 100):
    """Run the analyzer against real Umbra transactions."""
    # Build dataset
    dataset = build_umbra_dataset(rpc_url, limit)
    print(f"\nDataset: {len(dataset)} real Umbra transactions")

    if not dataset:
        print("No data fetched. Check RPC URL and block range.")
        return

    # Save dataset
    data_path = Path("data/umbra_real.jsonl")
    data_path.parent.mkdir(exist_ok=True)
    with open(data_path, "w") as f:
        for entry in dataset:
            f.write(json.dumps(entry) + "\n")
    print(f"Dataset saved to {data_path}")

    # Load profile and run analyzer
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from analyzer import (
        SteathTx, analyze_transaction, load_profile,
    )

    profile_path = Path(__file__).parent.parent / "domains" / "stealth_address_ops" / "profile.json"
    profile = load_profile(profile_path)

    # Convert real data to SteathTx format
    # Note: real benchmark is limited by what we can infer from on-chain data
    # We can check H2 (gas), H6 (amounts) directly
    # H1 (cluster), H3 (timing), H4 (funding), H5 (self-send) need more context
    all_amounts = [d["value_eth"] for d in dataset if d["value_eth"] > 0]

    results = {
        "total": len(dataset),
        "h2_gas_outliers": 0,
        "h6_unique_amounts": 0,
        "amount_distribution": {},
        "gas_distribution": {},
    }

    # Gas analysis
    gas_prices = [d["gas_price_gwei"] for d in dataset]
    if gas_prices:
        import statistics
        gas_mean = statistics.mean(gas_prices)
        gas_std = statistics.stdev(gas_prices) if len(gas_prices) > 1 else 1.0

        for d in dataset:
            z = abs(d["gas_price_gwei"] - gas_mean) / max(gas_std, 0.1)
            if z > 2.0:
                results["h2_gas_outliers"] += 1

        results["gas_distribution"] = {
            "mean": round(gas_mean, 2),
            "std": round(gas_std, 2),
            "min": round(min(gas_prices), 2),
            "max": round(max(gas_prices), 2),
        }

    # Amount analysis
    standard_denoms = [0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 50.0, 100.0]
    for d in dataset:
        amt = d["value_eth"]
        if amt > 0 and amt not in standard_denoms:
            # Check uniqueness in pool
            matches = sum(1 for a in all_amounts if abs(a - amt) < 0.001)
            if matches <= 1:
                results["h6_unique_amounts"] += 1

    # Amount buckets
    buckets = {"<0.1": 0, "0.1-1": 0, "1-10": 0, "10-100": 0, ">100": 0}
    for amt in all_amounts:
        if amt < 0.1:
            buckets["<0.1"] += 1
        elif amt < 1:
            buckets["0.1-1"] += 1
        elif amt < 10:
            buckets["1-10"] += 1
        elif amt < 100:
            buckets["10-100"] += 1
        else:
            buckets[">100"] += 1
    results["amount_distribution"] = buckets

    # Summary
    results["h2_gas_outlier_rate"] = f"{results['h2_gas_outliers'] / max(len(dataset), 1):.1%}"
    results["h6_unique_amount_rate"] = f"{results['h6_unique_amounts'] / max(len(dataset), 1):.1%}"

    print("\n" + "=" * 60)
    print("Real Data Benchmark Results")
    print("=" * 60)
    print(json.dumps(results, indent=2))

    # Save results
    results_path = Path("benchmarks/results_real.json")
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {results_path}")

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Real data benchmark for stealth address ops")
    parser.add_argument("--rpc", required=True, help="Ethereum RPC URL")
    parser.add_argument("--limit", type=int, default=100, help="Max transactions to fetch")
    parser.add_argument("--from-block", type=int, default=14000000, help="Start block")
    args = parser.parse_args()

    run_real_benchmark(args.rpc, args.limit)
