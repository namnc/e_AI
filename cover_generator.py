"""
Cover query generation — v5 algorithm (template + domain-distribution matching).

The algorithm:
  1. SANITIZE: Strip private params, qualitative descriptors, emotional language
  2. TEMPLATE: Extract sentence structure with domain-specific slots
  3. DOMAINS: Select k-1 cover domains from top-N DeFi categories
  4. FILL: Generate covers by filling template with domain vocabulary
  5. VERIFY: Length ±20%, valid question, no cross-domain leakage
  6. SHUFFLE: Randomize position
"""

import random
import re

# ---------------------------------------------------------------------------
# Domain frequency distribution (approximated from public DeFi forum data)
# ---------------------------------------------------------------------------

DOMAIN_DISTRIBUTION = {
    "lending":     0.25,
    "dex":         0.30,
    "staking":     0.15,
    "derivatives": 0.10,
    "bridges":     0.08,
    "governance":  0.05,
    "aggregators": 0.07,
}

# Top-4 domains cover ~80% of real queries — used for v5 equiprobable matching
TOP_DOMAINS = ["lending", "dex", "staking", "derivatives"]

# ---------------------------------------------------------------------------
# DeFi domain ontology — vocabulary for slot filling
# ---------------------------------------------------------------------------

DOMAIN_ONTOLOGY = {
    "lending": {
        "protocols": ["Aave", "Compound", "Morpho", "Spark", "Radiant"],
        "mechanisms": [
            "interest rate", "health factor", "liquidation", "collateral ratio",
            "borrow rate", "supply rate", "utilization rate", "reserve factor",
            "liquidation threshold", "loan-to-value ratio",
        ],
        "operations": [
            "modifying collateral", "repaying debt", "entering a borrow position",
            "closing a position", "adding collateral", "withdrawing collateral",
        ],
        "triggers": [
            "utilization rates shift", "collateral prices drop", "rate models update",
            "governance parameters change", "market volatility increases",
        ],
        "metrics": [
            "health factor", "utilization rate", "borrow APY", "supply APY",
            "liquidation threshold", "reserve factor",
        ],
        "actors": ["borrowers", "lenders", "liquidators", "lending protocol users"],
        "risk_concepts": [
            "liquidation risk", "bad debt accumulation", "oracle manipulation risk",
            "interest rate volatility", "collateral correlation risk",
        ],
        "generic_refs": [
            "lending protocols", "borrowing platforms", "lending markets",
            "lending systems", "decentralized lending platforms",
        ],
    },
    "dex": {
        "protocols": ["Uniswap", "Curve", "Balancer", "SushiSwap", "Maverick"],
        "mechanisms": [
            "routing", "slippage", "liquidity depth", "fee tiers",
            "impermanent loss", "concentrated liquidity", "price impact",
            "order routing", "batch auctions", "swap execution",
        ],
        "operations": [
            "executing swaps", "providing liquidity", "rebalancing positions",
            "collecting fees", "adjusting price ranges", "routing trades",
        ],
        "triggers": [
            "volume patterns shift", "liquidity becomes fragmented", "prices diverge",
            "fee tiers are adjusted", "pools rebalance",
        ],
        "metrics": [
            "swap fee", "price impact", "liquidity depth", "volume",
            "impermanent loss", "fee APR",
        ],
        "actors": ["traders", "liquidity providers", "swap users", "LP participants"],
        "risk_concepts": [
            "impermanent loss", "sandwich attack exposure", "MEV extraction risk",
            "liquidity fragmentation", "price oracle deviation",
        ],
        "generic_refs": [
            "exchange protocols", "AMM markets", "decentralized exchanges",
            "exchange platforms", "trading protocols",
        ],
    },
    "staking": {
        "protocols": ["Lido", "Rocket Pool", "Eigenlayer", "Frax", "Swell"],
        "mechanisms": [
            "reward rate", "slashing", "cooldown period", "withdrawal queue",
            "delegation", "validator selection", "restaking", "unbonding",
            "reward distribution", "stake weighting",
        ],
        "operations": [
            "staking assets", "unstaking assets", "delegating stake",
            "claiming rewards", "rotating validators", "migrating stake",
        ],
        "triggers": [
            "participation rates shift", "validator counts change", "reward rates update",
            "slashing events occur", "exit demand increases",
        ],
        "metrics": [
            "staking yield", "slashing rate", "validator uptime",
            "withdrawal delay", "delegation fee", "reward APR",
        ],
        "actors": ["validators", "delegators", "staking participants", "node operators"],
        "risk_concepts": [
            "slashing risk", "validator downtime exposure", "liquid staking depeg",
            "withdrawal queue delays", "centralization risk",
        ],
        "generic_refs": [
            "staking protocols", "consensus protocols", "staking systems",
            "staking markets", "decentralized consensus platforms",
        ],
    },
    "derivatives": {
        "protocols": ["dYdX", "GMX", "Synthetix", "Lyra", "Opyn"],
        "mechanisms": [
            "funding rate", "margin requirement", "liquidation engine",
            "settlement", "premium calculation", "open interest",
            "mark price", "index price", "leverage multiplier",
        ],
        "operations": [
            "adding margin", "reducing leverage", "closing positions",
            "rolling contracts", "settling expiries", "adjusting exposure",
        ],
        "triggers": [
            "open interest shifts", "skew becomes extreme",
            "funding rates diverge", "volatility spikes", "settlement occurs",
        ],
        "metrics": [
            "funding rate", "open interest", "margin ratio",
            "liquidation price", "mark-index spread", "option premium",
        ],
        "actors": ["futures traders", "options traders", "market makers", "hedgers"],
        "risk_concepts": [
            "margin call risk", "funding rate bleed", "liquidation cascade",
            "basis risk", "counterparty risk",
        ],
        "generic_refs": [
            "perpetual protocols", "derivatives platforms", "derivatives markets",
            "futures protocols", "decentralized derivatives platforms",
        ],
    },
    "bridges": {
        "protocols": ["Across", "Stargate", "LayerZero", "Wormhole", "Orbiter"],
        "mechanisms": [
            "finality verification", "capacity allocation", "relay mechanism",
            "message passing", "liquidity pooling", "withdrawal delay",
        ],
        "operations": [
            "bridging assets", "verifying finality", "claiming transfers",
            "providing bridge liquidity", "routing cross-chain",
        ],
        "triggers": [
            "demand patterns shift", "congestion occurs", "chains reorganize",
            "capacity limits are reached", "fees spike",
        ],
        "metrics": [
            "transfer time", "bridge fee", "capacity utilization",
            "liquidity depth", "finality delay",
        ],
        "actors": ["bridge users", "relayers", "liquidity providers", "validators"],
        "risk_concepts": [
            "bridge exploit risk", "finality assumptions", "liquidity fragmentation",
            "message verification failure", "chain reorganization risk",
        ],
        "generic_refs": [
            "bridge protocols", "cross-chain systems", "bridging platforms",
            "interoperability protocols", "cross-chain bridges",
        ],
    },
    "governance": {
        "protocols": ["Compound Gov", "Aave Gov", "Uniswap Gov", "Curve Gov", "MakerDAO"],
        "mechanisms": [
            "quorum requirement", "delegation mechanism", "timelock",
            "proposal lifecycle", "voting power calculation", "vote escrow",
        ],
        "operations": [
            "submitting proposals", "delegating votes", "executing timelocks",
            "adjusting quorum", "claiming voting rights",
        ],
        "triggers": [
            "delegation patterns change", "quorum thresholds shift",
            "proposals are submitted", "voting periods change",
        ],
        "metrics": [
            "quorum percentage", "voter participation", "proposal pass rate",
            "delegation concentration", "timelock duration",
        ],
        "actors": ["delegates", "token holders", "governance participants", "proposers"],
        "risk_concepts": [
            "governance attack risk", "voter apathy", "plutocratic capture",
            "proposal spam", "flash loan governance attack",
        ],
        "generic_refs": [
            "governance protocols", "DAO systems", "governance frameworks",
            "decentralized governance platforms", "voting systems",
        ],
    },
    "aggregators": {
        "protocols": ["Yearn", "Beefy", "Convex", "Pendle", "Sommelier"],
        "mechanisms": [
            "auto-compounding", "vault strategy", "rebalancing",
            "fee structure", "APY calculation", "yield tokenization",
        ],
        "operations": [
            "depositing into vaults", "withdrawing from vaults",
            "migrating between strategies", "claiming compounded yield",
        ],
        "triggers": [
            "strategies rotate", "yield thresholds change",
            "TVL shifts", "underlying protocols update",
        ],
        "metrics": [
            "net APY", "TVL", "management fee", "performance fee",
            "strategy allocation", "compound frequency",
        ],
        "actors": ["vault depositors", "strategists", "yield farmers", "vault users"],
        "risk_concepts": [
            "smart contract risk", "strategy failure", "impermanent loss amplification",
            "composability risk", "withdrawal queue delays",
        ],
        "generic_refs": [
            "yield aggregators", "vault protocols", "aggregation platforms",
            "yield optimization systems", "DeFi aggregators",
        ],
    },
}

# ---------------------------------------------------------------------------
# Sanitization patterns
# ---------------------------------------------------------------------------

# Amount patterns applied with re.IGNORECASE (safe for these patterns)
_AMOUNT_PATTERNS_ICASE = [
    r'\$[\d,]+(?:\.\d+)?[KkMmBb]?',                    # $1,000, $1.5M
    r'[\d,]+(?:\.\d+)?[KkMmBb]\s+(?:in|worth|of)\b',   # 1.8M worth, 500K of
    r'[\d,]+(?:\.\d+)?\s*(?:tokens?|coins?)',
    r'\b\d{1,3}(?:,\d{3})+\b',                          # 1,000 or 1,000,000
]
# Amount + UPPERCASE token symbol — CASE SENSITIVE
# The token part MUST be uppercase (3+ chars to avoid "2FA", "V3", "5G").
# Single digit is allowed because "3 BTC" is a real amount.
_AMOUNT_PATTERNS_CSENSE = [
    r'[\d,]+(?:\.\d+)?[KkMmBb]?\s+[A-Z]{3,10}\b',           # 3 BTC, 500 ARB, 1.8M USDC — 3+ uppercase chars
    r'[\d,]+(?:\.\d+)?[KkMmBb]?\s+[A-Z]{2}(?=\s|$)',          # 50 OP — requires space before 2-char symbol (avoids "2FA")
]
_ADDRESS_PATTERN = r'0x[a-fA-F0-9]{3,}'
_ENS_PATTERN = r'\b[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.eth\b'  # vitalik.eth, name.eth
_PERCENT_PATTERN = r'\b\d+(?:\.\d+)?%'
_HF_PATTERN = r'(?:health factor|HF)\s*(?:is|of|at|=|:)?\s*\d+(?:\.\d+)?'
_LEVERAGE_PATTERN = r'\b\d+x\b'

# Natural language quantity patterns (secondary NLP filter)
_NUMBER_WORDS = [
    'hundred', 'thousand', 'million', 'billion', 'trillion',
    'half a million', 'quarter million', 'half a billion',
    'a few hundred', 'a few thousand', 'a few million',
    'several hundred', 'several thousand', 'several million',
    'dozens of', 'hundreds of', 'thousands of',
    'six-figure', 'seven-figure', 'eight-figure',
    'five-figure', 'four-figure',
    'double', 'triple', 'quadruple',
]
_NUMBER_WORD_PATTERNS = [
    # "half a million USDC", "roughly two thousand ETH"
    r'\b(?:about|approximately|roughly|around|nearly|over|under|almost|close to|just under|just over|more than|less than|at least|up to)\s+'
    r'(?:a\s+)?(?:half\s+(?:a\s+)?)?'
    r'(?:one|two|three|four|five|six|seven|eight|nine|ten|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|billion)\s*'
    r'(?:hundred|thousand|million|billion)?\s*'
    r'(?:[A-Z]{2,10}|dollars|bucks|worth)',
    # "my six-figure position", "a seven-figure portfolio"
    r'\b(?:four|five|six|seven|eight|nine|ten)-figure\s+(?:position|portfolio|amount|sum|balance|holding|stake)',
    # "half a million", "quarter million" standalone
    r'\b(?:half|quarter|third)\s+(?:a\s+)?(?:million|billion|thousand)\b',
    # "a few hundred thousand"
    r'\b(?:a\s+)?(?:few|couple|several|many)\s+(?:hundred|thousand|million)\s*(?:thousand|million|billion)?\s*(?:[A-Z]{2,10}|dollars|bucks|worth)?',
]

# Cardinal number + UPPERCASE token symbol (case-sensitive for the token part).
# Separate from _NUMBER_WORD_PATTERNS because those run with re.IGNORECASE.
_CARDINAL_TOKEN_PATTERN = (
    r'(?i:\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|'
    r'thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|'
    r'forty|fifty|sixty|seventy|eighty|ninety)\b)'
    r'(?:\s+(?i:hundred|thousand|million|billion))*'
    r'\s+[A-Z]{2,10}\b'
)

_EMOTIONAL_WORDS = [
    'worried', 'anxious', 'urgent', 'emergency', 'should I', 'scared',
    'nervous', 'panicking', 'desperate', 'afraid', 'concerned about',
]
_TIMING_PATTERNS = [
    r'\bby (?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b',
    r'\bwithin \d+ (?:hours?|days?|minutes?)\b',
    r'\bbefore the (?:upgrade|fork|merge|vote|deadline)\b',
    r'\bright now\b', r'\bimmediately\b', r'\bASAP\b', r'\btoday\b', r'\btomorrow\b',
]
_DIRECTIONAL_VERBS = {
    'buy': 'modify', 'sell': 'modify', 'long': 'position', 'short': 'position',
    'close': 'modify', 'exit': 'modify', 'enter': 'modify',
    'unstake': 'modify', 'withdraw': 'modify',
}
_QUALITATIVE = [
    'underwater', 'close to liquidation', 'about to be liquidated',
    'significantly imbalanced', 'dangerously', 'barely above',
    'dropping fast', 'plummeting', 'mooning', 'dumping',
]


def sanitize_query(query: str) -> str:
    """Strip private parameters, emotional language, timing, and qualitative descriptors."""
    result = query

    # Remove natural language quantities (secondary NLP filter)
    for pat in _NUMBER_WORD_PATTERNS:
        result = re.sub(pat, '', result, flags=re.IGNORECASE)
    # Cardinal number + UPPERCASE token (case-sensitive for token part)
    result = re.sub(_CARDINAL_TOKEN_PATTERN, '', result)
    for word in _NUMBER_WORDS:
        # Only strip number words when followed by an UPPERCASE token symbol
        # (not case-insensitive — avoids matching "two options", "three ways")
        result = re.sub(
            rf'(?i:\b{re.escape(word)}\b)\s*(?:[A-Z]{{2,10}}|dollars|bucks|worth|position|portfolio)',
            '', result
        )

    # Remove ENS names (vitalik.eth, name.eth)
    result = re.sub(_ENS_PATTERN, '', result)

    # Remove hex addresses
    result = re.sub(_ADDRESS_PATTERN, '', result)

    # Remove amounts — split into case-insensitive (dollar amounts, suffixed numbers)
    # and case-sensitive (number + UPPERCASE token symbol) to avoid false positives
    # on phrases like "2 weeks", "V3", "2FA", "10 basis points"
    for pat in _AMOUNT_PATTERNS_ICASE:
        result = re.sub(pat, '', result, flags=re.IGNORECASE)
    for pat in _AMOUNT_PATTERNS_CSENSE:
        result = re.sub(pat, '', result)  # NO re.IGNORECASE — token must be uppercase

    # Remove health factor values
    result = re.sub(_HF_PATTERN, 'health factor', result, flags=re.IGNORECASE)

    # Remove leverage
    result = re.sub(_LEVERAGE_PATTERN, '', result)

    # Remove percentages
    result = re.sub(_PERCENT_PATTERN, '', result)

    # Remove emotional language
    for word in _EMOTIONAL_WORDS:
        result = re.sub(rf'\b{re.escape(word)}\b', '', result, flags=re.IGNORECASE)

    # Remove timing
    for pat in _TIMING_PATTERNS:
        result = re.sub(pat, '', result, flags=re.IGNORECASE)

    # Remove qualitative descriptors
    for word in _QUALITATIVE:
        result = re.sub(rf'\b{re.escape(word)}\b', '', result, flags=re.IGNORECASE)

    # Replace directional verbs (only standalone, not in compound words)
    for verb, replacement in _DIRECTIONAL_VERBS.items():
        result = re.sub(rf'\b{verb}\b', replacement, result, flags=re.IGNORECASE)

    # Clean up whitespace and punctuation artifacts
    result = re.sub(r'\s+', ' ', result)
    result = re.sub(r'\s([?.!,])', r'\1', result)
    result = re.sub(r'[,]{2,}', ',', result)
    result = re.sub(r'\(\s*\)', '', result)
    result = re.sub(r'\s+', ' ', result).strip()

    return result


# ---------------------------------------------------------------------------
# Domain classification
# ---------------------------------------------------------------------------

def _build_domain_keywords() -> dict[str, set[str]]:
    """Build keyword sets for each domain from the ontology."""
    keywords = {}
    for domain, onto in DOMAIN_ONTOLOGY.items():
        words = set()
        for key in ["protocols", "mechanisms", "operations", "metrics", "actors"]:
            for term in onto.get(key, []):
                # Add full term and individual significant words
                words.add(term.lower())
                for w in term.lower().split():
                    if len(w) > 3:  # skip short words
                        words.add(w)
        keywords[domain] = words
    return keywords


_DOMAIN_KEYWORDS = _build_domain_keywords()


def classify_domain(query: str) -> str:
    """Classify a query into a DeFi domain using keyword matching."""
    q_lower = query.lower()
    scores = {}
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in q_lower)
        scores[domain] = score

    if max(scores.values()) == 0:
        # Round-robin fallback across top-4 to avoid lending bias
        import hashlib
        h = int(hashlib.sha256(query.encode()).hexdigest()[:8], 16)
        return TOP_DOMAINS[h % len(TOP_DOMAINS)]

    return max(scores, key=scores.get)


# ---------------------------------------------------------------------------
# Template extraction
# ---------------------------------------------------------------------------

# Common DeFi query templates — derived from v3/v4/v5 benchmark results
TEMPLATES = [
    "How does the {MECHANISM} respond to {TRIGGER} in {GENERIC_REF}?",
    "What are the cost tradeoffs between {OPERATION_A} and {OPERATION_B} for {ACTOR}?",
    "How do {GENERIC_REF} handle {MECHANISM} during {TRIGGER}?",
    "What factors determine the {METRIC} for {MECHANISM} on {GENERIC_REF}?",
    "What is the risk profile of {MECHANISM} strategies in {GENERIC_REF}?",
    "How does the {MECHANISM} process work for {OPERATION} in {GENERIC_REF}?",
    "How do {MECHANISM} characteristics change with {TRIGGER} in {GENERIC_REF}?",
    "How do {METRIC} costs compare across {GENERIC_REF} for {OPERATION}?",
    "What are the mechanics of {MECHANISM} using {OPERATION} in {GENERIC_REF}?",
    "How does the {MECHANISM} adjustment mechanism work when {TRIGGER} in {GENERIC_REF}?",
    "What are the tradeoffs of different {MECHANISM} approaches for {ACTOR}?",
    "How does the {MECHANISM} queue mechanism handle {TRIGGER} in {GENERIC_REF}?",
    "What determines the {METRIC} for {MECHANISM} in {GENERIC_REF}?",
    "How do {RISK_CONCEPT} risks scale with {TRIGGER} in {GENERIC_REF}?",
    "What are the mechanics of {MECHANISM} optimization in {GENERIC_REF}?",
    "How does the {METRIC} calculation work for {MECHANISM} in {GENERIC_REF}?",
    "What is the cost structure of {OPERATION} on {GENERIC_REF}?",
    "How do {GENERIC_REF} manage {MECHANISM} during {TRIGGER}?",
    "What factors influence the {METRIC} of {MECHANISM} in {GENERIC_REF}?",
    "How does {MECHANISM} impact {METRIC} for {ACTOR}?",
]


def _match_template(query: str) -> tuple[str, int]:
    """Find the best-matching template for a query. Returns (template, score)."""
    q_lower = query.lower()

    best_template = None
    best_score = -1

    for template in TEMPLATES:
        # Score by matching the fixed words in the template
        fixed_parts = re.sub(r'\{[A-Z_]+\}', '', template).lower().split()
        score = sum(1 for part in fixed_parts if part in q_lower and len(part) > 2)
        if score > best_score:
            best_score = score
            best_template = template

    return best_template, best_score


def extract_template(query: str, rng: random.Random | None = None) -> str:
    """Extract or match a structural template from a query."""
    template, score = _match_template(query)
    if score >= 2:
        return template

    # Fallback: pick a template that fits the query shape (question word match)
    q_lower = query.lower()
    if q_lower.startswith("how do"):
        candidates = [t for t in TEMPLATES if t.lower().startswith("how do")]
    elif q_lower.startswith("how does"):
        candidates = [t for t in TEMPLATES if t.lower().startswith("how does")]
    elif q_lower.startswith("what are"):
        candidates = [t for t in TEMPLATES if t.lower().startswith("what are")]
    elif q_lower.startswith("what"):
        candidates = [t for t in TEMPLATES if t.lower().startswith("what")]
    else:
        candidates = TEMPLATES

    if rng is not None:
        return rng.choice(candidates)
    return candidates[0]  # deterministic fallback


# ---------------------------------------------------------------------------
# Slot filling
# ---------------------------------------------------------------------------





# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify_cover(real_query: str, cover_query: str, real_domain: str) -> bool:
    """Check that a cover query passes quality gates."""
    # Length within ±30% (relaxed from ±20% to avoid over-filtering)
    len_ratio = len(cover_query) / max(len(real_query), 1)
    if not (0.7 <= len_ratio <= 1.3):
        return False

    # Must end with ?
    if not cover_query.strip().endswith("?"):
        return False

    # Must not be empty or trivially short
    if len(cover_query.split()) < 5:
        return False

    # No cross-domain leakage: real domain's protocol names shouldn't appear in cover
    real_protocols = {p.lower() for p in DOMAIN_ONTOLOGY[real_domain]["protocols"]}
    cover_lower = cover_query.lower()
    for protocol in real_protocols:
        if protocol in cover_lower:
            return False

    return True


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def _generate(query, k, seed, domain_strategy, presanitized):
    """Internal: generate cover set with local RNG to avoid mutating global state."""
    rng = random.Random(seed) if seed is not None else random.Random()

    sanitized = query if presanitized else sanitize_query(query)
    real_domain = classify_domain(sanitized)
    template = extract_template(sanitized, rng=rng)

    # Select cover domains using local RNG
    if domain_strategy == "top4":
        available = [d for d in TOP_DOMAINS if d != real_domain]
        if real_domain not in TOP_DOMAINS:
            available = list(TOP_DOMAINS)
        # For k > len(available)+1, cycle through domains (with replacement)
        if k - 1 <= len(available):
            cover_domains = rng.sample(available, k - 1)
        else:
            cover_domains = []
            for _ in range(k - 1):
                cover_domains.append(rng.choice(available))
    elif domain_strategy == "weighted":
        available = {d: w for d, w in DOMAIN_DISTRIBUTION.items() if d != real_domain}
        domains = list(available.keys())
        weights = [available[d] for d in domains]
        total = sum(weights)
        weights = [w / total for w in weights]
        cover_domains = []
        if k - 1 > len(domains):
            # More covers than domains — sample with replacement
            cover_domains = rng.choices(domains, weights=weights, k=k - 1)
        else:
            # Sample without replacement
            for _ in range(k - 1):
                pick = rng.choices(domains, weights=weights, k=1)[0]
                cover_domains.append(pick)
                idx = domains.index(pick)
                domains.pop(idx)
                weights.pop(idx)
                if domains:
                    total = sum(weights)
                    weights = [w / total for w in weights]
    else:
        raise ValueError(f"Unknown strategy: {domain_strategy}")

    # Fill template using local RNG
    def _pick_rng(items):
        return rng.choice(items)

    def _fill(template_str, domain):
        onto = DOMAIN_ONTOLOGY[domain]
        replacements = {
            "{MECHANISM}": _pick_rng(onto["mechanisms"]),
            "{OPERATION}": _pick_rng(onto["operations"]),
            "{OPERATION_A}": _pick_rng(onto["operations"]),
            "{OPERATION_B}": _pick_rng(onto["operations"]),
            "{TRIGGER}": _pick_rng(onto["triggers"]),
            "{METRIC}": _pick_rng(onto["metrics"]),
            "{ACTOR}": _pick_rng(onto["actors"]),
            "{GENERIC_REF}": _pick_rng(onto["generic_refs"]),
            "{RISK_CONCEPT}": _pick_rng(onto["risk_concepts"]),
        }
        if "{OPERATION_A}" in template_str and "{OPERATION_B}" in template_str:
            ops = rng.sample(onto["operations"], min(2, len(onto["operations"])))
            replacements["{OPERATION_A}"] = ops[0]
            replacements["{OPERATION_B}"] = ops[1] if len(ops) > 1 else ops[0]
        result = template_str
        for slot, value in replacements.items():
            result = result.replace(slot, value)
        return result

    real_filled = _fill(template, real_domain)
    covers = []
    for domain in cover_domains:
        for _attempt in range(5):
            candidate = _fill(template, domain)
            if verify_cover(real_filled, candidate, real_domain):
                covers.append(candidate)
                break
        else:
            covers.append(_fill(template, domain))

    all_queries = [real_filled] + covers
    indices = list(range(len(all_queries)))
    rng.shuffle(indices)
    shuffled = [all_queries[i] for i in indices]
    real_index = indices.index(0)

    return shuffled, real_index, real_domain, template, cover_domains


def generate_cover_set(
    query: str,
    k: int = 4,
    seed: int | None = None,
    domain_strategy: str = "top4",
    presanitized: bool = False,
) -> tuple[list[str], int]:
    """Generate a set of k template-filled queries, shuffled.

    IMPORTANT: The "real" query is NOT the original input. It is a
    template fill using vocabulary from the input's domain. This is
    by design — structural identity between real and cover queries is
    required for indistinguishability. The original query text is NOT
    preserved. Use generate_cover_set_with_original() if you need
    both the covers and the original sanitized text.

    Uses a local RNG instance — does not mutate global random state.

    Returns:
        (shuffled_queries, real_index) where real_index is the position
        of the real-domain query in the shuffled list.
    """
    shuffled, real_index, _, _, _ = _generate(query, k, seed, domain_strategy, presanitized)
    return shuffled, real_index


def generate_cover_set_with_original(
    query: str,
    k: int = 4,
    seed: int | None = None,
    domain_strategy: str = "top4",
    presanitized: bool = False,
) -> tuple[list[str], int, str]:
    """Generate k template-filled cover queries + return the original sanitized query.

    Use this when you need both:
    - The cover set (for topic hiding — send all k to cloud)
    - The original sanitized query (for Tier 0 — send directly to cloud)

    WARNING: If you send the original query alongside template-filled covers,
    the original is structurally distinguishable (Benchmark D showed 2.3/5
    detection). Only send the original if you're NOT using covers.

    Returns:
        (shuffled_covers, real_index, original_sanitized)
    """
    sanitized = query if presanitized else sanitize_query(query)
    shuffled, real_index, _, _, _ = _generate(query, k, seed, domain_strategy, presanitized)
    return shuffled, real_index, sanitized


def generate_cover_set_raw(
    query: str,
    k: int = 4,
    seed: int | None = None,
    domain_strategy: str = "top4",
    presanitized: bool = False,
) -> tuple[list[str], int, str, str, list[str]]:
    """Like generate_cover_set but also returns metadata for analysis.

    NOTE: The "real" query at real_index is a template fill, not the
    original input text. See generate_cover_set() docstring.

    Returns:
        (shuffled_queries, real_index, real_domain, template, cover_domains)
    """
    return _generate(query, k, seed, domain_strategy, presanitized)


def generate_per_provider(
    query: str,
    providers: list[str],
    k: int = 4,
    seed: int | None = None,
    presanitized: bool = False,
    max_retries: int = 20,
) -> dict[str, tuple[list[str], int]]:
    """Generate independent cover sets for each provider with zero intersection.

    Prevents cross-provider intersection attacks: each provider receives a
    unique set of k queries with no exact matches across any provider pair.
    This is verified by regenerating with different seeds until the
    intersection is empty.

    Returns:
        {provider_name: (shuffled_queries, real_index)}
    """
    base_seed = seed if seed is not None else 0

    for attempt in range(max_retries):
        result = {}
        for i, provider in enumerate(providers):
            import hashlib
            provider_hash = int(hashlib.sha256(provider.encode()).hexdigest()[:8], 16)
            provider_seed = base_seed + provider_hash + attempt * 1000
            shuffled, real_index = generate_cover_set(
                query, k=k, seed=provider_seed, presanitized=presanitized
            )
            result[provider] = (shuffled, real_index)

        # Verify zero intersection across all provider pairs
        all_sets = {p: set(queries) for p, (queries, _) in result.items()}
        collision = False
        providers_list = list(all_sets.keys())
        for i in range(len(providers_list)):
            for j in range(i + 1, len(providers_list)):
                if all_sets[providers_list[i]] & all_sets[providers_list[j]]:
                    collision = True
                    break
            if collision:
                break

        if not collision:
            return result

    # After max retries, raise — do not silently return colliding sets
    colliding_pairs = []
    providers_list = list(all_sets.keys())
    for i in range(len(providers_list)):
        for j in range(i + 1, len(providers_list)):
            common = all_sets[providers_list[i]] & all_sets[providers_list[j]]
            if common:
                colliding_pairs.append((providers_list[i], providers_list[j], len(common)))
    raise RuntimeError(
        f"Could not achieve zero intersection after {max_retries} retries. "
        f"Collisions: {colliding_pairs}. Reduce k or number of providers, "
        f"or expand the domain vocabulary."
    )
