# Prior art — behavioral_drift

## What this guard catches (one line)
Drift from a user's historical baseline that signals risky concentration, leverage creep, or compromised-account behavior — e.g., a user who normally holds 30% stables suddenly going 100% leveraged long, or a wallet whose tx pattern deviates sharply from historical norm.

## Existing tools that implement this (FULL or substantive coverage)

### Nansen
- URL: https://nansen.ai/, https://www.nansen.ai/post/how-to-analyze-wallet-behavior-in-crypto-a-guide-to-onchain-intelligence-smarter-trading
- What it does: AI-powered onchain analytics with 500M+ wallet labels; categorizes wallets into Smart Money, funds, institutions, etc.; tracks behavior patterns.
- Coverage of the heuristic set: Behavior labeling and trend tracking — at the *observer* level, not the wallet-self-monitoring level.
- Notable: Dominant in this space alongside Arkham.

### Arkham Intelligence
- URL: https://arkhamintelligence.com/
- What it does: Entity attribution via deanonymization heuristics + behavior labeling; concentration analysis in supply distribution.
- Coverage: Strong on attribution + concentration; weaker on per-user real-time anomaly alerts.

### Forta (anomaly detection bots)
- URL: https://forta.org/
- What it does: Decentralized network of detection bots; some bots monitor for anomalous wallet behavior (large unusual transfers, sudden new counterparty).
- Coverage: Bot-developer-defined heuristics; ZenGo wallet integration adds in-wallet anomaly alerts.
- Notable: Closest analog to "drift detection in a wallet."

### Collective anomaly-detection literature (MDPI 2022, etc.)
- URL: https://www.mdpi.com/2073-8994/14/2/328
- What it does: Academic ML methods for detecting anomalous crypto-wallet behavior.
- Coverage: Methodology references; not a deployed tool.

## Existing tools that implement this PARTIALLY

### DeBank / Zerion / Zapper portfolio trackers
- URL: https://debank.com/, https://zerion.io/, https://zapper.xyz/
- What it does: Show position composition over time.
- Coverage: User has the data; drift detection is left to the user.

### TradFi anomaly-detection patterns (TechCrunch overview)
- URL: https://techcrunch.com/2021/07/28/financial-firms-should-leverage-machine-learning-to-make-anomaly-detection-easier/
- What it does: ML-based anomaly detection used in TradFi.
- Coverage: Methodology reference, not crypto-specific.

### AI agent intent-drift (ARMO)
- URL: https://www.armosec.io/blog/detecting-intent-drift-in-ai-agents-with-runtime-behavioral-data/
- What it does: Detects drift in AI-agent behavior at runtime (tool-use sequences).
- Coverage: Conceptual analog to wallet-behavior drift; framework reference.

## Adjacent / not-quite-this-guard

### Compromised-account monitoring (Forta, Hypernative)
- URL: https://hypernative.io/
- What it does: Catches compromise/exploit signatures in real time.
- Why adjacent: Compromise is one cause of drift; broader compromise detection doesn't cover concentration/leverage drift.

### Risk-rating dashboards
- Why adjacent: Static portfolio scoring, not behavioral-baseline drift.

## Where e_AI behavioral_drift differs

Nansen and Arkham operate the *observer* side (analyst watches wallets). Forta has bot infrastructure but coverage is fragmented. There is no widely-deployed *self-monitoring, wallet-resident* drift detector — "your portfolio leverage is 2× your 90-day baseline; your tx pattern deviates from your historical norm." e_AI's wedge: local-LLM has full historical context (wallet history, position graph) without leaking to a third party — and the analysis is per-user-baseline rather than population-baseline. Honest: this is a generic ML problem (anomaly detection on time-series financial behavior); novelty is in the *local-LLM + privacy-preserving* framing rather than the detection algorithm. Also: the heuristic set ("what counts as drift?") is poorly specified across the literature.

## Open positioning question for the post

What's the user complaint this addresses? Is it "I want to be warned before I make a leveraged trade I'll regret" (paternalistic, may not be wanted) or "I want to detect compromise" (overlaps with Hypernative)? Without a sharp user story, this guard risks feeling like a solution-in-search-of-a-problem.

## Sources

- [Nansen — Wallet behavior analysis guide](https://www.nansen.ai/post/how-to-analyze-wallet-behavior-in-crypto-a-guide-to-onchain-intelligence-smarter-trading)
- [Arkham vs Nansen comparison](https://startupik.com/arkham-intelligence-vs-nansen-which-wallet-tracking-tool-is-better/)
- [Forta — Onchain threat detection bots](https://www.forta.org/blog/what-are-on-chain-threat-detection-bots)
- [ZenGo + Forta integration](https://www.forta.org/blog/zengo-and-forta-add-in-wallet-monitoring-to-protect-end-users)
- [Collective anomaly detection (MDPI)](https://www.mdpi.com/2073-8994/14/2/328)
- [ARMO — AI agent intent drift](https://www.armosec.io/blog/detecting-intent-drift-in-ai-agents-with-runtime-behavioral-data/)
