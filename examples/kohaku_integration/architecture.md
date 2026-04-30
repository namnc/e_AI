# e_AI v2 × Kohaku: Integration Architecture

## The problem

e_AI has 9 domain profiles. Each hooks into a different layer of the wallet stack. A single middleware wrapping Kohaku plugins only catches 1 of 9.

## Kohaku's 4 integration surfaces

```
┌─────────────────────────────────────────────────────────┐
│  User action (send, sign, query, vote, bridge)          │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │ Layer 4: Plugin Operations                      │    │
│  │   prepareShield / prepareTransfer / prepareUnshield  │
│  │   → Railgun, Privacy Pools                      │    │
│  └────────────────────┬────────────────────────────┘    │
│                       │                                  │
│  ┌────────────────────┴────────────────────────────┐    │
│  │ Layer 3: TxSigner                               │    │
│  │   signMessage / sendTransaction                 │    │
│  │   → ALL outgoing transactions and signatures    │    │
│  └────────────────────┬────────────────────────────┘    │
│                       │                                  │
│  ┌────────────────────┴────────────────────────────┐    │
│  │ Layer 2: EthereumProvider                       │    │
│  │   getBalance / call / request / getLogs          │    │
│  │   → ALL RPC queries to the chain                │    │
│  └────────────────────┬────────────────────────────┘    │
│                       │                                  │
│  ┌────────────────────┴────────────────────────────┐    │
│  │ Layer 1: Host                                   │    │
│  │   provider + network + storage + keystore       │    │
│  │   → App context, persistent state               │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

## Profile → Layer mapping

| Profile | Layer | Hook | What it intercepts |
|---|---|---|---|
| stealth_address_ops | 4 (Plugin) | `prepareShield/Unshield` | Stealth addr deposits/withdrawals |
| approval_phishing | 3 (TxSigner) | `sendTransaction` | approve/increaseAllowance calls |
| offchain_signature | 3 (TxSigner) | `signMessage` | EIP-712, Permit2, Seaport signatures |
| governance_proposal | 3 (TxSigner) | `sendTransaction` | Governance execute/vote calls |
| l2_bridge_linkage | 3 (TxSigner) | `sendTransaction` | Bridge deposit/withdraw calls |
| rpc_leakage | 2 (Provider) | `getBalance/call/request` | All RPC queries |
| cross_protocol_risk | 1 (Host) | Background monitor | Continuous portfolio state |
| l2_anonymity_set | 1 (Host) | Background monitor | Continuous pool size monitoring |

## Implementation: 4 guards, not 1 middleware

### Guard 1: Plugin Guard (Layer 4)
```typescript
// Wraps PluginInstance — intercepts privacy protocol operations
function withPluginGuard<T extends PluginInstance>(plugin: T, profiles: Profile[]): T
```
**Profiles:** stealth_address_ops
**Trigger:** Before prepareShield/prepareTransfer/prepareUnshield
**Action:** Block or warn based on heuristic analysis

### Guard 2: Transaction Guard (Layer 3)
```typescript
// Wraps TxSigner — intercepts ALL outgoing transactions and signatures
function withTxGuard(signer: TxSigner, profiles: Profile[]): TxSigner
```
**Profiles:** approval_phishing, offchain_signature, governance_proposal, l2_bridge_linkage
**Trigger:** Before sendTransaction or signMessage
**Action:** Decode calldata/typed data → match against relevant profile → block/warn

This is the highest-value guard. It catches:
- `sendTransaction`: decode function selector → route to approval_phishing (approve/increaseAllowance), governance_proposal (execute/vote), l2_bridge_linkage (bridge deposit/withdraw)
- `signMessage`: decode EIP-712 typed data → route to offchain_signature (Permit2, Seaport, setApprovalForAll)

### Guard 3: Provider Guard (Layer 2)
```typescript
// Wraps EthereumProvider — intercepts ALL RPC queries
function withProviderGuard(provider: EthereumProvider, profiles: Profile[]): EthereumProvider
```
**Profiles:** rpc_leakage
**Trigger:** Before getBalance, call, request, getLogs
**Action:** Analyze query pattern over time → warn if pattern reveals strategy → suggest batching, Helios, Tor

This extends e_AI v1's cover query concept to the RPC layer.

### Guard 4: Background Monitor (Layer 1)
```typescript
// Runs on Host — continuous monitoring, not per-action
function startBackgroundMonitor(host: Host, profiles: Profile[]): Monitor
```
**Profiles:** cross_protocol_risk, l2_anonymity_set
**Trigger:** Periodic (every N blocks or every M minutes)
**Action:** Scan portfolio state → flag concentration risk, thin pools, oracle dependencies

## Routing logic

When a user action hits Kohaku:

```
User action
    │
    ├─ Is it a plugin operation? ──→ Guard 1 (Plugin)
    │
    ├─ Is it a transaction? ──→ Guard 2 (Transaction)
    │   ├─ Decode selector
    │   ├─ approve/permit? → approval_phishing profile
    │   ├─ governance? → governance_proposal profile  
    │   ├─ bridge? → l2_bridge_linkage profile
    │   └─ other? → generic checks only
    │
    ├─ Is it a signature? ──→ Guard 2 (Transaction)
    │   ├─ Decode EIP-712 typed data
    │   ├─ Permit2/Seaport? → offchain_signature profile
    │   └─ unknown? → warn "unrecognized signature type"
    │
    └─ Is it an RPC query? ──→ Guard 3 (Provider)
        ├─ Log query to pattern tracker
        ├─ Check pattern against rpc_leakage profile
        └─ If pattern detected → suggest cover queries / Helios
```

Background monitor runs independently on a timer.

## What this means for Kohaku PR

Instead of one `@kohaku-eth/ops-advisor` package, we propose:

```
@kohaku-eth/guards
├── plugin-guard.ts      ← wraps PluginInstance
├── tx-guard.ts          ← wraps TxSigner  
├── provider-guard.ts    ← wraps EthereumProvider
├── background-monitor.ts ← runs on Host
├── profile-router.ts    ← routes actions to correct profile
└── index.ts             ← exports withGuards(host, profiles)
```

Single entry point:
```typescript
import { withGuards } from '@kohaku-eth/guards';

const guarded = withGuards(host, {
    profiles: loadAllProfiles('domains/'),
    onBlock: (alert) => showWarning(alert),
    onCritical: (alert) => blockAction(alert),
});
```
