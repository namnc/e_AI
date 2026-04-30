# Failure Analysis: approval_phishing

*Auto-generated. Review and refine.*

1. **FALSE NEGATIVES**:
   - **Phishing with Known Legitimate Contracts**: An attacker could use a known, verified contract for approval without triggering H2 or H3, especially if the contract has a recent history of legitimate transactions.
   - **Custom Functionality Misuse**: A spender using custom function selectors that aren’t flagged by H4 but still pose significant risks due to their nature.

2. **FALSE POSITIVES**:
   - **Recently Deployed Legitimate Contracts**: New, yet legitimate contracts might be flagged as "unverified" for a short period until they get listed on registries, leading to unnecessary alerts.
   - **Dormant Approvals with Recent Interactions**: A user might have approved an unlimited token limit recently and still interact frequently enough that H5 doesn’t trigger despite the high risk.

3. **FUNDAMENTAL LIMITATIONS**:
   - **Heuristics for Custom Tokens**: The profile struggles to assess risks involving custom tokens or non-fungible tokens (NFTs) that don't follow standard ERC-20/721 interfaces.
   - **User Intent Interpretation**: Technology can’t fully understand the user’s intent behind approving a token, leading to over- or under-flagging of certain behaviors.