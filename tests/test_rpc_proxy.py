"""
RPC proxy hardening tests.

Covers the Phase-2 hardening items from the Codex 2026-05-07 review:
  - CORS allowlist (default: disabled; explicit allowlist required)
  - JSON-RPC batch handling (list payload returns list response)
  - Body-size cap (4 MB) → 413
  - --dry-run does NOT forward to upstream
  - Auth-token gate (Bearer required when --auth-token set)
  - State-pruning over the 5-minute window (balance_address_seen,
    call_target_log, known_position_log, pool_queries — not just query_log)
  - Pre-trade swap selectors trigger rpc_leakage H3

Wired as `python -m unittest tests.test_rpc_proxy -v` from CI.
"""
from __future__ import annotations

import json
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import MagicMock

import httpx

from proxy.rpc_proxy import (
    MAX_BODY_BYTES,
    ProxyState,
    RPCProxyHandler,
    analyze_request,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _RecordingUpstream(BaseHTTPRequestHandler):
    """Tiny upstream that records the last body and returns a canned response."""

    received_bodies: list[bytes] = []
    canned_response: bytes = b'{"jsonrpc":"2.0","id":1,"result":"0x1"}'

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(n)
        type(self).received_bodies.append(body)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(self.canned_response)))
        self.end_headers()
        self.wfile.write(self.canned_response)

    def log_message(self, *a, **kw):
        pass


def _start_server(handler_cls, port: int) -> HTTPServer:
    server = HTTPServer(("127.0.0.1", port), handler_cls)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server


def _free_port() -> int:
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _configure_handler(
    *,
    upstream: str,
    dry_run: bool = False,
    allowed_origins: tuple[str, ...] = (),
    auth_token: str | None = None,
):
    """Reset the class-level config on RPCProxyHandler before each test."""
    RPCProxyHandler.upstream = upstream
    RPCProxyHandler.state = ProxyState()
    RPCProxyHandler.dry_run = dry_run
    RPCProxyHandler.allowed_origins = allowed_origins
    RPCProxyHandler.auth_token = auth_token
    RPCProxyHandler.http_client = httpx.Client(timeout=5)


# ---------------------------------------------------------------------------
# Pure-state tests (no server)
# ---------------------------------------------------------------------------

class TestStatePruning(unittest.TestCase):
    """Verify the 5-minute window prunes ALL time-keyed maps, not just query_log."""

    def test_old_entries_pruned_across_all_maps(self):
        state = ProxyState()
        old = time.time() - 600  # 10 minutes ago

        # Seed every time-keyed structure with a stale entry.
        state.query_log.append({"method": "eth_chainId", "time": old, "params_summary": ""})
        state.balance_address_seen["0xstale"] = old
        state.call_target_log.append({"target": "0xstale", "time": old})
        state.known_position_log.append({"target": "0xstale", "time": old})
        state.pool_queries.append({"address": "0xstale", "time": old})

        # Trigger a cheap analyze_request — it runs the prune step.
        analyze_request("eth_chainId", [], state)

        self.assertNotIn("0xstale", state.balance_address_seen,
                         "balance_address_seen should be pruned to 5-min window")
        self.assertEqual(state.call_target_log, [],
                         "call_target_log should be pruned to 5-min window")
        self.assertEqual(state.known_position_log, [],
                         "known_position_log should be pruned to 5-min window")
        self.assertEqual(state.pool_queries, [],
                         "pool_queries should be pruned to 5-min window")
        # query_log: only the stale one was inserted; new analyze_request adds
        # the chainId entry, so length is 1 (the new one).
        self.assertTrue(all(q["time"] > old for q in state.query_log))


class TestAnalyzeRequest(unittest.TestCase):
    def test_balance_address_linkage_h1(self):
        state = ProxyState()
        # 4 distinct addresses → triggers H1 (>3)
        for i in range(4):
            alerts = analyze_request("eth_getBalance", [f"0x{i:040x}", "latest"], state)
        self.assertTrue(
            any(a.heuristic == "H1" and a.profile == "rpc_leakage" for a in alerts),
            "4 balance addresses in window must trigger rpc_leakage H1",
        )

    def test_swap_selector_triggers_h3(self):
        state = ProxyState()
        # Uniswap V2 swapExactTokensForTokens selector
        params = [{"to": "0xrouter", "data": "0x38ed1739" + "00" * 100}]
        alerts = analyze_request("eth_estimateGas", params, state)
        self.assertTrue(
            any(a.heuristic == "H3" for a in alerts),
            "swap selector in eth_estimateGas must trigger rpc_leakage H3",
        )

    def test_unknown_method_no_alert(self):
        state = ProxyState()
        alerts = analyze_request("eth_chainId", [], state)
        self.assertEqual(alerts, [])


# ---------------------------------------------------------------------------
# HTTP integration tests (real proxy + recording upstream)
# ---------------------------------------------------------------------------

class TestProxyHTTP(unittest.TestCase):
    """Spin up the proxy + a recording upstream; assert wire behavior."""

    upstream: HTTPServer = None
    proxy: HTTPServer = None
    upstream_port: int = 0
    proxy_port: int = 0

    @classmethod
    def setUpClass(cls):
        cls.upstream_port = _free_port()
        cls.proxy_port = _free_port()
        # Start recording upstream
        _RecordingUpstream.received_bodies = []
        cls.upstream = _start_server(_RecordingUpstream, cls.upstream_port)
        # Configure proxy handler
        _configure_handler(upstream=f"http://127.0.0.1:{cls.upstream_port}")
        cls.proxy = _start_server(RPCProxyHandler, cls.proxy_port)

    @classmethod
    def tearDownClass(cls):
        if cls.proxy:
            cls.proxy.shutdown()
            cls.proxy.server_close()
        if cls.upstream:
            cls.upstream.shutdown()
            cls.upstream.server_close()
        if RPCProxyHandler.http_client:
            RPCProxyHandler.http_client.close()

    def setUp(self):
        # Reset upstream record + state between tests
        _RecordingUpstream.received_bodies = []
        RPCProxyHandler.state = ProxyState()
        # Default: no CORS, no auth, not dry-run
        RPCProxyHandler.allowed_origins = ()
        RPCProxyHandler.auth_token = None
        RPCProxyHandler.dry_run = False

    def _post(self, body, headers=None):
        return httpx.post(
            f"http://127.0.0.1:{self.proxy_port}",
            content=body,
            headers=headers or {"Content-Type": "application/json"},
            timeout=5,
        )

    # ---- CORS ----

    def test_cors_disabled_by_default(self):
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_chainId", "params": []})
        resp = self._post(body, {"Content-Type": "application/json", "Origin": "https://evil.example"})
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("access-control-allow-origin", {k.lower() for k in resp.headers.keys()},
                         "CORS must be DISABLED by default — no ACAO header should be sent")

    def test_cors_allowed_origin_emits_acao(self):
        RPCProxyHandler.allowed_origins = ("https://app.kohaku.app",)
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_chainId", "params": []})
        resp = self._post(body, {"Content-Type": "application/json", "Origin": "https://app.kohaku.app"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get("Access-Control-Allow-Origin"), "https://app.kohaku.app")
        self.assertEqual(resp.headers.get("Vary"), "Origin")

    def test_cors_non_allowlisted_origin_no_acao(self):
        RPCProxyHandler.allowed_origins = ("https://app.kohaku.app",)
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_chainId", "params": []})
        resp = self._post(body, {"Content-Type": "application/json", "Origin": "https://evil.example"})
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("access-control-allow-origin", {k.lower() for k in resp.headers.keys()})

    def test_options_preflight_rejects_non_allowlisted(self):
        RPCProxyHandler.allowed_origins = ("https://app.kohaku.app",)
        resp = httpx.request(
            "OPTIONS",
            f"http://127.0.0.1:{self.proxy_port}",
            headers={"Origin": "https://evil.example"},
            timeout=5,
        )
        self.assertEqual(resp.status_code, 403, "preflight from non-allowlisted origin must 403")

    # ---- Body-size cap ----

    def test_body_cap_rejects_oversized(self):
        big = b'{"jsonrpc":"2.0","id":1,"method":"eth_chainId","params":[' + b'"x",' * (MAX_BODY_BYTES // 4) + b'"x"]}'
        # Slightly above MAX_BODY_BYTES
        self.assertGreater(len(big), MAX_BODY_BYTES)
        resp = self._post(big, {"Content-Type": "application/json"})
        self.assertEqual(resp.status_code, 413)

    # ---- Batch handling ----

    def test_batch_request_returns_list_response(self):
        batch = [
            {"jsonrpc": "2.0", "id": 1, "method": "eth_chainId", "params": []},
            {"jsonrpc": "2.0", "id": 2, "method": "eth_chainId", "params": []},
        ]
        # Upstream needs to return a list to match — set canned response.
        _RecordingUpstream.canned_response = json.dumps([
            {"jsonrpc": "2.0", "id": 1, "result": "0x1"},
            {"jsonrpc": "2.0", "id": 2, "result": "0x1"},
        ]).encode()
        resp = self._post(json.dumps(batch))
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIsInstance(body, list, "batch request must produce list response")
        self.assertEqual(len(body), 2)
        # Restore canned response
        _RecordingUpstream.canned_response = b'{"jsonrpc":"2.0","id":1,"result":"0x1"}'

    def test_empty_batch_returns_400(self):
        resp = self._post(b"[]")
        self.assertEqual(resp.status_code, 400)

    # ---- Dry-run ----

    def test_dry_run_does_not_forward_upstream(self):
        RPCProxyHandler.dry_run = True
        before = len(_RecordingUpstream.received_bodies)
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_chainId", "params": []})
        resp = self._post(body)
        self.assertEqual(resp.status_code, 200)
        after = len(_RecordingUpstream.received_bodies)
        self.assertEqual(before, after, "dry-run must NOT forward to upstream")
        # Synthetic dry-run flag in body
        body_json = resp.json()
        self.assertTrue(body_json.get("_e_ai_dry_run"))

    # ---- Auth token ----

    def test_auth_token_required_when_set(self):
        RPCProxyHandler.auth_token = "secret123"
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_chainId", "params": []})
        # No Authorization header → 401
        resp = self._post(body)
        self.assertEqual(resp.status_code, 401)
        # Wrong scheme → 401
        resp = self._post(body, {"Content-Type": "application/json", "Authorization": "Basic xxx"})
        self.assertEqual(resp.status_code, 401)
        # Correct token → 200
        resp = self._post(body, {"Content-Type": "application/json", "Authorization": "Bearer secret123"})
        self.assertEqual(resp.status_code, 200)


if __name__ == "__main__":
    unittest.main()
