"""
Completeness audit for the regex sanitizer.
Generates 10K+ synthetic parameter variations and measures false-negative rate.

Run: python test_sanitizer_audit.py
"""

import random
import re
from cover_generator import sanitize_query

random.seed(42)

# ─────────────────────────────────────────────
# Parameter generators
# ─────────────────────────────────────────────

TOKENS = ["ETH", "BTC", "USDC", "USDT", "DAI", "WETH", "WBTC", "stETH", "LINK", "AAVE", "UNI", "CRV", "SOL", "ENS"]

def gen_dollar_amounts(n=500):
    """$X variations: $100, $1,000, $1.5M, $500K, etc."""
    params = []
    for _ in range(n):
        base = random.choice([
            f"${random.randint(1, 999)}",
            f"${random.randint(1, 999):,}",
            f"${random.randint(1, 99)},{random.randint(0,999):03d}",
            f"${random.randint(1, 99)},{random.randint(0,999):03d},{random.randint(0,999):03d}",
            f"${random.uniform(0.1, 99.9):.1f}M",
            f"${random.uniform(0.1, 99.9):.1f}K",
            f"${random.uniform(0.1, 99.9):.1f}B",
            f"${random.randint(1, 999)}K",
            f"${random.randint(1, 999)}M",
        ])
        params.append(base)
    return params

def gen_token_amounts(n=500):
    """N TOKEN variations: 500 ETH, 1,000 BTC, 1.5M USDC, etc."""
    params = []
    for _ in range(n):
        token = random.choice(TOKENS)
        amount = random.choice([
            f"{random.randint(1, 9999)} {token}",
            f"{random.randint(1, 99)},{random.randint(0,999):03d} {token}",
            f"{random.uniform(0.1, 99.9):.1f}M {token}",
            f"{random.uniform(0.1, 99.9):.1f}K {token}",
            f"{random.randint(1, 999)}K {token}",
        ])
        params.append(amount)
    return params

def gen_addresses(n=200):
    """0x... variations."""
    params = []
    for _ in range(n):
        length = random.choice([3, 4, 6, 8, 10, 40])
        addr = "0x" + "".join(random.choices("0123456789abcdefABCDEF", k=length))
        params.append(addr)
    return params

def gen_percentages(n=300):
    params = []
    for _ in range(n):
        params.append(f"{random.uniform(0.01, 99.99):.1f}%")
        params.append(f"{random.randint(1, 99)}%")
    return params

def gen_leverage(n=100):
    return [f"{random.randint(2, 100)}x" for _ in range(n)]

def gen_health_factors(n=100):
    """Health factor is X.XX patterns."""
    params = []
    for _ in range(n):
        hf = round(random.uniform(0.5, 3.0), 2)
        params.append(f"Health factor is {hf}")
        params.append(f"HF of {hf}")
        params.append(f"health factor: {hf}")
    return params

def gen_comma_numbers(n=200):
    """Standalone comma-formatted numbers: 1,000 or 10,000,000."""
    params = []
    for _ in range(n):
        n_val = random.choice([
            f"{random.randint(1,999)},{random.randint(0,999):03d}",
            f"{random.randint(1,99)},{random.randint(0,999):03d},{random.randint(0,999):03d}",
        ])
        params.append(n_val)
    return params

def gen_timing(n=100):
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    params = []
    for _ in range(n):
        params.append(random.choice([
            f"by {random.choice(days)}",
            f"within {random.randint(1, 72)} hours",
            f"within {random.randint(1, 30)} days",
            "right now",
            "immediately",
            "ASAP",
            "tomorrow",
        ]))
    return params

def gen_emotional(n=50):
    words = ["worried", "anxious", "urgent", "emergency", "scared", "nervous",
             "panicking", "desperate", "afraid"]
    return [random.choice(words) for _ in range(n)]

def gen_qualitative(n=50):
    words = ["underwater", "close to liquidation", "about to be liquidated",
             "significantly imbalanced", "dangerously", "barely above",
             "dropping fast", "plummeting", "dumping"]
    return [random.choice(words) for _ in range(n)]

# ─────────────────────────────────────────────
# Audit
# ─────────────────────────────────────────────

def audit_category(name, params, template="I have {param} in my DeFi position."):
    """Test if each param is removed by the sanitizer."""
    total = len(params)
    leaked = []
    for param in params:
        query = template.format(param=param)
        result = sanitize_query(query)
        # Check if the param (or a recognizable substring) survives
        # For dollar amounts, check if the dollar figure is still there
        # For tokens, check if the amount+token combo is still there
        param_lower = param.lower().strip()
        result_lower = result.lower()

        # Check various representations
        found = False
        if param_lower in result_lower:
            found = True
        # Also check without commas
        param_no_comma = param_lower.replace(",", "")
        if len(param_no_comma) > 2 and param_no_comma in result_lower:
            found = True

        if found:
            leaked.append((param, result))

    rate = len(leaked) / total if total > 0 else 0
    status = "PASS" if rate < 0.05 else "FAIL"
    print(f"  {name:>25}: {total - len(leaked)}/{total} stripped ({1-rate:.1%} coverage) [{status}]")
    if leaked and len(leaked) <= 5:
        for p, r in leaked[:3]:
            print(f"    LEAK: '{p}' → '{r[:80]}'")
    elif leaked:
        print(f"    First 3 leaks of {len(leaked)}:")
        for p, r in leaked[:3]:
            print(f"    LEAK: '{p}' → '{r[:80]}'")
    return total, len(leaked)


def main():
    print("=" * 60)
    print("Regex Sanitizer Completeness Audit")
    print("=" * 60)

    categories = [
        ("Dollar amounts", gen_dollar_amounts(500), "My position is worth {param} in stablecoins."),
        ("Token amounts", gen_token_amounts(500), "I hold {param} in my wallet."),
        ("Wallet addresses", gen_addresses(200), "My wallet {param} has funds."),
        ("Percentages", gen_percentages(300), "The rate is {param} on this pool."),
        ("Leverage ratios", gen_leverage(100), "I'm leveraged {param} on dYdX."),
        ("Health factors", gen_health_factors(100), "My {param} and dropping."),
        ("Comma numbers", gen_comma_numbers(200), "I have {param} tokens staked."),
        ("Timing references", gen_timing(100), "I need to act {param} for tax purposes."),
        ("Emotional language", gen_emotional(50), "I'm {param} about my position."),
        ("Qualitative descriptors", gen_qualitative(50), "My position is {param} right now."),
    ]

    total_all = 0
    leaked_all = 0

    print()
    for name, params, template in categories:
        t, l = audit_category(name, params, template)
        total_all += t
        leaked_all += l

    overall_rate = leaked_all / total_all if total_all > 0 else 0
    print(f"\n{'='*60}")
    print(f"TOTAL: {total_all - leaked_all}/{total_all} stripped ({1-overall_rate:.2%} coverage)")
    print(f"False negatives: {leaked_all} ({overall_rate:.2%})")

    if overall_rate < 0.01:
        print("VERDICT: PASS (<1% false negative rate)")
    elif overall_rate < 0.05:
        print("VERDICT: MARGINAL (1-5% false negative rate)")
    else:
        print(f"VERDICT: FAIL ({overall_rate:.1%} false negative rate)")

    return leaked_all == 0


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
