"""
e_AI v2 AI Agent Guard — intercepts agent tool calls before execution.

STATUS: ILLUSTRATIVE ADAPTER, NOT a profile-driven runtime.
Per Codex 2026-05-07 review, the demo's two advertised risky
scenarios ("Agent approves unlimited tokens" and "Agent checks 5
wallet balances") currently DO NOT emit warnings — the decorator
maps approval-tool intent to `eth_sendTransaction` but only passes
function metadata, not calldata; balance-check tool maps to
`eth_call` but the rpc_leakage detector counts only `eth_getBalance`.
Plus the loader globs `domains/*/profile.json` indiscriminately,
including v1 variants (loads 22 profiles, not 16). Hardening + tool-
intent adapter wiring is queued. Treat this file as a pattern
reference for how an agent guard would integrate, not as the
canonical agent runtime. See README "Integration demos (status:
illustrative adapters)" section.

Works with any agent framework (LangChain, OpenAI function calling,
custom agents). Wraps tool execution with profile-based risk analysis.

For AI access method: the agent queries on-chain data and submits
transactions on behalf of the user. The guard checks both:
  1. Query patterns (rpc_leakage profile) — does the query reveal strategy?
  2. Transaction intent (approval_phishing, etc.) — is the action safe?

Usage:
    from examples.ai_agent.guard import AgentGuard

    guard = AgentGuard(profiles_dir="domains/")

    # Wrap tool execution
    @guard.check
    def execute_swap(token_in, token_out, amount):
        ...

    # Or check manually
    alerts = guard.check_action("eth_sendTransaction", {...})
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Any


@dataclass
class Alert:
    profile: str
    heuristic: str
    severity: str
    confidence: float
    signal: str
    recommendation: str


@dataclass
class GuardResult:
    action: str  # "pass" | "warn" | "block"
    alerts: list[Alert] = field(default_factory=list)


class AgentGuard:
    """Guards AI agent actions against e_AI v2 profiles."""

    def __init__(
        self,
        profiles_dir: str = "domains/",
        block_on_critical: bool = True,
    ):
        self.profiles = self._load_profiles(profiles_dir)
        self.block_on_critical = block_on_critical
        self.rpc_log: list[dict] = []

    # Skip set: _template + _feedback + 6 v1 sanitization variants (Part 3
    # supporting material, not v2 production guards). Per docs/v1_variants.md.
    _SKIP_DOMAINS = {
        "_template",
        "_feedback",
        "defi",
        "defi_14b",
        "defi_bootstrap",
        "defi_claude",
        "defi_generated",
        "defi_websearch",
    }

    def _load_profiles(self, profiles_dir: str) -> dict[str, dict]:
        """Load v2 production profile.json files from domain directories."""
        profiles = {}
        base = Path(profiles_dir)
        for domain_dir in sorted(base.iterdir()):
            if not domain_dir.is_dir():
                continue
            if domain_dir.name in self._SKIP_DOMAINS:
                continue
            profile_path = domain_dir / "profile.json"
            if profile_path.exists():
                with open(profile_path) as f:
                    profiles[domain_dir.name] = json.load(f)
        return profiles

    def check_action(self, method: str, params: dict) -> GuardResult:
        """Check an agent action against all relevant profiles.

        Args:
            method: "eth_sendTransaction", "eth_signTypedData", "eth_call", etc.
            params: Method-specific parameters

        Returns:
            GuardResult with action (pass/warn/block) and alerts
        """
        alerts = []

        # Transaction checks
        if method == "eth_sendTransaction":
            alerts.extend(self._check_tx(params))

        # Signature checks
        if method in ("eth_signTypedData_v4", "eth_signTypedData"):
            alerts.extend(self._check_signature(params))

        # RPC pattern checks
        if method in ("eth_getBalance", "eth_call", "eth_getLogs"):
            self.rpc_log.append({"method": method, "params": params, "time": time.time()})
            alerts.extend(self._check_rpc_pattern())

        # Determine action
        has_critical = any(a.severity == "critical" and a.confidence > 0.8 for a in alerts)
        if has_critical and self.block_on_critical:
            action = "block"
        elif alerts:
            action = "warn"
        else:
            action = "pass"

        return GuardResult(action=action, alerts=alerts)

    # ABI selectors for tool-intent → calldata adaptation
    _APPROVE_SELECTOR = "0x095ea7b3"  # approve(address,uint256)
    _MAX_UINT256_HEX = "f" * 64

    def _build_tool_intent(self, fn_name: str, args: tuple, kwargs: dict) -> tuple[str, dict]:
        """Translate an agent tool call into (rpc_method, params) the guard
        can analyze. Adapter — tool intent → RPC-shaped params.

        Specifically handles:
          - approval tools: build calldata so _check_tx sees a real
            unlimited-approval pattern, not just function metadata
          - balance tools: emit eth_getBalance with the queried address
            so _check_rpc_pattern can count balance-checked addresses
          - signing tools: pass typed-data through
          - other transaction tools: emit eth_sendTransaction with
            best-effort target inference
        """
        fn_lower = fn_name.lower()

        # Approval tools: approve_token(token, spender, amount)
        if "approve" in fn_lower and len(args) >= 2:
            token = str(args[0]) if len(args) > 0 else kwargs.get("token", "0x")
            spender = str(args[1]) if len(args) > 1 else kwargs.get("spender", "0x")
            amount = args[2] if len(args) > 2 else kwargs.get("amount", "")
            # Build calldata: selector + spender (32B left-pad) + amount (32B left-pad)
            spender_hex = spender.lower().replace("0x", "").rjust(64, "0")
            if isinstance(amount, str) and amount.lower() == "unlimited":
                amount_hex = self._MAX_UINT256_HEX
            else:
                try:
                    amt_int = int(amount) if not isinstance(amount, int) else amount
                    amount_hex = format(amt_int, "x").rjust(64, "0")
                except (TypeError, ValueError):
                    amount_hex = self._MAX_UINT256_HEX  # be conservative
            data = self._APPROVE_SELECTOR + spender_hex + amount_hex
            return "eth_sendTransaction", {"to": token, "data": data, "_tool": fn_name}

        # Balance tools: check_balance(address) → eth_getBalance, NOT eth_call
        # (the rpc_leakage pattern detector counts eth_getBalance specifically).
        if any(w in fn_lower for w in ["balance", "get_balance"]):
            address = str(args[0]) if args else kwargs.get("address", "")
            return "eth_getBalance", [address, "latest"]

        # Position / price tools → eth_call against an address
        if any(w in fn_lower for w in ["price", "position"]):
            target = str(args[0]) if args else kwargs.get("target", "")
            return "eth_call", [{"to": target, "data": "0x"}, "latest"]

        # Signing tools
        if any(w in fn_lower for w in ["sign", "permit"]):
            typed = args[0] if args and isinstance(args[0], dict) else kwargs.get("typed_data", {})
            return "eth_signTypedData_v4", {"typed_data": typed}

        # Generic transaction tools (swap/transfer/send/stake/deposit/withdraw)
        if any(w in fn_lower for w in ["swap", "transfer", "send", "stake", "deposit", "withdraw"]):
            target = str(args[0]) if args else kwargs.get("to", "")
            return "eth_sendTransaction", {"to": target, "data": "0x", "_tool": fn_name}

        return "unknown", {"function": fn_name, "args": args, "kwargs": kwargs}

    def check(self, fn: Callable) -> Callable:
        """Decorator that checks agent tool calls before execution.

        The decorator translates tool intent into RPC-shaped params so the
        underlying analyzers (`_check_tx`, `_check_rpc_pattern`,
        `_check_signature`) see realistic input. Previously the wrapper
        passed only function metadata (name + args), which silently
        bypassed every detector.
        """
        def wrapper(*args, **kwargs):
            fn_name = fn.__name__
            method, params = self._build_tool_intent(fn_name, args, kwargs)

            result = self.check_action(method, params)

            if result.action == "block":
                raise RuntimeError(
                    f"AgentGuard BLOCKED {fn_name}: "
                    + "; ".join(f"[{a.heuristic}] {a.signal}" for a in result.alerts)
                )

            if result.action == "warn":
                print(f"  [AgentGuard] WARNING for {fn_name}:")
                for a in result.alerts:
                    print(f"    [{a.profile}/{a.heuristic}] {a.signal}")

            return fn(*args, **kwargs)
        return wrapper

    def _check_tx(self, params: dict) -> list[Alert]:
        """Check transaction against approval/governance/bridge profiles."""
        alerts = []
        data = params.get("data", "")
        to = params.get("to", "")

        if not data or len(data) < 10:
            return alerts

        selector = data[:10] if data.startswith("0x") else "0x" + data[:8]

        # Unlimited approval
        if selector in ("0x095ea7b3", "0x39509351"):
            if "ffffffff" in data.lower():
                alerts.append(Alert(
                    profile="approval_phishing", heuristic="H1",
                    severity="high", confidence=0.95,
                    signal=f"Agent approving unlimited tokens to {to}",
                    recommendation="Limit approval to exact amount needed",
                ))

        return alerts

    def _check_signature(self, params: dict) -> list[Alert]:
        """Check signature against offchain_signature profile."""
        alerts = []
        typed_data = params.get("typed_data", params)

        primary_type = ""
        if isinstance(typed_data, dict):
            primary_type = typed_data.get("primaryType", "")

        if primary_type in ("PermitSingle", "PermitBatch"):
            alerts.append(Alert(
                profile="offchain_signature", heuristic="H1",
                severity="high", confidence=0.9,
                signal=f"Agent signing {primary_type} — authorizes token transfer off-chain",
                recommendation="Verify spender and amount. Set short expiration.",
            ))

        return alerts

    def _check_rpc_pattern(self) -> list[Alert]:
        """Check RPC query patterns against rpc_leakage profile."""
        alerts = []
        cutoff = time.time() - 300  # 5 min window
        recent = [q for q in self.rpc_log if q["time"] > cutoff]

        # Multiple balance checks. eth_getBalance can carry params as
        # either a list ([address, block]) or a dict ({"address": ...});
        # handle both shapes safely.
        balance_targets = set()
        for q in recent:
            if q["method"] == "eth_getBalance":
                p = q.get("params", None)
                addr = ""
                if isinstance(p, dict):
                    addr = p.get("address", "")
                elif isinstance(p, list) and p:
                    addr = p[0] if isinstance(p[0], str) else ""
                if addr:
                    balance_targets.add(addr)

        if len(balance_targets) > 3:
            alerts.append(Alert(
                profile="rpc_leakage", heuristic="H1",
                severity="high", confidence=0.8,
                signal=f"Agent checked balances for {len(balance_targets)} addresses — links them to same user",
                recommendation="Use local light client or batch through Tor",
            ))

        return alerts


# --- Demo ---

def demo():
    print("=" * 60)
    print("e_AI v2 AI Agent Guard Demo")
    print("=" * 60)

    guard = AgentGuard(profiles_dir="domains/")
    print(f"Loaded {len(guard.profiles)} profiles")

    # Simulate agent tools
    @guard.check
    def approve_token(token: str, spender: str, amount: str):
        print(f"  [Agent] Approving {amount} {token} to {spender}")
        return True

    @guard.check
    def check_balance(address: str):
        print(f"  [Agent] Checking balance of {address}")
        return 100.0

    @guard.check
    def execute_swap(token_in: str, token_out: str, amount: float):
        print(f"  [Agent] Swapping {amount} {token_in} → {token_out}")
        return True

    # Scenario 1: Agent tries unlimited approval
    print("\n--- Scenario 1: Agent approves unlimited tokens ---")
    try:
        approve_token("USDC", "0xunknown", "unlimited")
    except RuntimeError as e:
        print(f"  BLOCKED: {e}")

    # Scenario 2: Agent checks multiple balances (RPC leakage)
    print("\n--- Scenario 2: Agent checks 5 wallet balances ---")
    for addr in ["0xaaa", "0xbbb", "0xccc", "0xddd", "0xeee"]:
        check_balance(addr)

    # Scenario 3: Normal swap (should pass)
    print("\n--- Scenario 3: Agent executes normal swap ---")
    execute_swap("ETH", "USDC", 1.0)

    print("\n" + "=" * 60)


if __name__ == "__main__":
    demo()
