"""
Unit tests for the regex sanitizer.
Verifies that all classes of private parameters are stripped.

Run: python -m pytest test_sanitizer.py -v
  or: python test_sanitizer.py
"""

from cover_generator import sanitize_query


# ─────────────────────────────────────────────
# Dollar amounts
# ─────────────────────────────────────────────

def test_dollar_amounts():
    assert "$1,000" not in sanitize_query("I have $1,000 in my wallet")
    assert "$1.5M" not in sanitize_query("My position is worth $1.5M")
    assert "$500K" not in sanitize_query("I want to deploy $500K")
    assert "$10,000,000" not in sanitize_query("Treasury has $10,000,000")
    assert "$2.5" not in sanitize_query("Fee is $2.5 per transaction")


# ─────────────────────────────────────────────
# Token amounts
# ─────────────────────────────────────────────

def test_token_amounts():
    assert "1,000 ETH" not in sanitize_query("I hold 1,000 ETH in Aave")
    assert "500 ETH" not in sanitize_query("Swap 500 ETH to USDC")
    assert "1.8M USDC" not in sanitize_query("Debt is 1.8M USDC")
    assert "200 ETH" not in sanitize_query("Add 200 ETH collateral")
    assert "50,000 LINK" not in sanitize_query("Holding 50,000 LINK tokens")
    assert "10,000 AAVE" not in sanitize_query("Staked 10,000 AAVE in safety module")
    assert "32 ETH" not in sanitize_query("Running a validator with 32 ETH")
    assert "3 BTC" not in sanitize_query("I have 3 BTC on Maker")


def test_token_amounts_with_suffixes():
    assert "500K USDC" not in sanitize_query("Flash loan 500K USDC from Aave")
    assert "1.8M USDC" not in sanitize_query("1.8M USDC debt outstanding")
    assert "5M ETH" not in sanitize_query("Pool has 5M ETH")


# ─────────────────────────────────────────────
# Wallet addresses
# ─────────────────────────────────────────────

def test_addresses():
    assert "0x742d35Cc" not in sanitize_query("My wallet 0x742d35Cc6634C0532925a3b844Bc9e7595f2bD38 has funds")
    assert "0xdead" not in sanitize_query("Cold storage at 0xdead...beef")
    assert "0xABC" not in sanitize_query("Gnosis Safe at 0xABC has stablecoins")


# ─────────────────────────────────────────────
# Percentages and ratios
# ─────────────────────────────────────────────

def test_percentages():
    assert "10%" not in sanitize_query("If ETH drops 10% tomorrow")
    assert "3.5%" not in sanitize_query("Premium is 3.5% for puts")
    assert "65%" not in sanitize_query("IV at 65% seems high")
    assert "2.3%" not in sanitize_query("Pool is 2.3% imbalanced")


def test_health_factor():
    result = sanitize_query("Health factor is 1.15 and dropping")
    assert "1.15" not in result


def test_leverage():
    assert "5x" not in sanitize_query("Leveraged 5x long ETH on dYdX")
    assert "10x" not in sanitize_query("My 10x position is underwater")


# ─────────────────────────────────────────────
# Timing references
# ─────────────────────────────────────────────

def test_timing():
    assert "Friday" not in sanitize_query("Need to sell by Friday for tax purposes")
    assert "48 hours" not in sanitize_query("Close within 48 hours")
    assert "tomorrow" not in sanitize_query("Voting on proposal tomorrow")
    assert "now" not in sanitize_query("Should I add collateral right now")


# ─────────────────────────────────────────────
# Emotional language
# ─────────────────────────────────────────────

def test_emotional():
    assert "worried" not in sanitize_query("I'm worried about liquidation")
    assert "anxious" not in sanitize_query("Feeling anxious about this position")
    assert "emergency" not in sanitize_query("Emergency exit from all positions")
    assert "desperate" not in sanitize_query("I'm desperate to close this")


# ─────────────────────────────────────────────
# Qualitative descriptors
# ─────────────────────────────────────────────

def test_qualitative():
    assert "underwater" not in sanitize_query("My position is underwater")
    assert "close to liquidation" not in sanitize_query("Position is close to liquidation")
    assert "dangerously" not in sanitize_query("HF is dangerously low")


# ─────────────────────────────────────────────
# Directional verbs
# ─────────────────────────────────────────────

def test_directional_verbs():
    result = sanitize_query("I want to buy ETH")
    assert "buy" not in result.lower().split()

    result = sanitize_query("Should I sell my tokens")
    assert "sell" not in result.lower().split()


# ─────────────────────────────────────────────
# Preservation: non-sensitive content survives
# ─────────────────────────────────────────────

def test_preserves_protocol_names():
    result = sanitize_query("How does Aave V3 health factor work?")
    assert "Aave" in result

def test_preserves_mechanism_names():
    result = sanitize_query("How does the liquidation mechanism work?")
    assert "liquidation" in result

def test_preserves_generic_questions():
    q = "What is impermanent loss in AMMs?"
    result = sanitize_query(q)
    assert "impermanent loss" in result


# ─────────────────────────────────────────────
# Known limitations: natural language paraphrases
# These tests document what the regex CANNOT catch.
# They are expected to FAIL (params leak through).
# ─────────────────────────────────────────────

def test_natural_language_quantities():
    """Natural language number-word patterns should be caught by the secondary filter."""
    should_catch = [
        "half a million USDC",
        "roughly two thousand ETH",
        "my six-figure position",
        "a few hundred thousand dollars",
        "several thousand ETH",
        "over a hundred thousand USDC",
    ]
    for phrase in should_catch:
        result = sanitize_query(f"I have {phrase} in my wallet")
        assert phrase.lower() not in result.lower(), f"LEAKED: '{phrase}' in '{result}'"

def test_broad_token_symbols():
    """Tokens not in original hardcoded list should still be stripped."""
    assert "500 ARB" not in sanitize_query("Should I sell 500 ARB on Uniswap?")
    assert "250 OP" not in sanitize_query("What happens if my 250 OP collateral drops?")
    assert "800 PEPE" not in sanitize_query("How risky is it to LP 800 PEPE with ETH?")
    assert "1000 MATIC" not in sanitize_query("I staked 1000 MATIC on Lido")

def test_ens_names():
    """ENS names should be stripped."""
    result = sanitize_query("What happens if vitalik.eth moves funds into Aave?")
    assert "vitalik.eth" not in result
    result2 = sanitize_query("I sent tokens to myname.eth")
    assert "myname.eth" not in result2

def test_known_limitation_semantic():
    """Purely semantic quantity references still bypass the sanitizer.
    These require true NLU, not pattern matching."""
    semantic = [
        "about double what I started with",
        "more than I can afford to lose",
        "a whale-sized position",
    ]
    for phrase in semantic:
        result = sanitize_query(phrase)
        # We expect these to leak — they're beyond regex/keyword detection
        assert phrase.lower() in result.lower(), (
            f"Surprisingly caught: '{phrase}' → '{result}'. Update test if filter improved."
        )

def test_cardinal_numbers_with_tokens():
    """Bare cardinal + uppercase token should be stripped."""
    assert "two ETH" not in sanitize_query("I have two ETH and want to sell").upper()
    assert "three BTC" not in sanitize_query("I hold three BTC in cold storage").upper()
    assert "fifty ARB" not in sanitize_query("fifty ARB tokens remaining").upper()

def test_cardinal_no_false_positives():
    """Cardinal + lowercase word should NOT be stripped."""
    assert "two options" in sanitize_query("I have two options here")
    assert "three ways" in sanitize_query("There are three ways to do this")
    assert "five protocols" in sanitize_query("I checked five protocols")

def test_no_false_positives_on_benign_numbers():
    """Numbers followed by common English words should not be stripped."""
    # These were reported as false positives in audit
    r = sanitize_query("What happens after 2 weeks in the unstaking queue?")
    assert "2 weeks" in r, f"False positive: '2 weeks' stripped from '{r}'"

    r = sanitize_query("How does Uniswap V3 compare to V2 on gas costs?")
    assert "V3" in r, f"False positive: 'V3' stripped from '{r}'"

    r = sanitize_query("What is 2FA and should I enable it on my wallet?")
    assert "2FA" in r.upper(), f"False positive: '2FA' stripped from '{r}'"

    r = sanitize_query("Is 10 basis points a typical fee?")
    assert "basis" in r, f"False positive: 'basis' stripped from '{r}'"

    r = sanitize_query("I have 3 pools on Uniswap")
    assert "3 pools" in r, f"False positive: '3 pools' stripped from '{r}'"

    r = sanitize_query("There are 5 options for bridging")
    assert "5 options" in r, f"False positive: '5 options' stripped from '{r}'"


# ─────────────────────────────────────────────
# Full query integration tests
# ─────────────────────────────────────────────

def test_alice_query():
    """The Alice scenario from the post."""
    q = ("I have an Aave V3 position with 1,000 ETH collateral and 1.8M USDC debt. "
         "My health factor is 1.15. ETH is at $2,500. If ETH drops 10% to $2,250, "
         "my HF drops to about 1.035. Should I add 200 ETH more collateral now?")
    result = sanitize_query(q)
    assert "1,000" not in result
    assert "1.8M" not in result
    assert "1.15" not in result
    assert "$2,500" not in result
    assert "10%" not in result
    assert "200 ETH" not in result
    assert "Aave" in result  # protocol name preserved


def test_no_empty_output():
    """Sanitization should not produce empty or trivially short output."""
    queries = [
        "How does Aave V3 health factor change when collateral is added?",
        "What are the gas costs for DEX swaps on Ethereum?",
        "How does impermanent loss work in Uniswap V3?",
    ]
    for q in queries:
        result = sanitize_query(q)
        assert len(result.split()) >= 3, f"Too short: '{result}' from '{q}'"


# ─────────────────────────────────────────────
# Run
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
            print(f"  PASS: {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL: {t.__name__}: {e}")
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
