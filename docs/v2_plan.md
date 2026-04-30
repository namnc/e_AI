# e_AI v2: Guard All Ethereum Access Methods

## Vision

e_AI v1 protects DeFi queries sent to cloud LLMs (text sanitization).
e_AI v2 extends to protecting **everything users do on Ethereum** across all 4 access methods.

Same architecture: domain profiles (JSON) + local LLM + validation engine + meta-framework.
New capability: pre-submission transaction analysis, behavioral detection, cross-protocol risk.

## Why local LLM is the right architecture

The analyzer needs the user's **full context** (transaction history, address set, DeFi positions, behavioral patterns) to detect risks that span transactions and protocols. Running this analysis remotely would itself be a privacy leak. The moat is: **the analysis is impossible without full context, and full context cannot be shared.**

## The 4 access methods

### AI (agents acting on behalf of user)
- **v1 (done):** Query sanitization, cover queries for DeFi questions
- **v2:** Agent interaction graph privacy, RPC query patterns

| Profile | Status |
|---|---|
| `defi_query` (v1) | Audited |
| `agent_privacy` | Planned |
| `rpc_leakage` | Planned |

### Wallet (direct user transactions)
- **v1:** Not covered
- **v2:** Transaction analysis, signature decoding, behavioral monitoring

| Profile | Status |
|---|---|
| `stealth_address_ops` | Done (11/11 validated) |
| `approval_phishing` | Done (11/11 validated) |
| `offchain_signature` | Next priority |
| `pq_readiness` | Planned |
| `mev_vulnerability` | Planned |
| `wrong_chain_address` | Planned |
| `behavioral_drift` | Planned |
| `backup_security` | Planned |

### Application (DApp frontend interactions)
- **v1:** Not covered
- **v2:** Cross-protocol risk, governance analysis, Sybil detection

| Profile | Status |
|---|---|
| `governance_proposal` | Planned |
| `cross_protocol_risk` | Planned |
| `sybil_self_detection` | Planned |

**Gap:** Frontend-level risks (phishing clone sites, compromised JS) need URL/content verification, not transaction analysis. May need a separate module.

### L2 (Layer 2 and cross-chain)
- **v1:** Not covered
- **v2:** Bridge linkage, sequencer privacy, L2 anonymity sets

| Profile | Status |
|---|---|
| `l2_bridge_linkage` | Planned |
| `sequencer_privacy` | Planned |
| `l2_anonymity_set` | Planned |
| `builder_censorship` | Planned |
| `mixing_behavioral` | Planned |

## Architecture

```
e_AI/
├── core/                      ← shared infrastructure
│   ├── domain_profile.py      ← v1 schema (text sanitization)
│   ├── tx_profile.py          ← v2 schema (transaction analysis)
│   ├── profile_loader.py      ← loads + validates both types
│   ├── llm_backend.py         ← Ollama / Anthropic
│   └── llm_analyzer.py        ← LLM-powered analysis (v2)
│
├── meta/                      ← profile generation + validation
│   ├── analyzer.py            ← dataset → profile (v1)
│   ├── prompts.py             ← v1 LLM prompts
│   ├── prompts_v2.py          ← v2 LLM prompts
│   ├── validation_engine.py   ← v1 property checks
│   ├── tx_validation_engine.py ← v2 property checks (11 checks)
│   ├── refiner.py             ← iterative validate → fix loop
│   └── ...
│
├── domains/                   ← self-contained domain packages
│   ├── _template/             ← copy to start new domain
│   ├── defi/                  ← v1 (audited)
│   ├── stealth_address_ops/   ← v2 (validated)
│   ├── approval_phishing/     ← v2 (validated)
│   └── ...
│
├── docs/
│   ├── v2_plan.md             ← this file
│   ├── adding_a_domain.md     ← how to add a new domain
│   ├── improving_a_domain.md  ← how to improve existing
│   └── architecture.md        ← system design (existing)
│
└── examples/
    └── kohaku_integration/    ← wallet SDK middleware
```

## Three rules preventing bloat

1. **core/ and meta/ are frozen for domain work.** Domain contributors only touch `domains/<name>/`.
2. **Each domain is one self-contained directory.** Profile + analyzer + data + benchmarks + README.
3. **Template-driven new domains.** `cp -r domains/_template domains/new` → fill in → validate.

## Integration targets

- **Kohaku** (EF privacy wallet SDK): middleware wrapping any plugin
- **Standalone wallets**: Python/TypeScript library import
- **Browser extensions**: inject pre-submission checks
- **Agent frameworks**: extend v1 query sanitization with v2 action analysis

## Roadmap

| Phase | What | When |
|---|---|---|
| **v2.0** | Framework + 2 profiles (stealth ops, approval phishing) | Done |
| **v2.1** | offchain_signature profile + Kohaku integration PoC | Next |
| **v2.2** | Real data benchmarks + confidence calibration | Needs RPC + labeled data |
| **v2.3** | 3 more wallet profiles (MEV, wrong-chain, PQ readiness) | |
| **v2.4** | Application profiles (governance, cross-protocol) | |
| **v2.5** | L2 profiles (bridge linkage, sequencer, anonymity set) | |
| **v3.0** | Frontend verification module (application gap) | Research needed |

## Score

| Access method | v1 | v2.0 (now) | v2.5 (target) |
|---|---|---|---|
| AI | 1 profile | 1 profile | 3 profiles |
| Wallet | 0 | 2 profiles | 8 profiles |
| Application | 0 | 0 | 3 profiles + gap |
| L2 | 0 | 0 | 5 profiles |
| **Total** | **1** | **3** | **19** |
