# On-Chain Staking Mechanism for AI Inference Accountability

> **Status**: Research agenda. The interface below is illustrative, not a deployed contract.

## Problem

A cloud LLM provider that observes DeFi queries has economic incentive to exploit them (front-running, liquidation hunting). Today there is no mechanism to penalize this behavior — unlike TradFi brokers who face SEC/FINRA sanctions for front-running.

## Proposed Mechanism

An on-chain registry where inference providers stake collateral and commit to honest behavior. Dishonesty is penalized via slashing, analogous to Ethereum validator staking.

### Sample Interface (Solidity)

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IInferenceProviderRegistry {
    struct Provider {
        address operator;
        uint256 stake;              // ETH staked as collateral
        bytes32 modelHash;          // SHA-256 of committed model weights
        bytes32 codeHash;           // SHA-256 of serving code
        string modelName;           // e.g., "meta-llama/Llama-3.3-70B"
        uint256 registeredAt;
        uint256 slashCount;
        bool active;
    }

    // Registration
    function register(
        bytes32 modelHash,
        bytes32 codeHash,
        string calldata modelName
    ) external payable;             // msg.value = stake amount

    // Query: get provider info
    function getProvider(address operator) external view returns (Provider memory);
    function isActive(address operator) external view returns (bool);
    function getStake(address operator) external view returns (uint256);

    // Fraud proof submission
    function submitFraudProof(
        address provider,
        bytes calldata teeAttestation,     // TEE-signed {model_hash, query_hash, response_hash}
        bytes calldata evidence            // Proof of dishonesty
    ) external;

    // Slashing (called by governance or fraud-proof verifier)
    function slash(address provider, uint256 amount, string calldata reason) external;

    // Withdrawal (after unbonding period)
    function initiateWithdrawal() external;
    function completeWithdrawal() external;  // after cooldown

    // Events
    event ProviderRegistered(address indexed operator, bytes32 modelHash, uint256 stake);
    event FraudProofSubmitted(address indexed accuser, address indexed provider, bytes32 evidenceHash);
    event Slashed(address indexed provider, uint256 amount, string reason);
    event WithdrawalInitiated(address indexed provider, uint256 unlockTime);
}
```

### Slashing Conditions and Thresholds

Not all misbehavior is equally provable. We distinguish three tiers:

| Tier | Fault Type | Provability | Slashing Amount | Example |
|---|---|---|---|---|
| **1: Attestation mismatch** | Provider's TEE attestation doesn't match committed model hash | **Machine-verifiable** — compare hashes on-chain | 100% of stake | Provider committed Llama-3.3-70B but TEE attests a different hash |
| **2: Transcript inconsistency** | Provider's TEE-sealed transcript shows response differs from what user received | **Machine-verifiable** — compare hashes | 50% of stake | Provider modified the response after TEE sealing |
| **3: Response quality / honesty** | Provider gave deliberately wrong advice or differential treatment | **NOT machine-verifiable** — requires human judgment | Governance vote | Provider systematically gave worse answers to suspected real queries |

**Important**: Only Tiers 1-2 are automatically slashable. Tier 3 requires an off-chain dispute resolution mechanism (similar to Kleros or Optimistic Rollup fraud proofs with a challenge period).

### Economic Parameters

```
Minimum stake:        10 ETH (~$25,000 at $2,500/ETH)
Unbonding period:     7 days
Challenge period:     48 hours (for fraud proofs)
Slashing for Tier 1:  100% of stake
Slashing for Tier 2:  50% of stake
Slashing for Tier 3:  Governance-determined (0-100%)
Reward for valid 
  fraud proof:        10% of slashed amount (incentivizes monitoring)
```

### Economic Security Condition

For slashing to deter misbehavior:

```
Expected cost of cheating > Expected profit from cheating

p_detect × stake_slashed > profit_per_exploit

Where:
  p_detect  = probability of detection (from challenge-response testing)
  stake     = provider's staked ETH
  profit    = expected MEV from exploiting a single user's query
```

Example: If challenge-response testing detects differential treatment with 10% probability, and exploiting a single user's query yields $50,000 in MEV profit:

```
Required stake > $50,000 / 0.10 = $500,000

At $2,500/ETH: minimum 200 ETH staked
```

This is comparable to Ethereum validator stakes (32 ETH) but higher, reflecting the greater potential for financial harm.

### Integration with Existing Infrastructure

| Component | Existing Project | Integration Point |
|---|---|---|
| TEE attestation | NVIDIA CC, Phala Network | Provider submits attestation report to registry |
| Dispute resolution | Kleros, UMA Optimistic Oracle | Tier 3 fraud proofs routed to decentralized arbitration |
| Staking mechanics | EigenLayer | Could use EigenLayer restaking for capital efficiency |
| Provider reputation | DeepBook (Sui), Bittensor | On-chain query count + slashing history = reputation score |

### What This Does NOT Solve

- **Cannot prove "bad advice"** in a machine-verifiable way. "The provider told me to add collateral when I should have closed" is a subjective judgment, not an on-chain-provable fault.
- **Cannot prevent a provider from INTERNALLY logging queries** and selling the data off-chain. Slashing only works when misbehavior produces on-chain evidence.
- **Cannot force a provider to participate.** The registry is opt-in. Providers with no stake can still operate — they just don't get the "verified" badge that privacy-conscious users would require.

### Deployment Roadmap

1. **Phase 1 (deployable now)**: Registry contract with model-hash commitments. No TEE integration — providers self-attest. Slashing only for attestation mismatch (Tier 1).
2. **Phase 2 (near-term)**: TEE integration via Phala Network or NVIDIA CC SDK. Providers submit TEE attestation reports. Slashing for transcript inconsistency (Tier 2).
3. **Phase 3 (research)**: Dispute resolution for response quality (Tier 3). Requires integration with Kleros/UMA for decentralized arbitration.
