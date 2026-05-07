# Repository publication checklist — 2026-05-07

Final gate before making the repo public. Mechanical items verified
autonomously and marked. Remaining open items genuinely need a human call
or post-publication step.

## Self-containment

- [x] No external pointer escapes (no references to `AI_PS`, internal <!-- lint-allow-ai-ps -->
      working directories, or private analysis docs)
- [x] All prior-art research lives in `docs/prior_art/` (16 files)
- [x] All add-a-domain documentation lives in `docs/`
- [x] CONTRIBUTING.md is the public entry point for contributors
- [x] `docs/v1_variants.md` explains the `defi*/` directories
- [x] Top-level README replaced — current `README.md` is the v2-aware
      version (the original Part-1-focused README is preserved at
      `docs/v1_README_archive.md`)

## Tests + CI

- [x] CI runs v1 sanitizer tests + classifier validation
- [x] CI runs v2 domain tests (all 16 production profiles, including
      builder_censorship)
- [x] CI runs validation engine across all production profiles
- [x] CI skips `defi*/` variants (Part 3 supporting material; data not yet
      populated)
- [x] All 16 production `test_profile.py` pass locally
- [x] All 16 per-domain demos run end-to-end (verified 2026-05-07)
- [x] All 16 v2 production guards now ship rule-based `analyzer.py`
- [x] `core/llm_analyzer.py` graceful degradation verified (model
      unreachable → falls back to rule-based)

## Sensitive content scan (verified 2026-05-07)

- [x] No `TODO`/`FIXME`/`XXX`/`HACK` markers in production paths.
      Skeleton TODO markers exist only in `domains/<name>/cover_generator.py`
      template files (defi_*, l2_anonymity_set, l2_bridge_linkage); these
      are intentional skeleton patterns from `meta/bootstrap_domain.py`'s
      template, not wired into any production demo or CI test path,
      and explicitly documented as "SKELETON" in their headers.
- [x] No personal emails, real wallet addresses (other than well-known
      sample addresses), API keys, or private credentials in tracked
      files. The only `0x...` addresses in code are well-known Ethereum
      identifiers (USDC, USDT, function selectors, jaredfromsubway.eth's
      public profile).
- [x] No `.env` or credential files in `git ls-files`.
- [x] `requirements.txt` lists only public packages: `anthropic`,
      `httpx`, `torch`, `transformers`, `scikit-learn`, `numpy`,
      `datasets`. No private/internal packages.
- [x] `git log -p --all | grep` for credential patterns returned only
      heuristic-incident strings in JSONL data files (e.g., the literal
      string "Password-only backup encryption..." as a labeled-incident
      description, not an actual password). Clean.

## Documentation polish

- [x] Top-level README is the v2-aware version (see Self-containment)
- [x] Per-domain READMEs include heuristics table + prior art
- [x] Per-domain demo READMEs include limitations + trust assumptions
- [x] CONTRIBUTING.md present
- [x] `docs/profile_schema.md` reference present
- [x] `docs/v1_variants.md` explains the `defi*/` directories
- [x] `docs/scenarios.md` covers six concrete real-incident walkthroughs
- [x] `docs/composition.md` covers the transaction lifecycle composition
- [x] `docs/access_layer_context.md` places the substrate within the
      broader 2026 Ethereum privacy roadmap
- [x] `docs/v2_substrate_overview.md` preserves the long-form draft

## Provenance + attribution

- [x] Top-level README states AI-assistance + human-review pattern
      (see "License + provenance" section)
- [x] CONTRIBUTING.md includes the THEOREM | CLAIM | FRAMING marker
      convention
- [x] LICENSE file present (MIT, Copyright 2026 Nam Ngo)

## Decisions locked in (2026-05-07)

- **Branch model**: v2 maintained as a long-running branch alongside v1
  on `main`. No rename. CI triggers both branches (already configured).
- **Publication timing**: deferred. Substrate matures before the
  ethresear.ch post lands. Repo can be flipped public independently
  (the in-repo `ethresearch_v2_guards_draft.md` carries the argument
  for readers regardless of post-publication state) — but that's a
  separate decision.

## Maturity gates (before posting on ethresear.ch)

Items likely worth seeing land before the post — not all required, but
each closes a soft spot a reader would push on:

- [ ] **At least one strong-novelty guard calibrated against real
      incidents.** `mixing_behavioral` against Tutela's compromised-
      deposit set (~42.8K records documented) is the most concrete
      candidate. `stealth_address_ops` against Wahrstätter's analysis
      dataset is the other.
- [ ] **`builder_censorship` and `sequencer_privacy` hard-coded
      registries replaced** with pulls from maintained sources
      (mevwatch / relayscan / L2Beat). Today they live in the analyzer
      source code; production hardening replaces this.
- [ ] **At least one wallet-team integration battle-tested.** Kohaku
      middleware demo runs locally; running it inside Kohaku's actual
      flow with real test transactions surfaces the rough edges.
- [ ] **Wahrstätter heuristic coverage verification** — confirm e_AI's
      6 `stealth_address_ops` heuristics map cleanly to / extend
      Wahrstätter's published 4-heuristic set. The "first runtime
      defense" claim depends on this being defensible.
- [ ] **PIR primitive position-PoC iteration** with Keewoo lands on
      shared framing (the McEliece-as-stress-test reframe). The post
      cites this as forward-looking; settling it strengthens the
      reference.
- [ ] **External-reviewer sanity-check** on at least the strong-novelty
      cluster claims. Could be one Kohaku-team review or one trusted
      external researcher.

Optional (less load-bearing):

- [ ] LLM behavioral layer tested with larger local model
      (qwen2.5:14b or 32b) to confirm `qwen2.5:7b` isn't a quality
      ceiling for the demos.
- [ ] One additional domain shipped to validate extension framework
      a second time (after `builder_censorship`). Candidates: sybil
      multi-wallet linkability or frontend phishing.

## On-repo-going-public (whenever you flip visibility)

These are mechanical and can run independently of the post:

- [x] All gates above this section verified clean (engineering / tests /
      content scan / provenance / docs / license)
- [ ] Voice / copy-edit pass on `ethresearch_v2_guards_draft.md` —
      engineering structure done; voice is yours. (Not blocking
      visibility flip if the draft is acceptable as-is.)
- [ ] Push commit `1ffa707` (un-pushed since 2026-05-01) — un-pushed
      state is acceptable but cleaner to flush before public.

## After publication (when post lands)

- [ ] Rename `ethresearch_v2_guards_draft.md` →
      `ethresearch_v2_guards.md` (matches Part 1 / Part 2 unsuffixed
      pattern).
- [ ] Add a "Series" link in README's series section pointing to the
      published ethresear.ch URL.
- [ ] Tag a release (e.g., `v2.0.0`) corresponding to the publication
      snapshot.
- [ ] Open a Discussions board so external contributors have a
      low-friction surface for questions.

## Summary

Mechanical gates: **all green**.

Branch + publication-timing: **decided** (v2 alongside v1, post deferred).

Maturity gates: **work-in-progress** — closing them is the substrate's
forward path.
