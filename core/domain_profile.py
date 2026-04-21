"""
Domain profile schema — the central data structure that replaces all hardcoded
domain-specific constants (ontology, sanitizer patterns, templates, entity names).

A DomainProfile is a JSON-serializable dict loaded from domains/<name>/profile.json.
The DeFi system's constants become the first instance of this schema.
"""

from __future__ import annotations

from typing import TypedDict


class SubdomainEntry(TypedDict, total=False):
    """Vocabulary and metadata for one subdomain (e.g., 'lending', 'dex')."""
    protocols: list[str]       # named entities (Aave, Compound, ...)
    mechanisms: list[str]      # domain-specific concepts
    operations: list[str]      # user actions
    triggers: list[str]        # event conditions
    metrics: list[str]         # measurable quantities
    actors: list[str]          # participant roles
    risk_concepts: list[str]   # threat categories
    generic_refs: list[str]    # anonymized category names


class StructuralPattern(TypedDict, total=False):
    """One regex pattern for sanitization."""
    pattern: str               # regex string
    flags: str                 # "IGNORECASE" | "CASESENSITIVE"
    category: str              # "amount", "address", "identifier", etc.
    replacement: str           # what to replace with (default: "")


class SensitivePatterns(TypedDict, total=False):
    """All sanitization patterns for a domain."""
    # Regex patterns grouped by application phase
    amount_patterns_icase: list[str]
    amount_patterns_csense: list[str]
    amount_known_token_pattern: str
    known_tokens: str                    # regex alternation of known token symbols
    false_positive_words: list[str]
    address_patterns: list[str]
    ens_pattern: str
    percent_pattern: str
    hf_pattern: str                      # health-factor / domain-specific metric pattern
    leverage_pattern: str
    number_words: list[str]
    number_word_patterns: list[str]
    cardinal_token_pattern: str
    cardinal_known_token: str
    worded_percent_pattern: str
    worded_decimal_pattern: str
    worded_fraction_token: str
    worded_decimal_token: str
    emotional_words: list[str]
    timing_patterns: list[str]
    directional_verbs: dict[str, str]
    qualitative_words: list[str]

    # Entity names for genericization (longest-first sorted)
    entity_names: list[str]


class NormalizationConfig(TypedDict, total=False):
    """Input normalization settings."""
    currency_symbols: list[str]          # symbols to normalize to $
    hyphenated_cardinals: list[str]      # words that form hyphenated compounds


class TemplateSlots(TypedDict, total=False):
    """Maps template slot names to ontology categories."""
    MECHANISM: str
    OPERATION: str
    OPERATION_A: str
    OPERATION_B: str
    TRIGGER: str
    METRIC: str
    ACTOR: str
    GENERIC_REF: str
    RISK_CONCEPT: str


class ProfileMeta(TypedDict, total=False):
    """Metadata about the profile."""
    domain_name: str
    version: str
    generated_by: str          # "hand-crafted" or model name
    validation_status: str     # "draft" | "validated" | "audited"


class DomainProfile(TypedDict, total=False):
    """Complete domain profile — replaces all hardcoded domain constants."""
    meta: ProfileMeta
    domain_distribution: dict[str, float]
    top_domains: list[str]
    subdomains: dict[str, SubdomainEntry]
    sensitive_patterns: SensitivePatterns
    normalization: NormalizationConfig
    templates: list[str]
    template_slots: dict[str, str]
