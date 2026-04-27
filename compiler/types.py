"""
Core types for the Privacy Protection Compiler.

A Tool is a privacy-preserving operation with declared properties.
A ThreatModel describes what the adversary can do.
Constraints describe what the user has (hardware, latency budget, cost).
A Pipeline is a composed sequence of tools with combined guarantees.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Layer(Enum):
    """Which layer a tool belongs to."""
    QUERY_TRANSFORM = 1    # regex, decompose, cover, genericize
    CRYPTOGRAPHIC = 2      # TEE, MPC, split inference, PIR
    AI_NATIVE = 3          # semantic sanitize, obfuscate, distill


class AdversaryCapability(Enum):
    """What the adversary can do."""
    PASSIVE_OBSERVER = auto()       # reads query logs
    ANALYTICS_CORRELATION = auto()  # links queries to chain activity
    ACTIVE_RESPONSE = auto()        # modifies responses to fingerprint
    MODEL_ACCESS = auto()           # knows the model architecture
    MULTI_PROVIDER_COLLUDE = auto() # multiple providers share data
    NATION_STATE = auto()           # unlimited resources


class PrivacyProperty(Enum):
    """What privacy guarantee a tool provides."""
    PARAM_HIDING = auto()           # strips format-matchable params
    SEMANTIC_HIDING = auto()        # hides meaning, not just format
    TOPIC_HIDING = auto()           # hides what domain/topic
    IDENTITY_HIDING = auto()        # hides who is asking
    QUERY_UNLINKABILITY = auto()    # queries can't be linked to same user
    COMPUTATIONAL_PRIVACY = auto()  # cloud can't see data at all (crypto)
    INFORMATION_THEORETIC = auto()  # provably no information leaked


class HardwareRequirement(Enum):
    """What hardware a tool needs."""
    BROWSER_ONLY = auto()      # runs in browser, no backend
    LOCAL_CPU = auto()          # needs local CPU (regex, simple ops)
    LOCAL_LLM_7B = auto()       # needs 7B+ local model
    LOCAL_LLM_14B = auto()      # needs 14B+ local model
    LOCAL_LLM_70B = auto()      # needs 70B+ local model
    LOCAL_GPU = auto()          # needs local GPU
    TEE_CLOUD = auto()          # needs TEE-capable cloud
    MPC_MULTI_SERVER = auto()   # needs N non-colluding servers


# ---------------------------------------------------------------------------
# Core data structures
# ---------------------------------------------------------------------------

@dataclass
class ToolSpec:
    """A privacy tool's declared specification.

    Tools register their properties, requirements, and costs.
    The compiler uses these to select and compose tools.
    """
    name: str
    layer: Layer
    description: str

    # What this tool provides
    provides: set[PrivacyProperty] = field(default_factory=set)

    # What adversary capabilities this tool defends against
    defends_against: set[AdversaryCapability] = field(default_factory=set)

    # What this tool requires
    hardware: HardwareRequirement = HardwareRequirement.BROWSER_ONLY
    requires_profile: bool = False          # needs a domain profile
    requires_local_llm: bool = False        # needs a local LLM

    # Cost estimates
    latency_ms: int = 0                     # added latency per query
    cost_per_query_usd: float = 0.0         # marginal cost
    setup_cost_usd: float = 0.0             # one-time cost

    # Quality impact
    utility_retention: float = 1.0          # 0-1, how much answer quality preserved
    false_positive_rate: float = 0.0        # how much benign data gets stripped

    # Composability
    input_type: str = "text"                # what it takes
    output_type: str = "text"               # what it produces
    composable_after: list[str] = field(default_factory=list)   # tools that can precede
    composable_before: list[str] = field(default_factory=list)  # tools that can follow


@dataclass
class ThreatModel:
    """Describes the adversary and what needs protecting."""
    adversary: set[AdversaryCapability] = field(default_factory=lambda: {
        AdversaryCapability.PASSIVE_OBSERVER,
    })
    protect: set[PrivacyProperty] = field(default_factory=lambda: {
        PrivacyProperty.PARAM_HIDING,
    })
    # Domain context
    domain: str = "unknown"
    sensitivity_level: str = "standard"  # "standard", "high", "critical"


@dataclass
class Constraints:
    """What the user has available."""
    hardware: HardwareRequirement = HardwareRequirement.BROWSER_ONLY
    max_latency_ms: int = 5000              # per-query latency budget
    max_cost_per_query_usd: float = 0.01    # per-query cost budget
    local_model_size_b: int = 0             # local model size in billions (0 = none)
    has_tee: bool = False
    has_mpc_servers: int = 0                # number of MPC servers available
    profile_path: str | None = None         # domain profile if available


@dataclass
class PipelineStep:
    """One step in a composed pipeline."""
    tool: ToolSpec
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class CompiledPipeline:
    """The output of the compiler — a composed privacy pipeline."""
    steps: list[PipelineStep]
    threat_model: ThreatModel
    constraints: Constraints

    # Combined guarantees
    provides: set[PrivacyProperty] = field(default_factory=set)
    defends_against: set[AdversaryCapability] = field(default_factory=set)

    # Combined costs
    total_latency_ms: int = 0
    total_cost_per_query_usd: float = 0.0
    estimated_utility_retention: float = 1.0

    # What's NOT covered
    residual_risks: list[str] = field(default_factory=list)
    unmet_requirements: list[str] = field(default_factory=list)
