"""
e_AI v2 Local RPC Proxy

HTTP JSON-RPC proxy that sits between wallet and local node.
Forwards all requests while running profile-based analysis on
accumulated state.

Profiles active:
  - rpc_leakage: detects query patterns that reveal strategy
  - cross_protocol_risk: accumulates portfolio state from reads
  - l2_anonymity_set: tracks pool sizes from log queries

Usage:
    # Start proxy (forwards to local Helios or node)
    python -m proxy.rpc_proxy --upstream http://localhost:8545 --port 8546

    # Point wallet to proxy
    # MetaMask → Settings → Networks → RPC URL: http://localhost:8546

    # With all profiles:
    python -m proxy.rpc_proxy --upstream http://localhost:8545 --profiles domains/

    # Dry run (log only, don't block):
    python -m proxy.rpc_proxy --upstream http://localhost:8545 --dry-run
"""

from __future__ import annotations

import json
import sys
import time
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any
import httpx
from collections import defaultdict
from dataclasses import dataclass, field

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("rpc_proxy")


# ---------------------------------------------------------------------------
# Alert system
# ---------------------------------------------------------------------------

@dataclass
class Alert:
    profile: str
    heuristic: str
    severity: str
    confidence: float
    signal: str
    recommendation: str


@dataclass
class ProxyState:
    """Accumulated state from RPC queries."""
    # RPC leakage tracking
    query_log: list[dict] = field(default_factory=list)
    balance_addresses: set = field(default_factory=set)
    call_targets: dict = field(default_factory=lambda: defaultdict(int))

    # Cross-protocol risk tracking
    known_positions: dict = field(default_factory=dict)  # address → {protocol → value}

    # L2 anonymity set tracking
    pool_queries: list[dict] = field(default_factory=list)

    # Stats
    total_requests: int = 0
    total_alerts: int = 0
    start_time: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Profile-based analysis
# ---------------------------------------------------------------------------

def analyze_request(method: str, params: list, state: ProxyState) -> list[Alert]:
    """Analyze an RPC request against loaded profiles."""
    alerts = []
    state.total_requests += 1

    # Log query
    state.query_log.append({
        "method": method,
        "time": time.time(),
        "params_summary": str(params)[:200] if params else "",
    })

    # Prune old entries (keep last 5 min)
    cutoff = time.time() - 300
    state.query_log = [q for q in state.query_log if q["time"] > cutoff]

    # --- rpc_leakage checks ---

    # H1: Balance checks linking addresses
    if method == "eth_getBalance" and params:
        addr = params[0] if isinstance(params[0], str) else ""
        if addr:
            state.balance_addresses.add(addr.lower())
            if len(state.balance_addresses) > 3:
                alerts.append(Alert(
                    profile="rpc_leakage",
                    heuristic="H1",
                    severity="high",
                    confidence=0.8,
                    signal=f"Balance checked for {len(state.balance_addresses)} addresses in 5 min window — these are now linked by your RPC provider",
                    recommendation="Use local light client (Helios) to avoid leaking address relationships",
                ))

    # H2: Position monitoring (repeated eth_call)
    if method == "eth_call" and params:
        target = params[0].get("to", "") if isinstance(params[0], dict) else ""
        if target:
            state.call_targets[target.lower()] += 1
            if state.call_targets[target.lower()] > 5:
                alerts.append(Alert(
                    profile="rpc_leakage",
                    heuristic="H2",
                    severity="medium",
                    confidence=0.6,
                    signal=f"eth_call to {target[:16]}... called {state.call_targets[target.lower()]}x in 5 min — reveals position monitoring",
                    recommendation="Reduce polling frequency or use local node",
                ))

    # H3: Pre-trade simulation
    if method == "eth_estimateGas" and params:
        data = params[0].get("data", "") if isinstance(params[0], dict) else ""
        if data and len(data) > 10:
            selector = data[:10]
            # Common swap selectors
            swap_selectors = {"0x38ed1739", "0x7ff36ab5", "0x18cbafe5", "0x5c11d795", "0x8803dbee"}
            if selector in swap_selectors:
                alerts.append(Alert(
                    profile="rpc_leakage",
                    heuristic="H3",
                    severity="high",
                    confidence=0.75,
                    signal="Gas estimation for swap transaction — RPC provider knows you're about to trade before you submit",
                    recommendation="Simulate swaps locally or use private RPC",
                ))

    # --- cross_protocol_risk checks (accumulate from eth_call responses) ---
    # This would parse call results to build portfolio picture.
    # Simplified: just count unique protocols queried.
    if method == "eth_call" and params:
        target = (params[0].get("to", "") if isinstance(params[0], dict) else "").lower()
        if target:
            state.known_positions[target] = state.known_positions.get(target, 0) + 1
            # H3: concentration check
            total_calls = sum(state.known_positions.values())
            if total_calls > 10:
                max_protocol = max(state.known_positions, key=state.known_positions.get)
                max_pct = state.known_positions[max_protocol] / total_calls
                if max_pct > 0.7:
                    alerts.append(Alert(
                        profile="cross_protocol_risk",
                        heuristic="H3",
                        severity="medium",
                        confidence=0.5,
                        signal=f"{max_pct:.0%} of your contract calls target {max_protocol[:16]}... — potential concentration risk",
                        recommendation="Monitor exposure across protocols",
                    ))

    # --- l2_anonymity_set checks ---
    if method == "eth_getLogs" and params:
        filter_params = params[0] if isinstance(params[0], dict) else {}
        address = filter_params.get("address", "")
        if address:
            state.pool_queries.append({
                "address": address,
                "time": time.time(),
            })

    state.total_alerts += len(alerts)
    return alerts


def analyze_response(method: str, params: list, result: Any, state: ProxyState) -> list[Alert]:
    """Analyze an RPC response (for state accumulation)."""
    alerts = []

    # l2_anonymity_set: check pool sizes from getLogs results
    if method == "eth_getLogs" and isinstance(result, list):
        log_count = len(result)
        if log_count < 20 and state.pool_queries:
            last_query = state.pool_queries[-1]
            alerts.append(Alert(
                profile="l2_anonymity_set",
                heuristic="H1",
                severity="high" if log_count < 5 else "medium",
                confidence=0.7,
                signal=f"Pool at {last_query['address'][:16]}... has only {log_count} events — thin anonymity set",
                recommendation="Wait for more pool activity before transacting",
            ))

    return alerts


# ---------------------------------------------------------------------------
# HTTP Handler
# ---------------------------------------------------------------------------

class RPCProxyHandler(BaseHTTPRequestHandler):
    upstream: str = "http://localhost:8545"
    state: ProxyState = ProxyState()
    dry_run: bool = False

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            request = json.loads(body)
        except json.JSONDecodeError:
            self._send_error(400, "Invalid JSON")
            return

        method = request.get("method", "")
        params = request.get("params", [])
        req_id = request.get("id", 1)

        # Pre-request analysis
        pre_alerts = analyze_request(method, params, self.state)

        # Log alerts
        for alert in pre_alerts:
            level = "WARNING" if alert.severity in ("critical", "high") else "INFO"
            log.log(
                logging.WARNING if level == "WARNING" else logging.INFO,
                f"[{alert.profile}/{alert.heuristic}] {alert.severity}: {alert.signal}"
            )
            if alert.recommendation:
                log.info(f"  → {alert.recommendation}")

        # Block critical if not dry-run
        critical = [a for a in pre_alerts if a.severity == "critical" and a.confidence > 0.8]
        if critical and not self.dry_run:
            error_msg = "; ".join(f"[{a.heuristic}] {a.signal}" for a in critical)
            self._send_json({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32000, "message": f"e_AI Guard blocked: {error_msg}"},
            })
            return

        # Forward to upstream
        try:
            client = httpx.Client(timeout=30)
            resp = client.post(
                self.upstream,
                content=body,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            response = resp.json()
        except (httpx.HTTPError, json.JSONDecodeError) as e:
            self._send_error(502, f"Upstream error: {e}")
            return

        # Post-response analysis
        result = response.get("result")
        post_alerts = analyze_response(method, params, result, self.state)
        for alert in post_alerts:
            log.log(
                logging.WARNING if alert.severity in ("critical", "high") else logging.INFO,
                f"[{alert.profile}/{alert.heuristic}] {alert.severity}: {alert.signal}"
            )

        # Return response to client
        self._send_json(response)

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()

    def _send_json(self, data: dict):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, code: int, message: str):
        body = json.dumps({
            "jsonrpc": "2.0",
            "id": None,
            "error": {"code": -32000, "message": message},
        }).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _set_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, format, *args):
        """Suppress default HTTP logging — we use our own logger."""
        pass


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

def run_proxy(
    upstream: str = "http://localhost:8545",
    port: int = 8546,
    dry_run: bool = False,
):
    """Start the RPC proxy server."""
    RPCProxyHandler.upstream = upstream
    RPCProxyHandler.state = ProxyState()
    RPCProxyHandler.dry_run = dry_run

    server = HTTPServer(("127.0.0.1", port), RPCProxyHandler)

    log.info(f"e_AI RPC Proxy started")
    log.info(f"  Listening: http://127.0.0.1:{port}")
    log.info(f"  Upstream:  {upstream}")
    log.info(f"  Mode:      {'dry-run (log only)' if dry_run else 'active (will block critical)'}")
    log.info(f"  Profiles:  rpc_leakage, cross_protocol_risk, l2_anonymity_set")
    log.info(f"  Point your wallet RPC to: http://127.0.0.1:{port}")
    log.info(f"")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        state = RPCProxyHandler.state
        elapsed = time.time() - state.start_time
        log.info(f"\nProxy stopped. Stats:")
        log.info(f"  Uptime: {elapsed:.0f}s")
        log.info(f"  Requests: {state.total_requests}")
        log.info(f"  Alerts: {state.total_alerts}")
        log.info(f"  Unique addresses seen: {len(state.balance_addresses)}")
        log.info(f"  Unique contracts called: {len(state.known_positions)}")
        server.server_close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="e_AI v2 Local RPC Proxy")
    parser.add_argument("--upstream", default="http://localhost:8545",
                        help="Upstream RPC URL (Helios, local node, etc.)")
    parser.add_argument("--port", type=int, default=8546,
                        help="Proxy listen port (default: 8546)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Log only, don't block any requests")
    args = parser.parse_args()

    run_proxy(args.upstream, args.port, args.dry_run)
