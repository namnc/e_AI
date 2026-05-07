# wrong_chain_address — Demo

Flags pre-send recipient-validation risk: address with no activity on the
target chain, contract that cannot receive the token, address-poisoning
lookalike, chain-ID mismatch between signing and intended target, and
deprecated/migrated/paused recipient contracts.

## Run

```sh
python3 examples/per_domain/wrong_chain_address/demo.py
```

The demo loads `sample_tx.json` (a $50K USDC send where the wallet is on
chain ID 1 but the user intends Polygon, the recipient is a lookalike
planted by a dust attacker, the recipient has zero activity on Polygon,
and the recipient is a paused/migrated contract that cannot receive the
token), runs the rule-based analyzer, and adds LLM behavioral context.
Falls back to rule-based-only if Ollama is offline.

## What the guard catches (heuristics)

| ID | Name | Severity |
|---|---|---|
| H1 | Address has no activity on target chain | high |
| H2 | Contract address cannot receive tokens | critical |
| H3 | Address poisoning | critical |
| H4 | Chain ID mismatch | critical |
| H5 | Deprecated contract | high |

Full profile + signal definitions: `domains/wrong_chain_address/profile.json`

## Expected output

The sample triggers H1 (no Polygon activity) + H2 (contract cannot receive)
+ H3 (poisoned lookalike) + H4 (chain-id mismatch + EIP-55 fail) + H5
(paused + migrated), producing CRITICAL risk + `should_block: true`.

## Limitations (CROPS #14: epistemic status)

- Sample is **synthetic** — not a captured event.
- Lookalike detection here is a boolean flag; production analyzer would
  compute prefix / suffix / Hamming-distance similarity against the wallet's
  address book and recent transaction history.
- Recipient activity counts, contract bytecode/interface flags, and
  pause/migration state are inputs the analyzer trusts; production must
  wire these from RPC + block-explorer sources.

## Trust assumptions (CROPS #13)

- Recipient activity counts and contract metadata (paused / migrated) are
  trusted as inputs from explorer or RPC sources.
- LLM is local-only (Ollama) by default; recipient data does not leave the host.
