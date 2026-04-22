"""
Profile sanitizer — genericize a profile before sending to cloud LLM for review.

The same privacy philosophy that protects user queries also protects the profile:
strip specific entity names, replace with generic placeholders, send for review,
then de-genericize the response.

Usage:
    from meta.profile_sanitizer import genericize_profile, degenericize_profile

    safe_profile, mapping = genericize_profile(profile)
    cloud_suggestions = cloud_review(safe_profile)
    real_suggestions = degenericize_text(cloud_suggestions, mapping)
"""

from __future__ import annotations

import copy
import json
import re


def genericize_profile(profile: dict) -> tuple[dict, dict]:
    """Strip specific entity names from a profile, replace with generic placeholders.

    Returns:
        (genericized_profile, mapping) where mapping allows de-genericization.
        The mapping is {placeholder: real_name} and should NEVER be sent to cloud.
    """
    safe = copy.deepcopy(profile)
    mapping: dict[str, str] = {}
    counter = {"entity": 0}

    # Genericize entity_names
    sp = safe.get("sensitive_patterns", {})
    new_entities = []
    for name in sp.get("entity_names", []):
        counter["entity"] += 1
        placeholder = f"ENTITY_{counter['entity']:03d}"
        mapping[placeholder] = name
        new_entities.append(placeholder)
    sp["entity_names"] = new_entities

    # Genericize protocol names in subdomains
    for sd_name, sd_data in safe.get("subdomains", {}).items():
        new_protocols = []
        for proto in sd_data.get("protocols", []):
            existing = next((k for k, v in mapping.items() if v == proto), None)
            if existing:
                new_protocols.append(existing)
            else:
                counter["entity"] += 1
                placeholder = f"ENTITY_{counter['entity']:03d}"
                mapping[placeholder] = proto
                new_protocols.append(placeholder)
        sd_data["protocols"] = new_protocols

        # Genericize generic_refs
        new_refs = []
        for i, ref in enumerate(sd_data.get("generic_refs", [])):
            placeholder = f"REF_{sd_name}_{i}"
            mapping[placeholder] = ref
            new_refs.append(placeholder)
        sd_data["generic_refs"] = new_refs

    # Genericize known tokens in components — replace entire value
    # (tokens like "usdc\.e" contain backslashes that break JSON round-trips
    #  if replaced via string substitution, so we replace the whole field)
    comp = sp.get("components", {})
    if "KNOWN_TOKENS" in comp:
        mapping["_KNOWN_TOKENS_ORIGINAL"] = comp["KNOWN_TOKENS"]
        comp["KNOWN_TOKENS"] = "token_placeholder"

    # Also genericize patterns that embed known tokens
    # (these are long regex strings — replace entire fields, not substrings)
    for key in ("amount_known_token_pattern", "cardinal_known_token",
                "worded_fraction_token", "worded_decimal_token"):
        if key in sp and sp[key]:
            mapping[f"_PATTERN_{key}"] = sp[key]
            sp[key] = f"PATTERN_PLACEHOLDER_{key}"

    # Strip domain_heuristics (reveals threat model specifics)
    if "domain_heuristics" in safe:
        mapping["_domain_heuristics"] = safe.pop("domain_heuristics")

    # Redact meta
    mapping["_domain_name"] = safe["meta"].get("domain_name", "unknown")
    safe["meta"]["domain_name"] = "redacted"
    safe["meta"]["_note"] = "Entity names genericized for cloud review"

    return safe, mapping


def degenericize_text(text: str, mapping: dict) -> str:
    """Replace placeholders in text with real names using the mapping.

    Used to de-genericize cloud LLM suggestions (free text, not JSON).
    Only replaces ENTITY_NNN and REF_ placeholders, not internal keys.
    """
    result = text
    for placeholder in sorted(mapping.keys(), key=len, reverse=True):
        if placeholder.startswith("_"):
            continue  # skip internal keys
        result = result.replace(placeholder, mapping[placeholder])
    return result


def degenericize_profile(profile: dict, mapping: dict) -> dict:
    """Restore real entity names in a profile using the mapping.

    Uses structured traversal instead of string replacement to avoid
    JSON escaping issues with values like "usdc\\.e".
    """
    restored = copy.deepcopy(profile)

    # Build reverse mapping for entity/ref placeholders only
    reverse = {k: v for k, v in mapping.items() if not k.startswith("_")}

    def _restore_list(items: list) -> list:
        return [reverse.get(item, item) if isinstance(item, str) else item
                for item in items]

    def _restore_str(val: str) -> str:
        return reverse.get(val, val)

    # Restore entity_names
    sp = restored.get("sensitive_patterns", {})
    if "entity_names" in sp:
        sp["entity_names"] = _restore_list(sp["entity_names"])

    # Restore subdomain protocols and generic_refs
    for sd_data in restored.get("subdomains", {}).values():
        if "protocols" in sd_data:
            sd_data["protocols"] = _restore_list(sd_data["protocols"])
        if "generic_refs" in sd_data:
            sd_data["generic_refs"] = _restore_list(sd_data["generic_refs"])

    # Restore KNOWN_TOKENS
    comp = sp.get("components", {})
    if "_KNOWN_TOKENS_ORIGINAL" in mapping:
        comp["KNOWN_TOKENS"] = mapping["_KNOWN_TOKENS_ORIGINAL"]

    # Restore token-embedding patterns
    for key in ("amount_known_token_pattern", "cardinal_known_token",
                "worded_fraction_token", "worded_decimal_token"):
        map_key = f"_PATTERN_{key}"
        if map_key in mapping:
            sp[key] = mapping[map_key]

    # Restore domain_heuristics
    if "_domain_heuristics" in mapping:
        restored["domain_heuristics"] = mapping["_domain_heuristics"]

    # Restore domain name
    if "_domain_name" in mapping:
        restored["meta"]["domain_name"] = mapping["_domain_name"]

    # Remove note
    restored["meta"].pop("_note", None)

    return restored


def save_mapping(mapping: dict, path: str):
    """Save the mapping to disk. KEEP LOCAL — never send to cloud."""
    with open(path, "w") as f:
        json.dump(mapping, f, indent=2, ensure_ascii=False)


def load_mapping(path: str) -> dict:
    """Load a mapping from disk."""
    with open(path) as f:
        return json.load(f)
