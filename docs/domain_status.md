# Domain Status & Task List

*Auto-updatable. Run artifact check to refresh.*

## Built Domains

### stealth_address_ops (REFERENCE)
- [x] profile.json (11/11 validated)
- [x] README.md
- [x] test_profile.py (23 tests pass)
- [x] data/labeled_incidents.jsonl (27 incidents)
- [x] data/umbra_real_sample.jsonl (20 real txs)
- [x] benchmarks/real_data.py
- [x] profile_generated.json (7b variant)
- [x] profile_generated_14b.json (14b variant)
- [x] analysis/failure_analysis.md
- [x] analysis/variant_comparison.md
- [x] cover_generator.py (with adversary simulation)
- [x] compiler.py (analyzer + cover gen + LLM pipeline)
- [x] analyzer.py (rule-based + synthetic benchmark)

### approval_phishing
- [x] profile.json (11/11)
- [x] README.md
- [x] test_profile.py (10 tests)
- [x] data/labeled_incidents.jsonl (17)
- [x] benchmarks/benchmark.py
- [x] profile_generated.json (7b)
- [x] analysis/failure_analysis.md
- [ ] **profile_generated_14b.json** (14b variant)
- [ ] **analysis/variant_comparison.md**
- [ ] domain-specific analyzer.py (currently uses generic checks)
- [ ] real data benchmark (Forta/ScamSniffer phishing tx dataset)
- N/A cover generator (security domain, not privacy)

### offchain_signature
- [x] profile.json (11/11)
- [x] README.md
- [x] test_profile.py (11 tests)
- [x] data/labeled_incidents.jsonl (24)
- [x] benchmarks/benchmark.py
- [x] profile_generated.json (7b)
- [x] analysis/failure_analysis.md
- [ ] **profile_generated_14b.json**
- [ ] **analysis/variant_comparison.md**
- [ ] domain-specific analyzer.py (signature decoder)
- [ ] real data benchmark (EIP-712 phishing signatures dataset)
- N/A cover generator (security domain)

### rpc_leakage
- [x] profile.json (11/11)
- [x] README.md
- [x] test_profile.py (10 tests)
- [x] data/labeled_incidents.jsonl (20)
- [x] benchmarks/benchmark.py
- [x] profile_generated.json (7b)
- [x] analysis/failure_analysis.md
- [ ] **profile_generated_14b.json**
- [ ] **analysis/variant_comparison.md**
- [ ] **cover_generator.py** (cover queries -- extends v1 concept to RPC layer)
- [ ] domain-specific analyzer.py (pattern tracker)
- [ ] real data benchmark (capture real RPC patterns)

### governance_proposal
- [x] profile.json (11/11)
- [x] README.md
- [x] test_profile.py (10 tests)
- [x] data/labeled_incidents.jsonl (21)
- [x] benchmarks/benchmark.py
- [ ] **profile_generated.json** (7b variant)
- [ ] **profile_generated_14b.json**
- [ ] **analysis/failure_analysis.md**
- [ ] **analysis/variant_comparison.md**
- [ ] domain-specific analyzer.py (proposal decoder)
- [ ] real data benchmark (historical malicious proposals)
- N/A cover generator (security domain)

### l2_bridge_linkage
- [x] profile.json (11/11)
- [x] README.md
- [x] test_profile.py (10 tests)
- [x] data/labeled_incidents.jsonl (20)
- [x] benchmarks/benchmark.py
- [ ] **profile_generated.json**
- [ ] **profile_generated_14b.json**
- [ ] **analysis/failure_analysis.md**
- [ ] **analysis/variant_comparison.md**
- [ ] **cover_generator.py** (optimize bridge params to blend)
- [ ] domain-specific analyzer.py
- [ ] real data benchmark (bridge tx dataset)

### cross_protocol_risk
- [x] profile.json (11/11)
- [x] README.md
- [x] test_profile.py (10 tests)
- [x] data/labeled_incidents.jsonl (21)
- [x] benchmarks/benchmark.py
- [ ] **profile_generated.json**
- [ ] **profile_generated_14b.json**
- [ ] **analysis/failure_analysis.md**
- [ ] **analysis/variant_comparison.md**
- [ ] domain-specific analyzer.py (portfolio scanner)
- [ ] real data benchmark (historical cascading liquidations)
- N/A cover generator (security domain)

### l2_anonymity_set
- [x] profile.json (11/11)
- [x] README.md
- [x] test_profile.py (10 tests)
- [x] data/labeled_incidents.jsonl (20)
- [x] benchmarks/benchmark.py
- [ ] **profile_generated.json**
- [ ] **profile_generated_14b.json**
- [ ] **analysis/failure_analysis.md**
- [ ] **analysis/variant_comparison.md**
- [ ] **cover_generator.py** (timing/amount optimization like stealth ops)
- [ ] domain-specific analyzer.py
- [ ] real data benchmark (L2 pool size data)

### defi_query (v1)
- [x] profile.json (audited, 829 lines)
- [x] README.md
- [x] v1 tests (test_sanitizer.py, test_sanitizer_audit.py, test_sanitizer_fuzz.py, test_benchmarks.py)
- [x] v1 benchmarks (run_benchmarks.py)
- [x] cover_generator.py (v5)
- [x] 5 profile variants (defi_14b, defi_bootstrap, defi_claude, defi_generated, defi_websearch)
- [x] analysis/ (cover_strategies.md, failure_analysis.md)
- Note: v1 uses different schema (DomainProfile) and test system. Not migrating to v2 format.
- [ ] **READMEs for variant directories** (defi_14b, defi_bootstrap, defi_claude, defi_generated, defi_websearch)

## Automatable Tasks (by priority)

### Batch 1: LLM bootstrap (fills most gaps)
Run `python -m meta.bootstrap_domain domains/<name>` for:
- [ ] governance_proposal (missing: variant, failure)
- [ ] l2_bridge_linkage (missing: variant, failure)
- [ ] cross_protocol_risk (missing: variant, failure)
- [ ] l2_anonymity_set (missing: variant, failure)

Then generate 14b variants for:
- [ ] approval_phishing
- [ ] offchain_signature
- [ ] rpc_leakage
- [ ] governance_proposal
- [ ] l2_bridge_linkage
- [ ] cross_protocol_risk
- [ ] l2_anonymity_set

### Batch 2: Variant comparisons (after batch 1)
Run comparison analysis for domains with 2+ variants:
- [ ] approval_phishing
- [ ] offchain_signature
- [ ] rpc_leakage
- [ ] governance_proposal
- [ ] l2_bridge_linkage
- [ ] cross_protocol_risk
- [ ] l2_anonymity_set

### Batch 3: Cover generators (privacy domains only)
Build cover generators for:
- [ ] rpc_leakage (cover queries -- v1 concept extended to RPC)
- [ ] l2_bridge_linkage (optimize bridge amount/timing)
- [ ] l2_anonymity_set (timing/amount vs pool state)

### Batch 4: Domain-specific analyzers
Build analyzers (rule-based checks like stealth_address_ops/analyzer.py) for:
- [ ] approval_phishing (decode approve calldata, check amounts)
- [ ] offchain_signature (decode EIP-712 typed data)
- [ ] governance_proposal (decode proposal calldata, simulate effects)
- [ ] cross_protocol_risk (portfolio scanner from accumulated state)
- [ ] l2_bridge_linkage (bridge tx analysis)
- [ ] rpc_leakage (query pattern tracker -- partially in RPC proxy already)
- [ ] l2_anonymity_set (pool size monitor)

### Batch 5: v1 domain READMEs
- [ ] domains/defi_14b/README.md
- [ ] domains/defi_bootstrap/README.md
- [ ] domains/defi_claude/README.md
- [ ] domains/defi_generated/README.md
- [ ] domains/defi_websearch/README.md

### Batch 6: Real data benchmarks (needs external data)
- [ ] approval_phishing: Forta alert dataset
- [ ] offchain_signature: EIP-712 phishing signatures
- [ ] governance_proposal: historical malicious proposals (Beanstalk, etc.)
- [ ] cross_protocol_risk: cascading liquidation events
- [ ] l2_bridge_linkage: bridge transaction patterns
- [ ] l2_anonymity_set: L2 privacy pool deposit counts

## Planned Domains (not yet built)

| Domain | Access | CROPS | Integration | Automatable? |
|---|---|---|---|---|
| pq_readiness | Wallet | S | Wallet guard | Yes -- heuristics from our PQ SA research |
| mev_vulnerability | Wallet | S | Wallet guard | Partially -- needs mempool data |
| wrong_chain_address | Wallet | S | Wallet guard | Yes -- chain/address analysis |
| behavioral_drift | Wallet | S | Wallet guard + RPC | Partially -- needs threshold definitions |
| backup_security | Wallet | S | Wallet guard | Yes -- heuristics from encrypted_backup research |
| mixing_behavioral | L2 | P | Wallet guard | Yes -- extends stealth_address_ops to mixers |
| agent_privacy | AI | P | RPC guard | Partially -- needs agent framework integration |
| sequencer_privacy | L2 | P | RPC guard | Yes -- extends l2_anonymity_set |
| general_crypto_query | AI | P | LLM proxy | Yes -- extend v1 defi profile to broader topics |

### Auto-buildable now (from existing research)
These can be generated immediately from our AI_PS research:
- **pq_readiness**: from `projects/pq_stealth_address/` + `projects/onchain_pq_ciphertext/` findings
- **backup_security**: from `projects/encrypted_backup_recovery/` problem list
- **mixing_behavioral**: from stealth_address_ops H3+H6 generalized
- **wrong_chain_address**: straightforward chain/address validation rules
- **sequencer_privacy**: extends l2_anonymity_set H2

### Needs new research
- **mev_vulnerability**: needs mempool modeling, MEV-Boost data
- **behavioral_drift**: needs portfolio tracking threshold research
- **agent_privacy**: needs agent framework interaction graph analysis
- **general_crypto_query**: needs v1 profile extension to new subdomains
