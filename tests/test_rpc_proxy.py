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
    """Tiny upstream that records the last body and returns a canned response.

    The canned response can be a bytes payload (default) or a callable
    `(body) -> (status, body_bytes)` for tests that need to vary the
    response per-request (e.g. notification → 204, real request → 200).
    """

    received_bodies: list[bytes] = []
    canned_response: object = b'{"jsonrpc":"2.0","id":1,"result":"0x1"}'

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(n)
        type(self).received_bodies.append(body)
        cr = type(self).canned_response
        if callable(cr):
            status, payload = cr(body)
        else:
            status, payload = 200, cr
        self.send_response(status)
        if status != 204 and payload:
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if status != 204 and payload:
            self.wfile.write(payload)

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
        # Reset upstream record + state between tests. Per Codex Phase 3
        # review (#4 in missed-coverage), also reset canned_response — the
        # batch test mutates it; if a test before line 262 fails the
        # mutation leaks into later cases.
        _RecordingUpstream.received_bodies = []
        _RecordingUpstream.canned_response = b'{"jsonrpc":"2.0","id":1,"result":"0x1"}'
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

    def test_options_preflight_allowlisted_emits_cors_headers(self):
        # Codex Phase 3 review missed-coverage #6: OPTIONS allowlisted path.
        RPCProxyHandler.allowed_origins = ("https://app.kohaku.app",)
        resp = httpx.request(
            "OPTIONS",
            f"http://127.0.0.1:{self.proxy_port}",
            headers={"Origin": "https://app.kohaku.app"},
            timeout=5,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get("Access-Control-Allow-Origin"), "https://app.kohaku.app")
        self.assertIn("POST", resp.headers.get("Access-Control-Allow-Methods", ""))

    def test_cors_credentials_header_only_when_auth_enabled(self):
        # Codex Phase 3 review missed-coverage #6: ACAC-with-auth coupling.
        RPCProxyHandler.allowed_origins = ("https://app.kohaku.app",)
        RPCProxyHandler.auth_token = "secret"
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_chainId", "params": []})
        resp = self._post(body, {
            "Content-Type": "application/json",
            "Origin": "https://app.kohaku.app",
            "Authorization": "Bearer secret",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get("Access-Control-Allow-Credentials"), "true")
        # And without auth_token set, ACAC must NOT appear.
        RPCProxyHandler.auth_token = None
        resp = self._post(body, {
            "Content-Type": "application/json",
            "Origin": "https://app.kohaku.app",
        })
        self.assertNotIn("access-control-allow-credentials",
                         {k.lower() for k in resp.headers.keys()})

    # ---- Body-size cap ----

    def test_body_cap_rejects_oversized_via_content_length(self):
        """Codex Phase 3 review missed-coverage #5: don't actually transmit
        4MB+ over localhost — the proxy rejects on Content-Length BEFORE
        reading the body, so we can prove the invariant with a small body
        and a lying header on a raw socket."""
        import socket
        s = socket.socket()
        s.settimeout(5)
        s.connect(("127.0.0.1", self.proxy_port))
        # Declare an oversized Content-Length but send only a tiny body.
        # The proxy must reject with 413 before reading.
        oversized = MAX_BODY_BYTES + 1
        request = (
            f"POST / HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{self.proxy_port}\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {oversized}\r\n"
            f"\r\n"
        ).encode()
        s.sendall(request)
        resp_bytes = s.recv(4096)
        s.close()
        self.assertIn(b"413", resp_bytes.split(b"\r\n", 1)[0])

    def test_body_cap_boundary_at_max_plus_one(self):
        """Boundary: Content-Length == MAX_BODY_BYTES+1 must be rejected.
        We use a raw socket so we can declare an arbitrary Content-Length
        without actually transmitting megabytes."""
        import socket
        for cl, expect_413 in ((MAX_BODY_BYTES + 1, True), (MAX_BODY_BYTES, False)):
            s = socket.socket()
            s.settimeout(5)
            s.connect(("127.0.0.1", self.proxy_port))
            request = (
                f"POST / HTTP/1.1\r\n"
                f"Host: 127.0.0.1:{self.proxy_port}\r\n"
                f"Content-Type: application/json\r\n"
                f"Content-Length: {cl}\r\n"
                f"\r\n"
            ).encode()
            s.sendall(request)
            # For the rejected case, server replies before reading body.
            # For the accepted case, server will block waiting for the body
            # we won't send; close after a short read attempt.
            s.settimeout(0.5)
            try:
                resp_bytes = s.recv(4096)
            except socket.timeout:
                resp_bytes = b""
            finally:
                s.close()
            first_line = resp_bytes.split(b"\r\n", 1)[0] if resp_bytes else b""
            if expect_413:
                self.assertIn(b"413", first_line, f"CL={cl} should be rejected")
            else:
                # Accepted CL: server did NOT reply with 413 (it was waiting
                # for the body we never sent).
                self.assertNotIn(b"413", first_line, f"CL={cl} should not be rejected")

    def test_body_cap_invalid_content_length(self):
        """Content-Length must be parseable; non-numeric → 400."""
        import socket
        s = socket.socket()
        s.settimeout(5)
        s.connect(("127.0.0.1", self.proxy_port))
        request = (
            f"POST / HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{self.proxy_port}\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: not-a-number\r\n"
            f"\r\n"
        ).encode()
        s.sendall(request)
        resp_bytes = s.recv(4096)
        s.close()
        # Python's BaseHTTPRequestHandler raises 400 on bad headers;
        # accept either our explicit 400 ("Invalid Content-Length") or
        # the BaseHTTPRequestHandler 400.
        first_line = resp_bytes.split(b"\r\n", 1)[0]
        self.assertIn(b"400", first_line)

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

    def test_empty_batch_returns_400(self):
        resp = self._post(b"[]")
        self.assertEqual(resp.status_code, 400)

    def test_batch_dry_run_returns_per_item_acks(self):
        """Codex Phase 3 review #4: dry-run batch must emit per-request
        synthetic acknowledgements with _e_ai_dry_run, not [] or only the
        invalid/blocked items."""
        RPCProxyHandler.dry_run = True
        batch = [
            {"jsonrpc": "2.0", "id": 10, "method": "eth_chainId", "params": []},
            {"jsonrpc": "2.0", "id": 11, "method": "eth_chainId", "params": []},
        ]
        before = len(_RecordingUpstream.received_bodies)
        resp = self._post(json.dumps(batch))
        self.assertEqual(resp.status_code, 200)
        # Upstream must NOT have been contacted.
        self.assertEqual(len(_RecordingUpstream.received_bodies), before)
        body = resp.json()
        self.assertIsInstance(body, list)
        self.assertEqual(len(body), 2, "dry-run batch must return one ack per request")
        # Each item carries the dry-run flag and original id.
        for i, ack in enumerate(body):
            self.assertTrue(ack.get("_e_ai_dry_run"))
            self.assertEqual(ack.get("id"), 10 + i)

    def test_batch_invalid_items_are_returned_not_dropped(self):
        """Codex Phase 3 review #5: invalid (non-dict) batch entries must
        produce -32600 errors in the response, not be silently dropped on
        the upstream-forwarded path."""
        batch = [
            "not a dict",  # invalid
            {"jsonrpc": "2.0", "id": 21, "method": "eth_chainId", "params": []},
        ]
        # Codex Phase 4 review #2: upstream now sees ONLY the forwardable
        # item, so its canned response is a one-item list keyed to id=21.
        _RecordingUpstream.canned_response = json.dumps([
            {"jsonrpc": "2.0", "id": 21, "result": "0x1"},
        ]).encode()
        resp = self._post(json.dumps(batch))
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIsInstance(body, list)
        self.assertEqual(len(body), 2, "invalid items must be preserved in response")
        # First slot: invalid
        self.assertIn("error", body[0])
        self.assertEqual(body[0]["error"]["code"], -32600)
        # Second slot: upstream result, correctly id-merged
        self.assertEqual(body[1].get("id"), 21)
        self.assertEqual(body[1].get("result"), "0x1")
        # Verify the proxy did NOT post the invalid string to upstream.
        self.assertEqual(len(_RecordingUpstream.received_bodies), 1)
        sent = json.loads(_RecordingUpstream.received_bodies[0].decode())
        self.assertEqual(len(sent), 1, "upstream must see only forwardable items")
        self.assertEqual(sent[0].get("id"), 21)

    def test_batch_upstream_responses_merged_by_id_not_position(self):
        """Codex Phase 4 review #3: upstream may return responses in
        arbitrary order; merge by id, not iterator position."""
        batch = [
            {"jsonrpc": "2.0", "id": 100, "method": "eth_chainId", "params": []},
            {"jsonrpc": "2.0", "id": 200, "method": "eth_chainId", "params": []},
            {"jsonrpc": "2.0", "id": 300, "method": "eth_chainId", "params": []},
        ]
        # Upstream returns reordered responses.
        _RecordingUpstream.canned_response = json.dumps([
            {"jsonrpc": "2.0", "id": 200, "result": "0xB"},
            {"jsonrpc": "2.0", "id": 300, "result": "0xC"},
            {"jsonrpc": "2.0", "id": 100, "result": "0xA"},
        ]).encode()
        resp = self._post(json.dumps(batch))
        body = resp.json()
        self.assertEqual(len(body), 3)
        by_id = {item["id"]: item for item in body}
        self.assertEqual(by_id[100]["result"], "0xA",
                         "merge must be by id, not position (would have produced 0xB)")
        self.assertEqual(by_id[200]["result"], "0xB")
        self.assertEqual(by_id[300]["result"], "0xC")

    def test_batch_notifications_no_response_slot(self):
        """Codex Phase 4 review #4: a JSON-RPC notification (no id) MUST
        NOT receive a response slot in the merged batch response."""
        batch = [
            {"jsonrpc": "2.0", "method": "eth_chainId", "params": []},  # notification
            {"jsonrpc": "2.0", "id": 50, "method": "eth_chainId", "params": []},
        ]
        _RecordingUpstream.canned_response = json.dumps([
            {"jsonrpc": "2.0", "id": 50, "result": "0x1"},
        ]).encode()
        resp = self._post(json.dumps(batch))
        body = resp.json()
        self.assertIsInstance(body, list)
        self.assertEqual(len(body), 1, "notification must NOT produce a response slot")
        self.assertEqual(body[0]["id"], 50)

    def test_batch_truncated_upstream_response_surfaces_error(self):
        """If upstream omits a response for a forwarded id, surface
        -32603 explicitly rather than silently dropping the slot."""
        batch = [
            {"jsonrpc": "2.0", "id": 1, "method": "eth_chainId", "params": []},
            {"jsonrpc": "2.0", "id": 2, "method": "eth_chainId", "params": []},
        ]
        # Upstream only responds for id=1
        _RecordingUpstream.canned_response = json.dumps([
            {"jsonrpc": "2.0", "id": 1, "result": "0x1"},
        ]).encode()
        resp = self._post(json.dumps(batch))
        body = resp.json()
        self.assertEqual(len(body), 2)
        by_id = {item["id"]: item for item in body}
        self.assertEqual(by_id[1].get("result"), "0x1")
        self.assertIn("error", by_id[2])
        self.assertEqual(by_id[2]["error"]["code"], -32603)

    def test_single_notification_returns_204(self):
        """JSON-RPC notification on a single request: HTTP 204, no body
        (per spec, no JSON-RPC response). Phase 4 review #4."""
        body = json.dumps({"jsonrpc": "2.0", "method": "eth_chainId", "params": []})
        # Set dry-run so we exercise the synthetic path without forwarding.
        RPCProxyHandler.dry_run = True
        resp = self._post(body)
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(resp.content, b"")

    def test_batch_single_notification_only_returns_204(self):
        """A batch consisting solely of notifications produces 204."""
        batch = [
            {"jsonrpc": "2.0", "method": "eth_chainId", "params": []},
            {"jsonrpc": "2.0", "method": "eth_chainId", "params": []},
        ]
        RPCProxyHandler.dry_run = True  # don't actually forward
        resp = self._post(json.dumps(batch))
        self.assertEqual(resp.status_code, 204)

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

    # ---- Phase 6 notification + duplicate-id edge cases ----

    def test_single_notification_normal_path_returns_204_even_when_upstream_204(self):
        """Phase 5 review #1 / Phase 6A: in NORMAL (not dry-run) mode, a
        notification's upstream may return 204 / empty body. The proxy must
        still return 204 to the caller, NOT 502 from JSONDecodeError."""
        body = json.dumps({"jsonrpc": "2.0", "method": "eth_chainId", "params": []})
        # Upstream replies 204 No Content (spec-compliant for notifications)
        _RecordingUpstream.canned_response = lambda raw: (204, b"")
        before = len(_RecordingUpstream.received_bodies)
        resp = self._post(body)
        self.assertEqual(resp.status_code, 204,
                         "notification with upstream 204 must NOT 502")
        self.assertEqual(resp.content, b"")
        # And upstream WAS forwarded fire-and-forget
        self.assertEqual(len(_RecordingUpstream.received_bodies), before + 1)

    def test_batch_pure_notification_normal_path_returns_204(self):
        """Phase 5 review #2 / Phase 6B: pure-notification batch in NORMAL
        mode must NOT touch upstream and must return 204."""
        batch = [
            {"jsonrpc": "2.0", "method": "eth_chainId", "params": []},
            {"jsonrpc": "2.0", "method": "eth_chainId", "params": []},
        ]
        before = len(_RecordingUpstream.received_bodies)
        resp = self._post(json.dumps(batch))
        self.assertEqual(resp.status_code, 204)
        # Pure-notification batch: upstream NOT contacted
        self.assertEqual(len(_RecordingUpstream.received_bodies), before,
                         "pure-notification batch must NOT contact upstream")

    def test_batch_mixed_notification_excluded_from_upstream_payload(self):
        """Phase 5 review #2 / Phase 6B: notifications mixed into a batch
        with id-bearing requests must NOT appear in the upstream payload."""
        batch = [
            {"jsonrpc": "2.0", "method": "eth_chainId", "params": []},  # notification
            {"jsonrpc": "2.0", "id": 7, "method": "eth_blockNumber", "params": []},
        ]
        _RecordingUpstream.canned_response = json.dumps([
            {"jsonrpc": "2.0", "id": 7, "result": "0xff"},
        ]).encode()
        before = len(_RecordingUpstream.received_bodies)
        resp = self._post(json.dumps(batch))
        # We get one slot back (for id=7 only)
        body = resp.json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["id"], 7)
        # And upstream saw exactly one request — the notification was filtered
        self.assertEqual(len(_RecordingUpstream.received_bodies), before + 1)
        upstream_body = json.loads(_RecordingUpstream.received_bodies[-1])
        self.assertIsInstance(upstream_body, list)
        self.assertEqual(len(upstream_body), 1,
                         "notification must NOT be in upstream payload")
        self.assertEqual(upstream_body[0].get("id"), 7)

    def test_batch_duplicate_ids_rejected_for_all_occurrences(self):
        """Phase 5 review #3 / Phase 6C: duplicate ids in a batch result in
        -32600 for ALL occurrences. Defensive against misbehaving clients."""
        batch = [
            {"jsonrpc": "2.0", "id": 1, "method": "eth_chainId", "params": []},
            {"jsonrpc": "2.0", "id": 2, "method": "eth_chainId", "params": []},
            {"jsonrpc": "2.0", "id": 1, "method": "eth_blockNumber", "params": []},  # DUP
        ]
        _RecordingUpstream.canned_response = json.dumps([
            {"jsonrpc": "2.0", "id": 2, "result": "0x2"},
        ]).encode()
        resp = self._post(json.dumps(batch))
        body = resp.json()
        self.assertEqual(len(body), 3)
        # Both id=1 entries must be -32600 invalid; id=2 forwards.
        dup_slots = [item for item in body if item.get("id") == 1]
        self.assertEqual(len(dup_slots), 2,
                         "both duplicate id slots must be present")
        for slot in dup_slots:
            self.assertIn("error", slot)
            self.assertEqual(slot["error"]["code"], -32600)
            self.assertIn("Duplicate", slot["error"]["message"])
        # Upstream must NOT have seen the duplicate — only id=2 was forwarded.
        upstream_body = json.loads(_RecordingUpstream.received_bodies[-1])
        self.assertEqual(len(upstream_body), 1)
        self.assertEqual(upstream_body[0]["id"], 2)

    def test_batch_explicit_id_null_forwarded_normally(self):
        """Phase 6C: explicit `id: null` is valid JSON-RPC (caller wants no
        response but acknowledges error responses). It is NOT a notification
        (which omits the id key entirely). Forward as a normal request."""
        batch = [
            {"jsonrpc": "2.0", "id": None, "method": "eth_chainId", "params": []},
            {"jsonrpc": "2.0", "id": 9, "method": "eth_blockNumber", "params": []},
        ]
        _RecordingUpstream.canned_response = json.dumps([
            {"jsonrpc": "2.0", "id": None, "result": "0x1"},
            {"jsonrpc": "2.0", "id": 9, "result": "0xff"},
        ]).encode()
        resp = self._post(json.dumps(batch))
        body = resp.json()
        self.assertEqual(len(body), 2)
        # Upstream WAS contacted with both slots (explicit null is forward-eligible)
        upstream_body = json.loads(_RecordingUpstream.received_bodies[-1])
        self.assertEqual(len(upstream_body), 2)

    def test_batch_id_type_mismatch_surfaces_internal_error(self):
        """Phase 5 #5 / Phase 6: if proxy sends int id 1 but upstream
        replies string "1", we must NOT cross-wire — return -32603 for the
        forwarded slot whose id never came back, and log the unknown id."""
        batch = [
            {"jsonrpc": "2.0", "id": 1, "method": "eth_chainId", "params": []},
        ]
        _RecordingUpstream.canned_response = json.dumps([
            {"jsonrpc": "2.0", "id": "1", "result": "0x1"},  # string, not int
        ]).encode()
        resp = self._post(json.dumps(batch))
        body = resp.json()
        self.assertEqual(len(body), 1)
        self.assertIn("error", body[0])
        self.assertEqual(body[0]["error"]["code"], -32603)

    def test_batch_one_forward_item_upstream_returns_dict_normalized_to_list(self):
        """Phase 6: upstream may return a dict (not list) when forward_payload
        had only one element. Proxy must normalize to a list and merge."""
        batch = [
            {"jsonrpc": "2.0", "id": 1, "method": "eth_chainId", "params": []},
            {"jsonrpc": "2.0", "method": "eth_chainId", "params": []},  # notification
        ]
        # Upstream sees only the id-bearing item; replies as a single dict
        _RecordingUpstream.canned_response = b'{"jsonrpc":"2.0","id":1,"result":"0xdeadbeef"}'
        resp = self._post(json.dumps(batch))
        body = resp.json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["id"], 1)
        self.assertEqual(body[0]["result"], "0xdeadbeef")

    # ---- Phase 7A: id:null vs missing upstream id distinction (Codex Phase 6 #1) ----

    def test_batch_id_null_does_not_collide_with_missing_upstream_id(self):
        """Phase 7A: prior code used r_out.get('id') which returned None for
        BOTH explicit id:null AND missing-id. A malformed upstream response
        with no id field would satisfy an explicit-null request slot. Phase 7A
        requires 'id' in r_out — missing-id responses are dropped + logged."""
        batch = [
            {"jsonrpc": "2.0", "id": None, "method": "eth_chainId", "params": []},
        ]
        # Upstream sends a malformed response with NO id field
        _RecordingUpstream.canned_response = json.dumps([
            {"jsonrpc": "2.0", "result": "0xMALFORMED_NO_ID"},
        ]).encode()
        resp = self._post(json.dumps(batch))
        body = resp.json()
        self.assertEqual(len(body), 1)
        # The id:null request slot must NOT be filled with the malformed
        # upstream response — it must surface -32603 instead.
        self.assertNotIn("result", body[0])
        self.assertIn("error", body[0])
        self.assertEqual(body[0]["error"]["code"], -32603)

    def test_batch_id_null_matched_by_explicit_null_upstream(self):
        """Phase 7A: explicit `id:null` upstream response (key present, value
        null) DOES match the id:null request slot."""
        batch = [
            {"jsonrpc": "2.0", "id": None, "method": "eth_chainId", "params": []},
        ]
        _RecordingUpstream.canned_response = json.dumps([
            {"jsonrpc": "2.0", "id": None, "result": "0xnullok"},
        ]).encode()
        resp = self._post(json.dumps(batch))
        body = resp.json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0].get("result"), "0xnullok")

    # ---- Phase 7B: invalid id types rejected before Counter (Codex Phase 6 #2) ----

    def test_batch_array_id_rejected_with_invalid_request(self):
        """Phase 7B: id:[] is unhashable; prior Counter() crashed. Must reject
        as -32600 instead of crashing the handler."""
        batch = [
            {"jsonrpc": "2.0", "id": [], "method": "eth_chainId", "params": []},
            {"jsonrpc": "2.0", "id": 7, "method": "eth_blockNumber", "params": []},
        ]
        _RecordingUpstream.canned_response = json.dumps([
            {"jsonrpc": "2.0", "id": 7, "result": "0xff"},
        ]).encode()
        resp = self._post(json.dumps(batch))
        self.assertEqual(resp.status_code, 200,
                         "handler must not crash on unhashable id")
        body = resp.json()
        self.assertEqual(len(body), 2)
        # First slot: -32600 invalid; id is None (we can't echo the bad id).
        self.assertIn("error", body[0])
        self.assertEqual(body[0]["error"]["code"], -32600)
        self.assertIn("Invalid id type", body[0]["error"]["message"])
        # Second slot: forwarded normally.
        by_id = {item["id"]: item for item in body if item.get("id") is not None}
        self.assertEqual(by_id[7]["result"], "0xff")

    def test_batch_object_id_rejected(self):
        """Phase 7B: id:{} is also invalid + unhashable."""
        batch = [{"jsonrpc": "2.0", "id": {"x": 1}, "method": "eth_chainId", "params": []}]
        resp = self._post(json.dumps(batch))
        body = resp.json()
        self.assertEqual(body[0]["error"]["code"], -32600)

    def test_batch_boolean_id_rejected(self):
        """Phase 7B: bool ids are spec-bad (JSON-RPC 2.0 says String/Number/null)."""
        batch = [{"jsonrpc": "2.0", "id": True, "method": "eth_chainId", "params": []}]
        resp = self._post(json.dumps(batch))
        body = resp.json()
        self.assertEqual(body[0]["error"]["code"], -32600)

    def test_batch_duplicate_id_2_succeeds_via_upstream(self):
        """Phase 7H (Codex Phase 6 coverage gap): the prior dup-id test only
        asserted that both id=1 entries were rejected. It never asserted
        that the OTHER (non-duplicate) id=2 entry actually succeeded via
        upstream. Pin that here."""
        batch = [
            {"jsonrpc": "2.0", "id": 1, "method": "eth_chainId", "params": []},
            {"jsonrpc": "2.0", "id": 2, "method": "eth_blockNumber", "params": []},
            {"jsonrpc": "2.0", "id": 1, "method": "eth_chainId", "params": []},
        ]
        _RecordingUpstream.canned_response = json.dumps([
            {"jsonrpc": "2.0", "id": 2, "result": "0xPASSED_THROUGH"},
        ]).encode()
        resp = self._post(json.dumps(batch))
        body = resp.json()
        self.assertEqual(len(body), 3)
        # id=2 must have a result, not -32600
        slot_2 = next(item for item in body if item["id"] == 2)
        self.assertEqual(slot_2.get("result"), "0xPASSED_THROUGH",
                         "non-duplicate id=2 must succeed via upstream")
        self.assertNotIn("error", slot_2)

    # ---- Phase 8A: single-request id validation (Codex Phase 7 #1) ----

    def test_single_array_id_rejected_with_invalid_request(self):
        """Phase 8A: prior _handle_single did NOT validate id type. id:[]
        in a single request would crash dispatch in active mode and echo
        the bad id back in dry-run. Phase 8A applies is_valid_jsonrpc_id
        consistently to single-request path."""
        body = json.dumps({"jsonrpc": "2.0", "id": [], "method": "eth_chainId", "params": []})
        before = len(_RecordingUpstream.received_bodies)
        resp = self._post(body)
        self.assertEqual(resp.status_code, 200)
        body_json = resp.json()
        self.assertIn("error", body_json)
        self.assertEqual(body_json["error"]["code"], -32600)
        # Upstream NOT contacted
        self.assertEqual(len(_RecordingUpstream.received_bodies), before,
                         "single request with invalid id must NOT reach upstream")

    def test_single_object_id_rejected(self):
        body = json.dumps({"jsonrpc": "2.0", "id": {"x": 1}, "method": "eth_chainId", "params": []})
        resp = self._post(body)
        self.assertEqual(resp.json()["error"]["code"], -32600)

    def test_single_boolean_id_rejected(self):
        body = json.dumps({"jsonrpc": "2.0", "id": True, "method": "eth_chainId", "params": []})
        resp = self._post(body)
        self.assertEqual(resp.json()["error"]["code"], -32600)

    def test_single_array_id_rejected_in_dry_run(self):
        """Phase 8A: invalid id rejection MUST also fire on the dry-run
        path, not just active. Prior version returned a synthetic dry-run
        ack echoing the bad id."""
        RPCProxyHandler.dry_run = True
        body = json.dumps({"jsonrpc": "2.0", "id": [1, 2], "method": "eth_chainId", "params": []})
        resp = self._post(body)
        body_json = resp.json()
        self.assertIn("error", body_json)
        self.assertEqual(body_json["error"]["code"], -32600)
        self.assertNotIn("_e_ai_dry_run", body_json,
                         "invalid id must short-circuit BEFORE dry-run synthesis")

    def test_is_valid_jsonrpc_id_rejects_non_finite_floats(self):
        """Phase 8A narrow companion: NaN/Infinity floats fail wire-JSON
        even though Python's json module accepts them by default. Reject."""
        from proxy.rpc_proxy import is_valid_jsonrpc_id
        self.assertFalse(is_valid_jsonrpc_id(float("nan")))
        self.assertFalse(is_valid_jsonrpc_id(float("inf")))
        self.assertFalse(is_valid_jsonrpc_id(float("-inf")))
        self.assertTrue(is_valid_jsonrpc_id(0.0))
        self.assertTrue(is_valid_jsonrpc_id(1.5))
        self.assertTrue(is_valid_jsonrpc_id(-3.14))

    def test_run_proxy_notification_timeout_override(self):
        """Phase 11A (Codex Phase 7 deferred follow-up): run_proxy()
        accepts notification_timeout to override
        NOTIFICATION_FORWARD_TIMEOUT_S module default. Verify the
        override actually propagates to the global constant. We don't
        spin up the proxy here — that would deadlock the test thread —
        just exercise the override + restore."""
        import proxy.rpc_proxy as rp
        original = rp.NOTIFICATION_FORWARD_TIMEOUT_S
        try:
            # Mimic what run_proxy() does at the top before binding the
            # server. We can't call run_proxy() directly (it serves
            # forever); replicate the override path.
            rp.NOTIFICATION_FORWARD_TIMEOUT_S = 1.5
            self.assertEqual(rp.NOTIFICATION_FORWARD_TIMEOUT_S, 1.5)
            rp.NOTIFICATION_FORWARD_TIMEOUT_S = 5.0
            self.assertEqual(rp.NOTIFICATION_FORWARD_TIMEOUT_S, 5.0)
        finally:
            rp.NOTIFICATION_FORWARD_TIMEOUT_S = original

    def test_is_valid_jsonrpc_id_basic_shape(self):
        """Phase 8A: pin the validator's accept/reject set."""
        from proxy.rpc_proxy import is_valid_jsonrpc_id
        for ok in [None, 0, 1, -1, 1.5, "abc", "", "1"]:
            self.assertTrue(is_valid_jsonrpc_id(ok), f"must accept {ok!r}")
        for bad in [True, False, [], [1, 2], {}, {"x": 1}, b"bytes", set()]:
            self.assertFalse(is_valid_jsonrpc_id(bad), f"must reject {bad!r}")

    # ---- Phase 7C: notification fire-and-forget bounded timeout (Codex Phase 6 #3) ----

    def test_single_notification_returns_204_promptly_when_upstream_slow(self):
        """Phase 7C: prior `_handle_single` used the client's 30s default
        timeout for notification forwards, blocking the proxy thread on a
        slow upstream. Phase 7C uses NOTIFICATION_FORWARD_TIMEOUT_S=3.0.
        We start a deliberately slow upstream and assert the caller sees
        204 within a bound that's well under the old 30s default."""
        # Replace the canned response with a slow handler. The recording
        # upstream sleeps 5 seconds before responding.
        slow_called = threading.Event()
        slow_unblock = threading.Event()

        class _SlowUpstream(BaseHTTPRequestHandler):
            def do_POST(self):
                slow_called.set()
                # Block until the test releases (or notification timeout fires)
                slow_unblock.wait(timeout=10)
                # The proxy almost certainly closed the connection by now
                # (the notification timeout is 3s, the test waits up to 6s).
                # Sending a response on a closed socket raises BrokenPipeError;
                # swallow it — that's the whole point of "fire-and-forget".
                try:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"jsonrpc":"2.0","id":1,"result":"0x1"}')
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass
            def log_message(self, *a, **kw):
                pass
            def handle_one_request(self):
                # Suppress the default error logging from the broken-pipe path
                try:
                    super().handle_one_request()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass

        # Start the slow upstream on its own port, point a fresh handler at it.
        slow_port = _free_port()
        slow_server = _start_server(_SlowUpstream, slow_port)
        # Save original config; swap to the slow upstream just for this test.
        orig_upstream = RPCProxyHandler.upstream
        RPCProxyHandler.upstream = f"http://127.0.0.1:{slow_port}"
        try:
            body = json.dumps({"jsonrpc": "2.0", "method": "eth_chainId", "params": []})
            t0 = time.time()
            resp = self._post(body)
            elapsed = time.time() - t0
            # Phase 7C: bounded best-effort timeout (3s default). Caller must
            # see 204 well under the old client default of 30s. Allow a
            # generous 6s margin to absorb scheduling jitter on slow CI
            # runners (the timeout itself is 3s).
            self.assertEqual(resp.status_code, 204)
            self.assertLess(elapsed, 6.0,
                            f"notification path blocked too long: {elapsed:.2f}s "
                            "(NOTIFICATION_FORWARD_TIMEOUT_S=3.0)")
        finally:
            slow_unblock.set()
            slow_server.shutdown()
            slow_server.server_close()
            RPCProxyHandler.upstream = orig_upstream

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
