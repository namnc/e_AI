"""
Cover query generation — v5 algorithm (template + domain-distribution matching).

The algorithm:
  1. SANITIZE: Strip private params, qualitative descriptors, emotional language
  2. TEMPLATE: Extract sentence structure with domain-specific slots
  3. DOMAINS: Select k-1 cover domains from top-N categories
  4. FILL: Generate covers by filling template with domain vocabulary
  5. VERIFY: Length ±20%, valid question, no cross-domain leakage
  6. SHUFFLE: Randomize position

All domain-specific constants (ontology, patterns, templates) are loaded from
a domain profile (domains/<name>/profile.json). The DeFi profile is loaded
by default for backward compatibility.
"""

import random
import re

from core.profile_loader import get_default_profile

# ---------------------------------------------------------------------------
# Module state — initialized from domain profile
# ---------------------------------------------------------------------------
# These module-level variables are populated by _init_from_profile().
# They exist as module-level vars for backward compatibility with code
# that imports them directly (tests, benchmarks, migration scripts).

DOMAIN_DISTRIBUTION: dict = {}
TOP_DOMAINS: list = []
DOMAIN_ONTOLOGY: dict = {}

_AMOUNT_PATTERNS_ICASE: list = []
_AMOUNT_PATTERNS_CSENSE: list = []
_AMOUNT_KNOWN_TOKEN_PATTERN: str = ""
_FALSE_POSITIVE_WORDS: set = set()
_ADDRESS_PATTERNS: list = []
_ENS_PATTERN: str = ""
_PERCENT_PATTERN: str = ""
_HF_PATTERN: str = ""
_LEVERAGE_PATTERN: str = ""
_NUMBER_WORDS: list = []
_NUMBER_WORD_PATTERNS: list = []
_CARDINAL_TOKEN_PATTERN: str = ""
_CARDINAL_KNOWN_TOKEN: str = ""
_CARDINALS: str = ""
_COMPOUND_CARDINAL: str = ""
_WORDED_PERCENT_PATTERN: str = ""
_WORDED_DECIMAL_PATTERN: str = ""
_WORDED_FRACTION_TOKEN: str = ""
_WORDED_DECIMAL_TOKEN: str = ""
_EMOTIONAL_WORDS: list = []
_TIMING_PATTERNS: list = []
_DIRECTIONAL_VERBS: dict = {}
_QUALITATIVE: list = []
_PROTOCOL_NAMES: list = []

TEMPLATES: list = []

# Pre-normalization patterns (applied before input normalization)
_PRE_NORM_PATTERNS: list = []

# Normalization config
_CURRENCY_SYMBOLS: list = []
_HYPHENATED_CARDINALS: set = set()

# Derived
_DOMAIN_KEYWORDS: dict = {}


def _init_from_profile(profile: dict | None = None):
    """Initialize all module-level constants from a domain profile.

    Called once at module load with the default DeFi profile.
    Can be called again to switch to a different domain.
    Not thread-safe — call only from the main thread or with external locking.
    """
    global DOMAIN_DISTRIBUTION, TOP_DOMAINS, DOMAIN_ONTOLOGY
    global _AMOUNT_PATTERNS_ICASE, _AMOUNT_PATTERNS_CSENSE
    global _AMOUNT_KNOWN_TOKEN_PATTERN, _FALSE_POSITIVE_WORDS
    global _ADDRESS_PATTERNS, _ENS_PATTERN
    global _PERCENT_PATTERN, _HF_PATTERN, _LEVERAGE_PATTERN
    global _NUMBER_WORDS, _NUMBER_WORD_PATTERNS
    global _CARDINAL_TOKEN_PATTERN, _CARDINAL_KNOWN_TOKEN
    global _CARDINALS, _COMPOUND_CARDINAL
    global _WORDED_PERCENT_PATTERN, _WORDED_DECIMAL_PATTERN
    global _WORDED_FRACTION_TOKEN, _WORDED_DECIMAL_TOKEN
    global _EMOTIONAL_WORDS, _TIMING_PATTERNS, _DIRECTIONAL_VERBS, _QUALITATIVE
    global _PROTOCOL_NAMES, TEMPLATES
    global _PRE_NORM_PATTERNS
    global _CURRENCY_SYMBOLS, _HYPHENATED_CARDINALS
    global _DOMAIN_KEYWORDS

    if profile is None:
        profile = get_default_profile()

    sp = profile["sensitive_patterns"]
    comp = sp.get("components", {})

    DOMAIN_DISTRIBUTION = profile["domain_distribution"]
    TOP_DOMAINS = profile["top_domains"]
    DOMAIN_ONTOLOGY = profile["subdomains"]

    _AMOUNT_PATTERNS_ICASE = sp["amount_patterns_icase"]
    _AMOUNT_PATTERNS_CSENSE = sp["amount_patterns_csense"]
    _AMOUNT_KNOWN_TOKEN_PATTERN = sp["amount_known_token_pattern"]
    _FALSE_POSITIVE_WORDS = set(sp["false_positive_words"])
    _ADDRESS_PATTERNS = sp["address_patterns"]
    _ENS_PATTERN = sp["ens_pattern"]
    _PERCENT_PATTERN = sp["percent_pattern"]
    _HF_PATTERN = sp["hf_pattern"]
    _LEVERAGE_PATTERN = sp["leverage_pattern"]
    _NUMBER_WORDS = sp["number_words"]
    _NUMBER_WORD_PATTERNS = sp["number_word_patterns"]
    _CARDINALS = comp.get("CARDINALS", "")
    _COMPOUND_CARDINAL = comp.get("COMPOUND_CARDINAL", "")
    _CARDINAL_TOKEN_PATTERN = sp["cardinal_token_pattern"]
    _CARDINAL_KNOWN_TOKEN = sp["cardinal_known_token"]
    _WORDED_PERCENT_PATTERN = sp["worded_percent_pattern"]
    _WORDED_DECIMAL_PATTERN = sp["worded_decimal_pattern"]
    _WORDED_FRACTION_TOKEN = sp["worded_fraction_token"]
    _WORDED_DECIMAL_TOKEN = sp["worded_decimal_token"]
    _EMOTIONAL_WORDS = sp["emotional_words"]
    _TIMING_PATTERNS = sp["timing_patterns"]
    _DIRECTIONAL_VERBS = sp["directional_verbs"]
    _QUALITATIVE = sp["qualitative_words"]
    _PROTOCOL_NAMES = sp["entity_names"]

    TEMPLATES = profile["templates"]

    _PRE_NORM_PATTERNS = sp.get("pre_normalization_patterns", [
        r'\b\d+(?:\.\d+)?[eE][+-]?\d+\s*\w*\b',
        r'\b\d+(?:\.\d+)?[KkMmBb]\b',
        r'\b\d+(?:\.\d+)?[+~≈><]\s*\w*\b',
        r'\b\d+(?:\.\d+)?-\d+(?:\.\d+)?[xX×]?\s*\w*\b',
    ])

    norm = profile.get("normalization", {})
    _CURRENCY_SYMBOLS = norm.get("currency_symbols", ["€", "£", "¥", "₹", "₩", "₿"])
    _HYPHENATED_CARDINALS = set(norm.get("hyphenated_cardinals", [
        "twenty", "thirty", "forty", "fifty",
        "sixty", "seventy", "eighty", "ninety",
    ]))

    # Rebuild derived data structures
    _DOMAIN_KEYWORDS = _build_domain_keywords()


def _normalize_input(text: str) -> str:
    """Canonicalize input before regex matching.

    Fixes an entire class of bypasses: zero-width chars, fullwidth digits,
    joined number-token patterns (125ETH), separator variants (125-ETH),
    locale-specific currency/decimal/thousand separators, and Unicode fractions.
    """
    import unicodedata
    # NFKC normalization: fullwidth → ASCII, compatibility decomposition
    text = unicodedata.normalize('NFKC', text)
    # Normalize Unicode fraction slash (⁄ U+2044) to regular slash, then strip fraction patterns
    text = text.replace('\u2044', '/')
    text = re.sub(r'\b\d+/\d+\b', '', text)  # strip fractions like 1/2, 2/3
    # Normalize currency symbols to $ (so €500k, ¥500000, £1000 get caught by $ patterns)
    if _CURRENCY_SYMBOLS:
        syms = ''.join(re.escape(s) for s in _CURRENCY_SYMBOLS)
        text = re.sub(f'[{syms}]', '$', text)
    else:
        text = re.sub(r'[€£¥₹₩₿]', '$', text)
    # Normalize locale decimal separators: Arabic decimal (٫), comma-as-decimal (1,15 → 1.15)
    # Note: comma-as-decimal is ambiguous with thousand separators; we handle both
    text = text.replace('\u066b', '.')  # Arabic decimal separator
    # Normalize locale thousand separators to nothing: apostrophe (1'000), underscore (1_000), dot-as-thousands (1.234.567)
    text = re.sub(r"(\d)[''_](\d)", r'\1\2', text)
    # Handle US vs European decimal formats:
    # US: 1,234.56 (comma=thousands, dot=decimal) — commas should be stripped, dot stays
    # EU: 1.234,56 (dot=thousands, comma=decimal) — dots stripped, comma→dot
    # Detection heuristic: if comma is followed by exactly 3 digits (and another comma or end),
    # it's a US thousands separator. If comma is followed by 1-2 digits at end, it's EU decimal.
    # Step 1: Strip US-style thousand commas (digit,3digits pattern)
    text = re.sub(r'(\d),(\d{3})(?=,|\b|[^0-9])', r'\1\2', text)
    # Step 2: Strip EU-style dot-thousands (digit.3digits pattern)
    text = re.sub(r'(\d)\.(\d{3})(?=[,.]|\b)', r'\1\2', text)
    # Step 3: Convert EU decimal comma to dot (comma followed by 1-2 digits at word boundary)
    text = re.sub(r'(\d),(\d{1,2})\b', r'\1.\2', text)
    # Strip ALL Unicode format/control/invisible characters (Categories Cf, Cc except \n\t\r)
    text = ''.join(
        ch for ch in text
        if ch in '\n\t\r' or unicodedata.category(ch) not in ('Cf', 'Cc')
    )
    # Normalize hyphenated cardinals: "twenty-five" → "twenty five"
    text = re.sub(r'\b(\w+)-(\w+)\b', lambda m: f'{m.group(1)} {m.group(2)}'
                  if m.group(1).lower() in _HYPHENATED_CARDINALS
                  else m.group(0), text)
    # Insert space between digit and letter when joined: 125eth → 125 eth
    text = re.sub(r'(\d)([a-z])', r'\1 \2', text)
    text = re.sub(r'(\d)([A-Z]{3,})', r'\1 \2', text)
    # Insert space between letter and digit in some contexts: ETH500 stays, but normalize separators
    # Normalize common separators between numbers and tokens: 125-ETH, 125/ETH → 125 ETH
    text = re.sub(r'(\d)\s*[-/]\s*([a-zA-Z]{2,})', r'\1 \2', text)
    # Collapse multiple spaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def sanitize_query(query: str) -> str:
    """Strip private parameters, emotional language, timing, and qualitative descriptors."""
    import unicodedata as _ud

    # Step 0a: Light normalization — NFKC + strip invisible chars, but NO space insertion.
    # This canonicalizes fullwidth chars (０x → 0x, Ａ → A) so address/ENS patterns match,
    # without breaking base58/bech32 addresses with inserted spaces.
    result = _ud.normalize('NFKC', query)
    result = ''.join(ch for ch in result if ch in '\n\t\r' or _ud.category(ch) not in ('Cf', 'Cc'))
    for pat in _ADDRESS_PATTERNS:
        result = re.sub(pat, '', result)
    # Also strip ENS names before normalization
    result = re.sub(_ENS_PATTERN, '', result)

    # Step 0b: Strip patterns that normalization would break by inserting spaces
    for pat in _PRE_NORM_PATTERNS:
        result = re.sub(pat, '', result, flags=re.IGNORECASE)

    # Step 0c: Strip space-separated thousands BEFORE normalization splits them further
    result = re.sub(r'\b\d+\s\d{3}(?:\s\d{3})*(?:\s*[a-zA-Z]\w*)?\b', '', result, flags=re.IGNORECASE)

    # Step 0d: Normalize remaining input (fixes Unicode bypasses, joined tokens)
    result = _normalize_input(result)

    # Remove natural language quantities (secondary NLP filter)
    for pat in _NUMBER_WORD_PATTERNS:
        result = re.sub(pat, '', result, flags=re.IGNORECASE)
    # Cardinal number + tokens (uppercase or known)
    result = re.sub(_CARDINAL_KNOWN_TOKEN, '', result)
    result = re.sub(_CARDINAL_TOKEN_PATTERN, '', result)
    # Worded percentages, decimals, fractions
    result = re.sub(_WORDED_PERCENT_PATTERN, '', result)
    result = re.sub(_WORDED_DECIMAL_TOKEN, '', result)
    result = re.sub(_WORDED_DECIMAL_PATTERN, '', result)
    result = re.sub(_WORDED_FRACTION_TOKEN, '', result)
    for word in _NUMBER_WORDS:
        # Only strip number words when followed by an UPPERCASE token symbol
        # (not case-insensitive — avoids matching "two options", "three ways")
        result = re.sub(
            rf'(?i:\b{re.escape(word)}\b)\s*(?:[A-Z]{{2,10}}|dollars|bucks|worth|position|portfolio)',
            '', result
        )

    # (addresses and ENS names already stripped in Step 0a)

    # Remove amounts: five passes with different case handling.
    # Pass 0a: pre-normalization patterns again (catches residuals after normalization)
    for pat in _PRE_NORM_PATTERNS:
        result = re.sub(pat, '', result, flags=re.IGNORECASE)
    # Pass 0b: catch split-token amounts — normalization may have inserted spaces
    # into obfuscated inputs (e.g., "10⁠000-da i" → "10000 da i").
    # Strip: bare number followed by short fragments that look like split tokens.
    result = re.sub(r'\b\d{3,}\s+[a-zA-Z]{1,3}(?:\s+[a-zA-Z]{1,3})*\b', '', result)
    # Pass 1: case-insensitive known tokens (catches "500 usdc", "1.8m eth")
    result = re.sub(_AMOUNT_KNOWN_TOKEN_PATTERN, '', result, flags=re.IGNORECASE)
    # Pass 2: case-insensitive dollar amounts and suffixed numbers
    for pat in _AMOUNT_PATTERNS_ICASE:
        result = re.sub(pat, '', result, flags=re.IGNORECASE)
    # Pass 3: broad token-like word matching (catches novel tokens not in known list)
    # Uses a callback to skip known false positives (V3, DeFi, FAQ, etc.)
    def _strip_unless_fp(m):
        word = m.group().split()[-1]  # the token-like word
        if word in _FALSE_POSITIVE_WORDS:
            return m.group()  # preserve
        return ''  # strip
    for pat in _AMOUNT_PATTERNS_CSENSE:
        result = re.sub(pat, _strip_unless_fp, result)

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


# ---------------------------------------------------------------------------
# Sub-query genericization (Approach A)
# ---------------------------------------------------------------------------

# Protocol names to strip, longest first to avoid partial matches
_PROTOCOL_NAMES = sorted([
    "Aave V3", "Aave V2", "Aave",
    "UniswapX", "Uniswap V3", "Uniswap V2", "Uniswap", "Curve", "Balancer", "SushiSwap",
    "Morpho Blue", "Morpho", "Compound III", "Compound V3", "Compound V2", "Compound",
    "MakerDAO", "Maker", "dYdX", "GMX", "Synthetix", "Lyra", "Opyn",
    "Lido", "Rocket Pool", "Eigenlayer", "EigenLayer", "Pendle", "Yearn",
    "Convex", "Morpho", "Radiant", "Spark", "Frax", "Swell",
    "BendDAO", "Blur", "OpenSea", "Across", "Stargate", "LayerZero",
    "Wormhole", "Orbiter", "Gnosis Safe",
    "Blast", "Hyperliquid", "Camelot", "CoW Swap", "CoW Protocol",
    "Trader Joe", "Aerodrome", "Velodrome", "Beefy", "Sommelier",
    "Maple", "Goldfinch", "Centrifuge", "Ribbon", "Friktion",
    "Orca", "Raydium", "Jupiter", "Drift", "Mango",
    "Instadapp", "DeFi Saver", "Gearbox", "Kamino", "Jito", "Meteora",
    "Flashbots", "MEV Blocker", "Chainlink", "Pyth", "RedStone",
    "Euler", "Ethena", "Marginfi", "Berachain", "Polymarket",
    "Vertex", "Aevo", "Kwenta", "Perennial", "Angle",
    "EtherFi", "Puffer", "Kelp", "Renzo", "Mantle",
    "Maverick", "Venus",
    "Aave Gov", "Compound Gov", "Uniswap Gov", "Curve Gov",
], key=len, reverse=True)


def genericize_subquery(sub_query: str) -> str:
    """Strip protocol names from a sub-query, replacing with generic domain references.

    This is the key to the privacy-utility middle ground:
    - Preserves the specific MECHANISM ("health factor", "funding rate")
    - Removes the specific PROTOCOL ("Aave V3", "dYdX")
    - The cloud gets the right question without knowing which protocol the user cares about

    Benchmarked at: 3.0/5 utility (same as original), 20% detection (vs 80% original).
    """
    import unicodedata as _ud
    result = _ud.normalize('NFKC', sub_query)  # canonicalize fullwidth → ASCII
    result = ''.join(ch for ch in result if ch in '\n\t\r' or _ud.category(ch) not in ('Cf', 'Cc'))
    domain = classify_domain(result)
    onto = DOMAIN_ONTOLOGY.get(domain, {})
    generic_ref = onto.get("generic_refs", ["DeFi protocols"])[0]

    for proto in _PROTOCOL_NAMES:
        result = re.sub(rf'\b{re.escape(proto)}\b', generic_ref, result, flags=re.IGNORECASE)

    # Clean up doubled generic refs
    result = re.sub(rf'({re.escape(generic_ref)})\s+\1', generic_ref, result)
    result = re.sub(r'\s+', ' ', result).strip()
    return result


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


# ---------------------------------------------------------------------------
# Initialize from default profile at module load
# ---------------------------------------------------------------------------
_init_from_profile()
