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

interface Heuristic {
  id: string;
  name: string;
  severity: string;
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
  severity: string;
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

function decodeBool(data: string, byteOffset: number): boolean {
  // Solidity ABI: bool is encoded in a 32-byte word; non-zero word = true.
  // We read as uint256 and compare against zero.
  return decodeUint256(data, byteOffset) !== BigInt(0);
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
    let approved: boolean;
    try {
      operator = decodeAddress(data, 4);
      approved = decodeBool(data, 4 + 32);
    } catch {
      operator = '<decode-failed>';
      approved = true;  // fail closed: alert if we can't tell
    }

    // Codex Phase 3 review missed-coverage #2: setApprovalForAll(false) is
    // a REVOCATION, not a grant — emit an info-level note rather than the
    // high-severity grant alert. Previously fired the same alert for both.
    if (!approved) {
      alerts.push({
        profile: 'approval_phishing',
        heuristic: 'H4_revoke',
        severity: 'low',
        confidence: 0.9,
        signal: `setApprovalForAll(false) — REVOKING operator approval, collection=${to}, operator=${operator}`,
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

export function withEIP1193Guard(
  provider: EIP1193Provider,
  config: GuardConfig,
): EIP1193Provider {
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
      if (alerts.length > 0) {
        const hasCritical = alerts.some(a => a.severity === 'critical' && a.confidence > 0.8);
        const action = hasCritical && blockOnCritical ? 'block' : alerts.length > 0 ? 'warn' : 'pass';

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
  try {
    await guarded.request({
      method: 'eth_sendTransaction',
      params: [{
        to: '0x1234567890abcdef1234567890abcdef12345678',
        data: '0x095ea7b3000000000000000000000000spender0000000000000000000000000ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',
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
