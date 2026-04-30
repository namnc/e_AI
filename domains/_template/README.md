# Domain: [NAME]

**Type:** [Text query analysis | Transaction analysis]
**CROPS property:** [C | R | O | P | S]
**Status:** Draft
**Schema:** [`core/domain_profile.py` | `core/tx_profile.py`]
**Source:** [paper / report reference]

## What this domain does

[1-2 sentences: what risks does this profile detect?]

## Heuristics

| # | Heuristic | Severity | Countermeasure |
|---|---|---|---|
| H1 | | | |

## Getting started

1. Copy this template: `cp -r domains/_template domains/my_domain`
2. Edit `profile.json` with your heuristics, signals, recommendations, skills
3. Validate: `python -m meta.tx_validation_engine domains/my_domain/profile.json`
4. Fix any FAIL/MARGINAL checks
5. Add labeled data to `data/` for benchmarking
6. Write domain-specific analyzer if generic checks aren't sufficient
7. Update this README

## What needs human effort

- [ ] [list items that require domain expertise or real-world data]

## Improving this domain

See `docs/improving_a_domain.md`
