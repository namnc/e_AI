# governance_proposal — Demo

Flags pre-vote risk on DAO proposals: treasury drains to unknown recipients,
out-of-distribution parameter changes, proxy upgrades to unverified
implementations, timelock bypass attempts, and voter concentration that
allows a single party to push a proposal through.

## Run

```sh
python3 examples/per_domain/governance_proposal/demo.py
```

The demo loads `sample_tx.json` (a proposal that drains 25% of treasury to
two fresh EOAs, raises a collateral factor 10σ above historical mean,
upgrades a proxy to an unverified implementation containing `selfdestruct`
and unrestricted `delegatecall`, slashes timelock from 48h to 2h, and is
passed by a single 62% voter), runs the rule-based analyzer, and augments
with LLM analysis. The LLM step degrades gracefully if Ollama is offline.

## What the guard catches (heuristics)

| ID | Name | Severity |
|---|---|---|
| H1 | Treasury drain | critical |
| H2 | Parameter manipulation | high |
| H3 | Proxy upgrade to unverified code | critical |
| H4 | Timelocked bypass | critical |
| H5 | Voter concentration | high |

Full profile + signal definitions: `domains/governance_proposal/profile.json`

## Expected output

The sample triggers all five heuristics, producing CRITICAL overall risk
with `should_block: true`.

## Limitations (epistemic status)

- Sample is **synthetic** — not a captured DAO proposal.
- Bytecode-diff size is supplied as a flag; production would diff bytecode
  semantically and look for opcode-level changes.
- Voter concentration is computed from a supplied top-voter share; production
  would query on-chain vote tallies + delegated voting power.

## Trust assumptions

- Recipient labels and tx counts are trusted as inputs.
- Implementation verification status is trusted (e.g., Etherscan).
- LLM is local-only (Ollama) by default; proposal data does not leave the host.
