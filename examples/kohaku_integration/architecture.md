# e_AI v2 Integration Architecture

## 3 integration points, clean split

```
┌──────────────────────────────────────────────────────┐
│  User's machine                                      │
│                                                      │
│  ┌────────────────────────────────────────────────┐  │
│  │  Wallet (MetaMask, Rabby, Frame, any EIP-1193) │  │
│  │  Guard: pre-sign analysis                      │  │
│  │  Profiles: stealth_address_ops                 │  │
│  │            approval_phishing                   │  │
│  │            offchain_signature                  │  │
│  │            governance_proposal                 │  │
│  │            l2_bridge_linkage                   │  │
│  └─────────────────────┬──────────────────────────┘  │
│                        │                              │
│  ┌─────────────────────▼──────────────────────────┐  │
│  │  Local RPC (Helios / full node / L2 node)      │  │
│  │  Guard: query pattern + state accumulation     │  │
│  │  Profiles: rpc_leakage                         │  │
│  │            cross_protocol_risk                 │  │
│  │            l2_anonymity_set                    │  │
│  └────────────────────────────────────────────────┘  │
│                                                      │
│  ┌────────────────────────────────────────────────┐  │
│  │  LLM Proxy                                     │  │
│  │  Guard: query sanitization + cover queries     │  │
│  │  Profiles: defi_query (v1)                     │  │
│  └────────────────────────────────────────────────┘  │
│                                                      │
│  Local LLM (Ollama) ← shared by all guards           │
└──────────────────────────────────────────────────────┘
```

## Why this split

| Integration point | What it sees | Profiles | Count |
|---|---|---|---|
| **Wallet** | User actions (sign, send) | stealth_ops, approval_phishing, offchain_signature, governance_proposal, l2_bridge_linkage | 5 |
| **Local RPC** | On-chain reads (balances, calls, logs) | rpc_leakage, cross_protocol_risk, l2_anonymity_set | 3 |
| **LLM Proxy** | AI queries about DeFi | defi_query (v1) | 1 |

**Wallet** handles actions. **Local RPC** handles reads. **LLM Proxy** handles AI queries. No overlap.

## Assumptions

- **Local RPC is assumed.** Helios for L1, local node for L2, or any private RPC endpoint the user controls. The analysis reads accumulated local state -- it does NOT query external RPCs to gather data (that would be the privacy leak it's trying to prevent).
- **Inventing read privacy is out of scope.** PIR, ORAM, FHE-based private state access are research problems. We assume the user has a private way to read chain state. If they don't, the rpc_leakage profile warns them.
- **Wallet-agnostic.** The wallet guard wraps EIP-1193 (`request` method). Any wallet that implements EIP-1193 works.

## Wallet Guard (5 profiles)

Intercepts `eth_sendTransaction` and `eth_signTypedData_v4` before the wallet signs.

```
User action → Wallet Guard → decode calldata/typed data → route to profile
                                  │
                                  ├── approve/increaseAllowance → approval_phishing
                                  ├── EIP-712 Permit2/Seaport → offchain_signature
                                  ├── governance execute/vote → governance_proposal
                                  ├── bridge deposit/withdraw → l2_bridge_linkage
                                  └── stealth shield/unshield → stealth_address_ops
```

Implementation options:
- **MetaMask Snap** (largest reach)
- **Browser extension** (wallet-agnostic, intercepts `window.ethereum`)
- **wagmi/viem middleware** (DApp-level, any DApp using wagmi)
- **Kohaku plugin** (for Kohaku users)

See `examples/wallet_eip1193/guard.ts` for working EIP-1193 implementation.

## Local RPC Guard (3 profiles)

Accumulates state from on-chain reads that flow through the local node.

```
Wallet/DApp → Local RPC → serves query from local state
                │
                └── Guard accumulates:
                    ├── Balance queries → rpc_leakage (which addresses checked?)
                    ├── Contract calls → cross_protocol_risk (portfolio state)
                    └── Pool/log data → l2_anonymity_set (pool sizes over time)
```

The guard does NOT make additional queries. It passively observes what the wallet is already reading and builds the analysis from that.

See `examples/l2_monitor/guard.py` for L2 monitoring implementation.

## LLM Proxy Guard (1 profile)

This is e_AI v1. Sanitizes DeFi queries before sending to cloud LLM.

```
User/Agent → LLM Proxy → sanitize query → cloud LLM → synthesize answer
                │
                └── Removes: addresses, amounts, positions, strategies
                    Adds: cover queries (indistinguishable from real)
```

See `cover_generator.py` and `docs/walkthrough_handcrafted.md` for v1 documentation.

## Profile → Integration mapping

| # | Profile | Access method | Integration | CROPS |
|---|---|---|---|---|
| 1 | stealth_address_ops | Wallet | Wallet guard | P |
| 2 | approval_phishing | Wallet | Wallet guard | S |
| 3 | offchain_signature | Wallet | Wallet guard | S |
| 4 | governance_proposal | Application | Wallet guard | S |
| 5 | l2_bridge_linkage | L2 | Wallet guard | P |
| 6 | rpc_leakage | AI | Local RPC guard | P |
| 7 | cross_protocol_risk | Application | Local RPC guard | S |
| 8 | l2_anonymity_set | L2 | Local RPC guard | P |
| 9 | defi_query (v1) | AI | LLM proxy | P |

## What the user configures

1. Install wallet guard (snap / extension / library)
2. Run local RPC (Helios for L1, L2 node for L2)
3. Point wallet to local RPC
4. (Optional) Run LLM proxy if using cloud AI for DeFi questions

One-time setup, all profiles active automatically.
