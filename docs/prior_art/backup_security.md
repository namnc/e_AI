# Prior art — backup_security

## What this guard catches (one line)
Risky wallet-backup configurations — guardian sets vulnerable to coercion / collusion / single-trust-domain failure, cloud-stored seed phrases (iCloud, Google Drive), and quantum-vulnerable long-lived backup material (harvest-now-decrypt-later).

## Existing tools that implement this (FULL or substantive coverage)

### Argent (guardian-set design)
- URL: https://support.argent.xyz/, https://www.argent.xyz/
- What it does: Smart-contract wallet pioneering social-recovery; users designate guardians (other wallets, hardware devices, friends); recovery requires majority + time-delay (e.g., 48h).
- Coverage of the heuristic set: Implements the *defense* (guardian model) but doesn't surface "your guardian set is risky" warnings (single jurisdiction, all on same exchange, etc.).
- Notable: Reference design for social recovery on Ethereum.

### Safe (Safe{Wallet})
- URL: https://safe.global/, https://safe.mirror.xyz/t76RZPgEKdRmWNIbEzi75onWPeZrBrwbLRejuj-iPpQ
- What it does: Modular smart-account stack with multisig + recovery; supports plugins, hooks, signature verifiers.
- Coverage: Implementation of multi-signer / guardian flows; risk surfacing is up to integrators.
- Notable: De-facto multisig wallet for organizations and individuals.

### Vault12 / social-recovery commercial offerings
- URL: https://vault12.com/blog/vitalik-buterin-social-recovery/
- What it does: Commercial guardian-network products; cite Vitalik's social-recovery vision as foundation.
- Coverage: Operational guardian networks; some guidance on guardian selection.

### QuantumShield / Quantum Canary (quantum-backup risk)
- URL: https://quantumwalletcheck.com/wiki/quantum-safe-wallets, https://www.quantumcanary.org/
- What it does: Scan addresses for quantum-vulnerability markers including key-reuse and exposed public keys — relevant to long-lived backup material.
- Coverage: Quantum-vulnerability axis only; doesn't cover guardian-set risk.

## Existing tools that implement this PARTIALLY

### "Recovery Methods in Wallets" (Dynamic.xyz)
- URL: https://www.dynamic.xyz/blog/recovery-methods-in-wallets-an-overview
- What it does: Overview of recovery methods + tradeoffs.
- Coverage: Educational; informs heuristic design.

### iCloud / cloud-backup risk research
- What it does: Documented attacks (e.g., MetaMask + iCloud phishing) — $650K crypto loss case widely cited.
- Coverage: Risk-class documentation; informs the "cloud backup → single point of failure" heuristic.

### Shamir backup tools (Trezor, etc.)
- URL: https://trezor.io/
- What it does: Shamir secret sharing for seed-phrase backup.
- Coverage: Implementation of m-of-n backup; risk surfacing minimal.

## Adjacent / not-quite-this-guard

### MPC custody (Fireblocks, Copper, ZenGo)
- URL: https://zengo.com/
- What it does: Threshold-signature custody; alternative to guardian-set model.
- Why adjacent: Different recovery architecture (MPC vs social); not a guard for users on guardian models.

### Post-quantum signature schemes (ML-DSA, SLH-DSA via ERC-4337)
- URL: per ethereum.org PQ roadmap
- Why adjacent: Forward-fix that addresses quantum exposure; doesn't analyze existing backup config.

## Where e_AI backup_security differs

Argent and Safe implement the recovery models; Vault12 productizes guardian networks; QuantumShield covers quantum exposure as a separate axis. There is no widely-deployed tool that *analyzes a specific user's backup config* and warns: "your 3 guardians are all in the same jurisdiction (high coercion risk), 2 of them are CEX hot wallets (single-failure risk), and your seed phrase is in iCloud (HND-vulnerable to quantum + Apple compromise)." e_AI's wedge: configuration-aware, multi-axis (jurisdiction × custody-type × cloud-exposure × quantum-vulnerability) risk synthesis, runs locally so the backup config doesn't need to be uploaded anywhere. Honest: each axis has prior art; the *composition* and the *local-execution* are the contribution. Quality bar is high — false positives would be very annoying ("your friend in Germany shouldn't be a guardian" type warnings).

## Open positioning question for the post

Does the user actually want this? Backup-config audit is the kind of thing users do once (during setup) and then ignore. Is there a re-examination trigger (annual review? after a friend changes circumstance?) that justifies a guard, or is this a one-shot setup wizard?

## Sources

- [Argent Support — Guardians](https://support.argent.xyz/hc/en-us/articles/360007338877-How-to-recover-my-wallet-with-guardians-onchain-complete-guide)
- [Safe modular smart account architecture](https://safe.mirror.xyz/t76RZPgEKdRmWNIbEzi75onWPeZrBrwbLRejuj-iPpQ)
- [Mitosis — Social recovery wallets intro](https://university.mitosis.org/intro-to-social-recovery-wallets-safe-argent-and-erc-4337/)
- [Vault12 — Vitalik on social recovery](https://vault12.com/blog/vitalik-buterin-social-recovery/)
- [Recovery methods overview (Dynamic.xyz)](https://www.dynamic.xyz/blog/recovery-methods-in-wallets-an-overview)
- [QuantumShield — quantum-safe wallets](https://quantumwalletcheck.com/wiki/quantum-safe-wallets)
- [WWT — Are your backups quantum safe?](https://www.wwt.com/blog/are-your-backups-quantum-safe)
