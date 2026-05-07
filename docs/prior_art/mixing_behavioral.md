# Prior art — mixing_behavioral

## What this guard catches (one line)
Post-mixer linkability — operational behavioral patterns (timing, amount, gas, address reuse, FIFO matching) that allow an analyst to link a mixer withdrawal back to its originating deposit, even across chains.

## Existing tools that implement this (FULL or substantive coverage)

### Tutela (Pareto Labs)
- URL: https://github.com/pareto-xyz/tutela-app, https://arxiv.org/abs/2201.06811
- What it does: Anonymity-set auditor for Tornado Cash; implements 7 heuristics — 2 Ethereum-wide + 5 TC-specific (address-match reveal, gas-price reveal, denomination reveal, multi-denomination reveal, linked-address reveal). Computes true anonymity-set size by excluding compromised deposits.
- Coverage of the heuristic set: Most direct prior art. 42.8K / 97.3K (≈44%) Tornado equal-user deposits identified as compromised.
- Notable: Open source; the canonical reference for mixer-anonymity heuristics.

### "Clustering Deposit and Withdrawal Activity in Tornado Cash: A Cross-Chain Analysis" (arXiv 2510.09433, 2025)
- URL: https://arxiv.org/abs/2510.09433
- What it does: Three heuristics — address-reuse, transactional-linkage, FIFO temporal matching — applied across chains. Reports 5.1-12.6% direct linkage + 15-22pp additional via FIFO temporal matching.
- Coverage: Cross-chain extension that e_AI's behavioral profile would need to match.
- Notable: Adds the FIFO temporal-matching heuristic that wasn't in Tutela.

### "Analysis of Address Linkability in Tornado Cash on Ethereum" (Tang et al., Springer 2022)
- URL: https://link.springer.com/chapter/10.1007/978-981-16-9229-1_3
- What it does: Three heuristic clustering rules for linking user addresses; quantifies privacy-leakage risk.
- Coverage: Foundational — Tutela builds on this work.

### "Attacking Anonymity Set in Tornado Cash via Wallet Fingerprinting" (ACM AsiaCCS 2025)
- URL: https://dl.acm.org/doi/pdf/10.1145/3672608.3707896
- What it does: Adds wallet-fingerprint heuristic on top of existing methods.
- Coverage: Extends the heuristic set with browser/wallet fingerprint signals.

## Existing tools that implement this PARTIALLY

### Chainalysis Reactor / Elliptic / TRM Labs
- URL: https://www.chainalysis.com/, https://www.elliptic.co/, https://www.trmlabs.com/
- What it does: Commercial blockchain forensics with proprietary mixer-clustering heuristics.
- Coverage: Operate the *attacker* side of this guard — the threat being defended against.
- Notable: Defines the upper bound of detection capability the user is being warned about.

### RAILGUN / Privacy Pools user guidance
- URL: https://docs.railgun.org/wiki/learn/privacy-system
- What it does: Documents user-side hygiene (delay between deposit and withdraw, vary amounts).
- Coverage: Documentation, not runtime enforcement.

## Adjacent / not-quite-this-guard

### Tornado Cash anonymity-mining
- Why adjacent: Protocol-level incentive to wait, not a runtime guard.

### "Privacy Pools" paper (Buterin, Illum, Nadler, Schar, Soleimani, 2023)
- Why adjacent: Compliant-mixer architecture that frames the broader trust environment, but doesn't implement behavioral guards.

## Where e_AI mixing_behavioral differs

The academic literature has thoroughly defined the heuristics; Tutela operationalizes them as an *auditor* (point-in-time, after the fact). Commercial forensics tools operate the offensive side. The gap e_AI fills: **pre-withdrawal, runtime, wallet-side** prevention — at the moment a user is about to withdraw, surface "this withdrawal will be linked to your original deposit via FIFO + address-reuse with 60% confidence." Tutela tells you *after*; e_AI tells you *before*. Honest: heuristics are not novel — Tutela + the cross-chain paper define them. Novelty is in pre-emptive runtime delivery + cross-chain reasoning local to the user's wallet.

## Open positioning question for the post

The heuristic set is well-published. Is "Tutela, but at signing time, in your wallet" sufficient novelty? Or should the post emphasize the cross-chain dimension (5.1-12.6% direct + 15-22pp FIFO across chains) as the new contribution?

## Sources

- [Tutela paper](https://arxiv.org/abs/2201.06811)
- [Tutela GitHub](https://github.com/pareto-xyz/tutela-app)
- [Cross-chain TC analysis (arXiv 2510.09433)](https://arxiv.org/abs/2510.09433)
- [Tang et al. — Address Linkability](https://link.springer.com/chapter/10.1007/978-981-16-9229-1_3)
- [Wallet Fingerprinting Attack](https://dl.acm.org/doi/pdf/10.1145/3672608.3707896)
- [RAILGUN privacy guidance](https://docs.railgun.org/wiki/learn/privacy-system)
