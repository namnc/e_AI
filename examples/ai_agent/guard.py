"""
e_AI v2 AI Agent Guard — intercepts agent tool calls before execution.

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

    def _load_profiles(self, profiles_dir: str) -> dict[str, dict]:
        """Load all profile.json files from domain directories."""
        profiles = {}
        base = Path(profiles_dir)
        for domain_dir in base.iterdir():
            if domain_dir.is_dir() and domain_dir.name != "_template":
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

    def check(self, fn: Callable) -> Callable:
        """Decorator that checks agent tool calls before execution."""
        def wrapper(*args, **kwargs):
            # Try to infer the action type from function name and args
            fn_name = fn.__name__.lower()

            # Map common agent tool names to methods
            if any(word in fn_name for word in ["swap", "transfer", "send", "approve", "stake", "deposit"]):
                method = "eth_sendTransaction"
            elif any(word in fn_name for word in ["sign", "permit"]):
                method = "eth_signTypedData_v4"
            elif any(word in fn_name for word in ["balance", "price", "position"]):
                method = "eth_call"
            else:
                method = "unknown"

            result = self.check_action(method, {"function": fn_name, "args": args, "kwargs": kwargs})

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

        # Multiple balance checks
        balance_targets = set()
        for q in recent:
            if q["method"] == "eth_getBalance":
                p = q.get("params", {})
                addr = p.get("address", p[0] if isinstance(p, list) and p else "")
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
