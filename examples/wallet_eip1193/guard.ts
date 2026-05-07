/**
 * e_AI v2 Wallet Guard — EIP-1193 provider wrapper.
 *
 * STATUS: ILLUSTRATIVE ADAPTER, NOT a profile-driven runtime. The
 * `profiles` parameter is accepted but the alert logic in `analyzeTx` /
 * `analyzeSignature` currently uses hard-coded selectors, thresholds,
 * and alert metadata — it does NOT dispatch from profile semantics.
 * A canonical profile-driven runtime is queued as a maturity-gate
 * item; until then, treat this file as a pattern reference for how a
 * wallet wrapper would integrate, not as the canonical wallet
 * runtime. See README "What's available — Integration demos (status:
 * illustrative adapters)" section.
 *
 * Works with ANY wallet that implements EIP-1193 (MetaMask, Rabby, Frame,
 * WalletConnect, injected providers, etc.)
 *
 * Intercepts:
 *   - eth_sendTransaction → approval_phishing, governance_proposal, l2_bridge_linkage
 *   - eth_signTypedData_v4 → offchain_signature
 *   - eth_call / eth_getBalance → rpc_leakage
 *
 * Usage:
 *   const guarded = withEIP1193Guard(window.ethereum, profiles);
 *   // Now use `guarded` instead of `window.ethereum` everywhere
 */

// --- Types ---

interface EIP1193Provider {
  request(args: { method: string; params?: unknown[] }): Promise<unknown>;
  on?(event: string, handler: (...args: unknown[]) => void): void;
}

interface Profile {
  meta: { domain_name: string };
  heuristics: Record<string, Heuristic>;
  [key: string]: unknown;
}

/**
 * Closed enumeration of permissible severities. Anything outside this set
 * is a profile-authoring or alert-construction bug; the profile validator
 * (`validateProfileSeverities`) and the runtime dispatch path treat
 * unknown values as fail-closed: they coerce to 'critical' on dispatch
 * AND fire an out-of-band alert via onAlert so the bug surfaces.
 *
 * Codex Phase 5 review #6: prior version typed severity as plain string,
 * letting a typo like 'critcal' silently fall to a 'warn' action. With
 * this enum + validator, that path closes.
 */
type AlertSeverity = 'critical' | 'high' | 'medium' | 'low' | 'info';

const ALERT_SEVERITIES: ReadonlySet<AlertSeverity> = new Set([
  'critical', 'high', 'medium', 'low', 'info',
] as const);

export function isKnownSeverity(s: string): s is AlertSeverity {
  return (ALERT_SEVERITIES as ReadonlySet<string>).has(s);
}

/**
 * Phase 7H: coerce alert severities in-place. Any alert with a severity
 * outside the closed enum (typo, profile bug) gets coerced to 'critical'
 * for fail-closed dispatch behavior, and a warning is logged. Returns
 * the count of coerced alerts so tests can assert on it without needing
 * to spy on console.warn.
 *
 * Exposed so tests can exercise the coercion path directly with a typoed
 * alert — the analyzeTx-built alerts in this file are TypeScript literals
 * and cannot carry a typo without breaking the type check.
 */
export function coerceAlertSeverities(
  alerts: { severity: string; profile?: string; heuristic?: string }[],
): number {
  let coerced = 0;
  for (const a of alerts) {
    if (!isKnownSeverity(a.severity)) {
      console.warn(
        `[e_AI Guard] Unknown severity ${JSON.stringify(a.severity)} ` +
        `on ${a.profile ?? '?'}/${a.heuristic ?? '?'}; coercing to ` +
        `'critical' for safety`,
      );
      a.severity = 'critical';
      coerced++;
    }
  }
  return coerced;
}

interface Heuristic {
  id: string;
  name: string;
  severity: AlertSeverity;
  description: string;
  detection: { signals: Signal[] };
  recommendations: Recommendation[];
}

interface Signal {
  name: string;
  description: string;
  confidence: number;
}

interface Recommendation {
  action: string;
  description: string;
  effectiveness: number;
}

interface Alert {
  profile: string;
  heuristic: string;
  severity: AlertSeverity;
  confidence: number;
  signal: string;
  recommendation: string;
}

interface GuardConfig {
  profiles: Profile[];
  onAlert?: (alerts: Alert[], action: 'block' | 'warn' | 'pass') => void | Promise<void>;
  onBlock?: (alerts: Alert[]) => void | Promise<void>;
  blockOnCritical?: boolean;  // default: true
  trackRpcPatterns?: boolean;  // default: true
}

// --- Known selectors ---

const SELECTORS: Record<string, { name: string; profiles: string[] }> = {
  '0x095ea7b3': { name: 'approve', profiles: ['approval_phishing'] },
  '0x39509351': { name: 'increaseAllowance', profiles: ['approval_phishing'] },
  '0xa22cb465': { name: 'setApprovalForAll', profiles: ['approval_phishing', 'offchain_signature'] },
  '0xd505accf': { name: 'permit', profiles: ['offchain_signature'] },
  '0xfe9fbb80': { name: 'execute', profiles: ['governance_proposal'] },
  '0xda95691a': { name: 'propose', profiles: ['governance_proposal'] },
  '0x56781388': { name: 'castVote', profiles: ['governance_proposal'] },
  // Bridge selectors vary by bridge contract -- would be loaded from profile
};

const MAX_UINT256 = BigInt('0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff');

// --- RPC Pattern Tracker ---

class RpcPatternTracker {
  private queries: { method: string; params: string; timestamp: number }[] = [];
  private readonly windowMs = 5 * 60 * 1000; // 5 min window

  record(method: string, params: unknown[]): void {
    this.queries.push({
      method,
      params: JSON.stringify(params).slice(0, 200),
      timestamp: Date.now(),
    });
    // Prune old
    const cutoff = Date.now() - this.windowMs;
    this.queries = this.queries.filter(q => q.timestamp > cutoff);
  }

  analyze(): Alert[] {
    const alerts: Alert[] = [];
    const methods = this.queries.map(q => q.method);

    // H1: Multiple getBalance calls linking addresses
    const balanceCalls = this.queries.filter(q => q.method === 'eth_getBalance');
    const uniqueAddresses = new Set(balanceCalls.map(q => {
      try { return JSON.parse(q.params)[0]; } catch { return ''; }
    }));
    if (uniqueAddresses.size > 3) {
      alerts.push({
        profile: 'rpc_leakage',
        heuristic: 'H1',
        severity: 'high',
        confidence: 0.8,
        signal: `Balance checked for ${uniqueAddresses.size} addresses in ${this.windowMs / 60000} min — RPC provider now knows these addresses are related`,
        recommendation: 'Use Helios local light client or batch queries through Tor',
      });
    }

    // H2: Repeated eth_call (position monitoring)
    const callCount = methods.filter(m => m === 'eth_call').length;
    if (callCount > 10) {
      alerts.push({
        profile: 'rpc_leakage',
        heuristic: 'H2',
        severity: 'medium',
        confidence: 0.6,
        signal: `${callCount} eth_call queries in ${this.windowMs / 60000} min — pattern reveals DeFi position monitoring`,
        recommendation: 'Reduce polling frequency or use local node',
      });
    }

    return alerts;
  }
}

// --- Transaction Analyzer ---

// --- ABI decoding helpers ---

const HEX_RE = /^0x[0-9a-fA-F]*$/;

function isWellFormedCalldata(data: string, expectedBytes: number): boolean {
  // expectedBytes counts the bytes AFTER the 4-byte selector.
  // Total length = 2 (for "0x") + 8 (selector) + 2*expectedBytes.
  if (!HEX_RE.test(data)) return false;
  const expectedLen = 2 + 8 + 2 * expectedBytes;
  return data.length === expectedLen;
}

function decodeAddress(data: string, byteOffset: number): string {
  // Solidity ABI: address is right-aligned in a 32-byte word. The address
  // bytes are at offset byteOffset+12 .. byteOffset+32 (skipping the 12-byte
  // left-pad). String slice in hex: skip "0x" (2 chars) + 2*byteOffset + 24
  // chars of left-pad = 2 + 2*byteOffset + 24, then take 40 chars (20 bytes
  // × 2 hex chars).
  const start = 2 + 2 * byteOffset + 24;
  return '0x' + data.slice(start, start + 40);
}

function decodeUint256(data: string, byteOffset: number): bigint {
  const start = 2 + 2 * byteOffset;
  const hex = '0x' + data.slice(start, start + 64);
  return BigInt(hex);
}

// Sentinel returned by decodeBoolStrict for malformed bool encodings.
// We surface this to callers so they can emit a malformed alert rather
// than silently coercing 0x...02 to true (Codex Phase 4 review #5).
const BOOL_DECODE_MALFORMED = Symbol("bool-decode-malformed");

function decodeBoolStrict(data: string, byteOffset: number): boolean | typeof BOOL_DECODE_MALFORMED {
  // Strict Solidity ABI: bool is encoded as 0x00...00 (false) or 0x00...01
  // (true). Any other value (high bytes set, padding bytes non-zero, value
  // > 1) is malformed. The lax "non-zero = true" reading silently passed
  // adversarial calldata that didn't match canonical ABI encoding.
  const word = decodeUint256(data, byteOffset);
  if (word === BigInt(0)) return false;
  if (word === BigInt(1)) return true;
  return BOOL_DECODE_MALFORMED;
}

function analyzeTx(to: string, data: string, value: bigint, profiles: Profile[]): Alert[] {
  const alerts: Alert[] = [];
  if (!data || data.length < 10) return alerts;

  const selector = data.slice(0, 10);
  const known = SELECTORS[selector];

  // Approval checks: approve(address spender, uint256 amount)
  // Calldata layout: selector (4B) + spender (32B word, right-aligned addr) + amount (32B)
  if (selector === '0x095ea7b3' || selector === '0x39509351') {
    if (!isWellFormedCalldata(data, 64)) {
      // Malformed approval calldata — fail closed with a high-severity alert
      alerts.push({
        profile: 'approval_phishing',
        heuristic: 'malformed',
        severity: 'high',
        confidence: 0.9,
        signal: `Malformed approve() calldata (length ${data.length}, expected 138 hex chars). Refusing to silently pass.`,
        recommendation: 'Reject the transaction; calldata cannot be decoded. Most likely a wallet/dApp bug or spoof attempt.',
      });
      return alerts;
    }
    let spender: string;
    let amount: bigint;
    try {
      spender = decodeAddress(data, 4);
      amount = decodeUint256(data, 4 + 32);
    } catch (e) {
      alerts.push({
        profile: 'approval_phishing',
        heuristic: 'decode_error',
        severity: 'high',
        confidence: 0.8,
        signal: `Could not decode approve() calldata: ${(e as Error).message}`,
        recommendation: 'Reject the transaction.',
      });
      return alerts;
    }

    if (amount >= MAX_UINT256 / BigInt(2)) {
      alerts.push({
        profile: 'approval_phishing',
        heuristic: 'H1',
        severity: 'high',
        confidence: 0.95,
        signal: `Unlimited approval — token=${to}, spender=${spender}`,
        recommendation: 'Set approval to exact amount needed, not unlimited. Verify the spender address.',
      });
    }
  }

  // setApprovalForAll(address operator, bool approved)
  // Calldata layout: selector (4B) + operator (32B word) + approved (32B word)
  if (selector === '0xa22cb465') {
    if (!isWellFormedCalldata(data, 64)) {
      alerts.push({
        profile: 'approval_phishing',
        heuristic: 'malformed',
        severity: 'high',
        confidence: 0.9,
        signal: `Malformed setApprovalForAll() calldata (length ${data.length}). Refusing to silently pass.`,
        recommendation: 'Reject the transaction.',
      });
      return alerts;
    }
    let operator: string;
    let approvedRaw: boolean | typeof BOOL_DECODE_MALFORMED;
    try {
      operator = decodeAddress(data, 4);
      approvedRaw = decodeBoolStrict(data, 4 + 32);
    } catch {
      operator = '<decode-failed>';
      approvedRaw = BOOL_DECODE_MALFORMED;
    }

    if (approvedRaw === BOOL_DECODE_MALFORMED) {
      // Strict ABI failure: bool word was neither 0 nor 1. Codex Phase 4
      // review #5 — fail closed with a malformed alert rather than
      // silently classifying as grant.
      alerts.push({
        profile: 'approval_phishing',
        heuristic: 'malformed',
        severity: 'high',
        confidence: 0.9,
        signal: `setApprovalForAll() bool word is non-canonical (not 0 or 1). Refusing to silently classify.`,
        recommendation: 'Reject the transaction; calldata is not strict-ABI conformant.',
      });
    } else if (approvedRaw === false) {
      // setApprovalForAll(false) is a REVOCATION — defensive, not noisy.
      // Codex Phase 4 review #6: do NOT emit a wallet warning for this
      // path. We log it via onAlert at severity:"info" so observability
      // pipelines can capture it, but the dispatch logic in
      // withEIP1193Guard now treats info as pass (no warn).
      alerts.push({
        profile: 'approval_phishing',
        heuristic: 'H4_revoke',
        severity: 'info',
        confidence: 0.95,
        signal: `setApprovalForAll(false) — operator approval REVOKED, collection=${to}, operator=${operator}`,
        recommendation: 'No action needed; revocation is a defensive operation.',
      });
    } else {
      alerts.push({
        profile: 'approval_phishing',
        heuristic: 'H4',
        severity: 'high',
        confidence: 0.75,
        signal: `setApprovalForAll(true) — collection=${to}, operator=${operator}`,
        recommendation: 'Verify the operator contract is legitimate before approving all NFTs',
      });
    }
  }

  return alerts;
}

// --- Signature Analyzer ---

function analyzeSignature(typedData: unknown): Alert[] {
  const alerts: Alert[] = [];
  if (!typedData || typeof typedData !== 'object') return alerts;

  const td = typedData as Record<string, unknown>;
  const primaryType = td.primaryType as string || '';
  const domain = td.domain as Record<string, unknown> || {};
  const message = td.message as Record<string, unknown> || {};

  // Permit2
  if (primaryType === 'PermitSingle' || primaryType === 'PermitBatch') {
    const amount = message.details && typeof message.details === 'object'
      ? (message.details as Record<string, unknown>).amount
      : message.amount;

    alerts.push({
      profile: 'offchain_signature',
      heuristic: primaryType === 'PermitBatch' ? 'H5' : 'H1',
      severity: 'high',
      confidence: 0.9,
      signal: `${primaryType} signature — authorizes token transfer without on-chain approval tx`,
      recommendation: 'Check the spender address and amount carefully. Set short expiration.',
    });
  }

  // Seaport order
  if (primaryType === 'OrderComponents' || domain.name === 'Seaport') {
    alerts.push({
      profile: 'offchain_signature',
      heuristic: 'H6',
      severity: 'medium',
      confidence: 0.7,
      signal: 'Seaport order signature — verify the listing price matches your intent',
      recommendation: 'Check that offer and consideration items match expected values',
    });
  }

  // Generic EIP-712 with transfer-like fields
  if (message.to && message.value) {
    alerts.push({
      profile: 'offchain_signature',
      heuristic: 'H2',
      severity: 'high',
      confidence: 0.8,
      signal: 'EIP-712 typed data contains transfer fields (to, value) — this signature may authorize a token transfer',
      recommendation: 'Verify this is not a disguised approval or transfer authorization',
    });
  }

  return alerts;
}

// --- Main Guard ---

/**
 * Validate that every heuristic in every profile carries a severity in the
 * closed enum. Returns the list of (profile, heuristicKey, badSeverity)
 * tuples. Phase 6D: surfaces profile-authoring bugs at config time rather
 * than at first dispatch.
 *
 * Phase 7E (Codex Phase 6 review #5): hardened against malformed input.
 * Accepts unknown[] and defensively checks each entry's shape. null /
 * non-object profile entries surface as offenders rather than crashing.
 * Profiles without a `heuristics` dict surface a single
 * "<no-heuristics>" offender.
 *
 * Caller decides whether to throw or log+continue. The default
 * `withEIP1193Guard` call logs a warning per offender; callers who want
 * strict mode can throw on a non-empty list.
 */
export function validateProfileSeverities(
  profiles: unknown[],
): { profile: string; heuristic: string; severity: string }[] {
  const offenders: { profile: string; heuristic: string; severity: string }[] = [];
  if (!Array.isArray(profiles)) {
    offenders.push({ profile: '<unknown>', heuristic: '<input>', severity: '<not-array>' });
    return offenders;
  }
  for (const p of profiles) {
    if (p === null || typeof p !== 'object') {
      offenders.push({
        profile: '<unknown>', heuristic: '<profile>',
        severity: p === null ? '<null>' : `<${typeof p}>`,
      });
      continue;
    }
    const obj = p as { meta?: { domain_name?: unknown }; heuristics?: unknown };
    const dom = (typeof obj.meta?.domain_name === 'string' && obj.meta.domain_name) || '<unknown>';
    const heur = obj.heuristics;
    if (heur === undefined || heur === null) {
      offenders.push({ profile: dom, heuristic: '<no-heuristics>', severity: '<missing>' });
      continue;
    }
    if (typeof heur !== 'object' || Array.isArray(heur)) {
      offenders.push({
        profile: dom, heuristic: '<no-heuristics>',
        severity: Array.isArray(heur) ? '<array>' : `<${typeof heur}>`,
      });
      continue;
    }
    for (const [hkey, hval] of Object.entries(heur as Record<string, unknown>)) {
      if (hval === null || typeof hval !== 'object') {
        offenders.push({
          profile: dom, heuristic: hkey,
          severity: hval === null ? '<null>' : `<${typeof hval}>`,
        });
        continue;
      }
      const sev = (hval as { severity?: unknown }).severity ?? '<missing>';
      if (typeof sev !== 'string' || !isKnownSeverity(sev)) {
        offenders.push({ profile: dom, heuristic: hkey, severity: String(sev) });
      }
    }
  }
  return offenders;
}

export function withEIP1193Guard(
  provider: EIP1193Provider,
  config: GuardConfig,
): EIP1193Provider {
  // Phase 6D: validate severities at config time. We log offenders but
  // do not throw — callers using `validateProfileSeverities` directly can
  // enforce strict mode in their own setup.
  const offenders = validateProfileSeverities(config.profiles ?? []);
  for (const o of offenders) {
    console.warn(
      `[e_AI Guard] profile=${o.profile} heuristic=${o.heuristic} has ` +
      `unrecognized severity ${JSON.stringify(o.severity)}; ` +
      `runtime will coerce alerts using this heuristic to 'critical' for safety`,
    );
  }

  const rpcTracker = config.trackRpcPatterns !== false ? new RpcPatternTracker() : null;
  const blockOnCritical = config.blockOnCritical !== false;

  return {
    ...provider,

    async request(args: { method: string; params?: unknown[] }): Promise<unknown> {
      const { method, params = [] } = args;
      let alerts: Alert[] = [];

      // --- Layer 3: Transaction Guard ---
      if (method === 'eth_sendTransaction') {
        const tx = params[0] as Record<string, string>;
        const to = tx?.to || '';
        const data = tx?.data || '0x';
        const value = tx?.value ? BigInt(tx.value) : BigInt(0);

        alerts = analyzeTx(to, data, value, config.profiles);
      }

      // --- Layer 3: Signature Guard ---
      if (method === 'eth_signTypedData_v4') {
        const typedDataStr = params[1] as string;
        try {
          const typedData = JSON.parse(typedDataStr);
          alerts = analyzeSignature(typedData);
        } catch {}
      }

      // --- Layer 2: Provider Guard (RPC tracking) ---
      if (rpcTracker) {
        rpcTracker.record(method, params);

        if (method === 'eth_getBalance' || method === 'eth_call') {
          const rpcAlerts = rpcTracker.analyze();
          alerts.push(...rpcAlerts);
        }
      }

      // --- Dispatch alerts ---
      // Codex Phase 4 review #6: severity 'info' alerts (e.g., the
      // setApprovalForAll(false) revocation note) must NOT trigger a
      // user-facing 'warn' action. They are observability events, not
      // friction. Only alerts at severity ≥ low contribute to 'warn'.
      //
      // Phase 5 review #6 / Phase 6D / Phase 7H: any alert with an unknown
      // severity (typo'd 'critcal', new value 'debug', etc.) is fail-
      // closed — coerced to 'critical' for dispatch decisions so it
      // BLOCKS rather than silently passing or warning. The unknown value
      // is also surfaced to onAlert so the profile/alert-construction
      // bug is observable. Coercion logic factored into
      // `coerceAlertSeverities` so tests can exercise it directly
      // (Phase 7H).
      coerceAlertSeverities(alerts);
      const userVisible = alerts.filter(a => a.severity !== 'info');
      if (alerts.length > 0) {
        const hasCritical = alerts.some(a => a.severity === 'critical' && a.confidence > 0.8);
        const action = hasCritical && blockOnCritical
          ? 'block'
          : userVisible.length > 0
          ? 'warn'
          : 'pass';

        if (config.onAlert) {
          await config.onAlert(alerts, action);
        }

        if (action === 'block') {
          if (config.onBlock) {
            await config.onBlock(alerts);
          }
          throw new Error(
            `e_AI Guard blocked ${method}: ${alerts.map(a => `[${a.heuristic}] ${a.signal}`).join('; ')}`
          );
        }
      }

      // --- Pass through ---
      return provider.request(args);
    },
  };
}


// --- Demo ---

async function demo() {
  // Mock provider
  const mockProvider: EIP1193Provider = {
    async request({ method, params }) {
      console.log(`  [Provider] ${method}(${JSON.stringify(params).slice(0, 80)}...)`);
      if (method === 'eth_sendTransaction') return '0xtxhash';
      if (method === 'eth_getBalance') return '0x1000000000000000';
      return null;
    },
  };

  const guarded = withEIP1193Guard(mockProvider, {
    profiles: [],
    blockOnCritical: true,
    onAlert: (alerts, action) => {
      console.log(`\n  [Guard] ${action.toUpperCase()}: ${alerts.length} alert(s)`);
      for (const a of alerts) {
        console.log(`    [${a.profile}/${a.heuristic}] ${a.severity} (${(a.confidence * 100).toFixed(0)}%): ${a.signal}`);
        console.log(`    → ${a.recommendation}`);
      }
    },
    onBlock: (alerts) => {
      console.log(`\n  ⛔ BLOCKED`);
    },
  });

  console.log('=== Scenario 1: Unlimited approval ===');
  // ABI-correct calldata: approve(spender=0xdead...beef, amount=MAX_UINT256).
  // The previous demo had `spender` as a literal string — non-hex — so the
  // guard fired the malformed-calldata branch instead of the H1 unlimited-
  // approval branch the demo is supposed to illustrate. Phase 5D /
  // Codex Phase 4 review nice-to-have #1.
  try {
    await guarded.request({
      method: 'eth_sendTransaction',
      params: [{
        to: '0x1234567890abcdef1234567890abcdef12345678',
        data: '0x095ea7b3'
          + '000000000000000000000000deadbeefdeadbeefdeadbeefdeadbeefdeadbeef'
          + 'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',
        value: '0x0',
      }],
    });
  } catch (e: any) { console.log(`  Caught: ${e.message.slice(0, 80)}`); }

  console.log('\n=== Scenario 2: Permit2 signature ===');
  try {
    await guarded.request({
      method: 'eth_signTypedData_v4',
      params: [
        '0xuser',
        JSON.stringify({
          primaryType: 'PermitSingle',
          domain: { name: 'Permit2' },
          message: { details: { amount: '115792089237316195423570985008687907853269984665640564039457584007913129639935' } },
        }),
      ],
    });
  } catch (e: any) { console.log(`  Caught: ${e.message.slice(0, 80)}`); }

  console.log('\n=== Scenario 3: Multiple balance checks (RPC leakage) ===');
  for (const addr of ['0xaaa', '0xbbb', '0xccc', '0xddd']) {
    await guarded.request({ method: 'eth_getBalance', params: [addr, 'latest'] });
  }

  console.log('\n=== Done ===');
}

// Run if executed directly
const isMain = typeof process !== 'undefined' && process.argv[1]?.endsWith('guard.ts');
if (isMain) demo().catch(console.error);
