# Domain: Off-chain Signature Phishing

**Type:** Transaction analysis
**CROPS property:** S (Security)
**Status:** Draft
**Schema:** `core/tx_profile.py`
**Source:** Scam Sniffer 2025 Phishing Report; EIP-2612; EIP-712; Permit2 (Uniswap)

## What this domain does

Detects phishing attacks that exploit off-chain signature mechanisms (EIP-712 typed data, EIP-2612 permits, Permit2, Seaport orders) to steal tokens without requiring on-chain approval transactions. These attacks are the dominant wallet-drainer vector since 2024.

## Heuristics

| # | Heuristic | Severity | Countermeasure |
|---|---|---|---|
| H1 | Permit2 unlimited/long expiry | critical | Limit amount + set 1h expiry |
| H2 | EIP-712 typed data encoding token transfer | critical | Decode payload before signing |
| H3 | setApprovalForAll to unknown operator | high | Verify operator against registries |
| H4 | Signature from unverified dApp origin | high | Check domain against allowlist |
| H5 | Batch permit (multiple tokens) | critical | Decompose into individual permits |
| H6 | Seaport order below market price | high | Fetch floor price before signing |

## Skills

- **signature_decoder** -- Decode EIP-712, Permit2, Seaport payloads into human-readable form
- **dapp_verifier** -- Check dApp origin against registries, detect homoglyphs, verify contracts
- **price_checker** -- Fetch NFT floor prices and token valuations for order comparison

## What needs human effort

- [ ] Curate allowlist of verified protocol domains and contract addresses
- [ ] Collect labeled dataset of phishing vs legitimate signing requests
- [ ] Calibrate price thresholds for Seaport order detection (collection-specific)
- [ ] Integrate with real-time scam databases (Scam Sniffer, Forta)
- [ ] Validate homoglyph detection across Unicode character sets

## Improving this domain

See `docs/improving_a_domain.md`
