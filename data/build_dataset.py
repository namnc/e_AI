"""
Build the unified benchmark dataset from all sources.
Outputs: benchmark_dataset.jsonl (standard format for reuse by others).

Sources:
  - data/real_queries.json (rich metadata, 45 queries)
  - dataset.py (hardcoded, 140 queries)
  - Borderline cases (added here)
  - Real-world-sourced queries (from public DeFi forums)

Run: python data/build_dataset.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dataset import SENSITIVE_QUERIES, NON_SENSITIVE_QUERIES, COMPLEX_QUERIES, SANITIZED_QUERIES
from cover_generator import sanitize_query, classify_domain

OUT = Path(__file__).parent / "benchmark_dataset.jsonl"


def load_real_queries():
    with open(Path(__file__).parent / "real_queries.json") as f:
        data = json.load(f)
    entries = []
    for q in data.get("sensitive_queries", []):
        entries.append({
            "id": q["id"],
            "text": q["query"],
            "label": "sensitive",
            "difficulty": "easy",
            "category": q.get("category", ""),
            "private_params": q.get("private_params", []),
            "exploitable_by": q.get("exploitable_by", []),
            "estimated_damage_usd": q.get("estimated_damage_usd", ""),
            "source": q.get("source_realism", "synthetic"),
            "origin": "real_queries.json",
        })
    for q in data.get("non_sensitive_queries", []):
        entries.append({
            "id": q["id"],
            "text": q["query"],
            "label": "non_sensitive",
            "difficulty": "easy",
            "category": "generic_knowledge",
            "private_params": [],
            "exploitable_by": [],
            "estimated_damage_usd": "",
            "source": q.get("source", "synthetic"),
            "origin": "real_queries.json",
        })
    return entries


def load_dataset_py():
    entries = []
    for i, q in enumerate(SENSITIVE_QUERIES):
        entries.append({
            "id": f"DS{i+1:03d}",
            "text": q,
            "label": "sensitive",
            "difficulty": "easy",
            "category": classify_domain(q),
            "private_params": [],  # not labeled in dataset.py
            "exploitable_by": [],
            "estimated_damage_usd": "",
            "source": "synthetic",
            "origin": "dataset.py",
        })
    for i, q in enumerate(NON_SENSITIVE_QUERIES):
        entries.append({
            "id": f"DN{i+1:03d}",
            "text": q,
            "label": "non_sensitive",
            "difficulty": "easy",
            "category": "generic_knowledge",
            "private_params": [],
            "exploitable_by": [],
            "estimated_damage_usd": "",
            "source": "synthetic",
            "origin": "dataset.py",
        })
    return entries


# ─────────────────────────────────────────────
# Borderline cases: queries that are AMBIGUOUS
# ─────────────────────────────────────────────

BORDERLINE_QUERIES = [
    # Imply position without stating params
    {
        "text": "What's a good health factor to maintain on Aave?",
        "label": "borderline",
        "reason": "Implies the user HAS an Aave position, but no params stated",
        "category": "lending",
        "difficulty": "hard",
    },
    {
        "text": "Is Eigenlayer restaking worth the risk right now?",
        "label": "borderline",
        "reason": "Implies the user is considering restaking, reveals interest direction",
        "category": "staking",
        "difficulty": "hard",
    },
    {
        "text": "How do I check my liquidation price on Aave?",
        "label": "borderline",
        "reason": "'My liquidation price' implies active position, but no params",
        "category": "lending",
        "difficulty": "hard",
    },
    {
        "text": "Should I be worried about my Curve pool position with the depeg?",
        "label": "borderline",
        "reason": "'My Curve pool position' + 'worried' implies at-risk position",
        "category": "dex",
        "difficulty": "hard",
    },
    {
        "text": "What's the fastest way to exit a leveraged position on dYdX?",
        "label": "borderline",
        "reason": "Urgency ('fastest') implies distress; 'exit' reveals direction",
        "category": "derivatives",
        "difficulty": "hard",
    },
    {
        "text": "Can I use my stETH as collateral somewhere to get a loan?",
        "label": "borderline",
        "reason": "Reveals asset type (stETH) and intent (borrow against it)",
        "category": "lending",
        "difficulty": "medium",
    },
    {
        "text": "Are Aave V3 interest rates expected to drop soon?",
        "label": "borderline",
        "reason": "Could be general curiosity or rate-sensitive borrower",
        "category": "lending",
        "difficulty": "hard",
    },
    {
        "text": "What happens if ETH drops another 20% from here?",
        "label": "borderline",
        "reason": "'From here' implies current position exposure; '20%' is a scenario",
        "category": "lending",
        "difficulty": "medium",
    },
    {
        "text": "Is it safe to leave funds in Compound V3 after the governance vote?",
        "label": "borderline",
        "reason": "'My funds' + specific protocol + specific event reveals exposure",
        "category": "lending",
        "difficulty": "hard",
    },
    {
        "text": "How much gas would it cost to close all my DeFi positions?",
        "label": "borderline",
        "reason": "'All my DeFi positions' implies multiple positions, urgency to close",
        "category": "dex",
        "difficulty": "medium",
    },
    {
        "text": "What's the best DEX for large stablecoin swaps right now?",
        "label": "borderline",
        "reason": "'Large' implies whale-sized trade, 'right now' implies urgency",
        "category": "dex",
        "difficulty": "medium",
    },
    {
        "text": "How long does Lido unstaking take these days?",
        "label": "borderline",
        "reason": "Implies user wants to unstake from Lido — reveals position + intent",
        "category": "staking",
        "difficulty": "medium",
    },
    {
        "text": "Can I hedge my ETH exposure with on-chain options?",
        "label": "borderline",
        "reason": "'My ETH exposure' reveals asset, 'hedge' reveals strategy direction",
        "category": "derivatives",
        "difficulty": "medium",
    },
    {
        "text": "What are the withdrawal limits on Across bridge?",
        "label": "borderline",
        "reason": "Could be general research or planning a specific large transfer",
        "category": "bridges",
        "difficulty": "hard",
    },
    {
        "text": "Is it a good time to add liquidity to the ETH/USDC pool on Uniswap?",
        "label": "borderline",
        "reason": "Reveals intent to LP in a specific pair — actionable by front-runner",
        "category": "dex",
        "difficulty": "medium",
    },
    # Queries that LOOK sensitive but aren't (should be classified non_sensitive)
    {
        "text": "How much did jaredfromsubway.eth make from sandwich attacks?",
        "label": "non_sensitive",
        "reason": "References specific amounts but about public on-chain data, not user's position",
        "category": "generic_knowledge",
        "difficulty": "medium",
    },
    {
        "text": "What was the largest liquidation on Aave V3 last month?",
        "label": "non_sensitive",
        "reason": "Asks about historical public data, not user's position",
        "category": "generic_knowledge",
        "difficulty": "medium",
    },
    {
        "text": "How much ETH is currently staked in the Beacon Chain?",
        "label": "non_sensitive",
        "reason": "Public network statistic, reveals nothing about user",
        "category": "generic_knowledge",
        "difficulty": "medium",
    },
    {
        "text": "If someone had 1,000 ETH on Aave, what would their liquidation threshold be?",
        "label": "borderline",
        "reason": "'If someone had' is hypothetical framing but may be the user's actual position",
        "category": "lending",
        "difficulty": "hard",
    },
    {
        "text": "Hypothetically, what's the MEV profit from front-running a $500K swap?",
        "label": "borderline",
        "reason": "'Hypothetically' may mask a real planned trade",
        "category": "dex",
        "difficulty": "hard",
    },
    # Real-world-style queries (phrasing sourced from public DeFi forums)
    {
        "text": "gm, my HF is getting kinda low, should I be worried or just wait it out?",
        "label": "sensitive",
        "reason": "Informal phrasing typical of Discord/Telegram; reveals position concern",
        "category": "lending",
        "difficulty": "medium",
        "source": "Reddit r/defi style",
    },
    {
        "text": "anyone know if there's a way to swap a large amount of USDC to ETH without getting sandwiched?",
        "label": "borderline",
        "reason": "'Large amount' implies whale trade; asks about execution strategy",
        "category": "dex",
        "difficulty": "medium",
        "source": "Reddit r/defi style",
    },
    {
        "text": "thinking about going long on ETH with leverage, what protocol has the best rates?",
        "label": "borderline",
        "reason": "Reveals intent (long ETH, leveraged) but no specific params",
        "category": "derivatives",
        "difficulty": "medium",
        "source": "Reddit r/defi style",
    },
    {
        "text": "just got liquidated on my maker vault, how do I prevent this next time?",
        "label": "sensitive",
        "reason": "'Just got liquidated' + 'my maker vault' reveals recent loss event",
        "category": "lending",
        "difficulty": "easy",
        "source": "Reddit r/makerdao style",
    },
    {
        "text": "is it worth migrating from aave v2 to v3 or should i just close everything?",
        "label": "borderline",
        "reason": "Reveals active V2 position and intent to migrate or close",
        "category": "lending",
        "difficulty": "medium",
        "source": "Aave governance forum style",
    },
    {
        "text": "whats the deal with eigenlayer points, are they actually worth restaking for?",
        "label": "non_sensitive",
        "reason": "General question about incentive mechanism, no position implied",
        "category": "generic_knowledge",
        "difficulty": "medium",
        "source": "Reddit r/ethereum style",
    },
    {
        "text": "I keep hearing about people getting rekt by IL on uni v3, how bad is it really?",
        "label": "non_sensitive",
        "reason": "Asking about others' experiences, not own position",
        "category": "generic_knowledge",
        "difficulty": "medium",
        "source": "Reddit r/defi style",
    },
    {
        "text": "my bags are heavy, should I DCA out or hold? mostly ETH and some alts",
        "label": "sensitive",
        "reason": "Reveals portfolio composition (ETH + alts) and emotional state (heavy bags)",
        "category": "dex",
        "difficulty": "medium",
        "source": "Crypto Twitter style",
    },
    {
        "text": "ser how do I get the best yield on my stables without degen risk?",
        "label": "borderline",
        "reason": "Reveals asset type (stablecoins) and risk preference, but no amounts",
        "category": "aggregators",
        "difficulty": "medium",
        "source": "DeFi Discord style",
    },
    {
        "text": "need help figuring out how to report my defi gains for taxes, used like 10 protocols this year",
        "label": "borderline",
        "reason": "Reveals multi-protocol activity and gains (profitable), but no amounts",
        "category": "governance",
        "difficulty": "hard",
        "source": "Reddit r/CryptoTax style",
    },
]


# ─────────────────────────────────────────────
# Real forum-sourced queries (from public DeFi forums)
# Source: Aave governance forum, Aave FAQ, Uniswap support/blog, ethresear.ch
# These preserve actual user phrasings from public posts.
# ─────────────────────────────────────────────

FORUM_QUERIES = [
    # Aave governance forum — real user posts (governance.aave.com)
    {"text": "I've been trying to find a decent Aave Liquidation Calculator based on manually editable variables",
     "label": "borderline", "source": "Aave governance forum", "category": "lending",
     "reason": "Implies user has a position and wants to model liquidation scenarios"},
    {"text": "What % draw down when you will get liquidated at HF 1.0?",
     "label": "borderline", "source": "Aave governance forum", "category": "lending",
     "reason": "Asking about personal liquidation threshold without stating params"},
    {"text": "What would my HF be if the market drew down by X%?",
     "label": "sensitive", "source": "Aave governance forum", "category": "lending",
     "reason": "'my HF' reveals active position"},
    {"text": "I'm worried a 3rd party tool might have incorrect data such as when assets might change liquidation thresholds",
     "label": "borderline", "source": "Aave governance forum", "category": "lending",
     "reason": "Implies reliance on tools for position management"},
    {"text": "Would still be super useful to have a way to test future HF based on a wider market drawdown by different percentages",
     "label": "non_sensitive", "source": "Aave governance forum", "category": "generic_knowledge",
     "reason": "Feature request, not about personal position"},
    {"text": "Wanted to borrow an extra amount, trying to find out what my new liquidation price would be, was very hard",
     "label": "sensitive", "source": "Aave governance forum", "category": "lending",
     "reason": "'my new liquidation price' + 'borrow an extra amount' reveals intent to increase leverage"},
    {"text": "I noticed that part of my position was liquidated, although the price of ETH never fell enough to reach a critical health factor",
     "label": "sensitive", "source": "Aave governance forum (translated from Spanish)", "category": "lending",
     "reason": "Reveals liquidation event on personal position"},
    {"text": "Is there any way to just type in a specific address and check the health factor?",
     "label": "non_sensitive", "source": "Aave governance forum", "category": "generic_knowledge",
     "reason": "Tool question, could be about any address"},
    {"text": "I'm doing an analysis on a sample of 10,000 users and I need their historical health factors at the block level",
     "label": "non_sensitive", "source": "Aave governance forum (academic researcher)", "category": "generic_knowledge",
     "reason": "Academic research, not personal position"},

    # Aave FAQ — questions real users commonly ask (aave.com/faq)
    {"text": "What is a good Health Factor to maintain?",
     "label": "borderline", "source": "Aave FAQ", "category": "lending",
     "reason": "Implies user has or is planning a borrow position"},
    {"text": "What is my liquidation price?",
     "label": "sensitive", "source": "Aave FAQ", "category": "lending",
     "reason": "'my liquidation price' directly implies personal position"},
    {"text": "How can I avoid getting liquidated?",
     "label": "borderline", "source": "Aave FAQ", "category": "lending",
     "reason": "Implies current concern about liquidation risk"},
    {"text": "How much can I borrow?",
     "label": "borderline", "source": "Aave FAQ", "category": "lending",
     "reason": "Implies intent to borrow, reveals interest in leverage"},
    {"text": "Why would I borrow instead of selling my assets?",
     "label": "borderline", "source": "Aave FAQ", "category": "lending",
     "reason": "'my assets' implies holdings; considering borrow vs sell reveals strategy"},
    {"text": "How do I repay my borrow position?",
     "label": "sensitive", "source": "Aave FAQ", "category": "lending",
     "reason": "'my borrow position' confirms active debt"},
    {"text": "Can I opt-out of my asset being used as a collateral?",
     "label": "sensitive", "source": "Aave FAQ", "category": "lending",
     "reason": "'my asset' + 'collateral' confirms active supply position"},
    {"text": "How much would I pay in interest?",
     "label": "borderline", "source": "Aave FAQ", "category": "lending",
     "reason": "Implies active or planned borrow"},
    {"text": "What is the cooldown period for unstaking?",
     "label": "borderline", "source": "Aave FAQ", "category": "staking",
     "reason": "Implies intent to unstake — reveals staking position"},
    {"text": "What is the risk of staking?",
     "label": "non_sensitive", "source": "Aave FAQ", "category": "generic_knowledge",
     "reason": "General risk question, no personal info"},
    {"text": "Is it possible to use Flash Loans without coding?",
     "label": "non_sensitive", "source": "Aave FAQ", "category": "generic_knowledge",
     "reason": "General capability question"},

    # Uniswap support/blog — real user issues (blog.uniswap.org, support.uniswap.org)
    {"text": "My swap keeps failing and I don't know why, I've tried increasing slippage to 5%",
     "label": "borderline", "source": "Uniswap support pattern", "category": "dex",
     "reason": "Reveals active trading attempt; '5%' is a parameter"},
    {"text": "I got sandwiched on my last swap and lost like $200, how do I prevent this?",
     "label": "sensitive", "source": "Uniswap support pattern", "category": "dex",
     "reason": "Reveals loss amount ($200) and that user was sandwich attacked"},
    {"text": "Why did my transaction fail? It said 'insufficient output amount'",
     "label": "borderline", "source": "Uniswap support pattern", "category": "dex",
     "reason": "Reveals failed transaction, could be tracked on-chain"},
    {"text": "How do I set slippage tolerance to avoid getting front-run on large swaps?",
     "label": "borderline", "source": "Uniswap blog reader", "category": "dex",
     "reason": "'large swaps' implies whale-sized trades"},
    {"text": "Is UniswapX safer than regular swaps for avoiding MEV?",
     "label": "non_sensitive", "source": "Uniswap blog reader", "category": "generic_knowledge",
     "reason": "General comparison question"},

    # General DeFi forum patterns — synthesized from observed community discussions
    {"text": "has anyone bridged large amounts through wormhole recently? is it safe after the hack?",
     "label": "borderline", "source": "DeFi community pattern", "category": "bridges",
     "reason": "'large amounts' + specific bridge implies planned large transfer"},
    {"text": "trying to figure out if I should move my LP from v2 to v3, any calculator for IL comparison?",
     "label": "sensitive", "source": "DeFi community pattern", "category": "dex",
     "reason": "'my LP' reveals active LP position; considering migration reveals strategy"},
    {"text": "staking rewards seem way lower than advertised, is the APY shown pre or post fees?",
     "label": "borderline", "source": "DeFi community pattern", "category": "staking",
     "reason": "Implies active staking position with disappointment about returns"},
    {"text": "how the hell do I claim my airdrop tokens without getting scammed?",
     "label": "borderline", "source": "DeFi community pattern", "category": "governance",
     "reason": "Reveals pending airdrop claim — specific timing, potential value"},
    {"text": "any good dashboards to track all my defi positions across chains?",
     "label": "sensitive", "source": "DeFi community pattern", "category": "dex",
     "reason": "'all my defi positions across chains' reveals multi-chain, multi-protocol exposure"},
    {"text": "is it better to provide liquidity on polygon or arbitrum for ETH/USDC?",
     "label": "borderline", "source": "DeFi community pattern", "category": "dex",
     "reason": "Reveals intent to LP in a specific pair across L2s"},
    {"text": "what's the minimum amount worth providing liquidity for after gas fees?",
     "label": "borderline", "source": "DeFi community pattern", "category": "dex",
     "reason": "Implies small position — reveals approximate portfolio size"},
    {"text": "can someone explain the difference between isolated and cross margin on dydx?",
     "label": "non_sensitive", "source": "DeFi community pattern", "category": "generic_knowledge",
     "reason": "Pure educational question"},
    {"text": "I keep getting 'price impact too high' when trying to swap on a new token, what does that mean?",
     "label": "borderline", "source": "DeFi community pattern", "category": "dex",
     "reason": "Reveals trading activity on low-liquidity tokens"},
    {"text": "are there any protocols that let you earn yield on your NFTs without selling them?",
     "label": "borderline", "source": "DeFi community pattern", "category": "lending",
     "reason": "Reveals NFT holdings and desire for yield"},
    {"text": "how do I check if a token contract is safe before swapping?",
     "label": "non_sensitive", "source": "DeFi community pattern", "category": "generic_knowledge",
     "reason": "General security question"},
    {"text": "my metamask is showing a different balance than etherscan, which one is right?",
     "label": "borderline", "source": "DeFi community pattern", "category": "dex",
     "reason": "Reveals wallet discrepancy — potential issue with funds"},
    {"text": "thinking about using a flash loan to rebalance my curve pool position, is this worth the gas?",
     "label": "sensitive", "source": "DeFi community pattern", "category": "dex",
     "reason": "'my curve pool position' + flash loan intent reveals specific strategy"},
    {"text": "what happens to my staked ETH if a validator gets slashed?",
     "label": "borderline", "source": "DeFi community pattern", "category": "staking",
     "reason": "'my staked ETH' implies staking position; worried about slashing"},
    {"text": "is there a way to automate my yield farming so I don't have to claim and restake manually every week?",
     "label": "sensitive", "source": "DeFi community pattern", "category": "aggregators",
     "reason": "Reveals active yield farming, manual workflow, weekly schedule"},
    {"text": "why did my borrow rate on compound suddenly jump from 3% to 12%?",
     "label": "sensitive", "source": "DeFi community pattern", "category": "lending",
     "reason": "'my borrow rate' + specific percentages reveals active debt position"},
    {"text": "anyone else notice aave governance voting is dominated by like 5 whales?",
     "label": "non_sensitive", "source": "DeFi community pattern", "category": "generic_knowledge",
     "reason": "Observation about protocol governance, not personal"},
    {"text": "how do gas fees work when you're doing multiple transactions in one bundle?",
     "label": "non_sensitive", "source": "DeFi community pattern", "category": "generic_knowledge",
     "reason": "General technical question"},
    {"text": "is it still worth running an ethereum validator at home or is solo staking dead?",
     "label": "borderline", "source": "DeFi community pattern", "category": "staking",
     "reason": "Implies interest in or current solo staking setup"},
    {"text": "just discovered my LP position has been out of range for 2 weeks, RIP fees",
     "label": "sensitive", "source": "DeFi community pattern", "category": "dex",
     "reason": "'my LP position' + 'out of range for 2 weeks' reveals specific position state"},
    {"text": "how do I report defi income if I used like 20 different protocols across 5 chains?",
     "label": "sensitive", "source": "DeFi community pattern", "category": "governance",
     "reason": "Reveals extensive multi-chain DeFi activity and taxable income"},
]


def build_borderline():
    entries = []
    for i, q in enumerate(BORDERLINE_QUERIES):
        entries.append({
            "id": f"BL{i+1:03d}",
            "text": q["text"],
            "label": q["label"],
            "difficulty": q.get("difficulty", "medium"),
            "category": q.get("category", classify_domain(q["text"])),
            "private_params": [],
            "exploitable_by": [],
            "estimated_damage_usd": "",
            "source": q.get("source", "synthetic"),
            "reason": q.get("reason", ""),
            "origin": "borderline",
        })
    return entries


def build_forum():
    entries = []
    for i, q in enumerate(FORUM_QUERIES):
        entries.append({
            "id": f"FQ{i+1:03d}",
            "text": q["text"],
            "label": q["label"],
            "difficulty": q.get("difficulty", "medium"),
            "category": q.get("category", classify_domain(q["text"])),
            "private_params": [],
            "exploitable_by": [],
            "estimated_damage_usd": "",
            "source": q.get("source", "DeFi forum"),
            "reason": q.get("reason", ""),
            "origin": "forum_sourced",
        })
    return entries


def deduplicate(entries):
    """Remove duplicate queries by text (case-insensitive)."""
    seen = set()
    unique = []
    for e in entries:
        key = e["text"].lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(e)
    return unique


def main():
    print("Building unified benchmark dataset...")

    all_entries = []

    # Source 1: real_queries.json (richest metadata)
    rq = load_real_queries()
    print(f"  real_queries.json: {len(rq)} entries")
    all_entries.extend(rq)

    # Source 2: dataset.py
    dp = load_dataset_py()
    print(f"  dataset.py:        {len(dp)} entries")
    all_entries.extend(dp)

    # Source 3: borderline cases
    bl = build_borderline()
    print(f"  borderline:        {len(bl)} entries")
    all_entries.extend(bl)

    # Source 4: real forum-sourced queries
    forum = build_forum()
    print(f"  forum-sourced:     {len(forum)} entries")
    all_entries.extend(forum)

    # Source 5: WildChat-extracted queries (if available)
    # Note: WildChat-4.8M (3.2M real ChatGPT conversations) yielded only 14 DeFi queries
    # in 200K scanned — a 0.007% hit rate. Real DeFi position queries are inherently private;
    # users don't share them publicly. This scarcity is itself evidence for the paper's thesis.
    wildchat_path = Path(__file__).parent / "wildchat_defi_queries.jsonl"
    if wildchat_path.exists():
        with open(wildchat_path) as f:
            wc = [json.loads(line) for line in f]
        for i, entry in enumerate(wc):
            entry["id"] = f"WC{i+1:03d}"
        print(f"  wildchat:          {len(wc)} entries")
        all_entries.extend(wc)
    else:
        print(f"  wildchat:          (optional — run data/extract_wildchat_defi.py)")

    # Deduplicate
    before = len(all_entries)
    all_entries = deduplicate(all_entries)
    print(f"  Deduplicated: {before} → {len(all_entries)}")

    # Stats
    from collections import Counter
    labels = Counter(e["label"] for e in all_entries)
    difficulties = Counter(e["difficulty"] for e in all_entries)
    origins = Counter(e["origin"] for e in all_entries)
    categories = Counter(e["category"] for e in all_entries)

    print(f"\n=== Dataset Summary ===")
    print(f"Total: {len(all_entries)} queries")
    print(f"Labels:       {dict(labels)}")
    print(f"Difficulty:   {dict(difficulties)}")
    print(f"Origins:      {dict(origins)}")
    print(f"Categories:   {dict(categories)}")

    # Export to JSONL
    with open(OUT, "w") as f:
        for e in all_entries:
            f.write(json.dumps(e) + "\n")
    print(f"\nSaved to {OUT}")
    print(f"Format: JSONL — one JSON object per line")
    print(f"Load with: [json.loads(line) for line in open('benchmark_dataset.jsonl')]")


if __name__ == "__main__":
    main()
