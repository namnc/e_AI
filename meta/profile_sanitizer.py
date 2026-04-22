"""
Profile sanitizer — genericize a profile before sending to cloud LLM for review.

The same privacy philosophy that protects user queries also protects the profile:
strip specific entity names, replace with generic placeholders, send for review,
then de-genericize the response.

Usage:
    from meta.profile_sanitizer import genericize_profile, degenericize_profile

    # Before cloud review
    safe_profile, mapping = genericize_profile(profile)
    # Send safe_profile to cloud LLM for review
    cloud_suggestions = cloud_review(safe_profile)
    # After cloud review — restore real names in suggestions
    real_suggestions = degenericize_profile(cloud_suggestions, mapping)
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
    counter = {"entity": 0, "protocol": 0}

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
            # Reuse mapping if entity already mapped
            existing = next(
                (k for k, v in mapping.items() if v == proto), None
            )
            if existing:
                new_protocols.append(existing)
            else:
                counter["protocol"] += 1
                placeholder = f"PROTOCOL_{counter['protocol']:03d}"
                mapping[placeholder] = proto
                new_protocols.append(placeholder)
        sd_data["protocols"] = new_protocols

        # Genericize generic_refs (may contain domain-revealing language)
        new_refs = []
        for i, ref in enumerate(sd_data.get("generic_refs", [])):
            placeholder = f"REF_{sd_name}_{i}"
            mapping[placeholder] = ref
            new_refs.append(placeholder)
        sd_data["generic_refs"] = new_refs

    # Genericize known tokens in regex patterns (component)
    comp = sp.get("components", {})
    if "KNOWN_TOKENS" in comp:
        tokens = comp["KNOWN_TOKENS"].split("|")
        new_tokens = []
        for i, tok in enumerate(tokens):
            placeholder = f"token_{i:03d}"
            mapping[placeholder] = tok
            new_tokens.append(placeholder)
        comp["KNOWN_TOKENS"] = "|".join(new_tokens)

    # Strip domain_heuristics (reveals threat model specifics)
    safe.pop("domain_heuristics", None)

    # Redact meta
    safe["meta"]["domain_name"] = safe["meta"].get("domain_name", "redacted")
    safe["meta"]["_note"] = "Entity names genericized for cloud review"

    return safe, mapping


def degenericize_text(text: str, mapping: dict) -> str:
    """Replace placeholders in text with real names using the mapping.

    Used to de-genericize cloud LLM suggestions.
    """
    result = text
    # Sort by placeholder length descending to avoid partial replacements
    for placeholder in sorted(mapping.keys(), key=len, reverse=True):
        result = result.replace(placeholder, mapping[placeholder])
    return result


def degenericize_profile(profile: dict, mapping: dict) -> dict:
    """Restore real entity names in a profile using the mapping.

    Used after receiving cloud LLM suggestions to map back to real names.
    """
    # Convert to string, replace all placeholders, convert back
    as_str = json.dumps(profile, ensure_ascii=False)
    restored = degenericize_text(as_str, mapping)
    return json.loads(restored)


def save_mapping(mapping: dict, path: str):
    """Save the mapping to disk. KEEP LOCAL — never send to cloud."""
    with open(path, "w") as f:
        json.dump(mapping, f, indent=2, ensure_ascii=False)


def load_mapping(path: str) -> dict:
    """Load a mapping from disk."""
    with open(path) as f:
        return json.load(f)
