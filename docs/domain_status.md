# Domain Status & Task List

*Last updated: 2026-04-30*

---

## Built Domains (9)

| Domain | Access | CROPS | Integration | Tests | Variants | Failure | Cover | Analyzer | Real data |
|---|---|---|---|---|---|---|---|---|---|
| **stealth_address_ops** | Wallet | P | Wallet guard | 23 | 3 (hand+7b+14b) | Y | Y | Y | Y (20 Umbra txs) |
| **approval_phishing** | Wallet | S | Wallet guard | 10 | 1 (7b) | Y | N/A | - | - |
| **offchain_signature** | Wallet | S | Wallet guard | 11 | 1 (7b) | Y | N/A | - | - |
| **governance_proposal** | App | S | Wallet guard | 10 | - | - | N/A | - | - |
| **l2_bridge_linkage** | L2 | P | Wallet guard | 10 | - | - | - | - | - |
| **cross_protocol_risk** | App | S | RPC guard | 10 | - | - | N/A | - | - |
| **l2_anonymity_set** | L2 | P | RPC guard | 10 | - | - | - | - | - |
| **rpc_leakage** | AI | P | RPC guard | 10 | 1 (7b) | Y | - | partial (in proxy) | - |
| **defi_query (v1)** | AI | P | LLM proxy | v1 suite | 5 | Y | Y (v5) | Y | Y |

All 9 profiles pass 11/11 validation. 94 total tests passing.

Legend: Y = done, - = missing, N/A = not applicable (security domains don't need cover generators)

---

## Planned Domains (9)

| Domain | Access | CROPS | Integration | Source | Effort |
|---|---|---|---|---|---|
| **pq_readiness** | Wallet | S | Wallet guard | PQ SA + on-chain ciphertext findings | Quick |
| **mev_vulnerability** | Wallet | S | Wallet guard | Slippage × pool depth + private mempool check | Quick |
| **wrong_chain_address** | Wallet | S | Wallet guard | Chain/address validation rules | Quick |
| **backup_security** | Wallet | S | Wallet guard | encrypted_backup_recovery 10 problems | Quick |
| **mixing_behavioral** | L2 | P | Wallet guard | Extends stealth_ops H3+H6 to mixers | Quick |
| **sequencer_privacy** | L2 | P | RPC guard | Extends l2_anonymity_set H2 | Quick |
| **behavioral_drift** | Wallet | S | Wallet+RPC | Default thresholds, user customizable | Medium |
| **general_crypto_query** | AI | P | LLM proxy | Extend v1 to NFT/governance/staking | Medium |
| **agent_privacy** | AI | P | RPC guard | Agent interaction graph formalization | **Research needed** |

8 buildable now, 1 needs research.

---

## Task List

### Batch 0: Build 8 new domain profiles
Source from existing research, validate 11/11, bootstrap all artifacts.

| # | Domain | Heuristic source |
|---|---|---|
| 0.1 | pq_readiness | projects/pq_stealth_address/ + projects/onchain_pq_ciphertext/ |
| 0.2 | mev_vulnerability | Slippage model + public/private mempool check + DEX MEV protection list |
| 0.3 | wrong_chain_address | Chain ID validation, contract vs EOA, address poisoning detection |
| 0.4 | backup_security | projects/encrypted_backup_recovery/problem_list.md (P1-P10) |
| 0.5 | mixing_behavioral | stealth_address_ops H3+H6 generalized to Tornado Cash/Railgun/Privacy Pools |
| 0.6 | sequencer_privacy | l2_anonymity_set H2 expanded with per-L2 sequencer data |
| 0.7 | behavioral_drift | Portfolio concentration, leverage tracking, approval accumulation |
| 0.8 | general_crypto_query | Extend v1 defi profile subdomains to NFT, governance, staking, bridges |

### Batch 1: LLM bootstrap existing domains (variants + failure analysis)
Run `python -m meta.bootstrap_domain domains/<name>` for domains missing artifacts.

| # | Domain | Missing |
|---|---|---|
| 1.1 | governance_proposal | variant, failure analysis |
| 1.2 | l2_bridge_linkage | variant, failure analysis |
| 1.3 | cross_protocol_risk | variant, failure analysis |
| 1.4 | l2_anonymity_set | variant, failure analysis |

Generate 14b variants for all 7 domains missing them:

| # | Domain |
|---|---|
| 1.5 | approval_phishing |
| 1.6 | offchain_signature |
| 1.7 | rpc_leakage |
| 1.8 | governance_proposal |
| 1.9 | l2_bridge_linkage |
| 1.10 | cross_protocol_risk |
| 1.11 | l2_anonymity_set |

### Batch 2: Variant comparisons
After batch 1, run comparison for all domains with 2+ variants.

| # | Domain |
|---|---|
| 2.1-2.7 | approval_phishing, offchain_signature, rpc_leakage, governance_proposal, l2_bridge_linkage, cross_protocol_risk, l2_anonymity_set |

### Batch 3: Cover generators (privacy domains only)
| # | Domain | What the cover does |
|---|---|---|
| 3.1 | rpc_leakage | Cover queries (extends v1 concept to RPC) |
| 3.2 | l2_bridge_linkage | Optimize bridge amount/timing to blend |
| 3.3 | l2_anonymity_set | Timing/amount optimization vs pool state |
| 3.4 | mixing_behavioral | Cover params for mixer deposit/withdrawal |

### Batch 4: Domain-specific analyzers
Rule-based checks (like stealth_address_ops/analyzer.py).

| # | Domain | What it decodes/checks |
|---|---|---|
| 4.1 | approval_phishing | Decode approve calldata, check amounts vs MAX_UINT |
| 4.2 | offchain_signature | Decode EIP-712 typed data, identify Permit2/Seaport |
| 4.3 | governance_proposal | Decode proposal calldata, simulate parameter changes |
| 4.4 | cross_protocol_risk | Portfolio scanner from accumulated RPC state |
| 4.5 | l2_bridge_linkage | Bridge tx analysis (address/amount/timing) |
| 4.6 | rpc_leakage | Query pattern tracker (partially in proxy already) |
| 4.7 | l2_anonymity_set | Pool size monitor from getLogs |
| 4.8 | mev_vulnerability | Slippage calculator + pool depth check |
| 4.9 | pq_readiness | Key type detector (ECDSA vs PQ) |

### Batch 5: v1 domain READMEs
| # | File |
|---|---|
| 5.1-5.5 | defi_14b, defi_bootstrap, defi_claude, defi_generated, defi_websearch |

### Batch 6: Real data benchmarks
| # | Domain | Data source |
|---|---|---|
| 6.1 | approval_phishing | Forta alerts API |
| 6.2 | offchain_signature | EIP-712 phishing signature reports |
| 6.3 | governance_proposal | Historical attacks (Beanstalk, Tornado governance) |
| 6.4 | cross_protocol_risk | Cascading liquidation events (LUNA, etc.) |
| 6.5 | l2_bridge_linkage | Bridge transaction patterns (Hop, Across, Stargate) |
| 6.6 | l2_anonymity_set | L2 privacy pool deposit counts |
| 6.7 | mev_vulnerability | MEV-Boost relay data, sandwich tx history |

### Batch 7: Integration hardening
| # | Task |
|---|---|
| 7.1 | RPC proxy: add all domain checks (currently only rpc_leakage partially) |
| 7.2 | Wallet guard: add calldata decoder routing for all wallet profiles |
| 7.3 | Test all integration demos end-to-end |
| 7.4 | Write MetaMask Snap skeleton (highest-reach wallet integration) |

---

## Summary

| Batch | Items | Automatable | Needs human |
|---|---|---|---|
| 0: New profiles | 8 domains | Yes (from research) | Review heuristics |
| 1: LLM bootstrap | 11 tasks | Yes | - |
| 2: Comparisons | 7 tasks | Yes (after batch 1) | - |
| 3: Cover generators | 4 domains | Yes (code) | - |
| 4: Analyzers | 9 domains | Yes (code) | - |
| 5: v1 READMEs | 5 files | Yes | - |
| 6: Real data | 7 domains | Partially (needs data sources) | Data collection |
| 7: Integration | 4 tasks | Mostly (Snap needs wallet SDK) | Snap review |

**Total: 55 tasks. ~48 fully automatable.**
