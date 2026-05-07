# v1 query-sanitization variants — disposition

The `domains/defi*/` directories are **not v2 production guards**. They are
six v1 query-sanitization variants used for the meta-framework
generation-strategy comparison documented in
`ethresearch_meta_framework_draft.md` (Part 3).

| Directory | Purpose |
|---|---|
| `domains/defi/` | Hand-crafted DeFi profile (extracted from v5 constants) — Part 3 baseline |
| `domains/defi_14b/` | Local 14B + web search — best private-data-safe auto-generated |
| `domains/defi_bootstrap/` | Cloud + local bootstrap |
| `domains/defi_claude/` | Cloud Claude generation |
| `domains/defi_generated/` | Local 14B alone |
| `domains/defi_websearch/` | Web-enriched generation |

Each corresponds to a row in the Part 3 experimental table comparing six
generation strategies on a 216-query DeFi benchmark.

These variants currently lack populated labeled-incident data (their
`data/` dirs are present but empty) and so they fail the `tx_validation_engine`
under v2's standards. The CI workflow (`.github/workflows/tests.yml`,
`v2-domain-tests` job) explicitly skips them so the v2 production guard set
runs clean.

If you are looking for **transaction-analysis guards** (the v2 substrate
covered by this repo's main README), see `domains/<name>/` for the
non-defi_* directories. Those guards each pass the validation engine 11/11,
ship a `test_profile.py`, and have a runnable per-domain demo under
`examples/per_domain/<name>/`.

If you are looking for **query-sanitization variants** (the v1 work covered
by Parts 1 + 3), the `defi*/` directories will be useful when their labeled
data is populated; cf. Part 3's experimental setup.
