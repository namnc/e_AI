# e_AI — Privacy and Safety Guards for End Users on Ethereum

**Pre-submission guards** that catch the kinds of operational mistakes that
have cost Ethereum users hundreds of millions of dollars — before the
transaction is signed. Local-first, profile-driven, runnable today.

## Why this matters — measured incidents, not hypotheticals

| Threat class | Reported impact | e_AI guard |
|---|---|---|
| Stealth-address deanonymization | **48.5%** of Umbra users on Ethereum (Wahrstätter et al., [arXiv 2308.01703](https://arxiv.org/abs/2308.01703), ACM Web Conf 2024) | [`stealth_address_ops`](domains/stealth_address_ops/) ⭐ |
| Approval phishing / wallet drainers | **~$494M** in 2024 alone across 332K wallet addresses ([ScamSniffer 2024 annual report](https://drops.scamsniffer.io/scam-sniffer-2024-web3-phishing-attacks-wallet-drainers-drain-494-million/)), 85% on Ethereum; [Blockaid](https://www.blockaid.io/blog/putting-inferno-drainer-group-out-of-business) reports blocking 40K+ Angelferno drainer attempts in June 2025 alone | [`approval_phishing`](domains/approval_phishing/) |
| Sandwich / MEV in public mempool | One bot ([jaredfromsubway.eth](https://etherscan.io/address/0x1f2f10d1c40777ae1da742455c65828ff36df387)) ran ~238K attacks against ~106K victims in 3 months of 2023, taking ~$40.65M revenue / ~$6.3M net profit per [The Block](https://www.theblock.co/post/230218/jaredfromsubway-mev-bot) (figures from EigenPhi analysis; some MEV experts dispute the net-profit estimate) | [`mev_vulnerability`](domains/mev_vulnerability/) |
| Post-mixer behavioral linkage | **42,852 of 97,331** Tornado Cash deposits compromised by Tutela's seven heuristics ([Tutela](https://github.com/pareto-xyz/tutela-app)) | [`mixing_behavioral`](domains/mixing_behavioral/) ⭐ |
| Builder/relay censorship | Tornado Cash transactions silently dropped at compliance-regulated relays post-OFAC; per [soispoke's Dune dashboard](https://dune.com/soispoke/privacy-pools-nullifier-state-growth) the protocol still saw ~10,781 active txs in the most recent 90-day window | [`builder_censorship`](domains/builder_censorship/) |
| AI / RPC query leakage | [404 Media documented 130K+ AI-chat conversations](https://www.404media.co/more-than-130-000-claude-grok-chatgpt-and-other-llm-chats-readable-on-archive-org/) (Claude, Grok, ChatGPT, others) archived on the Wayback Machine; [Cyberhaven](https://www.cyberhaven.com/blog/4-2-of-workers-have-pasted-company-data-into-chatgpt) reports ~4.7% of enterprise users pasted confidential data into AI chat tools | [`rpc_leakage`](domains/rpc_leakage/) ⭐ |

⭐ = strong-novelty cluster — to our knowledge, no production pre-submission
tool fully covers these niches today. For the full set of 16 guards across
all 4 access methods, see [*What's available*](#whats-available) below or
[`docs/scenarios.md`](docs/scenarios.md) for concrete walkthroughs.

## Pick your path

**If you're an end user** → [`docs/scenarios.md`](docs/scenarios.md) walks
through six real incidents and what e_AI does at each. Then run a demo
matching your situation:
```sh
python3 examples/per_domain/<guard>/demo.py
```

**If you're a wallet / agent / DApp integrator** →
[`docs/composition.md`](docs/composition.md) shows how the 16 guards compose
across a transaction's full lifecycle (intent → wallet → submission →
inclusion → post-execution) and which of the five integration surfaces
(`examples/ai_agent/`, `examples/wallet_eip1193/`, `examples/dapp_frontend/`,
`examples/l2_monitor/`, `examples/kohaku_integration/`) fits your product.

**If you're a researcher or contributor** → [`CONTRIBUTING.md`](CONTRIBUTING.md)
+ [`docs/adding_a_domain.md`](docs/adding_a_domain.md). The extension
walkthrough is documented end-to-end; the `builder_censorship` guard was
built in one week using only that walkthrough (with the substrate work
already in place — first-time contributors should expect longer).

**If you want the architecture context** →
[`docs/access_layer_context.md`](docs/access_layer_context.md) places e_AI
within the broader 2026 Ethereum privacy roadmap (EIP-8141 frame
transactions, FOCIL forced-inclusion, encrypted frame transactions, 2D
nonces / restricted storage) and maps which problems are
protocol-handled vs access-layer-handled. Cites primary sources from
Vitalik, soispoke, and Nero_eth.

## How we built it — the journey

The repo maintains **two long-running branches**:

- `main` — Parts 1, 2, 3 (DeFi query-sanitization track; published /
  draft posts in the repo root)
- `v2` — this substrate (pre-submission transaction-analysis track;
  active development)

Both branches are CI-tested on every push. The journey:

1. **The Private Query Problem** ([`ethresearch_post.md`](ethresearch_post.md))
   — DeFi-specific tiered sanitization pipeline for cloud-LLM queries.
2. **Active Adversaries and Verifiable Inference**
   ([`companion_post_active_adversary.md`](companion_post_active_adversary.md))
   — extensions for stronger threat models.
3. **A Meta-Framework for Domain-Agnostic Privacy Protection**
   ([`ethresearch_meta_framework_draft.md`](ethresearch_meta_framework_draft.md))
   — auto-generation across text-query domains; validated on DeFi via six
   generation strategies.
4. **From DeFi Sanitization to Pre-Submission Transaction Guards**
   ([`ethresearch_v2_guards_draft.md`](ethresearch_v2_guards_draft.md))
   — same meta-framework applied to a *different task*: pre-submission
   transaction analysis. This substrate.

The Part 4 post is in draft; we're maturing the substrate (real-incident
calibration, registry-pull hardening, external-reviewer sanity-check)
before posting on ethresear.ch. See
[`docs/publication_checklist.md`](docs/publication_checklist.md) for the
maturity gates.

The substrate is offered as a **potential tooling direction**, not a
shipped product. Several guards live in already-occupied space (Blockaid,
Pocket Universe, Flashbots Protect, MEV Watch — see
[`docs/prior_art/`](docs/prior_art/) per-guard); four sit in genuinely
under-served niches; the framework + extension docs are designed for others
to extend.

## Quick start

```sh
git clone <this repo>
cd e_AI
git checkout v2
pip install -r requirements.txt

# Install Ollama + qwen2.5:7b for the local LLM layer (optional but recommended)
# https://ollama.com — `ollama serve` then `ollama pull qwen2.5:7b`

# Run a per-domain demo (16 profile-validated prototype guards)
python3 examples/per_domain/approval_phishing/demo.py
python3 examples/per_domain/stealth_address_ops/demo.py
python3 examples/per_domain/builder_censorship/demo.py

# Run an access-method integration demo
python3 examples/ai_agent/guard.py
python3 examples/l2_monitor/guard.py

# Run all v2 domain tests (schema + structural). Excludes _template +
# defi_* (Part 3 supporting variants; see docs/v1_variants.md).
for d in domains/*/test_profile.py domains/*/test_analyzer.py; do
  case "$(dirname "$d" | xargs basename)" in
    defi|defi_*|_template|_feedback) continue;;
  esac
  python3 "$d" || echo "FAIL: $d"
done

# Schema-validate every v2 production profile against the 11-check engine.
for d in domains/*/profile.json; do
  case "$(dirname "$d" | xargs basename)" in
    defi|defi_*|_template|_feedback) continue;;
  esac
  python3 -m meta.tx_validation_engine "$d" || echo "FAIL: $d"
done
```

CI runs all v2 domain tests + schema validation on every push to `v2`.
See [`.github/workflows/tests.yml`](.github/workflows/tests.yml). Note:
the validation engine performs **schema validation** (presence + shape +
calibration of fields), not **detector validation** (true-positive /
false-positive rates against real incidents). Detector-validation
fixtures are queued as a maturity gate; see
[`docs/publication_checklist.md`](docs/publication_checklist.md).

## What's available — 16 profile-validated prototype guards

These are **prototypes**: each has a profile that passes the 11-check
schema validation, a `test_profile.py` covering structure, a runnable
per-domain demo, and a rule-based `analyzer.py`. They are *not* yet
production-grade in the sense of being calibrated against real-incident
corpora or having been battle-tested in a wallet integration. Production
readiness varies by domain; per-guard readiness is captured in the
matrix below.

### Per-guard readiness matrix

| Guard | Schema | Tests | Rule analyzer | Per-domain demo | Real-incident fixtures | Live registry / data integration | Externally reviewed | Production candidate |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| `approval_phishing` | ✓ | ✓ | ✓ | ✓ | ✗ (synthetic) | ✗ (scam-DB hard-coded) | HOLDS (Codex Phase 10) | no |
| `backup_security` | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | HOLDS (Codex Phase 10) | no |
| `behavioral_drift` | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | HOLDS (Codex Phase 10) | no |
| `builder_censorship` | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ (relay set hard-coded) | HOLDS (Codex Phase 10) | no |
| `cross_protocol_risk` | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | HOLDS (Codex Phase 10) | no |
| `governance_proposal` | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | HOLDS (Codex Phase 10) | no |
| `l2_anonymity_set` | ✓ | ✓ | ✓ | ✓ | partial (soispoke 0xbow) | ✗ | HOLDS (Codex Phase 10) | no |
| `l2_bridge_linkage` ⭐ | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | HOLDS (Codex Phase 10) | no |
| `mev_vulnerability` | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | HOLDS (Codex Phase 10) | no |
| `mixing_behavioral` ⭐ | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | HOLDS (Codex Phase 10) | no |
| `offchain_signature` | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | HOLDS (Codex Phase 10) | no |
| `pq_readiness` | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | HOLDS (Codex Phase 10) | no |
| `rpc_leakage` ⭐ | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | HOLDS (Codex Phase 10) | no |
| `sequencer_privacy` | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ (registry hard-coded) | HOLDS (Codex Phase 10) | no |
| `stealth_address_ops` ⭐ | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | HOLDS (Codex Phase 10) | no |
| `wrong_chain_address` | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | HOLDS (Codex Phase 10) | no |

**Schema** = 11-check `tx_validation_engine` PASS · **Tests** = `test_profile.py`
PASS · **Rule analyzer** = `analyzer.py` covering profile heuristics
algorithmically · **Per-domain demo** = `examples/per_domain/<name>/demo.py`
runs end-to-end with rule-based + LLM analysis · **Real-incident fixtures**
= calibrated against captured-incident corpora (not synthetic samples) ·
**Live registry / data integration** = production data feeds wired (not
hard-coded in analyzer source) · **Externally reviewed** = a substantive
external pushback round has been done. Current status across all 16
guards: HOLDS (Codex Phase 10) — completed 2026-05-08 after a 7-iteration
fix-review-fix loop (Phases 4-10) covering proxy semantics, wallet ABI,
CI workflows, docs linter, and integration tests. Codex Phase 10 verdict:
GREEN, convergence achieved (no actionable bugs; remaining items are
multi-week architectural maturity gates, not blockers). Loop notes live
in the maintainers' internal pipeline, not in this public repo. A
second pushback round (broader than Codex; e.g., Kohaku-team review or
trusted external researcher) is queued as a maturity gate before final
publication · **Production candidate** = no item ships
with this column ✓ today; closing the prior columns is the path there.

⭐ = strong-novelty cluster.

### Cluster overview

**Wallet method (7 + 1 hygiene-only):** `approval_phishing`,
`backup_security`, `behavioral_drift`, `mev_vulnerability`,
`offchain_signature`, `pq_readiness`, `stealth_address_ops` ⭐. Plus
`wrong_chain_address` (Rabby Wallet has solved this UX; included for
unified-set completeness, not novelty).

**Application method (3):** `cross_protocol_risk`, `governance_proposal`,
`mixing_behavioral` ⭐.

**AI method (1):** `rpc_leakage` ⭐.

**L2 method (3 + 1 fresh):** `l2_anonymity_set`, `l2_bridge_linkage` ⭐,
`sequencer_privacy`. Plus `builder_censorship` — fresh CR-aligned domain
demonstrating the extension framework (built using only
[`docs/adding_a_domain.md`](docs/adding_a_domain.md), with substrate
work already in place; first-time contributors should expect longer).

### Integration demos (status: illustrative adapters)

Five access-method integration surfaces under `examples/`:
- `ai_agent/guard.py` — agent guard for AI-agent flows
- `dapp_frontend/guard.js` — DApp frontend SDK
- `kohaku_integration/` — Kohaku middleware (TypeScript)
- `l2_monitor/guard.py` — L2-specific monitor
- `wallet_eip1193/guard.ts` — wallet provider wrapper
- `proxy/rpc_proxy.py` — local RPC proxy

**Honest framing**: the per-domain demos under `examples/per_domain/`
**are profile-driven** — they load the profile, run the analyzer, and
report alerts. The five access-method integration surfaces above are
**illustrative adapters**: they accept profile inputs but several
(notably `wallet_eip1193/guard.ts` and `proxy/rpc_proxy.py`) currently
hard-code domain-specific logic in source rather than dispatching from
profile semantics. Making one canonical profile runtime + thin adapters
is queued as a maturity item; the current adapters are runnable
illustrations of the per-access-method integration pattern, not
canonical profile runtimes.

### Per-domain demos

`examples/per_domain/<name>/` — for each guard: `demo.py`, `sample_tx.json`,
`README.md`. Each demo loads the profile, runs the rule-based analyzer
(where applicable), and adds LLM behavioral context with **graceful
Ollama degradation** (the demo still produces a useful result if Ollama is
offline).

### Documentation

End-user reading path:
- [`docs/scenarios.md`](docs/scenarios.md) — six concrete real-incident
  scenarios with what e_AI catches and how to run the demo
- [`docs/composition.md`](docs/composition.md) — how the 16 guards compose
  across a transaction's lifecycle (intent → wallet → submission →
  inclusion → post-execution)
- [`docs/access_layer_context.md`](docs/access_layer_context.md) — where
  e_AI fits in the broader 2026 Ethereum privacy roadmap (EIP-8141, FOCIL,
  encrypted frame transactions, restricted-storage); cites Vitalik,
  soispoke, and Nero_eth primary sources

Contributor / R&D reading path:
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — entry point for adding a guard
- [`docs/adding_a_domain.md`](docs/adding_a_domain.md) — 11-step walkthrough
- [`docs/profile_schema.md`](docs/profile_schema.md) — formal schema reference
- [`docs/prior_art/<name>.md`](docs/prior_art/) — per-guard prior-art
  research (16 files)
- [`docs/deployment_guide.md`](docs/deployment_guide.md) — six privacy-safe
  deployment configurations
- [`docs/v1_variants.md`](docs/v1_variants.md) — disposition for the
  `defi*/` directories (v1 query-sanitization variants from the
  meta-framework paper; not v2 production guards)
- [`docs/publication_checklist.md`](docs/publication_checklist.md) — release
  gate

## Repository structure

```
core/                 # Profile schemas, LLM analyzer (with graceful degradation)
domains/              # 16 v2 production guards + 6 v1 sanitization variants (defi*/)
                      #   + _template (boilerplate) + _feedback (Part 3 cross-domain feedback)
meta/                 # Meta-framework: validation engine, bootstrapper, refiner
proxy/                # Local RPC proxy (transaction-analysis aware)
examples/             # Five integration demos for the four access methods
  per_domain/         # 16 per-guard demos (one folder each)
docs/                 # Adding-a-domain, profile schema, prior-art, deployment, walkthroughs
.github/workflows/    # CI: sanitizer tests + classifier validation + v2 domain tests
```

The `domains/defi*/` directories are v1 query-sanitization comparison
variants for the meta-framework paper, **not** v2 production guards. See
[`docs/v1_variants.md`](docs/v1_variants.md).

## Trust transparency

This substrate trusts:
- **Local machine** for all cryptographic and LLM operations by default
- **Ollama** at `localhost:11434` (default LLM backend; gracefully degrades
  if down — the rule-based analyzer still runs)
- **Block-explorer verification status** (input to `approval_phishing`)
- **External registries** (OFAC SDN list, scam DBs, builder-diversity
  feeds) — **if** wired live; otherwise sample data is hard-coded for the
  demo. Each guard's README documents its specific trust set.

No protocol-grade trust assumptions. The substrate operates at the access
layer between protocol and user; it does not change protocol behavior.

## Epistemic status

Each guard's heuristics are **CLAIMs** (evidence-grounded patterns), not
**THEOREMs** (formally proved). Profile schemas mark `validation_status`
per domain (draft / reviewed / accepted). Sample data is synthetic
(≥5 incidents per domain); production deployment requires real-incident
labeled corpora — which is exactly what the meta-framework is designed to
ingest.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) and
[`docs/adding_a_domain.md`](docs/adding_a_domain.md). The framework is
designed for extension: a new domain takes ~1 day for someone who has read
the docs once. The 11-check validation engine catches structural failures
before runtime; the per-domain demo template ensures any new guard ships
with a runnable PoC.

For R&D directions where the framework benefits most from external help —
real-incident labeled corpora to calibrate the analyzers, new
integration surfaces (mobile, hardware wallet), composition with
adjacent ecosystems (Blockaid, Helios, CoW, Kohaku) — see the *How others
can expand or upgrade* section of
[`docs/access_layer_context.md`](docs/access_layer_context.md).

## License + provenance

AI-assisted, human-reviewed before merging to `v2`. Per the project's
epistemic-transparency rule, contributions should mark new claims as
THEOREM | CLAIM | FRAMING.
