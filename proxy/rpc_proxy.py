"""
e_AI v2 Local RPC Proxy

STATUS: ILLUSTRATIVE ADAPTER, NOT a profile-driven runtime. The proxy
hard-codes detection logic for `rpc_leakage`, `cross_protocol_risk`,
and `l2_anonymity_set` directly in source — it does NOT dispatch from
profile semantics. A canonical profile-driven runtime is queued as a
maturity-gate item. Treat this file as a pattern reference for how
RPC-pattern monitoring could integrate, not as the canonical RPC
runtime. See README "Integration demos (status: illustrative
adapters)" section.

HARDENING (Phase 2, applied 2026-05-07 per Codex review):
  - CORS DISABLED by default. To allow a browser origin, pass
    --allow-origin <url> (repeatable). Non-allowlisted origins receive
    no Access-Control-Allow-Origin header and OPTIONS preflight returns
    403.
  - Optional bearer-token auth via --auth-token <secret>; when set,
    requests must carry `Authorization: Bearer <secret>` or get 401.
  - 4 MB request-body cap (MAX_BODY_BYTES) enforced before parsing JSON;
    oversize → 413.
  - JSON-RPC batch handling (list payload → list response).
  - State-pruning to a 5-minute window across ALL time-keyed maps
    (balance_address_seen, call_target_log, known_position_log,
    pool_queries — not just query_log).
  - Shared httpx.Client created at startup, closed cleanly on shutdown.
  - --dry-run does NOT forward to upstream; returns synthetic
    acknowledgment with _e_ai_dry_run flag and any pre-alerts.
  - --profiles flag accepted (no-op today; reserved for the future
    profile-driven runtime).

HTTP JSON-RPC proxy that sits between wallet and local node.
Forwards all requests while running pattern-based analysis on
accumulated state.

Pattern-detectors active (hard-coded):
  - rpc_leakage: detects query patterns that reveal strategy
  - cross_protocol_risk: accumulates portfolio state from reads
  - l2_anonymity_set: tracks pool sizes from log queries

Usage:
    # Start proxy (forwards to local Helios or node)
    python -m proxy.rpc_proxy --upstream http://localhost:8545 --port 8546

    # Point wallet to proxy
    # MetaMask → Settings → Networks → RPC URL: http://localhost:8546

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
    """Accumulated state from RPC queries.

    All time-keyed maps below are pruned to a 5-minute window in
    analyze_request (see _prune_state_windows). Previously only
    query_log was pruned; balance_addresses + call_targets +
    known_positions + pool_queries leaked across the entire session.
    """
    # RPC leakage tracking — query log
    query_log: list[dict] = field(default_factory=list)
    # Address-keyed timestamp maps (5-min window pruning).
    balance_address_seen: dict = field(default_factory=dict)  # addr → last-seen timestamp
    call_target_log: list[dict] = field(default_factory=list)  # rolling list of {target, time}

    # Cross-protocol risk tracking — rolling list (5-min window pruning).
    known_position_log: list[dict] = field(default_factory=list)

    # L2 anonymity set tracking
    pool_queries: list[dict] = field(default_factory=list)

    # Stats
    total_requests: int = 0
    total_alerts: int = 0
    start_time: float = field(default_factory=time.time)

    # Back-compat properties for tests that read the old field names.
    @property
    def balance_addresses(self) -> set:
        return set(self.balance_address_seen.keys())

    @property
    def call_targets(self) -> dict:
        d: defaultdict = defaultdict(int)
        for r in self.call_target_log:
            d[r["target"]] += 1
        return d

    @property
    def known_positions(self) -> dict:
        d: dict[str, int] = {}
        for r in self.known_position_log:
            d[r["target"]] = d.get(r["target"], 0) + 1
        return d


# ---------------------------------------------------------------------------
# Profile-based analysis
# ---------------------------------------------------------------------------

def is_valid_jsonrpc_id(x: Any) -> bool:
    """JSON-RPC 2.0: id MUST be String, Number, or NULL. Booleans, arrays,
    and objects are invalid. We exclude booleans even though Python `bool`
    is a subclass of `int` (so `Counter` would happily key on them) — bool
    ids are spec-bad and we reject for hygiene.

    Phase 7B + Phase 8A (Codex Phase 7 #1 narrow companion): non-finite
    floats (NaN, Infinity, -Infinity) are JSON-non-compliant on the wire
    even if Python's json module accepts them by default. Reject them too.
    """
    import math
    if x is None:
        return True
    if isinstance(x, bool):
        return False  # bool is int subclass; reject explicitly
    if isinstance(x, float):
        return math.isfinite(x)
    if isinstance(x, int):
        return True
    if isinstance(x, str):
        return True
    return False


def analyze_request(method: str, params: list, state: ProxyState) -> list[Alert]:
    """Analyze an RPC request against loaded profiles."""
    alerts = []
    state.total_requests += 1

    now = time.time()
    cutoff = now - 300  # 5-minute window

    # Log query
    state.query_log.append({
        "method": method,
        "time": now,
        "params_summary": str(params)[:200] if params else "",
    })

    # Prune ALL time-keyed maps to the 5-minute window (was: query_log only).
    state.query_log = [q for q in state.query_log if q["time"] > cutoff]
    state.balance_address_seen = {
        a: t for a, t in state.balance_address_seen.items() if t > cutoff
    }
    state.call_target_log = [r for r in state.call_target_log if r["time"] > cutoff]
    state.known_position_log = [r for r in state.known_position_log if r["time"] > cutoff]
    state.pool_queries = [r for r in state.pool_queries if r["time"] > cutoff]

    # --- rpc_leakage checks ---

    # H1: Balance checks linking addresses
    if method == "eth_getBalance" and params:
        addr = params[0] if isinstance(params[0], str) else ""
        if addr:
            state.balance_address_seen[addr.lower()] = now
            n_addr = len(state.balance_address_seen)
            if n_addr > 3:
                alerts.append(Alert(
                    profile="rpc_leakage",
                    heuristic="H1",
                    severity="high",
                    confidence=0.8,
                    signal=f"Balance checked for {n_addr} addresses in 5 min window — these are now linked by your RPC provider",
                    recommendation="Use local light client (Helios) to avoid leaking address relationships",
                ))

    # H2: Position monitoring (repeated eth_call)
    if method == "eth_call" and params:
        target = params[0].get("to", "") if isinstance(params[0], dict) else ""
        if target:
            target_lc = target.lower()
            state.call_target_log.append({"target": target_lc, "time": now})
            n_calls = sum(1 for r in state.call_target_log if r["target"] == target_lc)
            if n_calls > 5:
                alerts.append(Alert(
                    profile="rpc_leakage",
                    heuristic="H2",
                    severity="medium",
                    confidence=0.6,
                    signal=f"eth_call to {target[:16]}... called {n_calls}x in 5 min — reveals position monitoring",
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
    # Use the rolling 5-min window for the concentration check.
    if method == "eth_call" and params:
        target = (params[0].get("to", "") if isinstance(params[0], dict) else "").lower()
        if target:
            state.known_position_log.append({"target": target, "time": now})
            kp = state.known_positions  # property: counts within window
            total_calls = sum(kp.values())
            if total_calls > 10:
                max_protocol = max(kp, key=kp.get)
                max_pct = kp[max_protocol] / total_calls
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
                "time": now,
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

# Hardening defaults (overridable at run_proxy() time).
MAX_BODY_BYTES = 4 * 1024 * 1024  # 4 MB cap on request body

# Phase 7C: bounded best-effort timeout on the notification upstream POST.
# The proxy uses a single-threaded HTTPServer, so a slow upstream cannot
# be allowed to hold a notification request for the client's default
# timeout (30s) — that would also stall every other in-flight request.
# 3s is enough for a healthy local node and short enough that the wallet
# UX doesn't perceive a stall. Override at run_proxy() if needed.
NOTIFICATION_FORWARD_TIMEOUT_S = 3.0


class RPCProxyHandler(BaseHTTPRequestHandler):
    upstream: str = "http://localhost:8545"
    state: ProxyState = ProxyState()
    dry_run: bool = False
    # Hardening config (set at run_proxy startup)
    allowed_origins: tuple[str, ...] = ()  # empty = no CORS by default
    auth_token: str | None = None  # if set, require Authorization: Bearer <token>
    http_client: "httpx.Client | None" = None  # shared, set at startup

    # ------------------------------------------------------------------
    # Request entry points
    # ------------------------------------------------------------------

    def do_POST(self):
        if not self._check_auth():
            return
        body = self._read_body()
        if body is None:
            return  # error already sent

        try:
            request = json.loads(body)
        except json.JSONDecodeError:
            self._send_error(400, "Invalid JSON")
            return

        # JSON-RPC supports both single requests (dict) and batches (list).
        if isinstance(request, list):
            self._handle_batch(request, body)
        elif isinstance(request, dict):
            self._handle_single(request, body)
        else:
            self._send_error(400, "JSON-RPC payload must be object or array")

    def do_OPTIONS(self):
        """Handle CORS preflight (only if Origin is allowlisted)."""
        origin = self.headers.get("Origin", "")
        if origin and origin not in self.allowed_origins:
            # Reject preflight from non-allowlisted origin
            self.send_response(403)
            self.end_headers()
            return
        self.send_response(200)
        self._set_cors_headers(origin)
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    # ------------------------------------------------------------------
    # Request flow helpers
    # ------------------------------------------------------------------

    def _check_auth(self) -> bool:
        if self.auth_token is None:
            return True  # auth disabled
        header = self.headers.get("Authorization", "")
        expected = f"Bearer {self.auth_token}"
        if header != expected:
            self._send_error(401, "Unauthorized")
            return False
        return True

    def _read_body(self) -> bytes | None:
        try:
            content_length = int(self.headers.get("Content-Length", 0))
        except (TypeError, ValueError):
            self._send_error(400, "Invalid Content-Length")
            return None
        if content_length < 0 or content_length > MAX_BODY_BYTES:
            self._send_error(413, f"Request body exceeds {MAX_BODY_BYTES}-byte cap")
            return None
        return self.rfile.read(content_length)

    def _handle_single(self, request: dict, body: bytes):
        method = request.get("method", "")
        params = request.get("params", [])
        # JSON-RPC notifications omit "id" and expect NO response. Preserve
        # absence here (don't coerce to 1, which the prior version did);
        # the dry-run / block paths skip the synthetic JSON body for
        # notifications and reply with HTTP 204 instead (per Codex Phase 4
        # review #4).
        is_notification = "id" not in request
        req_id = request.get("id")

        # Phase 8A (Codex Phase 7 #1): single-request invalid id types must
        # be rejected for the same reason batch invalid ids are rejected
        # (Phase 7B). Without this check, a single dry-run with id:[]
        # echoed the bad id back; active mode forwarded the malformed
        # request upstream. Inconsistent JSON-RPC contract.
        if not is_notification and not is_valid_jsonrpc_id(req_id):
            self._send_json({
                "jsonrpc": "2.0", "id": None,
                "error": {
                    "code": -32600,
                    "message": (
                        f"Invalid id type: {type(req_id).__name__}; "
                        "must be string, number, or null"
                    ),
                },
            })
            return

        pre_alerts = analyze_request(method, params, self.state)
        for alert in pre_alerts:
            self._log_alert(alert)

        critical = [a for a in pre_alerts if a.severity == "critical" and a.confidence > 0.8]
        if critical and not self.dry_run:
            if is_notification:
                # Notification: no JSON-RPC response. Acknowledge at HTTP layer.
                self._send_no_content()
                return
            error_msg = "; ".join(f"[{a.heuristic}] {a.signal}" for a in critical)
            self._send_json({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32000, "message": f"e_AI Guard blocked: {error_msg}"},
            })
            return

        if self.dry_run:
            if is_notification:
                self._send_no_content()
                return
            # Don't forward in dry-run; return a synthetic acknowledgment so
            # the caller sees the proxy ran the analysis without touching
            # the upstream.
            self._send_json({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": None,
                "_e_ai_dry_run": True,
                "_e_ai_alerts": [
                    {"profile": a.profile, "heuristic": a.heuristic, "severity": a.severity}
                    for a in pre_alerts
                ],
            })
            return

        # JSON-RPC notification on the normal path: forward best-effort,
        # do NOT parse the upstream response. Real upstreams may return 204 /
        # empty body for notifications, which previously caused the proxy to
        # 502 (Codex Phase 5 review #1). Acknowledge to the caller with HTTP
        # 204; pre-analysis already ran.
        #
        # Phase 7C (Codex Phase 6 review #3): use a short timeout so a slow
        # upstream cannot block the proxy thread for the full client default
        # (30s) before the caller sees its 204. The proxy uses a single-
        # threaded HTTPServer, so a long forward stalls every other request.
        # The contract is now "best-effort short forward" — not full
        # asynchronous fire-and-forget, but bounded latency.
        if is_notification:
            try:
                self.http_client.post(
                    self.upstream,
                    content=body,
                    headers={"Content-Type": "application/json"},
                    timeout=NOTIFICATION_FORWARD_TIMEOUT_S,
                )
            except httpx.HTTPError as e:
                # Notification is fire-and-forget at the JSON-RPC layer; we
                # still log upstream connectivity issues but do not surface
                # them to the caller (no response slot to fail).
                log.warning(f"Notification forward to upstream failed: {e}")
            self._send_no_content()
            return

        try:
            resp = self.http_client.post(
                self.upstream,
                content=body,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            response = resp.json()
        except (httpx.HTTPError, json.JSONDecodeError) as e:
            self._send_error(502, f"Upstream error: {e}")
            return

        result = response.get("result")
        post_alerts = analyze_response(method, params, result, self.state)
        for alert in post_alerts:
            self._log_alert(alert)

        self._send_json(response)

    def _handle_batch(self, requests: list, body: bytes):
        """Handle JSON-RPC batch requests with id-correlated merge.

        Per-item plan slots:
          - "invalid"      → not a dict OR duplicate id; responds with -32600.
          - "blocked"      → critical alert; responds with guard-block error.
          - "dryrun"       → dry-run path; synthetic _e_ai_dry_run ack.
          - "forward"      → normal path; sent to upstream, filled by id.
          - "notification" → no id; pre-analysis only, NO response slot.

        Correctness invariants (Codex Phase 4 #2/#3/#4 + Phase 5 #2/#3):
          - Upstream NEVER sees invalid/blocked/dryrun/notification entries.
            forward_payload is built from id-bearing forward slots ONLY.
            Notifications are NOT appended (Phase 5 review #2).
          - Upstream responses are matched to forward slots BY id, not by
            iterator position. JSON-RPC permits reordering.
          - Notifications get pre-analysis but produce NO response in the
            merged output AND are not forwarded as part of the response-
            bearing batch. If the user wants HTTP-batch notification
            semantics on the wire, they go through `_handle_single` one
            at a time. (Most upstreams treat HTTP-batch notifications as
            no-op anyway, so this is a documented simplification.)
          - Duplicate id-bearing entries are rejected as -32600 for ALL
            occurrences (Phase 5 review #3). Two requests with the same
            id is illegal JSON-RPC; failing all of them deterministically
            is safer than letting one win.
        """
        if not requests:
            self._send_error(400, "Empty batch")
            return

        n = len(requests)
        plan: list[str] = ["forward"] * n
        prebuilt: list[dict | None] = [None] * n

        # Phase 7B: pre-validate ids BEFORE the duplicate-id Counter pass.
        # JSON-RPC 2.0 ids must be String, Number, or NULL. An array/object
        # id would crash Counter with TypeError (unhashable). A boolean id
        # is spec-bad and we reject for hygiene. We mark these slots as
        # "invalid" up front and exclude them from the duplicate scan.
        invalid_id_slots: set[int] = set()
        for i, r in enumerate(requests):
            if not isinstance(r, dict):
                # Non-dict entries get -32600 below in the main loop.
                continue
            if "id" in r and not is_valid_jsonrpc_id(r["id"]):
                invalid_id_slots.add(i)
                plan[i] = "invalid"
                prebuilt[i] = {
                    "jsonrpc": "2.0", "id": None,
                    "error": {
                        "code": -32600,
                        "message": (
                            f"Invalid id type in batch: "
                            f"{type(r['id']).__name__}; must be string, number, or null"
                        ),
                    },
                }

        # First pass: detect duplicate id-bearing entries. Any valid id
        # appearing in >1 entry is rejected for ALL occurrences (Phase 5
        # review #3). Notifications and invalid-id slots are excluded.
        from collections import Counter as _Counter
        id_counts = _Counter(
            r["id"] for i, r in enumerate(requests)
            if isinstance(r, dict) and "id" in r and i not in invalid_id_slots
        )
        dup_ids = {k for k, v in id_counts.items() if v > 1}

        # For forward slots, map id → slot index for the merge step.
        id_to_slot: dict[Any, int] = {}
        # Forward items to actually send upstream (id-bearing only).
        forward_payload: list[dict] = []

        for i, r in enumerate(requests):
            if i in invalid_id_slots:
                continue  # already handled above
            if not isinstance(r, dict):
                plan[i] = "invalid"
                prebuilt[i] = {
                    "jsonrpc": "2.0", "id": None,
                    "error": {"code": -32600, "message": "Invalid request in batch"},
                }
                continue

            method = r.get("method", "")
            params = r.get("params", [])
            is_notification = "id" not in r
            req_id = r.get("id")

            pre_alerts = analyze_request(method, params, self.state)
            for alert in pre_alerts:
                self._log_alert(alert)

            critical = [a for a in pre_alerts if a.severity == "critical" and a.confidence > 0.8]

            if is_notification:
                plan[i] = "notification"
                # Pre-analysis ran. No response slot. NOT forwarded as part
                # of the upstream batch (Phase 5 review #2). Critical alerts
                # on notifications are logged only.
                continue

            # Duplicate id-bearing entry: reject ALL occurrences as -32600
            # rather than letting the later one overwrite the earlier in
            # id_to_slot (Phase 5 review #3).
            if not is_notification and req_id in dup_ids:
                plan[i] = "invalid"
                prebuilt[i] = {
                    "jsonrpc": "2.0", "id": req_id,
                    "error": {
                        "code": -32600,
                        "message": f"Duplicate id {req_id!r} in batch",
                    },
                }
                continue

            if self.dry_run:
                plan[i] = "dryrun"
                prebuilt[i] = {
                    "jsonrpc": "2.0", "id": req_id, "result": None,
                    "_e_ai_dry_run": True,
                    "_e_ai_alerts": [
                        {"profile": a.profile, "heuristic": a.heuristic, "severity": a.severity}
                        for a in pre_alerts
                    ],
                }
            elif critical:
                plan[i] = "blocked"
                error_msg = "; ".join(f"[{a.heuristic}] {a.signal}" for a in critical)
                prebuilt[i] = {
                    "jsonrpc": "2.0", "id": req_id,
                    "error": {"code": -32000, "message": f"e_AI Guard blocked: {error_msg}"},
                }
            else:
                # Forward slot — track for id-based merge.
                id_to_slot[req_id] = i
                forward_payload.append(r)

        # If no forward items remain, respond locally without touching upstream.
        if not forward_payload and not id_to_slot:
            merged = [prebuilt[i] for i, p in enumerate(plan) if p != "notification"]
            if merged:
                self._send_json(merged)
            else:
                # Pure notifications batch → no JSON-RPC response.
                self._send_no_content()
            return

        # Build a FILTERED batch body containing only forwardable items.
        # Crucially we do NOT post the original body, which still contains
        # invalid / blocked / dryrun entries (Codex Phase 4 review #2).
        try:
            resp = self.http_client.post(
                self.upstream,
                content=json.dumps(forward_payload).encode(),
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            upstream_responses = resp.json()
        except (httpx.HTTPError, json.JSONDecodeError) as e:
            self._send_error(502, f"Upstream error: {e}")
            return

        # Upstream may return a list (batch) OR a single dict if forward_payload
        # had only one item. Normalize to a list.
        if isinstance(upstream_responses, dict):
            upstream_responses = [upstream_responses]
        if not isinstance(upstream_responses, list):
            self._send_error(502, "Upstream returned non-list, non-dict response to a batch")
            return

        # Merge by id — notifications generate no upstream response, so the
        # response list is permitted to be shorter than forward_payload.
        # Phase 7A (Codex Phase 6 review #1): require "id" in r_out
        # explicitly, NOT r_out.get("id"), so a malformed upstream response
        # with no id field cannot be matched against an explicit id:null
        # request. Without this check, both yield None and collide.
        for r_out in upstream_responses:
            if not isinstance(r_out, dict):
                continue
            if "id" not in r_out:
                log.warning(
                    "Upstream response missing 'id' field; dropping (cannot "
                    "be matched to a request slot — distinct from explicit "
                    "id:null which has the key present)"
                )
                continue
            r_id = r_out["id"]
            # Defensive: malformed upstream id (array/object/etc) can't be
            # used as a dict key in id_to_slot. Treat as unknown rather
            # than crashing.
            if not is_valid_jsonrpc_id(r_id):
                log.warning(
                    f"Upstream returned response with invalid id type "
                    f"{type(r_id).__name__}; dropping"
                )
                continue
            slot = id_to_slot.get(r_id)
            if slot is None:
                # Unknown id — log and drop. JSON-RPC servers should not
                # invent ids, so this is anomalous.
                log.warning(f"Upstream returned response for unknown id={r_id!r}; dropping")
                continue
            # Run post-response analysis against the original request.
            req = requests[slot]
            if isinstance(req, dict):
                result = r_out.get("result")
                post_alerts = analyze_response(
                    req.get("method", ""), req.get("params", []), result, self.state
                )
                for alert in post_alerts:
                    self._log_alert(alert)
            prebuilt[slot] = r_out

        # Any forward slot whose id never came back gets an explicit
        # truncation error rather than silently disappearing.
        for r_id, slot in id_to_slot.items():
            if prebuilt[slot] is None:
                prebuilt[slot] = {
                    "jsonrpc": "2.0", "id": r_id,
                    "error": {"code": -32603, "message": "Upstream omitted response for this id"},
                }

        # Build the final response: every slot EXCEPT notifications.
        merged = [prebuilt[i] for i, p in enumerate(plan) if p != "notification"]
        if merged:
            self._send_json(merged)
        else:
            self._send_no_content()

    # ------------------------------------------------------------------
    # Response helpers
    # ------------------------------------------------------------------

    def _send_json(self, data):
        body = json.dumps(data).encode()
        origin = self.headers.get("Origin", "")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._set_cors_headers(origin)
        self.end_headers()
        self.wfile.write(body)

    def _send_no_content(self):
        """HTTP 204 — used for JSON-RPC notifications, which by spec do
        NOT receive a JSON-RPC response. The HTTP layer still needs an
        acknowledgement (Codex Phase 4 review #4)."""
        origin = self.headers.get("Origin", "")
        self.send_response(204)
        self._set_cors_headers(origin)
        self.end_headers()

    def _send_error(self, code: int, message: str):
        body = json.dumps({
            "jsonrpc": "2.0",
            "id": None,
            "error": {"code": -32000, "message": message},
        }).encode()
        origin = self.headers.get("Origin", "")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._set_cors_headers(origin)
        self.end_headers()
        self.wfile.write(body)

    def _set_cors_headers(self, origin: str):
        """Set CORS headers only for allowlisted origins. Default: no CORS."""
        if origin and origin in self.allowed_origins:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            if self.auth_token is not None:
                self.send_header("Access-Control-Allow-Credentials", "true")

    def _log_alert(self, alert):
        level = logging.WARNING if alert.severity in ("critical", "high") else logging.INFO
        log.log(level, f"[{alert.profile}/{alert.heuristic}] {alert.severity}: {alert.signal}")
        if alert.recommendation and level == logging.WARNING:
            log.info(f"  → {alert.recommendation}")

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
    allowed_origins: tuple[str, ...] = (),
    auth_token: str | None = None,
):
    """Start the RPC proxy server.

    Hardening defaults:
      - allowed_origins=() — CORS DISABLED. No browser site can call the
        proxy unless its origin is explicitly allowlisted via
        --allow-origin.
      - auth_token=None — no auth required by default. Set --auth-token
        to require Authorization: Bearer <token>.
    """
    RPCProxyHandler.upstream = upstream
    RPCProxyHandler.state = ProxyState()
    RPCProxyHandler.dry_run = dry_run
    RPCProxyHandler.allowed_origins = tuple(allowed_origins)
    RPCProxyHandler.auth_token = auth_token
    # Single shared HTTP client for the lifetime of the proxy.
    RPCProxyHandler.http_client = httpx.Client(timeout=30)

    server = HTTPServer(("127.0.0.1", port), RPCProxyHandler)

    log.info(f"e_AI RPC Proxy started")
    log.info(f"  Listening: http://127.0.0.1:{port}")
    log.info(f"  Upstream:  {upstream}")
    log.info(f"  Mode:      {'dry-run (log only)' if dry_run else 'active (will block critical)'}")
    log.info(f"  CORS:      {'allowlist=' + str(list(allowed_origins)) if allowed_origins else 'DISABLED (default)'}")
    log.info(f"  Auth:      {'bearer-token required' if auth_token else 'NONE (default)'}")
    log.info(f"  Profiles:  rpc_leakage, cross_protocol_risk, l2_anonymity_set (hard-coded)")
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
    finally:
        # Close the shared HTTP client cleanly on shutdown.
        if RPCProxyHandler.http_client is not None:
            RPCProxyHandler.http_client.close()
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
                        help="Log only, don't forward to upstream")
    parser.add_argument("--allow-origin", action="append", default=[],
                        help="Allowlist a CORS origin (e.g., 'https://app.kohaku.app'). "
                             "Repeat to add multiple. Default: CORS disabled.")
    parser.add_argument("--auth-token", default=None,
                        help="Require 'Authorization: Bearer <token>' on requests. "
                             "Default: no auth required.")
    parser.add_argument("--profiles", default=None,
                        help="Reserved for future profile-driven runtime; currently "
                             "the proxy hard-codes rpc_leakage / cross_protocol_risk / "
                             "l2_anonymity_set logic in source. Setting this flag "
                             "today logs a notice and does not change behavior.")
    args = parser.parse_args()

    if args.profiles:
        log.warning(
            f"--profiles {args.profiles} accepted but currently a no-op: "
            "this proxy is an illustrative adapter with hard-coded logic. "
            "See README's 'Integration demos (status: illustrative adapters)' section."
        )

    run_proxy(
        upstream=args.upstream,
        port=args.port,
        dry_run=args.dry_run,
        allowed_origins=tuple(args.allow_origin),
        auth_token=args.auth_token,
    )
