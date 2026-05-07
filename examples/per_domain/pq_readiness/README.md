# pq_readiness — Demo

Assesses an account's exposure to a future cryptographically-relevant quantum
adversary: ECDH-only stealth registration, classical-only smart-account
validation, on-chain encrypted blobs without a PQ KEM, BLS validator
participation, and long-lived classical keys without rotation.

## Run

```sh
python3 examples/per_domain/pq_readiness/demo.py
```

The demo loads `sample_tx.json` (a long-lived account with a classical-only
smart account, ECDH-only stealth meta-address, 17 unprotected encrypted
blobs, active BLS validator participation, never rotated), runs the
rule-based analyzer, and augments with LLM analysis. The LLM step degrades
gracefully if Ollama is offline.

## What the guard catches (heuristics)

| ID | Name | Severity |
|---|---|---|
| H1 | ECDH-only stealth address registration | critical |
| H2 | Classical-only key in smart account | high |
| H3 | On-chain encrypted data using ECDH-derived key | critical |
| H4 | BLS threshold signature participation | high |
| H5 | Long-term key reuse without rotation | high |

Full profile + signal definitions: `domains/pq_readiness/profile.json`

## Expected output

The sample triggers all five heuristics, producing CRITICAL overall risk and
a low PQ readiness score (well below 1.0). LLM analysis (when available)
recommends migrating to a PQ-aware smart account module and rotating
long-term keys.

## Limitations (CROPS #14: epistemic status)

- "PQ readiness" here is a coarse local check, not a real-world Q-Day timer.
- ECDH-blob count is supplied; production would derive it by scanning the
  account's transaction history for known privacy-protocol selectors.
- BLS quantum-vulnerability is real but practical break is beyond Q-Day for
  most threat models; H4 is conservative.

## Trust assumptions (CROPS #13)

- Stealth-protocol versioning is trusted as input.
- Smart-account validation list is trusted as input.
- LLM is local-only (Ollama) by default; account snapshot does not leave the host.
