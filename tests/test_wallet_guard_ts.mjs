// Wallet guard.ts execution tests (Node, --experimental-strip-types).
//
// Codex Phase 3 review missed-coverage #1 + #2: the Python wallet ABI
// tests are a mirror, not the actual TS code. A TS refactor that keeps
// helper names but changes their bodies would silently regress. This
// test exercises withEIP1193Guard end-to-end and asserts on the alert
// shape, including the Phase 4B fix that distinguishes
// setApprovalForAll(true) vs setApprovalForAll(false).
//
// Run: node --experimental-strip-types --no-warnings tests/test_wallet_guard_ts.mjs
// Wired into CI in v2-integration-tests.

import { strict as assert } from "node:assert";
import { withEIP1193Guard } from "../examples/wallet_eip1193/guard.ts";

const ZERO_ADDR = "0x" + "00".repeat(20);
const MAX_UINT256 = "f".repeat(64);

function buildApprove(spender, amountHex) {
  const spenderWord = "0".repeat(24) + spender.toLowerCase().replace("0x", "");
  return "0x095ea7b3" + spenderWord + amountHex.padStart(64, "0");
}

function buildSetApprovalForAll(operator, approvedBool) {
  const operatorWord = "0".repeat(24) + operator.toLowerCase().replace("0x", "");
  const approvedWord = "0".repeat(63) + (approvedBool ? "1" : "0");
  return "0xa22cb465" + operatorWord + approvedWord;
}

function buildSetApprovalForAllRaw(operator, approvedWord32) {
  const operatorWord = "0".repeat(24) + operator.toLowerCase().replace("0x", "");
  return "0xa22cb465" + operatorWord + approvedWord32;
}

function buildIncreaseAllowance(spender, amountHex) {
  const spenderWord = "0".repeat(24) + spender.toLowerCase().replace("0x", "");
  return "0x39509351" + spenderWord + amountHex.padStart(64, "0");
}

function makeMockProvider() {
  return {
    async request({ method }) {
      // We don't care about the upstream result here; just need the
      // provider to resolve so the guard middleware completes.
      if (method === "eth_chainId") return "0x1";
      return null;
    },
  };
}

async function captureAlerts(method, params) {
  const captured = [];
  const actions = [];
  const guarded = withEIP1193Guard(makeMockProvider(), {
    profiles: [],
    onAlert: (alerts, action) => {
      for (const a of alerts) captured.push(a);
      actions.push(action);
    },
    blockOnCritical: false,  // we don't want to throw mid-test
    trackRpcPatterns: false,  // ignore the rpc_leakage path here
  });
  await guarded.request({ method, params });
  return { alerts: captured, actions };
}

async function main() {
  let failed = 0;

  // ---- approve(spender, MAX_UINT256) — unlimited approval ----
  {
    const spender = "0x" + "ab".repeat(20);
    const data = buildApprove(spender, MAX_UINT256);
    const { alerts, actions } = await captureAlerts("eth_sendTransaction", [
      { to: "0xtoken00000000000000000000000000000000ff", data, value: "0x0" },
    ]);
    try {
      const h1 = alerts.find((a) => a.heuristic === "H1");
      assert.ok(h1, "approve unlimited must produce H1 alert");
      assert.equal(h1.severity, "high");
      assert.match(h1.signal, /Unlimited approval/);
      // The signal includes the decoded spender; pin that.
      assert.ok(
        h1.signal.toLowerCase().includes(spender.toLowerCase()),
        "spender must appear in signal (was: tx.to bug pre-fix)",
      );
      console.log("OK: approve unlimited → H1 with correct spender");
    } catch (e) {
      console.error("FAIL: approve unlimited", e.message);
      failed++;
    }
  }

  // ---- setApprovalForAll(operator, true) — grant ----
  {
    const operator = "0x" + "cd".repeat(20);
    const data = buildSetApprovalForAll(operator, true);
    const { alerts, actions } = await captureAlerts("eth_sendTransaction", [
      { to: "0xcollection00000000000000000000000000000000", data, value: "0x0" },
    ]);
    try {
      const h4 = alerts.find((a) => a.heuristic === "H4");
      assert.ok(h4, "setApprovalForAll(true) must produce H4 alert");
      assert.equal(h4.severity, "high");
      assert.match(h4.signal, /setApprovalForAll\(true\)/);
      // No revoke alert in this case
      const revoke = alerts.find((a) => a.heuristic === "H4_revoke");
      assert.ok(!revoke, "grant must NOT produce H4_revoke");
      console.log("OK: setApprovalForAll(true) → H4 grant");
    } catch (e) {
      console.error("FAIL: setApprovalForAll(true)", e.message);
      failed++;
    }
  }

  // ---- setApprovalForAll(operator, false) — revocation (Phase 4B + 5B) ----
  {
    const operator = "0x" + "ef".repeat(20);
    const data = buildSetApprovalForAll(operator, false);
    const { alerts, actions } = await captureAlerts("eth_sendTransaction", [
      { to: "0xcollection11111111111111111111111111111111", data, value: "0x0" },
    ]);
    try {
      const revoke = alerts.find((a) => a.heuristic === "H4_revoke");
      assert.ok(revoke, "setApprovalForAll(false) must produce H4_revoke alert");
      assert.equal(revoke.severity, "info",
        "Phase 5B: revocation severity must be 'info', not 'low' or higher (Codex Phase 4 #6)");
      assert.match(revoke.signal, /REVOKED/);
      // No high-severity grant alert
      const grant = alerts.find((a) => a.heuristic === "H4" && a.severity === "high");
      assert.ok(!grant, "revocation must NOT produce a high-severity grant alert");
      // Phase 5B: revocation must NOT trigger a 'warn' user-facing action.
      assert.ok(
        !actions.includes("warn"),
        `revocation must NOT emit 'warn' (got actions=${JSON.stringify(actions)})`,
      );
      console.log("OK: setApprovalForAll(false) → H4_revoke@info, no warn");
    } catch (e) {
      console.error("FAIL: setApprovalForAll(false)", e.message);
      failed++;
    }
  }

  // ---- setApprovalForAll with non-canonical bool word — strict-malformed (Phase 5B) ----
  {
    const operator = "0x" + "11".repeat(20);
    // 0x...02 — non-canonical under strict ABI (must be 0 or 1).
    const data = buildSetApprovalForAllRaw(operator, "0".repeat(63) + "2");
    const { alerts } = await captureAlerts("eth_sendTransaction", [
      { to: "0xcollection33333333333333333333333333333333", data, value: "0x0" },
    ]);
    try {
      const malformed = alerts.find(
        (a) => a.heuristic === "malformed" && /non-canonical/.test(a.signal),
      );
      assert.ok(
        malformed,
        "non-canonical bool word must produce malformed alert under strict ABI (Phase 5B / Codex Phase 4 #5)",
      );
      assert.equal(malformed.severity, "high");
      const grant = alerts.find((a) => a.heuristic === "H4");
      assert.ok(!grant, "non-canonical bool must NOT silently classify as grant");
      console.log("OK: setApprovalForAll(0x02) → strict-malformed alert");
    } catch (e) {
      console.error("FAIL: non-canonical bool", e.message);
      failed++;
    }
  }

  // ---- increaseAllowance(spender, MAX) — should follow approve path ----
  {
    const spender = "0x" + "11".repeat(20);
    const data = buildIncreaseAllowance(spender, MAX_UINT256);
    const { alerts, actions } = await captureAlerts("eth_sendTransaction", [
      { to: "0xtoken22222222222222222222222222222222ee", data, value: "0x0" },
    ]);
    try {
      const h1 = alerts.find((a) => a.heuristic === "H1");
      assert.ok(h1, "increaseAllowance MAX must produce H1 alert");
      assert.equal(h1.severity, "high");
      console.log("OK: increaseAllowance MAX → H1");
    } catch (e) {
      console.error("FAIL: increaseAllowance MAX", e.message);
      failed++;
    }
  }

  // ---- approve with malformed calldata ----
  {
    const data = "0x095ea7b3" + "00".repeat(32);  // only 32 bytes after selector, not 64
    const { alerts, actions } = await captureAlerts("eth_sendTransaction", [
      { to: "0xtoken", data, value: "0x0" },
    ]);
    try {
      const malformed = alerts.find((a) => a.heuristic === "malformed");
      assert.ok(malformed, "malformed approve calldata must produce malformed alert");
      console.log("OK: malformed approve → malformed alert");
    } catch (e) {
      console.error("FAIL: malformed approve", e.message);
      failed++;
    }
  }

  if (failed > 0) {
    console.error(`\n${failed} test(s) failed`);
    process.exit(1);
  }
  console.log("\nAll wallet guard.ts execution tests passed");
}

main().catch((e) => {
  console.error("fatal:", e);
  process.exit(1);
});
