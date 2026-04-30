"""
Transaction risk profile schema — extends the e_AI DomainProfile pattern
for pre-submission transaction analysis.

e_AI's DomainProfile handles TEXT query sanitization (sensitive spans, cover
queries, templates). TransactionProfile handles TRANSACTION risk analysis
(heuristic detection, countermeasure recommendation, skill execution).

Both share:
  - ProfileMeta (meta, version, validation_status)
  - LLM backend (Ollama/Anthropic)
  - Validation engine pattern (property checks → traffic-light report)
  - Profile-as-data philosophy (JSON, not code)

TransactionProfile adds:
  - Heuristic definitions (detection signals, confidence, severity)
  - Recommendations with effectiveness scores
  - Skills (tools the system can invoke)
  - Adversary model
  - Benchmark specification
"""

from __future__ import annotations

from typing import TypedDict


# ---------------------------------------------------------------------------
# Shared with e_AI
# ---------------------------------------------------------------------------

class ProfileMeta(TypedDict, total=False):
    """Metadata about the profile. Same as e_AI."""
    domain_name: str
    version: str
    generated_by: str          # "hand-crafted" or model name
    validation_status: str     # "draft" | "validated" | "audited"
    source_paper: str          # arxiv / DOI reference
    baseline_deanon_rate: float
    target_deanon_rate: float


# ---------------------------------------------------------------------------
# Transaction-specific
# ---------------------------------------------------------------------------

class AdversaryModel(TypedDict, total=False):
    """What the adversary can and cannot do."""
    capabilities: list[str]
    limitations: list[str]


class RiskDomain(TypedDict, total=False):
    """The domain this profile covers."""
    name: str
    crops_property: str        # C, R, O, P, or S
    description: str
    protocols: list[str]       # e.g., ["Umbra", "Fluidkey", "ERC-5564"]
    adversary_model: AdversaryModel


class DetectionSignal(TypedDict, total=False):
    """A single signal that indicates a heuristic match."""
    name: str
    description: str
    data_needed: list[str]
    confidence: float          # 0.0 to 1.0


class Detection(TypedDict, total=False):
    """How to detect a heuristic match."""
    type: str                  # "graph_analysis" | "statistical" | "temporal" | "identity"
    signals: list[DetectionSignal]
    threshold: str             # human-readable threshold description


class Recommendation(TypedDict, total=False):
    """A countermeasure for a detected risk."""
    action: str
    description: str
    effectiveness: float       # 0.0 to 1.0
    user_cost: str             # "none" | "low" | "medium" | "high"
    skill_required: str | None


class BenchmarkScenario(TypedDict, total=False):
    """How to benchmark a single heuristic."""
    setup: str
    metric: str
    baseline: str


class Heuristic(TypedDict, total=False):
    """A deanonymization or risk heuristic."""
    id: str
    name: str
    paper_section: str
    severity: str              # "critical" | "high" | "medium" | "low"
    description: str
    detection: Detection
    recommendations: list[Recommendation]
    fundamental_limitation: str
    benchmark_scenario: BenchmarkScenario


class Skill(TypedDict, total=False):
    """A tool the analyzer or LLM can invoke."""
    tool: str
    description: str
    parameters: dict


class AdversaryLevel(TypedDict, total=False):
    """An adversary capability level for benchmarking."""
    name: str
    heuristics: list[str]
    description: str


class CombinedBenchmark(TypedDict, total=False):
    """End-to-end benchmark specification."""
    description: str
    methodology: dict[str, str]
    target: str
    metrics: list[str]
    adversary_levels: list[AdversaryLevel]


class Templates(TypedDict, total=False):
    """Output templates for risk assessments."""
    risk_assessment: str
    summary: str
    skill_suggestion: str


# ---------------------------------------------------------------------------
# Top-level profile
# ---------------------------------------------------------------------------

class TransactionProfile(TypedDict, total=False):
    """Complete transaction risk profile.

    Parallel to e_AI's DomainProfile but for transaction analysis instead of
    text sanitization. Loadable by the same profile_loader pattern.
    """
    meta: ProfileMeta
    risk_domain: RiskDomain
    heuristics: dict[str, Heuristic]
    skills: dict[str, Skill]
    combined_benchmark: CombinedBenchmark
    templates: Templates


# ---------------------------------------------------------------------------
# Required keys for validation
# ---------------------------------------------------------------------------

REQUIRED_KEYS = {"meta", "risk_domain", "heuristics", "skills"}

REQUIRED_HEURISTIC_KEYS = {
    "id", "name", "severity", "description", "detection", "recommendations",
}

REQUIRED_SIGNAL_KEYS = {"name", "description", "confidence"}
