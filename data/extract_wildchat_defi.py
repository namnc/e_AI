"""
Extract DeFi-related user queries from the WildChat-4.8M dataset.
Source: https://huggingface.co/datasets/allenai/WildChat-4.8M (ODC-BY license)

This streams the dataset (no full download needed) and filters for
crypto/DeFi-related first-turn user messages.

Usage:
  pip install datasets
  python data/extract_wildchat_defi.py [--max-results 500]

Output: data/wildchat_defi_queries.jsonl
"""

import argparse
import json
import re
from pathlib import Path

OUT = Path(__file__).parent / "wildchat_defi_queries.jsonl"

# Keywords that indicate DeFi/crypto content
DEFI_KEYWORDS = [
    # Protocols
    "aave", "uniswap", "compound", "makerdao", "curve", "lido", "eigenlayer",
    "dydx", "gmx", "synthetix", "balancer", "sushiswap", "yearn", "convex",
    "pendle", "morpho", "radiant", "frax", "lyra", "opyn",
    # DeFi concepts
    "health factor", "liquidat", "collateral ratio", "impermanent loss",
    "flash loan", "yield farm", "liquidity pool", "liquidity provision",
    "staking reward", "slippage", "sandwich attack", "front-run", "frontrun",
    "mev ", "defi", "tvl", "amm ", "dex ", "dapp",
    # Crypto assets in DeFi context
    "swap eth", "swap btc", "swap usdc", "swap usdt",
    "borrow eth", "borrow usdc", "lend eth", "lend usdc",
    "stake eth", "restaking", "liquid staking",
    # Wallets and chains
    "metamask", "gnosis safe", "ledger", "arbitrum", "optimism",
    "polygon defi", "ethereum defi", "layer 2", "l2 ",
    # Actions
    "provide liquidity", "remove liquidity", "add collateral",
    "repay loan", "repay debt", "bridge token", "bridge funds",
    "gas fee", "gas cost", "gas price",
]

# Exclude non-DeFi crypto (pure trading, price speculation, general crypto)
EXCLUDE_PATTERNS = [
    r"\b(price prediction|will .+ go up|should i buy .+ coin|to the moon)\b",
    r"\b(write me a|create a|generate a|help me write)\b",  # code generation requests
]


# Strong DeFi signals — unambiguous, require only 1 match
STRONG_KEYWORDS = [
    "aave", "uniswap", "compound finance", "makerdao", "maker vault",
    "curve finance", "curve pool", "lido staking", "eigenlayer",
    "dydx", "gmx protocol", "synthetix", "balancer pool", "sushiswap",
    "yearn finance", "convex finance", "pendle", "morpho",
    "health factor", "liquidat", "impermanent loss", "flash loan",
    "yield farm", "liquidity pool", "liquidity provision",
    "sandwich attack", "front-run", "frontrun",
    r"\bdefi\b", "decentralized finance",
    "swap eth", "swap btc", "swap usdc", "stake eth",
    "restaking", "liquid staking", "provide liquidity",
    "add collateral", "repay loan", "repay debt",
    "gnosis safe", "metamask.*swap", "bridge.*token",
]


def is_defi_query(text: str) -> bool:
    """Check if text contains DeFi-related content. Uses strict matching."""
    text_lower = text.lower()

    # Must contain at least one strong DeFi keyword (with word boundaries where needed)
    found = False
    for kw in STRONG_KEYWORDS:
        if kw.startswith(r"\b"):
            if re.search(kw, text_lower):
                found = True
                break
        elif kw in text_lower:
            found = True
            break

    if not found:
        return False

    # Exclude non-DeFi patterns
    for pat in EXCLUDE_PATTERNS:
        if re.search(pat, text_lower):
            return False

    # Minimum length and must look like a question/request, not code
    if text.count("\n") > 5:  # likely code or structured data
        return False

    return True


def classify_sensitivity(text: str) -> str:
    """Quick heuristic classification of query sensitivity."""
    text_lower = text.lower()

    # Strong sensitive signals
    sensitive_signals = [
        r"\bmy (?:position|wallet|portfolio|balance|debt|loan|stake|collateral)",
        r"\bi (?:have|hold|own|bought|sold|staked|borrowed|deposited|withdrew)",
        r"\$[\d,]+",  # dollar amounts
        r"\d+\s*(?:eth|btc|usdc|usdt|dai)",  # token amounts
        r"0x[a-fA-F0-9]{4,}",  # addresses
        r"\b(?:liquidat|underwater|margin call|stop loss)\b.*\b(?:my|i'm|i am)\b",
    ]
    for pat in sensitive_signals:
        if re.search(pat, text_lower):
            return "sensitive"

    # Borderline signals
    borderline_signals = [
        r"\bshould i\b",
        r"\bis it (?:safe|worth|good|bad)\b.*\b(?:defi|aave|uniswap|compound)\b",
        r"\bhow (?:do|can|should) i\b.*\b(?:swap|stake|lend|borrow|bridge)\b",
    ]
    for pat in borderline_signals:
        if re.search(pat, text_lower):
            return "borderline"

    return "non_sensitive"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-results", type=int, default=500)
    parser.add_argument("--max-scan", type=int, default=500_000,
                        help="Max conversations to scan (streaming)")
    args = parser.parse_args()

    try:
        from datasets import load_dataset
    except ImportError:
        print("ERROR: pip install datasets")
        return

    print(f"Streaming WildChat-4.8M (scanning up to {args.max_scan:,} conversations)...")
    print(f"Looking for DeFi-related first-turn user queries...")

    dataset = load_dataset("allenai/WildChat-4.8M", streaming=True, split="train")

    results = []
    scanned = 0

    for item in dataset:
        scanned += 1
        if scanned > args.max_scan:
            break

        if scanned % 50_000 == 0:
            print(f"  Scanned {scanned:,} | Found {len(results)} DeFi queries")

        # Get the first user message
        conversation = item.get("conversation", [])
        if not conversation:
            continue

        first_turn = None
        for turn in conversation:
            if turn.get("role") == "user":
                first_turn = turn.get("content", "")
                break

        if not first_turn or len(first_turn) < 20 or len(first_turn) > 500:
            continue

        if not is_defi_query(first_turn):
            continue

        # Found a DeFi query
        sensitivity = classify_sensitivity(first_turn)
        lang = item.get("language", "unknown")

        results.append({
            "text": first_turn.strip(),
            "label": sensitivity,
            "difficulty": "medium",
            "category": "wildchat_defi",
            "source": f"WildChat-4.8M (lang={lang})",
            "origin": "wildchat",
            "conversation_hash": item.get("conversation_hash", ""),
        })

        if len(results) >= args.max_results:
            break

    print(f"\nScanned {scanned:,} conversations")
    print(f"Found {len(results)} DeFi-related queries")

    if results:
        from collections import Counter
        labels = Counter(r["label"] for r in results)
        print(f"Labels: {dict(labels)}")

        # Save
        with open(OUT, "w") as f:
            for r in results:
                f.write(json.dumps(r) + "\n")
        print(f"Saved to {OUT}")

        # Show samples
        print(f"\n=== Samples ===")
        for r in results[:10]:
            print(f"  [{r['label']:>13}] {r['text'][:80]}")
    else:
        print("No DeFi queries found in the scanned portion.")
        print("Try increasing --max-scan (default 500K)")


if __name__ == "__main__":
    main()
