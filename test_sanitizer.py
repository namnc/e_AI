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

def test_mixed_case_defi_tokens():
    """Modern DeFi tokens with mixed case should be stripped."""
    assert "stETH" not in sanitize_query("I have 500 stETH staked")
    assert "wstETH" not in sanitize_query("200 wstETH as collateral")
    assert "cbETH" not in sanitize_query("Holding 100 cbETH on Coinbase")
    assert "frxETH" not in sanitize_query("50 frxETH in the pool")
    assert "USDC.e" not in sanitize_query("Bridged 500 USDC.e to Arbitrum")

def test_lowercase_token_amounts():
    """Users often type tokens in lowercase — must still be stripped."""
    assert "usdc" not in sanitize_query("I want to swap 500 usdc to eth on uniswap").lower()
    assert "1.8m usdc" not in sanitize_query("My debt is 1.8m usdc on aave").lower()
    assert "200 arb" not in sanitize_query("Holding 200 arb on Arbitrum").lower()
    assert "rseth" not in sanitize_query("I have 500 rsETH staked").lower()
    assert "susds" not in sanitize_query("Borrow 300 sUSDS against wBTC").lower()

def test_version_token_pairs_not_destroyed():
    """'V3 WBTC/ETH' should not be mangled into 'V /ETH'."""
    r = sanitize_query("How does Uniswap V3 WBTC/ETH concentrated liquidity work?")
    assert "V3" in r, f"V3 destroyed: {r}"
    # WBTC may be stripped (it's a token amount context) but V3 must survive

def test_no_erc_standard_destruction():
    """ERC-20, ERC-721, etc. should not be mangled."""
    r = sanitize_query("What is the ERC-20 token standard?")
    assert "ERC-20" in r or "ERC- 20" in r or ("ERC" in r and "20" in r and "token" in r), f"ERC-20 token mangled: '{r}'"
    assert "standard" in r, f"'standard' missing from: '{r}'"

def test_no_short_position_doubling():
    """'short positions' should not become 'position positions'."""
    r = sanitize_query("How do short positions work?")
    assert "position positions" not in r.lower(), f"Double position: {r}"

def test_ens_names():
    """ENS names should be stripped."""
    result = sanitize_query("What happens if vitalik.eth moves funds into Aave?")
    assert "vitalik.eth" not in result
    result2 = sanitize_query("I sent tokens to myname.eth")
    assert "myname.eth" not in result2

def test_lowercase_cardinal_tokens():
    """Cardinal + lowercase known token should be stripped."""
    assert "twenty eth" not in sanitize_query("I have twenty eth in my wallet").lower()
    assert "two hundred eth" not in sanitize_query("I hold two hundred eth").lower()

def test_worded_fractions_with_tokens():
    """Fractions like 'half ETH', 'a quarter ETH' should be stripped."""
    assert "half eth" not in sanitize_query("I have half ETH staked").lower()
    assert "quarter eth" not in sanitize_query("a quarter ETH remaining").lower()
    assert "half an eth" not in sanitize_query("just half an ETH left").lower()
    assert "and a half btc" not in sanitize_query("three and a half btc").lower()

def test_compound_cardinal_tokens():
    """Compound cardinal + token: 'twenty five ETH', 'one hundred and five ETH'."""
    assert "twenty five eth" not in sanitize_query("I have twenty five ETH").lower()
    assert "one hundred and five eth" not in sanitize_query("I have one hundred and five ETH").lower()
    assert "two thousand five hundred eth" not in sanitize_query("I have two thousand five hundred ETH").lower()

def test_plural_acronym_false_positives():
    """Plural acronyms like APIs, SDKs should NOT be stripped."""
    r = sanitize_query("How do 4 APIs compare to 5 SDKs?")
    assert "APIs" in r and "SDKs" in r, f"Plural acronyms stripped: {r}"
    r = sanitize_query("I checked 3 RPCs")
    assert "RPCs" in r, f"RPCs stripped: {r}"

def test_worded_decimal_with_token():
    """'zero point five eth' should be stripped."""
    assert "zero point five eth" not in sanitize_query("I have zero point five eth").lower()

def test_bare_magnitude_suffixes():
    """Bare 500k, 2m, 1.5m without $ or token should be stripped."""
    assert "500k" not in sanitize_query("Should I split 500k between protocols?").lower()
    assert "2m" not in sanitize_query("I have 2m in DeFi positions").lower()
    assert "1.5m notional" not in sanitize_query("1.5m notional exposure").lower()

def test_lowercase_novel_tokens():
    """All-lowercase novel tokens should be caught by broad pattern."""
    assert "pumpbtc" not in sanitize_query("I hold 500 pumpbtc in my wallet").lower()

def test_non_evm_addresses():
    """Solana, Bitcoin, Cosmos addresses should be stripped."""
    # Solana base58 (32-44 chars, alphanumeric, no 0/O/I/l)
    assert "9xQeWvG816" not in sanitize_query("My Solana wallet 9xQeWvG816bUx9EPjHmaT23yvVMiS9Wn3QPa7mK7iTs has funds")
    # Bitcoin bech32
    assert "bc1q" not in sanitize_query("Send to bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4")
    # Cosmos
    assert "cosmos1" not in sanitize_query("My Cosmos wallet cosmos1fl48vsnmsdzcv85q5d2q4z5ajdha8yu34mf0eh")

def test_genericize_missing_protocols():
    """Protocols not in the hardcoded list should ideally be caught."""
    from cover_generator import genericize_subquery
    r = genericize_subquery("Want to use Instadapp to migrate my Aave V2 position to Aave V3")
    assert "Instadapp" not in r, f"Instadapp leaked: {r}"

def test_joined_number_token():
    """125ETH, 125.0ETH — no space between number and token."""
    assert "125" not in sanitize_query("I have 125ETH in my wallet")
    assert "125.0" not in sanitize_query("I have 125.0ETH staked")

def test_separator_variants():
    """125-ETH, 125/ETH — separator between number and token."""
    assert "125" not in sanitize_query("I hold 125-ETH on Aave")
    assert "125" not in sanitize_query("I hold 125/ETH on Aave")

def test_zero_width_chars():
    """Zero-width characters should not bypass sanitization."""
    assert "500" not in sanitize_query("I have 500\u200bETH staked")
    assert "0x742d" not in sanitize_query("Address 0x742d\u200b35Cc6634C0532925a3b844Bc")

def test_fullwidth_digits():
    """Fullwidth digits (Unicode) should be normalized and caught."""
    # fullwidth 1.15 = \uff11\uff0e\uff11\uff15
    assert "1.15" not in sanitize_query("health factor \uff11\uff0e\uff11\uff15 on Aave")

def test_fullwidth_address_bypass():
    """Fullwidth 0x address should be normalized then stripped."""
    r = sanitize_query("\uff10x742d35Cc6634C0532925a3b844Bc9e7595f2bD38 has funds")
    assert "742d" not in r, f"Fullwidth address leaked: {r}"

def test_fullwidth_ens_bypass():
    """Fullwidth ENS name should be normalized then stripped."""
    from cover_generator import genericize_subquery
    r = sanitize_query("\uff56\uff49\uff54\uff41\uff4c\uff49\uff4b.eth sent tokens")
    assert "vitalik" not in r.lower(), f"Fullwidth ENS leaked: {r}"

def test_fullwidth_protocol_genericize():
    """Fullwidth protocol names should be genericized after normalization."""
    from cover_generator import genericize_subquery
    r = genericize_subquery("How does \uff21\uff41\uff56\uff45 V3 health factor work?")
    assert "aave" not in r.lower() and "Aave" not in r, f"Fullwidth protocol leaked: {r}"

def test_us_decimal_amounts():
    """US-format: 1,234.56 USDC — commas are thousands, dot is decimal."""
    r = sanitize_query("I have 1,234.56 USDC in my wallet")
    assert "1,234" not in r and "1.234" not in r and "234" not in r, f"US decimal leaked: {r}"
    r = sanitize_query("I have 1,234,567.89 USDC in my wallet")
    assert "234" not in r, f"US decimal leaked: {r}"

def test_comma_decimal_locale():
    """Comma-as-decimal: 1,15 (EU-style) should be caught after normalization."""
    r = sanitize_query("health factor is 1,15")
    assert "1,15" not in r and "1.15" not in r, f"Comma-decimal HF leaked: {r}"
    r = sanitize_query("rate is 10,5% on Aave")
    assert "10,5" not in r and "10.5" not in r, f"Comma-decimal percent leaked: {r}"

def test_leading_dot_health_factor():
    """Health factor .95, .5, etc. — leading dot decimal."""
    r = sanitize_query("health factor is .95")
    assert ".95" not in r and "95" not in r.split(), f"Leading-dot HF leaked: {r}"
    r = sanitize_query("HF .95 and falling")
    assert ".95" not in r, f"Leading-dot HF leaked: {r}"

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
    r = sanitize_query("I have two ETH and want to sell")
    assert "two ETH" not in r and "two eth" not in r.lower(), f"Leaked: {r}"
    r = sanitize_query("I hold three BTC in cold storage")
    assert "three BTC" not in r and "three btc" not in r.lower(), f"Leaked: {r}"
    r = sanitize_query("fifty ARB tokens remaining")
    assert "fifty ARB" not in r and "fifty arb" not in r.lower(), f"Leaked: {r}"

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
# Genericizer regression tests
# ─────────────────────────────────────────────

def test_gnosis_safe_genericizes_to_wallet():
    """Gnosis Safe should map to wallet management, not governance."""
    from cover_generator import genericize_subquery, classify_domain
    d = classify_domain("How does Gnosis Safe work?")
    assert d == "wallets", f"Gnosis Safe classified as {d}, expected wallets"
    r = genericize_subquery("Consolidate funds into a new Gnosis Safe")
    assert "wallet" in r.lower(), f"Gnosis Safe genericized wrong: {r}"
    assert "governance" not in r.lower(), f"Gnosis Safe leaked to governance: {r}"
    assert "Gnosis" not in r, f"Gnosis Safe not stripped: {r}"


def test_truncated_addresses():
    """Truncated addresses like 0xdead...beef and 0x5e6F...7g8H must be fully stripped."""
    for addr in ["0xdead...beef", "0x742d...f2bD", "0x5e6F...7g8H", "0x1a2B...3c4D"]:
        r = sanitize_query(f"Wallet {addr} has funds")
        # No hex/alphanumeric suffix should remain
        assert "beef" not in r.lower(), f"Suffix leaked: {r}"
        assert "f2bd" not in r.lower(), f"Suffix leaked: {r}"
        assert "7g8h" not in r.lower(), f"Suffix leaked: {r}"
        assert "3c4d" not in r.lower(), f"Suffix leaked: {r}"


def test_locale_bare_numbers():
    """Locale-formatted bare numbers must be stripped."""
    assert "1234" not in sanitize_query("I have 1,234,567 in my wallet")
    assert "1234" not in sanitize_query("I have 1,234.56 in my wallet")
    assert "1234" not in sanitize_query("I have 1.234,56 in my wallet")


def test_prefix_numbers_and_comparators():
    """Leading symbols like >500, ~1000, HF >1.15 must be stripped."""
    assert "500" not in sanitize_query("I have >500 ETH")
    assert "1000" not in sanitize_query("About ~1000 USDC left")
    assert "1.15" not in sanitize_query("My HF >1.15")
    assert "1.05" not in sanitize_query("Position HF <1.05")


def test_spaced_ranges():
    """Ranges with spaces like '500 - 1000 ETH' must be stripped."""
    r = sanitize_query("I need 500 - 1000 ETH")
    assert "500" not in r, f"Range lower bound leaked: {r}"
    assert "1000" not in r, f"Range upper bound leaked: {r}"


# ─────────────────────────────────────────────
# WildChat extractor regression tests
# ─────────────────────────────────────────────

def test_wildchat_metamask_swap():
    """MetaMask Swap is a DeFi product — should be detected."""
    import sys; sys.path.insert(0, "data")
    from extract_wildchat_defi import is_defi_query
    assert is_defi_query("How do I use the MetaMask Swap feature?")
    assert is_defi_query("Why is MetaMask Swap charging so much spread?")


def test_wildchat_no_content_generation_fp():
    """Content-generation prompts mentioning DeFi products should be excluded."""
    import sys; sys.path.insert(0, "data")
    from extract_wildchat_defi import is_defi_query
    assert not is_defi_query("Write a landing page for MetaMask Swap.")
    assert not is_defi_query("Create an ad for the MetaMask swap feature.")
    assert not is_defi_query("Can you write marketing copy for MetaMask swap?")


def test_wildchat_no_office_fp():
    """Non-DeFi text with DeFi product names should be excluded."""
    import sys; sys.path.insert(0, "data")
    from extract_wildchat_defi import is_defi_query
    assert not is_defi_query("How do I swap desks in the MetaMask office?")


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
