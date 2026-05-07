"""
AI-agent adapter unit tests.

Pins the contract of `AgentGuard._build_tool_intent` — the layer that
translates agent tool calls into RPC-shaped params so the underlying
analyzers see realistic input. Previously this layer was tested only
via a string-grep CI step on the demo's stdout (Codex Phase 3 review
missed-coverage #9). Stdout-grep tells you the demo emits a warning
string; it does not tell you the adapter built the right calldata or
that a "normal swap" path correctly elicits no warning.

Wired as `python3 tests/test_ai_agent_adapter.py` from CI.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Make examples/ai_agent importable.
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "examples" / "ai_agent"))

# Suppress profile-loading log noise during import.
import logging
logging.getLogger("e_ai.agent").setLevel(logging.ERROR)
logging.getLogger("e_ai.llm_analyzer").setLevel(logging.ERROR)

from guard import AgentGuard  # type: ignore


# Minimal stub so we don't need the full profile set just to test the
# adapter. AgentGuard's _build_tool_intent is a pure function of fn_name
# + args + kwargs — it doesn't depend on profiles.
class _NoProfileGuard(AgentGuard):
    def __init__(self):  # type: ignore
        # Skip the parent's profile-loading + LLM connect.
        self.profiles = []
        self.llm_analyzers: dict = {}
        self.user_history: list = []


class TestBuildToolIntent(unittest.TestCase):
    def setUp(self):
        self.g = _NoProfileGuard()

    # ---- Approval tools ----

    def test_approve_token_unlimited_builds_max_uint256(self):
        method, params = self.g._build_tool_intent(
            "approve_token", ("0xToken", "0xSpender", "unlimited"), {}
        )
        self.assertEqual(method, "eth_sendTransaction")
        self.assertEqual(params["to"], "0xToken")
        # Calldata: selector (10 chars) + spender word + amount word = 138 chars
        self.assertEqual(len(params["data"]), 2 + 8 + 64 + 64)
        # Selector
        self.assertEqual(params["data"][:10].lower(), "0x095ea7b3")
        # Amount word should be all f's (max uint256)
        self.assertEqual(params["data"][-64:].lower(), "f" * 64)

    def test_approve_token_finite_amount_encodes_correctly(self):
        method, params = self.g._build_tool_intent(
            "approve_token", ("0xToken", "0xabcdef0000000000000000000000000000000123", 1000), {}
        )
        # Amount 1000 = 0x3e8 → right-aligned in 32-byte word
        self.assertEqual(params["data"][-64:], "0" * 61 + "3e8")
        # Spender at calldata bytes [4..36): right-aligned in word
        spender_word = params["data"][10:74]
        self.assertEqual(spender_word, "0" * 24 + "abcdef0000000000000000000000000000000123")

    def test_approve_token_unparseable_amount_falls_back_to_unlimited(self):
        """Conservative fallback: if we can't parse the amount, treat as
        unlimited so the analyzer flags it. Pin that behavior."""
        method, params = self.g._build_tool_intent(
            "approve_token", ("0xToken", "0xSpender", object()), {}
        )
        self.assertEqual(params["data"][-64:].lower(), "f" * 64)

    # ---- Balance tools ----

    def test_check_balance_emits_eth_getBalance_not_eth_call(self):
        """Codex critical review #D: the demo had been emitting eth_call
        instead of eth_getBalance, so rpc_leakage H1 (count of unique
        balance-checked addresses) never fired. Pin this fix."""
        method, params = self.g._build_tool_intent(
            "check_balance", ("0xUserAddress",), {}
        )
        self.assertEqual(method, "eth_getBalance")
        self.assertEqual(params, ["0xUserAddress", "latest"])

    def test_get_balance_alias_routes_same(self):
        method, _ = self.g._build_tool_intent("get_balance", ("0xAnother",), {})
        self.assertEqual(method, "eth_getBalance")

    # ---- Other categories ----

    def test_price_tool_emits_eth_call(self):
        method, params = self.g._build_tool_intent("get_price", ("0xPool",), {})
        self.assertEqual(method, "eth_call")
        self.assertEqual(params[0]["to"], "0xPool")

    def test_sign_tool_emits_signTypedData(self):
        td = {"primaryType": "Permit", "domain": {}}
        method, params = self.g._build_tool_intent("sign_permit", (td,), {})
        self.assertEqual(method, "eth_signTypedData_v4")
        self.assertEqual(params["typed_data"], td)

    def test_swap_emits_eth_sendTransaction(self):
        method, params = self.g._build_tool_intent(
            "swap_tokens", ("0xRouter",), {}
        )
        self.assertEqual(method, "eth_sendTransaction")
        self.assertEqual(params["to"], "0xRouter")

    # ---- Negative path ----

    def test_unknown_tool_returns_unknown(self):
        method, params = self.g._build_tool_intent("totally_random_fn", (), {})
        self.assertEqual(method, "unknown")
        self.assertEqual(params["function"], "totally_random_fn")


if __name__ == "__main__":
    unittest.main()
