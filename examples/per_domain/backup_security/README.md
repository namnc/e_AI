# backup_security — Demo

Flags risk in wallet backup / social-recovery configurations:
password-only encryption with low entropy, stale guardians,
quantum-vulnerable encryption of permanent backup blobs, no coercion
resistance (single-secret backup), and non-deterministic per-action
secrets that are not backed up.

## Run

```sh
python3 examples/per_domain/backup_security/demo.py
```

The demo loads `sample_tx.json` (a backup encrypted with a 38-bit password
using ECDH+AES-GCM and stored permanently on Arweave, three guardians
unchecked for 240+ days, no deniable layer, and four Tornado Cash deposit
notes not in backup), runs the rule-based analyzer, and adds LLM behavioral
context. Falls back to rule-based-only if Ollama is offline.

## What the guard catches (heuristics)

| ID | Name | Severity |
|---|---|---|
| H1 | Password-only backup encryption | critical |
| H2 | Stale guardians | high |
| H3 | Quantum-vulnerable backup encryption | critical |
| H4 | No coercion resistance | high |
| H5 | Non-deterministic secrets not backed up | high |

Full profile + signal definitions: `domains/backup_security/profile.json`

## Expected output

The sample triggers H1 (38-bit password + weak KDF) + H2 (all guardians
stale, threshold unrecoverable) + H3 (ECDH-class encryption on permanent
on-chain blob) + H4 (no deniable layer) + H5 (Tornado Cash notes not
backed up), producing CRITICAL risk + `should_block: true`.

## Limitations (CROPS #14: epistemic status)

- Sample is **synthetic** — not a captured user backup configuration.
- KDF-strength threshold (Argon2id ≥ 64MB / ≥ 3 iter; password ≥ 50 bits)
  is conservative but not calibrated to user threat profile (casual vs
  high-value vs dissident). Production should make these per-profile.
- Coercion-resistance check is necessarily heuristic; the analyzer flags the
  absence of a deniable / honey-encryption layer rather than verifying its
  cryptographic soundness.

## Trust assumptions (CROPS #13)

- Backup-encryption labels and guardian-liveness timestamps are trusted as
  inputs from the wallet itself.
- LLM is local-only (Ollama) by default; backup metadata does not leave the host.
