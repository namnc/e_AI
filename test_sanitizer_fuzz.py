"""
Fuzz testing harness for the regex sanitizer.
Generates adversarial mutations of seed queries and checks for leaks.

Run: python3 test_sanitizer_fuzz.py [--rounds 1000]
"""

import argparse
import random
import re
import string
import sys
import unicodedata

from cover_generator import sanitize_query


# ─────────────────────────────────────────────
# Mutation strategies
# ─────────────────────────────────────────────

# Zero-width and invisible characters
INVISIBLE_CHARS = [
    '\u200b', '\u200c', '\u200d', '\u2060', '\ufeff', '\u00ad',
    '\u200e', '\u200f', '\u2028', '\u2029', '\u202a', '\u202c',
]

# Homoglyph digit substitutions
HOMOGLYPH_DIGITS = {
    '0': ['O', '\u0030', '\uff10', '\u06f0'],
    '1': ['l', 'I', '\uff11', '\u0661'],
    '2': ['\uff12', '\u0662'],
    '3': ['\uff13', '\u0663'],
    '5': ['\uff15', '\u0665'],
}

TOKENS = ['ETH', 'BTC', 'USDC', 'USDT', 'DAI', 'AAVE', 'LINK', 'ARB', 'OP', 'SOL']
AMOUNTS = [100, 500, 1000, 2500, 10000, 50000, 100000, 1000000, 2500000]


def mutate_insert_invisible(text: str, rng: random.Random) -> str:
    """Insert zero-width characters at random positions."""
    chars = list(text)
    for _ in range(rng.randint(1, 5)):
        pos = rng.randint(0, len(chars))
        chars.insert(pos, rng.choice(INVISIBLE_CHARS))
    return ''.join(chars)


def mutate_homoglyph_digits(text: str, rng: random.Random) -> str:
    """Replace digits with visual homoglyphs."""
    result = []
    for ch in text:
        if ch in HOMOGLYPH_DIGITS and rng.random() < 0.3:
            result.append(rng.choice(HOMOGLYPH_DIGITS[ch]))
        else:
            result.append(ch)
    return ''.join(result)


def mutate_separator(amount: int, rng: random.Random) -> str:
    """Format an amount with various separator styles."""
    style = rng.choice([
        'plain',           # 1000
        'comma',           # 1,000
        'dot_thousands',   # 1.000
        'space',           # 1 000
        'apostrophe',      # 1'000
        'underscore',      # 1_000
        'european',        # 1.000,00
    ])
    s = str(amount)
    if style == 'plain':
        return s
    elif style == 'comma':
        return f'{amount:,}'
    elif style == 'dot_thousands':
        return f'{amount:,}'.replace(',', '.')
    elif style == 'space':
        return f'{amount:,}'.replace(',', ' ')
    elif style == 'apostrophe':
        return f'{amount:,}'.replace(',', "'")
    elif style == 'underscore':
        return f'{amount:,}'.replace(',', '_')
    elif style == 'european':
        cents = rng.randint(0, 99)
        return f'{amount:,}'.replace(',', '.') + f',{cents:02d}'
    return s


def mutate_notation(amount: int, rng: random.Random) -> str:
    """Express an amount in various numeric notations."""
    style = rng.choice(['decimal', 'scientific', 'suffix', 'fraction'])
    if style == 'decimal':
        return str(amount)
    elif style == 'scientific':
        exp = len(str(amount)) - 1
        mantissa = amount / (10 ** exp)
        return f'{mantissa:.1f}e{exp}'
    elif style == 'suffix':
        if amount >= 1_000_000:
            return f'{amount/1_000_000:.1f}M'
        elif amount >= 1_000:
            return f'{amount/1_000:.0f}K'
        return str(amount)
    elif style == 'fraction':
        return f'{amount}'
    return str(amount)


def mutate_joining(amount_str: str, token: str, rng: random.Random) -> str:
    """Join amount and token with various separators."""
    sep = rng.choice([' ', '', '-', '/', '  ', '\t'])
    return f'{amount_str}{sep}{token}'


def mutate_case(token: str, rng: random.Random) -> str:
    """Vary token case."""
    style = rng.choice(['upper', 'lower', 'mixed', 'original'])
    if style == 'upper':
        return token.upper()
    elif style == 'lower':
        return token.lower()
    elif style == 'mixed':
        return ''.join(rng.choice([c.upper(), c.lower()]) for c in token)
    return token


def generate_adversarial_query(rng: random.Random) -> tuple[str, str]:
    """Generate an adversarial query with a known private parameter.

    Returns: (query, expected_leak) where expected_leak is the numeric
    amount that should be stripped.
    """
    amount = rng.choice(AMOUNTS)
    token = rng.choice(TOKENS)

    # Choose a mutation chain
    amount_str = rng.choice([
        mutate_separator(amount, rng),
        mutate_notation(amount, rng),
        str(amount),
    ])

    token_str = mutate_case(token, rng)
    combined = mutate_joining(amount_str, token_str, rng)

    # Optionally insert invisible chars
    if rng.random() < 0.3:
        combined = mutate_insert_invisible(combined, rng)

    # Optionally apply homoglyph substitution
    if rng.random() < 0.2:
        combined = mutate_homoglyph_digits(combined, rng)

    templates = [
        f"I have {combined} in my wallet",
        f"Should I sell {combined} on Uniswap?",
        f"My position is {combined} on Aave",
        f"I want to swap {combined} to USDC",
        f"Holding {combined} staked on Lido",
    ]
    query = rng.choice(templates)

    return query, str(amount)


# ─────────────────────────────────────────────
# Fuzzer
# ─────────────────────────────────────────────

def fuzz(rounds: int = 1000, seed: int = 42):
    rng = random.Random(seed)
    leaked = 0
    total = 0
    leak_examples = []

    for i in range(rounds):
        query, expected_amount = generate_adversarial_query(rng)
        result = sanitize_query(query)

        # Check if the amount (or a significant portion) survived
        # Normalize both for comparison
        result_digits = re.sub(r'[^\d]', '', result)
        amount_digits = re.sub(r'[^\d]', '', expected_amount)

        total += 1

        # The amount leaked if we can find a significant numeric substring
        if len(amount_digits) >= 3 and amount_digits in result_digits:
            leaked += 1
            if len(leak_examples) < 20:
                leak_examples.append((query[:80], result[:80], expected_amount))
        elif len(amount_digits) < 3:
            # For small amounts (< 100), check if the exact digits appear
            # surrounded by non-digit context
            if re.search(rf'\b{re.escape(expected_amount)}\b', result):
                leaked += 1
                if len(leak_examples) < 20:
                    leak_examples.append((query[:80], result[:80], expected_amount))

    # Report
    leak_rate = leaked / total if total > 0 else 0
    print(f"\n{'='*60}")
    print(f"Sanitizer Fuzz Test Results")
    print(f"{'='*60}")
    print(f"Rounds: {total}")
    print(f"Leaked: {leaked} ({leak_rate:.1%})")
    print(f"Clean:  {total - leaked} ({1-leak_rate:.1%})")

    if leak_examples:
        print(f"\nLeak examples (first {len(leak_examples)}):")
        for query, result, amount in leak_examples:
            print(f"  Amount={amount}")
            print(f"    IN:  {query}")
            print(f"    OUT: {result}")
            print()

    if leak_rate < 0.01:
        print("VERDICT: PASS (<1% leak rate)")
    elif leak_rate < 0.05:
        print("VERDICT: MARGINAL (1-5% leak rate)")
    else:
        print(f"VERDICT: FAIL ({leak_rate:.1%} leak rate)")

    # PASS or MARGINAL = acceptable for CI; FAIL = blocks build
    return leak_rate < 0.05


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    success = fuzz(args.rounds, args.seed)
    sys.exit(0 if success else 1)
