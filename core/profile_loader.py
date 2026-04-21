"""
Load and validate domain profiles from JSON files.

Usage:
    from core.profile_loader import load_profile, get_default_profile

    # Load explicit profile
    profile = load_profile("domains/medical/profile.json")

    # Get the default DeFi profile (backward-compatible)
    profile = get_default_profile()
"""

from __future__ import annotations

import json
import os
from typing import Any

# Cache loaded profiles to avoid repeated disk I/O
_profile_cache: dict[str, dict] = {}

# Default profile path (relative to project root)
_DEFAULT_PROFILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "domains", "defi", "profile.json",
)

# Required top-level keys
_REQUIRED_KEYS = {
    "meta", "domain_distribution", "top_domains",
    "subdomains", "sensitive_patterns", "templates",
}

# Required subdomain vocabulary keys
_REQUIRED_SUBDOMAIN_KEYS = {
    "protocols", "mechanisms", "operations", "triggers",
    "metrics", "actors", "risk_concepts", "generic_refs",
}


def load_profile(path: str) -> dict[str, Any]:
    """Load a domain profile from a JSON file.

    Validates that required keys exist and regex patterns compile.
    Caches by absolute path — subsequent calls return the same dict.
    """
    abs_path = os.path.abspath(path)
    if abs_path in _profile_cache:
        return _profile_cache[abs_path]

    with open(abs_path) as f:
        profile = json.load(f)

    _validate(profile, abs_path)
    _profile_cache[abs_path] = profile
    return profile


def get_default_profile() -> dict[str, Any]:
    """Load the default DeFi profile. Used for backward compatibility."""
    return load_profile(_DEFAULT_PROFILE)


def clear_cache():
    """Clear the profile cache (useful for testing)."""
    _profile_cache.clear()


def _validate(profile: dict, source: str):
    """Basic structural validation."""
    missing = _REQUIRED_KEYS - set(profile.keys())
    if missing:
        raise ValueError(f"Profile {source} missing required keys: {missing}")

    # Check subdomains have required vocabulary
    for name, sub in profile.get("subdomains", {}).items():
        missing_sub = _REQUIRED_SUBDOMAIN_KEYS - set(sub.keys())
        if missing_sub:
            raise ValueError(
                f"Subdomain '{name}' in {source} missing keys: {missing_sub}"
            )

    # Check templates exist
    if not profile.get("templates"):
        raise ValueError(f"Profile {source} has no templates")

    # Check top_domains reference valid subdomains
    valid_domains = set(profile.get("subdomains", {}).keys())
    for td in profile.get("top_domains", []):
        if td not in valid_domains:
            raise ValueError(
                f"top_domain '{td}' not found in subdomains of {source}"
            )
