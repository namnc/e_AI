"""
LLM prompts for the meta-framework pipeline.

All prompts used during domain profile generation are centralized here
for transparency and auditability.
"""

# ---------------------------------------------------------------------------
# Phase 1: Dataset analysis
# ---------------------------------------------------------------------------

SENSITIVITY_EXTRACTION = """\
You are a privacy analyst. For the given user query to a cloud AI assistant, \
identify every substring that carries private, exploitable, or sensitive information.

For each sensitive span, output:
- "span": the exact substring
- "category": one of: amount, identifier, credential, strategy, timing, emotional, qualitative, entity_name
- "reason": why an adversary could exploit this (1 sentence)

A span is sensitive if revealing it to the cloud provider could enable:
- Financial exploitation (front-running, liquidation hunting, market manipulation)
- Identity linking (wallet address, account ID, personal name)
- Strategy inference (trading intent, timing plans, risk posture)

Output JSON: {"spans": [{"span": "...", "category": "...", "reason": "..."}]}
If no sensitive spans exist, output: {"spans": []}
Be thorough — miss nothing. False positives are acceptable; false negatives are not."""

SUBDOMAIN_CLASSIFICATION = """\
You are a domain analyst. Classify the following query into a subdomain category \
within the domain it belongs to.

Rules:
- Use a short, lowercase label (1-2 words, e.g., "lending", "trading", "staking")
- The label must describe the FUNCTIONAL area, not the technology or format
- If the query spans multiple subdomains, pick the primary one
- If the query is generic/uncategorizable, use "general"
- Do NOT create labels for tangential topics — classify by the core subject

Output JSON: {"subdomain": "...", "confidence": "high" | "medium" | "low"}"""

SUBDOMAIN_CONSOLIDATION = """\
You are organizing a taxonomy. Given these subdomain labels extracted from a query dataset, \
consolidate them into exactly 4-8 clean subdomains.

This is a MERGING task. You must aggressively combine related labels. Examples:
- "crypto" + "cryptocurrencies" + "crypto_trading" + "blockchain" → "trading"
- "smart_contract" + "smart_contracts" + "security" → "smart_contracts"
- "investing" + "investment" + "finance" → "investing"
- "yield_farming" + "yield_aggregation" → "yield"
- "health" + "cardiology" + "gaming" → "general" (if off-topic for the domain)

Rules:
- Output MUST have between 4 and 8 consolidated labels, no more
- Merge ALL synonyms, plurals, and closely related labels into one
- Labels that appear only 1-2 times should be absorbed into a larger category
- Off-topic or hallucinated labels should map to "general"
- Each consolidated label should be lowercase_with_underscores

Output JSON: {"taxonomy": {"original_label": "consolidated_label", ...}, \
"subdomain_descriptions": {"consolidated_label": "one-line description", ...}}"""

VOCABULARY_EXTRACTION = """\
You are building a domain ontology. For the given subdomain and its example queries, \
extract vocabulary into these categories:

- entities: Named systems, products, protocols, organizations (e.g., "Aave", "Mayo Clinic")
- mechanisms: Domain-specific concepts and processes (e.g., "liquidation", "triage")
- operations: Actions users perform (e.g., "adding collateral", "filing a claim")
- triggers: Events or conditions that prompt questions (e.g., "prices drop", "symptoms worsen")
- metrics: Measurable quantities (e.g., "health factor", "blood pressure")
- actors: Participant roles (e.g., "borrowers", "patients")
- risk_concepts: Failure modes and threats (e.g., "liquidation risk", "misdiagnosis")
- generic_refs: Anonymized category names (e.g., "lending protocols", "healthcare providers")

Output JSON with these 8 keys, each mapping to a list of 5-15 terms.
Draw from the example queries but also include terms you know belong to this subdomain.
Avoid overlapping terms across categories."""

TEMPLATE_EXTRACTION = """\
You are a linguistic analyst. Given these example queries from a domain, \
extract 15-25 structural question templates.

A template replaces domain-specific nouns/concepts with slot placeholders:
- {MECHANISM} — a domain-specific concept or process
- {OPERATION} — a user action
- {TRIGGER} — an event or condition
- {METRIC} — a measurable quantity
- {ACTOR} — a participant role
- {GENERIC_REF} — anonymized category name
- {RISK_CONCEPT} — a failure mode or threat
- {ENTITY} — a named system or organization

Rules:
- Templates must be valid questions (end with ?)
- Each template should have 2-4 slots
- Templates should cover the variety of question structures in the examples
- Include "How does...", "What are...", "What factors...", "How do..." patterns
- Avoid overly specific templates that only match one query

Output JSON: {"templates": ["How does {MECHANISM} work in {GENERIC_REF}?", ...]}"""

# ---------------------------------------------------------------------------
# Phase 2: Pattern generation
# ---------------------------------------------------------------------------

PATTERN_GENERATION = """\
You are a regex engineer. Given these examples of sensitive spans from a domain, \
write regex patterns that would catch each category of sensitive information.

For each category of sensitive spans, output:
- "category": the category name
- "patterns": list of regex pattern strings (Python re module syntax)
- "flags": "IGNORECASE" or "CASESENSITIVE"
- "false_positive_examples": common words/phrases that look similar but are NOT sensitive
- "replacement": what to replace matches with (usually "" for deletion)

Rules:
- Patterns must be valid Python regex syntax
- Prefer broader patterns that catch variations (e.g., different number formats)
- Include negative lookaheads/lookbehinds to avoid false positives where possible
- Test mentally: would this pattern catch the spans shown but not common words?

Output JSON: {"patterns": [{"category": "...", "patterns": [...], "flags": "...", \
"false_positive_examples": [...], "replacement": "..."}]}"""

ENTITY_EXTRACTION = """\
You are building an entity list for privacy protection. Given queries from a domain, \
extract all named entities (organizations, products, protocols, services) that appear.

For each entity, also suggest a generic replacement category:
- "Aave V3" → "lending protocols"
- "Mayo Clinic" → "healthcare facilities"
- "Goldman Sachs" → "financial institutions"

Rules:
- Include version suffixes where relevant (e.g., "Aave V3" and "Aave" separately)
- Sort by length descending (longest first) to avoid partial-match issues
- Be comprehensive — include all entities in the queries

Output JSON: {"entities": [{"name": "...", "generic_ref": "..."}]}"""

