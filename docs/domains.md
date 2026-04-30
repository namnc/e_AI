# Domain Catalog

Each domain is a risk area that e_AI protects against. A domain profile encodes detection heuristics, countermeasures, and skills for that risk area.

---

## Wallet Guard Domains (5)

These profiles analyze user actions at signing time. The wallet intercepts `eth_sendTransaction` or `eth_signTypedData`, decodes the calldata/typed data, and routes to the matching profile.

### stealth_address_ops
**What it protects:** Privacy of stealth address users (ERC-5564, Umbra).
**The problem:** 48.5% of stealth address transactions are deanonymized through 6 operational heuristics -- not cryptographic breaks. Users leak through timing, amounts, gas patterns, address reuse, and funding sources.
**Source:** Béres et al., ACM Web Conference 2024 ([arxiv 2308.01703](https://arxiv.org/abs/2308.01703))
**CROPS property:** P (Privacy)

| Heuristic | What leaks | Countermeasure |
|---|---|---|
| H1 Same-entity withdrawal | Withdrawal address in sender's cluster | Fresh unlinked address |
| H2 Gas fingerprinting | Consistent gas params across txs | Randomize within block distribution |
| H3 Timing correlation | Spend shortly after deposit | Delay 6-24 hours |
| H4 Funding linkability | Gas paid from known address | ERC-4337 paymaster |
| H5 Self-transfer | Sender = recipient | Block the transaction |
| H6 Unique amounts | Non-standard amount narrows set | Round to standard denomination |

**Integration:** Wallet guard intercepts stealth address deposit/withdraw operations.
**Maturity:** Reference implementation. 3 profile variants, 23 tests, cover generator, real Umbra data, failure analysis.

---

### approval_phishing
**What it protects:** User funds from token approval exploits.
**The problem:** $713M lost to approval phishing in 2025. Users approve unlimited token spending to malicious contracts, or sign off-chain permits that drain wallets. Approvals persist indefinitely -- a contract approved years ago can still drain tokens.
**Source:** Forta / Scam Sniffer 2025 Phishing Report
**CROPS property:** S (Security)

| Heuristic | What it catches | Countermeasure |
|---|---|---|
| H1 Unlimited approval | approve(MAX_UINT256) | Limit to exact amount |
| H2 Unverified spender | Contract not verified, recently deployed | Block until verified |
| H3 Known scam address | Address in Forta/ScamSniffer database | Block immediately |
| H4 Suspicious function | Unknown selector, hidden approval in multicall | Decode and show effects |
| H5 Stale approval | Unlimited approval to unused contract >30 days | Periodic revocation |

**Integration:** Wallet guard decodes `approve`, `increaseAllowance`, `setApprovalForAll` selectors.
**Key insight:** Most damage comes from approvals that users set and forget. The stale approval scanner (H5) is unique to local analysis -- no cloud service tracks your full approval history.

---

### offchain_signature
**What it protects:** Users from malicious off-chain signatures that authorize on-chain actions.
**The problem:** EIP-712 typed data, Permit2, Seaport listings look like "sign a message" but actually authorize token transfers, NFT sales, or unlimited approvals. Growing fastest among phishing vectors because users don't understand what they're signing.
**CROPS property:** S (Security)

| Heuristic | What it catches | Countermeasure |
|---|---|---|
| H1 Permit2 unlimited | PermitSingle/PermitBatch with max amount or long expiry | Short expiry, exact amount |
| H2 Disguised transfer | EIP-712 with to/value fields = hidden transfer auth | Decode and explain in plain language |
| H3 setApprovalForAll | NFT collection-wide approval to unknown operator | Verify operator contract |
| H4 Unverified dApp | Signature requested from unknown origin | Block until dApp verified |
| H5 Batch permit | Multiple tokens in one signature | Show each token separately |
| H6 Below-market order | Seaport listing priced below floor | Price check against market data |

**Integration:** Wallet guard intercepts `eth_signTypedData_v4`, decodes the typed data structure.
**Key insight:** The signature LOOKS like a harmless message but IS an on-chain authorization. The gap is translation -- the profile teaches the system to decode typed data into human-readable consequences.

---

### governance_proposal
**What it protects:** DAO treasury and protocol parameters from malicious governance actions.
**The problem:** Governance proposals can drain treasuries, change critical parameters, upgrade proxies to malicious code, or bypass timelocks. Most governance participants vote without reading the proposal's actual on-chain effects.
**CROPS property:** S (Security)

| Heuristic | What it catches | Countermeasure |
|---|---|---|
| H1 Treasury drain | Transfer >10% of treasury to new address | Flag for community review |
| H2 Parameter manipulation | Liquidation thresholds, fees outside historical range | Simulate parameter change effects |
| H3 Proxy upgrade | Implementation changed to unverified code | Require verified + audited code |
| H4 Timelock bypass | Reduces or removes governance timelock | Block -- timelock removal is almost always malicious |
| H5 Voter concentration | >50% votes from <3 addresses | Warn about centralization |

**Integration:** Wallet guard decodes `execute`, `propose`, `castVote` selectors on known governor contracts.
**Key insight:** The heuristics check what the proposal DOES, not what it SAYS. A proposal titled "minor parameter update" that changes the treasury multisig is caught by H1.

---

### l2_bridge_linkage
**What it protects:** Cross-chain privacy when bridging assets between L1 and L2.
**The problem:** Bridge transactions create deterministic links between L1 and L2 identities. Same address, same amount, same timing, unique tokens -- all link the user across chains. Privacy gained on L2 is lost if the bridge leaks.
**CROPS property:** P (Privacy)

| Heuristic | What it catches | Countermeasure |
|---|---|---|
| H1 Same address bridge | Same address used on both chains | Use different address per chain |
| H2 Amount correlation | Bridge deposit matches withdrawal by exact amount + timing | Split amount, add delay |
| H3 Sequence fingerprint | Bridges to same set of L2s in recognizable pattern | Vary bridge usage |
| H4 Gas funding post-bridge | L2 address funded from bridged ETH | Use L2 paymaster or faucet |
| H5 Token bridge linkage | Unique tokens (NFTs, non-standard amounts) bridged | Sell/rebuy instead of bridge |

**Integration:** Wallet guard recognizes bridge contract addresses and deposit/withdraw selectors.
**Key insight:** H5 (unique token bridging) is near-deterministic. If you bridge CryptoPunk #7804 from L1 to Arbitrum, the link is permanent. Selling on L1 and rebuying on L2 breaks the link but costs more.

---

## Local RPC Guard Domains (3)

These profiles analyze RPC query patterns and accumulated state. The RPC proxy (`proxy/rpc_proxy.py`) passively observes queries flowing through it and builds analysis from the accumulated data.

### rpc_leakage
**What it protects:** User strategy and address relationships from RPC providers.
**The problem:** Every wallet query (balance check, contract call, transaction simulation) goes to an RPC provider. The query PATTERN reveals user strategy: which addresses are yours, which positions you're monitoring, what you're about to trade. Even with on-chain privacy, the RPC layer leaks intent.
**CROPS property:** P (Privacy)

| Heuristic | What it catches | Countermeasure |
|---|---|---|
| H1 Address linkage | Balance checked for multiple addresses → provider links them | Use local light client (Helios) |
| H2 Position monitoring | Repeated eth_call to lending protocol → reveals positions | Reduce polling, use local node |
| H3 Pre-trade intent | Swap simulation via eth_estimateGas → reveals intent before submission | Simulate locally |
| H4 Stealth scanning | Checking stealth address announcements → reveals which addresses are yours | Scan locally via Helios |
| H5 Portfolio composition | Token price checks correlated with holdings → reveals portfolio | Batch queries, add cover queries |

**Integration:** RPC proxy logs all queries, detects patterns over 5-minute windows.
**Key insight:** The RPC provider sees MORE than on-chain observers. They see intent BEFORE action. "User is about to liquidate position X" is visible from the simulation query before the liquidation transaction is submitted.

---

### cross_protocol_risk
**What it protects:** Users from compound risks that span multiple DeFi protocols.
**The problem:** A user's Aave position, Uniswap liquidity, and Compound borrows are not independent. A single oracle failure or price drop can trigger cascading liquidations across protocols. No existing tool sees the full picture because each protocol's UI only shows its own state.
**CROPS property:** S (Security)

| Heuristic | What it catches | Countermeasure |
|---|---|---|
| H1 Cascading liquidation | Swap would trigger lending liquidation | Simulate before execution |
| H2 Oracle dependency | Multiple positions depend on same oracle | Diversify oracle sources |
| H3 Concentration | >50% portfolio in one protocol | Monitor and alert |
| H4 Approval chain risk | Approved tokens in protocol A are collateral in B | Map approval → collateral dependencies |
| H5 Flash loan surface | Position attackable via flash loan | Monitor attack profitability |

**Integration:** RPC proxy accumulates contract call data to build portfolio picture. When calls to lending/DEX contracts exceed thresholds, cross-protocol analysis triggers.
**Key insight:** This profile needs no additional queries -- it builds its picture from what the wallet is ALREADY reading. The user's normal DeFi usage generates all the data needed.

---

### l2_anonymity_set
**What it protects:** Users from transacting when L2 privacy conditions are poor.
**The problem:** L2s have fewer users than L1, meaning smaller anonymity sets. A privacy pool with 5 depositors in 24h gives anonymity set of 5 regardless of how good the cryptography is. L2 block times (0.25-2s) create tighter timing correlation than L1's 12s. Centralized sequencers see all transactions.
**CROPS property:** P (Privacy)

| Heuristic | What it catches | Countermeasure |
|---|---|---|
| H1 Thin pool | <20 depositors in user's amount range in 24h | Wait or use L1 instead |
| H2 Sequencer visibility | Centralized sequencer sees all txs pre-batch | Use private submission or L1 for sensitive txs |
| H3 Forced inclusion leak | L1 forced inclusion reveals L2 tx origin | Only use for censorship resistance |
| H4 Timing correlation | Sub-second blocks tighten timing window | Proportionally longer delays |
| H5 Batch linkage | Same rollup batch = correlated by timing | Spread across batches |

**Integration:** RPC proxy monitors `eth_getLogs` results for privacy pool contracts. When log count is low, alerts that the anonymity set is thin.
**Key insight:** H4 is quantitative. Arbitrum's 0.25s blocks mean timing correlation is 48x tighter than L1's 12s. A 6-hour delay on L1 is equivalent to a 12-day delay on Arbitrum for the same anonymity benefit.

---

## LLM Proxy Domain (1)

### defi_query (v1)
**What it protects:** User's DeFi strategy and positions from cloud LLM providers.
**The problem:** Users ask AI assistants about their DeFi positions. "Should I add collateral to my 100K USDC Aave position?" leaks the position size, protocol, and intent to the LLM provider. The LLM provider may log, train on, or be compelled to disclose this data.
**CROPS property:** P (Privacy)

This is the original e_AI v1. Sanitizes queries by removing sensitive information (amounts, addresses, protocol names, positions) and generates cover queries that are indistinguishable from real ones.

**Integration:** LLM proxy between user/agent and cloud LLM API.
**Maturity:** Production. 829-line hand-crafted profile, 6 profile variants, 13-check validation, cover generator v5, multiple benchmarks, audited.

---

## Planned Domains (not yet built)

| Domain | Access | CROPS | What it would protect |
|---|---|---|---|
| pq_readiness | Wallet | S | Detect quantum-vulnerable keys/operations before execution |
| mev_vulnerability | Wallet | S | Estimate sandwich/front-running loss before swap submission |
| wrong_chain_address | Wallet | S | Detect sending to wrong chain or contract vs EOA mismatch |
| behavioral_drift | Wallet | S | Alert on portfolio concentration creep, leverage increase over time |
| backup_security | Wallet | S | Monitor guardian liveness, backup encryption strength, coercion risk |
| mixing_behavioral | L2 | P | Detect post-mixer linkability patterns across chains |
| agent_privacy | AI | P | Detect when AI agent interaction graph reveals the human behind it |
| sequencer_privacy | L2 | P | Track sequencer-specific behavior and centralization risks |
| general_crypto_query | AI | P | Extend v1 query sanitization beyond DeFi to NFT, governance, staking |
