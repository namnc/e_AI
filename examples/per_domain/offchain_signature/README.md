# offchain_signature — Demo

Flags pre-signing risk for off-chain signatures: Permit2 unlimited approvals,
EIP-712 typed data that disguises a transfer as a login, setApprovalForAll to
unknown operators, signatures from unverified or homoglyph dApp origins,
batch permits, and below-market Seaport orders.

## Run

```sh
python3 examples/per_domain/offchain_signature/demo.py
```

The demo loads `sample_tx.json` (an unlimited Permit2 approval to an unknown
spender, served by a 4-day-old homoglyph domain whose UI says "Sign in" but
whose payload encodes an approval), runs the rule-based analyzer, and
augments with LLM behavioral analysis. The LLM step degrades gracefully if
Ollama is offline.

## What the guard catches (heuristics)

| ID | Name | Severity |
|---|---|---|
| H1 | Permit2 unlimited or long expiry | critical |
| H2 | EIP-712 typed data encoding token transfer | critical |
| H3 | setApprovalForAll to unknown operator | high |
| H4 | Signature from unverified dApp origin | high |
| H5 | Batch permit (multiple tokens) | critical |
| H6 | Seaport order below market price | high |

Full profile + signal definitions: `domains/offchain_signature/profile.json`

## Expected output

The sample triggers H1 (unlimited + unknown spender), H2 (UI/payload
mismatch), and H4 (unverified, homoglyph, fresh dApp) — overall CRITICAL.

## Limitations (epistemic status)

- Sample is **synthetic** — not a captured phishing payload.
- `spender_in_protocol_registry` and `domain_in_protocol_registry` are
  trusted as inputs; production needs a curated registry + WHOIS / TLS
  cert lookups.
- Homoglyph detection is supplied as a flag, not derived from the URL.

## Trust assumptions

- Wallet is responsible for surfacing `ui_description` accurately.
- Protocol registry is trusted.
- LLM is local-only (Ollama) by default; signature payload does not leave the host.
