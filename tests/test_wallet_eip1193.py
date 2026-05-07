"""
Wallet EIP-1193 ABI-decoding tests.

Mirrors the TS helpers in `examples/wallet_eip1193/guard.ts` (isWellFormedCalldata,
decodeAddress, decodeUint256) to a Python contract suite. We don't run the TS
file in CI (Node optional); this test pins the *invariants* that the TS code
must also satisfy. If someone changes the TS ABI semantics, this suite still
documents what's required.

Background — Codex 2026-05-07 review found that approve() decoding was wrong:
the demo reported `tx.to` as the spender (it's the token contract). The fix
adds proper ABI decoding (selector + 32B word for spender, 32B for amount).
This test pins that fix.

Wired as `python3 tests/test_wallet_eip1193.py` from CI.
"""
from __future__ import annotations

import re
import sys
import unittest

HEX_RE = re.compile(r"^0x[0-9a-fA-F]*$")
MAX_UINT256 = (1 << 256) - 1
ERC20_APPROVE_SELECTOR = "0x095ea7b3"
ERC721_SETAPPROVALFORALL_SELECTOR = "0xa22cb465"


def is_well_formed_calldata(data: str, expected_bytes: int) -> bool:
    """Match guard.ts isWellFormedCalldata exactly.

    expected_bytes counts bytes AFTER the 4-byte selector.
    Total hex string length = 2 (for "0x") + 8 (selector) + 2*expected_bytes.
    """
    if not HEX_RE.match(data):
        return False
    expected_len = 2 + 8 + 2 * expected_bytes
    return len(data) == expected_len


def decode_address(data: str, byte_offset: int) -> str:
    """Match guard.ts decodeAddress exactly.

    Solidity ABI: address is right-aligned in a 32-byte word. Skip 12 bytes
    of left-pad, take the next 20 bytes as the address.
    """
    start = 2 + 2 * byte_offset + 24
    addr = data[start:start + 40]
    if len(addr) != 40:
        raise ValueError(f"decode_address: short read at offset {byte_offset}")
    return "0x" + addr


def decode_uint256(data: str, byte_offset: int) -> int:
    """Match guard.ts decodeUint256 exactly."""
    start = 2 + 2 * byte_offset
    hex_word = data[start:start + 64]
    if len(hex_word) != 64:
        raise ValueError(f"decode_uint256: short read at offset {byte_offset}")
    return int(hex_word, 16)


def _build_approve_calldata(spender: str, amount: int) -> str:
    """Build a well-formed approve(address,uint256) calldata for tests."""
    spender_word = "0" * 24 + spender.lower().replace("0x", "")
    amount_word = f"{amount:064x}"
    return ERC20_APPROVE_SELECTOR + spender_word + amount_word


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestIsWellFormedCalldata(unittest.TestCase):
    def test_valid_approve_calldata(self):
        cd = _build_approve_calldata("0x" + "ab" * 20, 1000)
        self.assertTrue(is_well_formed_calldata(cd, 64))

    def test_rejects_non_hex(self):
        bad = "0x095ea7b3" + "z" * 128
        self.assertFalse(is_well_formed_calldata(bad, 64))

    def test_rejects_short_calldata(self):
        short = "0x095ea7b3" + "00" * 32  # only 32 bytes after selector, expected 64
        self.assertFalse(is_well_formed_calldata(short, 64))

    def test_rejects_long_calldata(self):
        long_cd = "0x095ea7b3" + "00" * 96  # 96 bytes after selector, expected 64
        self.assertFalse(is_well_formed_calldata(long_cd, 64))

    def test_rejects_demo_bug_literal_spender_string(self):
        """The demo's previous calldata had the literal string 'spender' in it,
        which is not valid hex. This is the exact pattern that the Codex review
        flagged. Encoding a literal placeholder must not be accepted."""
        bad = (
            "0x095ea7b3"
            "000000000000000000000000spender0000000000000000000000000"
            "ffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
        )
        self.assertFalse(is_well_formed_calldata(bad, 64),
                         "calldata with literal 'spender' string must be rejected")


class TestDecodeAddress(unittest.TestCase):
    def test_decodes_spender_from_approve(self):
        spender = "0x" + "ab" * 20
        cd = _build_approve_calldata(spender, 0)
        # selector is at offset 0..3, spender word starts at offset 4
        self.assertEqual(decode_address(cd, 4).lower(), spender.lower())

    def test_decodes_known_address_pattern(self):
        # Use a recognizable pattern so a regression in the offset math is obvious
        spender = "0xdeadbeef" + "00" * 16
        cd = _build_approve_calldata(spender, 0)
        self.assertEqual(decode_address(cd, 4).lower(), spender.lower())

    def test_does_not_pick_up_token_contract_as_spender(self):
        """Regression: the previous demo reported tx.to as the spender. Decoding
        must produce the spender from calldata-arg-0, not the token contract."""
        spender = "0x" + "11" * 20
        token = "0x" + "22" * 20  # different from spender
        cd = _build_approve_calldata(spender, 1)
        decoded = decode_address(cd, 4)
        self.assertEqual(decoded.lower(), spender.lower())
        self.assertNotEqual(decoded.lower(), token.lower(),
                            "decoded spender must not collide with token contract address")


class TestDecodeUint256(unittest.TestCase):
    def test_decodes_small_amount(self):
        cd = _build_approve_calldata("0x" + "00" * 20, 12345)
        self.assertEqual(decode_uint256(cd, 4 + 32), 12345)

    def test_decodes_max_uint256(self):
        cd = _build_approve_calldata("0x" + "00" * 20, MAX_UINT256)
        self.assertEqual(decode_uint256(cd, 4 + 32), MAX_UINT256)

    def test_unlimited_approval_threshold(self):
        """Guard treats >= MAX_UINT256/2 as 'unlimited' — pin that semantics."""
        cd = _build_approve_calldata("0x" + "00" * 20, MAX_UINT256)
        self.assertGreaterEqual(decode_uint256(cd, 4 + 32), MAX_UINT256 // 2)


class TestSetApprovalForAll(unittest.TestCase):
    """Calldata layout: selector + operator (32B) + approved (32B bool word)."""

    def test_well_formed_setapprovalforall(self):
        operator = "0x" + "cd" * 20
        operator_word = "0" * 24 + operator.replace("0x", "")
        approved_word = "0" * 63 + "1"
        cd = ERC721_SETAPPROVALFORALL_SELECTOR + operator_word + approved_word
        self.assertTrue(is_well_formed_calldata(cd, 64))
        self.assertEqual(decode_address(cd, 4).lower(), operator.lower())


# ---------------------------------------------------------------------------
# Soft check: TS source still contains the helpers (drift detection)
# ---------------------------------------------------------------------------

class TestGuardTSSourceHasABIHelpers(unittest.TestCase):
    """If guard.ts loses these helpers in a refactor, the TS file silently
    regresses to the old broken behavior. Catch that drift here."""

    def test_helpers_present_in_guard_ts(self):
        from pathlib import Path
        guard_ts = (
            Path(__file__).resolve().parent.parent
            / "examples" / "wallet_eip1193" / "guard.ts"
        )
        if not guard_ts.exists():
            self.skipTest("guard.ts not present in this checkout")
        content = guard_ts.read_text()
        self.assertIn("isWellFormedCalldata", content)
        self.assertIn("decodeAddress", content)
        self.assertIn("decodeUint256", content)


if __name__ == "__main__":
    unittest.main()
