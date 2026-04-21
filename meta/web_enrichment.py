"""
Web enrichment — uses internet search to fill vocabulary gaps in generated profiles.

Three enrichment points:
  1. Ontology enrichment: search "[subdomain] terminology" to find missing vocabulary
  2. Threat model construction: search "[domain] data exploitation cases"
  3. False positive calibration: search "[domain] common abbreviations"

The search function is injectable — pass any callable(query: str) -> list[str]
that returns a list of result snippets. This allows using DuckDuckGo, SerpAPI,
or any other search backend.

Usage:
    from meta.web_enrichment import enrich_profile, make_ddgs_search

    # With DuckDuckGo (install: pip install ddgs)
    profile = enrich_profile(profile, search_fn=make_ddgs_search())

    # With a custom search function
    def my_search(query):
        # ... call your search API ...
        return ["snippet1", "snippet2"]
    profile = enrich_profile(profile, search_fn=my_search)
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Callable

from llm_backend import call_llm


# Type alias for search functions
SearchFn = Callable[[str], list[str]]


def _extract_json(text: str) -> dict | list | None:
    for start_char, end_char in [('{', '}'), ('[', ']')]:
        start = text.find(start_char)
        if start == -1:
            continue
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == '\\':
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == start_char:
                depth += 1
            elif ch == end_char:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break
    return None


# ---------------------------------------------------------------------------
# Search query generation
# ---------------------------------------------------------------------------

SEARCH_QUERY_PROMPT = """\
You are helping enrich a domain vocabulary for a privacy protection system. \
Given a subdomain name and its current vocabulary, generate 3-5 web search \
queries that would find additional terminology, entities, and concepts.

Focus on:
- Finding entities (organizations, products, protocols) not in the current list
- Finding domain-specific mechanisms and processes
- Finding common abbreviations and acronyms in this field

Output JSON: {"queries": ["search query 1", "search query 2", ...]}"""

EXTRACT_TERMS_PROMPT = """\
You are extracting domain vocabulary from web search results. Given search \
result snippets about a specific subdomain, extract:

- entities: Named organizations, products, protocols, services
- mechanisms: Domain-specific concepts and processes
- abbreviations: Common acronyms and their meanings

Only extract terms that are genuinely part of this subdomain. Skip generic words.

Output JSON: {
  "entities": ["Entity1", "Entity2"],
  "mechanisms": ["concept1", "concept2"],
  "abbreviations": ["ABC", "DEF"]
}"""

THREAT_SEARCH_PROMPT = """\
You are researching threats for a privacy protection system. Given web search \
results about data exploitation in a domain, extract:

- exploit_types: Types of information exploitation that have occurred
- leaked_data_types: Categories of sensitive data that were exploited
- real_cases: Brief descriptions of real incidents

Output JSON: {
  "exploit_types": ["type1", "type2"],
  "leaked_data_types": ["category1", "category2"],
  "real_cases": ["brief description of incident"]
}"""

FP_SEARCH_PROMPT = """\
Given web search results about common abbreviations and terminology in a domain, \
extract uppercase abbreviations (2-5 characters) that are domain terminology, \
NOT sensitive data. These will be used as false-positive exclusions in a \
privacy sanitizer (so numbers next to these words won't be stripped).

Output JSON: {"abbreviations": ["ABC", "DEF", "GHI"]}"""


# ---------------------------------------------------------------------------
# Enrichment point 1: Ontology enrichment
# ---------------------------------------------------------------------------

def enrich_ontology(
    profile: dict,
    search_fn: SearchFn,
    progress: bool = True,
) -> dict:
    """Search for additional vocabulary for each subdomain.

    Modifies profile in place.
    """
    subdomains = profile.get("subdomains", {})
    domain_name = profile.get("meta", {}).get("domain_name", "unknown")

    for sd_name, sd_data in subdomains.items():
        if progress:
            print(f"  Enriching ontology: {sd_name}")

        # Generate search queries via LLM
        current_vocab = {
            "entities": sd_data.get("protocols", [])[:10],
            "mechanisms": sd_data.get("mechanisms", [])[:10],
        }
        resp = call_llm(
            prompt=(
                f"Domain: {domain_name}\n"
                f"Subdomain: {sd_name}\n"
                f"Current vocabulary: {json.dumps(current_vocab)}"
            ),
            system=SEARCH_QUERY_PROMPT,
            max_tokens=512,
        )
        parsed = _extract_json(resp)
        queries = parsed.get("queries", []) if isinstance(parsed, dict) else []

        if not queries:
            queries = [
                f"{sd_name} {domain_name} terminology 2026",
                f"{sd_name} popular platforms products services",
                f"{sd_name} key concepts mechanisms",
            ]

        # Execute searches
        all_snippets = []
        for query in queries[:5]:
            try:
                snippets = search_fn(query)
                all_snippets.extend(snippets)
            except Exception as e:
                if progress:
                    print(f"    [warn] Search failed for '{query}': {e}")

        if not all_snippets:
            if progress:
                print(f"    No search results for {sd_name}")
            continue

        # Extract terms from results via LLM
        snippet_block = "\n".join(f"- {s}" for s in all_snippets[:30])
        resp = call_llm(
            prompt=f"Subdomain: {sd_name}\n\nSearch results:\n{snippet_block}",
            system=EXTRACT_TERMS_PROMPT,
            max_tokens=1024,
        )
        parsed = _extract_json(resp)
        if not isinstance(parsed, dict):
            continue

        # Merge new terms (deduplicate)
        new_entities = parsed.get("entities", [])
        new_mechanisms = parsed.get("mechanisms", [])

        existing_protocols = set(p.lower() for p in sd_data.get("protocols", []))
        existing_mechanisms = set(m.lower() for m in sd_data.get("mechanisms", []))

        added_p = 0
        for ent in new_entities:
            if isinstance(ent, str) and ent.lower() not in existing_protocols:
                sd_data.setdefault("protocols", []).append(ent)
                existing_protocols.add(ent.lower())
                added_p += 1

        added_m = 0
        for mech in new_mechanisms:
            if isinstance(mech, str) and mech.lower() not in existing_mechanisms:
                sd_data.setdefault("mechanisms", []).append(mech)
                existing_mechanisms.add(mech.lower())
                added_m += 1

        if progress:
            print(f"    Added {added_p} entities, {added_m} mechanisms")

    return profile


# ---------------------------------------------------------------------------
# Enrichment point 2: Threat model
# ---------------------------------------------------------------------------

def enrich_threat_model(
    profile: dict,
    search_fn: SearchFn,
    progress: bool = True,
) -> dict:
    """Search for real-world exploitation cases to inform threat model.

    Adds a threat_model section to the profile.
    """
    domain_name = profile.get("meta", {}).get("domain_name", "unknown")

    if progress:
        print(f"  Enriching threat model for '{domain_name}'")

    queries = [
        f"{domain_name} data breach exploitation cases 2024 2025 2026",
        f"{domain_name} information leakage privacy violation incidents",
        f"{domain_name} user data exploited by provider",
    ]

    all_snippets = []
    for query in queries:
        try:
            snippets = search_fn(query)
            all_snippets.extend(snippets)
        except Exception as e:
            if progress:
                print(f"    [warn] Search failed: {e}")

    if not all_snippets:
        if progress:
            print(f"    No search results for threat model")
        return profile

    snippet_block = "\n".join(f"- {s}" for s in all_snippets[:30])
    resp = call_llm(
        prompt=f"Domain: {domain_name}\n\nSearch results:\n{snippet_block}",
        system=THREAT_SEARCH_PROMPT,
        max_tokens=1024,
    )
    parsed = _extract_json(resp)
    if isinstance(parsed, dict):
        profile["threat_model"] = {
            "exploit_types": parsed.get("exploit_types", []),
            "leaked_data_types": parsed.get("leaked_data_types", []),
            "real_cases": parsed.get("real_cases", []),
            "source": "web_enrichment",
        }
        if progress:
            print(f"    Found {len(parsed.get('exploit_types', []))} exploit types, "
                  f"{len(parsed.get('real_cases', []))} cases")

    return profile


# ---------------------------------------------------------------------------
# Enrichment point 3: False positive calibration
# ---------------------------------------------------------------------------

def enrich_false_positives(
    profile: dict,
    search_fn: SearchFn,
    progress: bool = True,
) -> dict:
    """Search for common abbreviations to add to false-positive list.

    Prevents the sanitizer from stripping domain terminology.
    """
    domain_name = profile.get("meta", {}).get("domain_name", "unknown")

    if progress:
        print(f"  Calibrating false positives for '{domain_name}'")

    queries = [
        f"{domain_name} common abbreviations acronyms glossary",
        f"{domain_name} terminology acronym list",
    ]

    all_snippets = []
    for query in queries:
        try:
            snippets = search_fn(query)
            all_snippets.extend(snippets)
        except Exception as e:
            if progress:
                print(f"    [warn] Search failed: {e}")

    if not all_snippets:
        return profile

    snippet_block = "\n".join(f"- {s}" for s in all_snippets[:20])
    resp = call_llm(
        prompt=f"Domain: {domain_name}\n\nSearch results:\n{snippet_block}",
        system=FP_SEARCH_PROMPT,
        max_tokens=512,
    )
    parsed = _extract_json(resp)
    if isinstance(parsed, dict):
        new_abbrevs = parsed.get("abbreviations", [])
        sp = profile.setdefault("sensitive_patterns", {})
        existing = set(sp.get("false_positive_words", []))
        added = 0
        for abbr in new_abbrevs:
            if isinstance(abbr, str) and abbr not in existing and 2 <= len(abbr) <= 6:
                sp.setdefault("false_positive_words", []).append(abbr)
                existing.add(abbr)
                added += 1
        if progress:
            print(f"    Added {added} false-positive abbreviations")

    return profile


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def enrich_profile(
    profile: dict,
    search_fn: SearchFn,
    progress: bool = True,
) -> dict:
    """Run all three enrichment points.

    Args:
        profile: the generated DomainProfile dict (modified in place)
        search_fn: callable(query: str) -> list[str] returning result snippets

    Returns:
        the enriched profile
    """
    print("Phase 2b: Web enrichment")

    profile = enrich_ontology(profile, search_fn, progress=progress)
    profile = enrich_threat_model(profile, search_fn, progress=progress)
    profile = enrich_false_positives(profile, search_fn, progress=progress)

    print("  Web enrichment complete.")
    return profile


# ---------------------------------------------------------------------------
# Built-in search backends
# ---------------------------------------------------------------------------

def make_ddgs_search(max_results: int = 5) -> SearchFn:
    """Create a search function using DuckDuckGo (requires: pip install ddgs).

    Returns a callable(query: str) -> list[str] suitable for enrich_profile().
    """
    try:
        from ddgs import DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            raise ImportError(
                "Neither 'ddgs' nor 'duckduckgo_search' is installed. "
                "Install with: pip install ddgs"
            )

    def search_fn(query: str) -> list[str]:
        results = list(DDGS().text(query, max_results=max_results))
        return [r.get("body", "") for r in results if r.get("body")]

    return search_fn
