"""
Tool registry — all available privacy protection tools with their specifications.

Each tool declares its properties, requirements, and costs.
The compiler selects from this registry based on the threat model.

Tools are organized by layer:
  Layer 1: Query transformation (implemented in this repo)
  Layer 2: Cryptographic infrastructure (external, declared for composition)
  Layer 3: AI-native privacy (research, declared for future composition)
"""

from compiler.types import (
    ToolSpec, Layer, PrivacyProperty, AdversaryCapability, HardwareRequirement,
)


# ---------------------------------------------------------------------------
# Layer 1: Query Transformation (implemented)
# ---------------------------------------------------------------------------

REGEX_SANITIZER = ToolSpec(
    name="regex_sanitizer",
    layer=Layer.QUERY_TRANSFORM,
    description="Strip format-matchable private parameters (amounts, addresses, "
                "percentages, timing, emotional language) via regex patterns "
                "loaded from a domain profile.",
    provides={PrivacyProperty.PARAM_HIDING},
    defends_against={AdversaryCapability.PASSIVE_OBSERVER},
    hardware=HardwareRequirement.BROWSER_ONLY,
    requires_profile=True,
    latency_ms=1,
    utility_retention=0.5,  # amounts lost, structure preserved
    input_type="text",
    output_type="text",
    composable_before=["llm_decomposer", "genericizer", "cover_generator"],
)

LLM_DECOMPOSER = ToolSpec(
    name="llm_decomposer",
    layer=Layer.QUERY_TRANSFORM,
    description="Decompose a user query into 2-3 generic sub-queries using a "
                "local LLM. Private parameters stay local; only mechanism "
                "questions go to cloud.",
    provides={PrivacyProperty.PARAM_HIDING, PrivacyProperty.TOPIC_HIDING},
    defends_against={
        AdversaryCapability.PASSIVE_OBSERVER,
        AdversaryCapability.ANALYTICS_CORRELATION,
    },
    hardware=HardwareRequirement.LOCAL_LLM_14B,
    requires_local_llm=True,
    requires_profile=True,
    latency_ms=2000,
    utility_retention=0.85,
    input_type="text",
    output_type="sub_queries",
    composable_after=["regex_sanitizer"],
    composable_before=["genericizer", "cover_generator"],
)

GENERICIZER = ToolSpec(
    name="genericizer",
    layer=Layer.QUERY_TRANSFORM,
    description="Strip protocol/entity names from sub-queries, replacing with "
                "generic domain references. Preserves mechanism questions.",
    provides={PrivacyProperty.PARAM_HIDING},
    defends_against={AdversaryCapability.PASSIVE_OBSERVER},
    hardware=HardwareRequirement.LOCAL_CPU,
    requires_profile=True,
    latency_ms=1,
    utility_retention=0.95,
    input_type="sub_queries",
    output_type="sub_queries",
    composable_after=["llm_decomposer"],
    composable_before=["cover_generator"],
)

COVER_GENERATOR = ToolSpec(
    name="cover_generator",
    layer=Layer.QUERY_TRANSFORM,
    description="Generate k-1 template-filled cover queries from other subdomains. "
                "Provides k-plausible deniability when combined with transport "
                "unlinkability.",
    provides={PrivacyProperty.TOPIC_HIDING, PrivacyProperty.QUERY_UNLINKABILITY},
    defends_against={
        AdversaryCapability.PASSIVE_OBSERVER,
        AdversaryCapability.ANALYTICS_CORRELATION,
    },
    hardware=HardwareRequirement.LOCAL_CPU,
    requires_profile=True,
    latency_ms=5,
    utility_retention=1.0,  # covers don't affect real query's answer
    input_type="sub_queries",
    output_type="query_sets",
    composable_after=["genericizer"],
)

TOR_TRANSPORT = ToolSpec(
    name="tor_transport",
    layer=Layer.QUERY_TRANSFORM,
    description="Send each query in a cover set via a different Tor circuit. "
                "Provides transport unlinkability — cloud can't link queries "
                "to the same user.",
    provides={PrivacyProperty.IDENTITY_HIDING, PrivacyProperty.QUERY_UNLINKABILITY},
    defends_against={
        AdversaryCapability.PASSIVE_OBSERVER,
        AdversaryCapability.ANALYTICS_CORRELATION,
    },
    hardware=HardwareRequirement.LOCAL_CPU,
    latency_ms=3000,
    input_type="query_sets",
    output_type="query_sets",
    composable_after=["cover_generator"],
)

LOCAL_SYNTHESIZER = ToolSpec(
    name="local_synthesizer",
    layer=Layer.QUERY_TRANSFORM,
    description="Local LLM synthesizes final answer from sub-query responses "
                "and private parameters. Private data never leaves device.",
    provides={PrivacyProperty.PARAM_HIDING},
    defends_against={AdversaryCapability.PASSIVE_OBSERVER},
    hardware=HardwareRequirement.LOCAL_LLM_14B,
    requires_local_llm=True,
    latency_ms=3000,
    utility_retention=0.85,
    input_type="answers",
    output_type="text",
    composable_after=["cover_generator", "tor_transport"],
)

# ---------------------------------------------------------------------------
# Layer 2: Cryptographic Infrastructure (declared, not implemented)
# ---------------------------------------------------------------------------

TEE_INFERENCE = ToolSpec(
    name="tee_inference",
    layer=Layer.CRYPTOGRAPHIC,
    description="Run cloud LLM inside a Trusted Execution Environment (SGX, TDX, "
                "SEV-SNP). Cloud operator cannot inspect queries or responses. "
                "Requires remote attestation.",
    provides={PrivacyProperty.COMPUTATIONAL_PRIVACY},
    defends_against={
        AdversaryCapability.PASSIVE_OBSERVER,
        AdversaryCapability.ANALYTICS_CORRELATION,
        AdversaryCapability.ACTIVE_RESPONSE,
    },
    hardware=HardwareRequirement.TEE_CLOUD,
    latency_ms=500,
    cost_per_query_usd=0.005,
    utility_retention=1.0,  # no quality loss
    input_type="text",
    output_type="text",
)

SPLIT_INFERENCE = ToolSpec(
    name="split_inference",
    layer=Layer.CRYPTOGRAPHIC,
    description="Run embedding layers locally, send intermediate activations "
                "to cloud. Activations are less interpretable than raw text.",
    provides={PrivacyProperty.PARAM_HIDING, PrivacyProperty.SEMANTIC_HIDING},
    defends_against={
        AdversaryCapability.PASSIVE_OBSERVER,
    },
    hardware=HardwareRequirement.LOCAL_GPU,
    latency_ms=1000,
    utility_retention=0.90,
    input_type="text",
    output_type="text",
)

MPC_INFERENCE = ToolSpec(
    name="mpc_inference",
    layer=Layer.CRYPTOGRAPHIC,
    description="Split query across N non-colluding servers via Secure Multi-Party "
                "Computation. No single server sees the full query. "
                "Information-theoretic security.",
    provides={
        PrivacyProperty.COMPUTATIONAL_PRIVACY,
        PrivacyProperty.INFORMATION_THEORETIC,
    },
    defends_against={
        AdversaryCapability.PASSIVE_OBSERVER,
        AdversaryCapability.ANALYTICS_CORRELATION,
        AdversaryCapability.ACTIVE_RESPONSE,
        AdversaryCapability.MODEL_ACCESS,
    },
    hardware=HardwareRequirement.MPC_MULTI_SERVER,
    latency_ms=10000,
    cost_per_query_usd=0.05,
    utility_retention=1.0,
    input_type="text",
    output_type="text",
)

PRIVATE_INFORMATION_RETRIEVAL = ToolSpec(
    name="pir",
    layer=Layer.CRYPTOGRAPHIC,
    description="Retrieve relevant context from a cloud knowledge base without "
                "revealing which records were accessed. For RAG architectures.",
    provides={PrivacyProperty.QUERY_UNLINKABILITY},
    defends_against={
        AdversaryCapability.PASSIVE_OBSERVER,
    },
    hardware=HardwareRequirement.LOCAL_CPU,
    latency_ms=2000,
    input_type="text",
    output_type="context",
)

# ---------------------------------------------------------------------------
# Layer 3: AI-Native Privacy (research, declared for future composition)
# ---------------------------------------------------------------------------

SEMANTIC_SANITIZER = ToolSpec(
    name="semantic_sanitizer",
    layer=Layer.AI_NATIVE,
    description="NER + paraphrase model that removes meaning, not just format. "
                "Catches 'whale-sized position', 'near liquidation', and other "
                "semantic leaks that regex misses.",
    provides={PrivacyProperty.PARAM_HIDING, PrivacyProperty.SEMANTIC_HIDING},
    defends_against={
        AdversaryCapability.PASSIVE_OBSERVER,
        AdversaryCapability.ANALYTICS_CORRELATION,
    },
    hardware=HardwareRequirement.LOCAL_LLM_7B,
    requires_local_llm=True,
    latency_ms=500,
    utility_retention=0.70,
    input_type="text",
    output_type="text",
    composable_before=["llm_decomposer", "genericizer"],
)

PROMPT_OBFUSCATOR = ToolSpec(
    name="prompt_obfuscator",
    layer=Layer.AI_NATIVE,
    description="Rewrite query to preserve the answer while hiding intent. "
                "Transforms specific questions into equivalent generic ones.",
    provides={PrivacyProperty.SEMANTIC_HIDING, PrivacyProperty.TOPIC_HIDING},
    defends_against={
        AdversaryCapability.PASSIVE_OBSERVER,
        AdversaryCapability.MODEL_ACCESS,
    },
    hardware=HardwareRequirement.LOCAL_LLM_14B,
    requires_local_llm=True,
    latency_ms=2000,
    utility_retention=0.75,
    input_type="text",
    output_type="text",
)

LOCAL_DISTILLATION = ToolSpec(
    name="local_distillation",
    layer=Layer.AI_NATIVE,
    description="Distill cloud model capabilities for the user's specific domain "
                "into a local model. Zero cloud exposure after distillation.",
    provides={
        PrivacyProperty.COMPUTATIONAL_PRIVACY,
        PrivacyProperty.INFORMATION_THEORETIC,
    },
    defends_against={
        AdversaryCapability.PASSIVE_OBSERVER,
        AdversaryCapability.ANALYTICS_CORRELATION,
        AdversaryCapability.ACTIVE_RESPONSE,
        AdversaryCapability.MODEL_ACCESS,
        AdversaryCapability.MULTI_PROVIDER_COLLUDE,
        AdversaryCapability.NATION_STATE,
    },
    hardware=HardwareRequirement.LOCAL_LLM_70B,
    requires_local_llm=True,
    setup_cost_usd=100.0,  # training cost
    latency_ms=3000,
    utility_retention=0.70,
    input_type="text",
    output_type="text",
)

ADVERSARIAL_EMBEDDINGS = ToolSpec(
    name="adversarial_embeddings",
    layer=Layer.AI_NATIVE,
    description="Add perturbations to token embeddings that preserve semantic "
                "content for the model but confuse reconstruction attacks.",
    provides={PrivacyProperty.SEMANTIC_HIDING},
    defends_against={
        AdversaryCapability.PASSIVE_OBSERVER,
        AdversaryCapability.MODEL_ACCESS,
    },
    hardware=HardwareRequirement.LOCAL_GPU,
    latency_ms=100,
    utility_retention=0.85,
    input_type="embeddings",
    output_type="embeddings",
)

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

ALL_TOOLS: dict[str, ToolSpec] = {
    # Layer 1
    "regex_sanitizer": REGEX_SANITIZER,
    "llm_decomposer": LLM_DECOMPOSER,
    "genericizer": GENERICIZER,
    "cover_generator": COVER_GENERATOR,
    "tor_transport": TOR_TRANSPORT,
    "local_synthesizer": LOCAL_SYNTHESIZER,
    # Layer 2
    "tee_inference": TEE_INFERENCE,
    "split_inference": SPLIT_INFERENCE,
    "mpc_inference": MPC_INFERENCE,
    "pir": PRIVATE_INFORMATION_RETRIEVAL,
    # Layer 3
    "semantic_sanitizer": SEMANTIC_SANITIZER,
    "prompt_obfuscator": PROMPT_OBFUSCATOR,
    "local_distillation": LOCAL_DISTILLATION,
    "adversarial_embeddings": ADVERSARIAL_EMBEDDINGS,
}

LAYER_1_TOOLS = {k: v for k, v in ALL_TOOLS.items() if v.layer == Layer.QUERY_TRANSFORM}
LAYER_2_TOOLS = {k: v for k, v in ALL_TOOLS.items() if v.layer == Layer.CRYPTOGRAPHIC}
LAYER_3_TOOLS = {k: v for k, v in ALL_TOOLS.items() if v.layer == Layer.AI_NATIVE}
