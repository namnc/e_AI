# Composition — how the guards compose across a transaction's lifecycle

The 16 guards are not isolated tools. They fire at different points in a
transaction's life — from intent-formation to post-execution traces — and
compose through the five integration surfaces. This document shows where
each guard fires and how the surfaces channel them.

## Lifecycle phases

```
[Phase 1: Intent]                — user thinks, queries LLM, queries RPC
       ↓
[Phase 2: Wallet pre-sign]       — wallet inspects the constructed tx
       ↓
[Phase 3: Submission]            — tx leaves the host (mempool / private / direct)
       ↓
[Phase 4: Inclusion]             — tx lands in a block, becomes public
       ↓
[Phase 5: Post-execution]        — the trace is on-chain forever
```

Each phase has guards that fire there and guards that observe state
accumulated from earlier phases.

---

### Phase 1 — Intent

User reads RPC state, queries an AI assistant, or watches DApp dashboards
to decide what to do.

| Guard | Fires when |
|---|---|
| `rpc_leakage` | User issues balance/log/storage queries that reveal portfolio or strategy to the RPC provider. Cumulative — fires after a session crosses heuristic thresholds. |
| `behavioral_drift` | User's recent positions have drifted from baseline — concentration, leverage creep. Cumulative; fires when about to add to the drift. |

**Surface**: RPC proxy (`proxy/rpc_proxy.py`) catches the RPC pattern
locally; AI agent guard (`examples/ai_agent/guard.py`) catches it in
agent-mediated flows. Both compose with the local LLM.

**Real example (`rpc_leakage`)**: a user with arbitrage strategy who polls
five wallets every six hours leaks the address set + cadence to whichever
RPC provider serves them. The guard fires on the cumulative pattern, not on
any single query. See [scenarios §5](scenarios.md#5-ai-assistant-query-leakage-cyberhaven-2024-chatgpt-history-exposure).

---

### Phase 2 — Wallet pre-sign

The wallet has the constructed transaction object, signed-message intent,
or proposal. This is where the **majority of guards fire** — the rich
context (calldata, signature payload, target contract, history) is
available before any commitment.

| Guard | Fires when |
|---|---|
| `approval_phishing` | `approve()` / `setApprovalForAll()` / Permit2-signature with unlimited or scam-contract target |
| `offchain_signature` | EIP-712 typed-data sign request matches malicious permit pattern |
| `mev_vulnerability` | Public-mempool swap with high slippage / large size / no MEV-protection route |
| `stealth_address_ops` | Stealth-address withdrawal whose timing/amount/gas/funding pattern matches Wahrstätter's deanon heuristics |
| `pq_readiness` | Operation that would expose a quantum-vulnerable secret (first-use of a key with public-pubkey state, etc.) |
| `wrong_chain_address` | Chain-ID / contract-vs-EOA mismatch (largely solved by Rabby; included for completeness) |
| `backup_security` | Recovery / guardian-rotation / new-device signing tx where the underlying backup posture is risky |
| `cross_protocol_risk` | Tx that increases concentration or correlated exposure across DeFi protocols |
| `governance_proposal` | About to vote on a proposal that contains treasury-drain / parameter-manipulation / proxy-upgrade patterns |

**Surfaces**:
- Wallet EIP-1193 (`examples/wallet_eip1193/guard.ts`) — wraps any
  EIP-1193 provider; intercepts `eth_sendTransaction`,
  `eth_signTypedData_v4`, `eth_call`, `eth_getBalance`
- DApp frontend (`examples/dapp_frontend/guard.js`) — JavaScript SDK that
  intercepts contract interactions before they reach the wallet
- Kohaku integration (`examples/kohaku_integration/`) — full TypeScript
  middleware demonstrating the wallet-side composition

**Real example (`approval_phishing`)**: Blockaid reported blocking 40,000+
Angelferno drainer attempts in June 2025 alone (~$494M total losses to
wallet drainers across 2024 per ScamSniffer's annual report). e_AI's `approval_phishing`
fires pre-sign on the same heuristic class — unlimited approval + unverified
contract + bytecode-template scam-DB match. See
[scenarios §2](scenarios.md#2-approval-phishing-blockaidslowmistscam-sniffer-2024-2025-incident-class).

---

### Phase 3 — Submission

The wallet picks a path: public mempool, private mempool, or direct-to-
builder. This phase is where censorship resistance and front-running are
decided.

| Guard | Fires when |
|---|---|
| `builder_censorship` | Selected relay set is censoring; OFAC interaction; no forced-inclusion path; builder monoculture |
| `sequencer_privacy` | L2 destination chain has a centralized sequencer that will see the tx pre-batch |

**Surface**: All four pre-sign surfaces above can pre-emptively check the
submission-path posture. The forthcoming EIP-8141 / FOCIL composition
(see [`docs/access_layer_context.md`](access_layer_context.md)) will move
some of this responsibility into the protocol — but the access-layer guard
remains useful for current users with current relay configurations.

**Real example (`builder_censorship`)**: Tornado Cash users post-OFAC face
silent drops at relays with compliance lists (bloXroute Regulated,
Manifold). Per soispoke's 2026-05-07 Dune dashboard, Tornado Cash is still
processing 10,781 txs / 90 days — those users need to know which relay set
to configure. See [scenarios §4](scenarios.md#4-builderrelay-censorship--tornado-cash-post-ofac).

---

### Phase 4 — Inclusion

The tx lands in a block and becomes public. Behavioral fingerprinting
becomes possible from this point forward.

| Guard | Fires when |
|---|---|
| `l2_anonymity_set` | Privacy pool on L2 has fewer than 20 active depositors in the user's denomination; the withdrawal would land in a thin anonymity set |
| `l2_bridge_linkage` | Bridge tx pattern enables cross-chain identity correlation |
| `mixing_behavioral` | Pattern after the mixing step would survive Tutela-class heuristics |

**Surfaces**:
- L2 monitor (`examples/l2_monitor/guard.py`) — observes pool / bridge /
  sequencer state, fires alerts on cross-chain patterns
- All wallet-side surfaces — the guards run pre-sign with the post-
  inclusion threat model in mind

**Real example (`l2_anonymity_set`)**: per the soispoke 2026-05-07 Dune
dashboard, 0xbow Privacy Pools runs at ~1.5 nullifier-events per pool per
day across 14 pools. The H1 threshold (`<20 depositors/24h → WARN`,
`<5 → BLOCK`) fires correctly on this measured thinness. See
[scenarios §6 / l2_anonymity_set guide](../domains/l2_anonymity_set/README.md).

**Real example (`mixing_behavioral`)**: Tutela demonstrated 42,852 of
97,331 Tornado Cash deposits compromised by post-deposit behavioral
heuristics. See [scenarios §6](scenarios.md#6-post-mixer-behavioral-linkage-tutela--pareto-xyz).

---

### Phase 5 — Post-execution

After the block lands, the trace is on-chain forever. **No protocol-level
defense closes this phase** — it is access-layer responsibility.

| Concern | What e_AI does |
|---|---|
| Repeated trades from the same shielded balance with recognizable patterns | `behavioral_drift` + `mixing_behavioral` fire pre-Phase-2 to prevent the recognizable pattern from materializing |
| IP exposure on first submission (network peers see the originating IP) | **Out of scope for e_AI** — wallet-level Tor / mixnet is the answer; surfaced in [`docs/access_layer_context.md`](access_layer_context.md) |
| On-chain target / amount metadata after encrypted-frame-tx decrypts | **Out of scope for e_AI** — protocol-level private execution state is the long-run answer (not yet planned for L1) |

These two residual gaps are exactly what soispoke flagged as "what Alice
still needs to worry about" after all four protocol upgrades land
(EIP-8141 native AA, 2D nonces, encrypted frame transactions, FOCIL). See
[`docs/access_layer_context.md`](access_layer_context.md) for the broader
roadmap.

---

## Cross-phase compositions

Some real risks cross phases. The guards compose to surface them:

**Whale arbitrage with public mempool**: Phase 1 `rpc_leakage` fires on
sustained balance polling → Phase 2 `mev_vulnerability` fires pre-sign on
high-slippage swap → Phase 3 `builder_censorship` checks if the chosen
submission path is private. Reader composition: a single tx triggers two
or three guards across the lifecycle. The wallet UI surfaces all of them
and recommends the unified mitigation set.

**Stealth-address withdrawal**: Phase 2 `stealth_address_ops` fires on
timing-too-tight + same-entity withdrawal patterns; the recommendation
(`use ERC-4337 paymaster`) connects naturally to the upcoming EIP-8141
native paymaster (Phase 3). The guard documents this transition path —
when EIP-8141 ships, the H4 mitigation becomes a first-class language
construct.

**Privacy-pool deposit then withdrawal**: Phase 4 `l2_anonymity_set` checks
pool size at deposit; Phase 4 `mixing_behavioral` checks withdrawal pattern
hygiene. The same guard set spans both.

---

## Integration surface summary

| Surface | Phase coverage | Best-fit user |
|---|---|---|
| Wallet EIP-1193 (`examples/wallet_eip1193/guard.ts`) | 2, 3 | Wallet teams (MetaMask plugin pattern) |
| DApp frontend (`examples/dapp_frontend/guard.js`) | 2, 3 | DApp teams (browser SDK pattern) |
| AI agent (`examples/ai_agent/guard.py`) | 1, 2 | Agent builders (pre-action checklist) |
| RPC proxy (`proxy/rpc_proxy.py`) | 1 | Privacy-conscious users; anyone routing wallet RPC traffic locally |
| L2 monitor (`examples/l2_monitor/guard.py`) | 4 | L2-protocol teams; privacy-pool operators |
| Kohaku integration (`examples/kohaku_integration/`) | 1, 2, 3 | Multi-method composition reference |

The five surfaces compose: a wallet team can use EIP-1193 + DApp +
RPC proxy + L2 monitor together. The Kohaku integration is the canonical
multi-surface composition reference.

---

## What this composition delivers — concretely

If a user runs the full e_AI stack on their wallet:

- **Phase 1**: their RPC queries route through the local proxy; the proxy
  warns when query patterns reveal strategy
- **Phase 2**: every transaction is checked against the 8 wallet-method
  guards before signing; critical alerts block by default; medium alerts
  warn
- **Phase 3**: the relay set + private-mempool config + L2 sequencer
  posture is checked on every submission
- **Phase 4**: pool sizes and bridge patterns are surfaced before
  the user commits
- **Phase 5**: residual gaps (IP exposure, post-decrypt traces) are
  surfaced as "out of scope — use Tor / wait for protocol upgrade"

All checks run **locally** by default — the LLM behavioral layer is local
Ollama (`qwen2.5:7b`) with graceful degradation if Ollama is offline. No
private data leaves the host unless the user explicitly opts in to a cloud
backend.

---

## Where this fits in the broader Ethereum stack

The guards above are the access-layer composition over four protocol-level
primitives currently in roadmap discussions: EIP-8141 (native AA + frame
transactions), 2D nonces (specialized nullifier storage), encrypted frame
transactions (ordering / mempool privacy), FOCIL (forced-inclusion
committee list). See [`docs/access_layer_context.md`](access_layer_context.md)
for the full architecture map and what each layer owns.
