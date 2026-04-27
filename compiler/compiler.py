"""
Privacy Protection Compiler — selects and composes privacy tools
based on threat model and hardware constraints.

Usage:
    from compiler.compiler import compile_pipeline
    from compiler.types import ThreatModel, Constraints, AdversaryCapability, PrivacyProperty

    threat = ThreatModel(
        adversary={AdversaryCapability.PASSIVE_OBSERVER, AdversaryCapability.ANALYTICS_CORRELATION},
        protect={PrivacyProperty.PARAM_HIDING, PrivacyProperty.TOPIC_HIDING},
        domain="defi",
    )
    constraints = Constraints(
        hardware=HardwareRequirement.LOCAL_LLM_14B,
        max_latency_ms=10000,
        local_model_size_b=14,
        profile_path="domains/defi/profile.json",
    )

    pipeline = compile_pipeline(threat, constraints)
    print(pipeline)
"""

from __future__ import annotations

from compiler.types import (
    ThreatModel, Constraints, CompiledPipeline, PipelineStep,
    ToolSpec, PrivacyProperty, AdversaryCapability, HardwareRequirement,
    Layer,
)
from compiler.tools import ALL_TOOLS


# Hardware capability ordering (higher = more capable)
_HW_LEVEL = {
    HardwareRequirement.BROWSER_ONLY: 0,
    HardwareRequirement.LOCAL_CPU: 1,
    HardwareRequirement.LOCAL_LLM_7B: 2,
    HardwareRequirement.LOCAL_LLM_14B: 3,
    HardwareRequirement.LOCAL_GPU: 4,
    HardwareRequirement.LOCAL_LLM_70B: 5,
    HardwareRequirement.TEE_CLOUD: 6,
    HardwareRequirement.MPC_MULTI_SERVER: 7,
}


def _hw_available(required: HardwareRequirement, available: Constraints) -> bool:
    """Check if the required hardware is available given constraints."""
    if required == HardwareRequirement.TEE_CLOUD:
        return available.has_tee
    if required == HardwareRequirement.MPC_MULTI_SERVER:
        return available.has_mpc_servers >= 3
    if required in (HardwareRequirement.LOCAL_LLM_7B,
                    HardwareRequirement.LOCAL_LLM_14B,
                    HardwareRequirement.LOCAL_LLM_70B):
        required_size = {
            HardwareRequirement.LOCAL_LLM_7B: 7,
            HardwareRequirement.LOCAL_LLM_14B: 14,
            HardwareRequirement.LOCAL_LLM_70B: 70,
        }[required]
        return available.local_model_size_b >= required_size
    # For BROWSER_ONLY, LOCAL_CPU, LOCAL_GPU — assume available
    return _HW_LEVEL.get(required, 0) <= _HW_LEVEL.get(available.hardware, 0)


def _candidate_tools(threat: ThreatModel, constraints: Constraints) -> list[ToolSpec]:
    """Filter tools that are both useful and feasible."""
    candidates = []
    for tool in ALL_TOOLS.values():
        # Must defend against at least one adversary capability we face
        if not tool.defends_against & threat.adversary:
            continue
        # Must provide at least one property we need
        if not tool.provides & threat.protect:
            continue
        # Must have the hardware
        if not _hw_available(tool.hardware, constraints):
            continue
        # Must fit latency budget (individually)
        if tool.latency_ms > constraints.max_latency_ms:
            continue
        # Must fit cost budget
        if tool.cost_per_query_usd > constraints.max_cost_per_query_usd:
            continue
        # If needs profile, must have one
        if tool.requires_profile and not constraints.profile_path:
            continue
        candidates.append(tool)
    return candidates


def _score_tool(tool: ToolSpec, threat: ThreatModel) -> float:
    """Score a tool by how much of the threat model it addresses."""
    property_coverage = len(tool.provides & threat.protect) / max(len(threat.protect), 1)
    adversary_coverage = len(tool.defends_against & threat.adversary) / max(len(threat.adversary), 1)
    utility = tool.utility_retention
    # Weighted: properties most important, then adversary, then utility
    return property_coverage * 0.5 + adversary_coverage * 0.3 + utility * 0.2


def _is_composable(pipeline: list[ToolSpec], next_tool: ToolSpec) -> bool:
    """Check if next_tool can be added after the current pipeline."""
    if not pipeline:
        return True
    last = pipeline[-1]
    # Check type compatibility
    if next_tool.composable_after and last.name not in next_tool.composable_after:
        # Not explicitly composable, but allow if types match
        if last.output_type != next_tool.input_type:
            return False
    return True


def compile_pipeline(
    threat: ThreatModel,
    constraints: Constraints,
) -> CompiledPipeline:
    """Compile a privacy protection pipeline from threat model and constraints.

    Selection strategy:
    1. Find all feasible tools (hardware, latency, cost)
    2. Score by threat coverage
    3. Greedily compose highest-scoring composable tools
    4. Check combined properties meet requirements
    5. Report residual risks for unmet requirements
    """
    candidates = _candidate_tools(threat, constraints)

    if not candidates:
        return CompiledPipeline(
            steps=[],
            threat_model=threat,
            constraints=constraints,
            residual_risks=["No feasible tools found for the given constraints"],
            unmet_requirements=[str(p) for p in threat.protect],
        )

    # Sort by score (highest first), then by layer (lower layers first for composition)
    scored = sorted(
        candidates,
        key=lambda t: (-_score_tool(t, threat), t.layer.value),
    )

    # Greedy composition: add tools while they fit and are composable
    selected: list[ToolSpec] = []
    total_latency = 0
    total_cost = 0.0
    covered_properties: set[PrivacyProperty] = set()
    covered_adversary: set[AdversaryCapability] = set()

    for tool in scored:
        # Skip if it would exceed budget
        if total_latency + tool.latency_ms > constraints.max_latency_ms:
            continue
        if total_cost + tool.cost_per_query_usd > constraints.max_cost_per_query_usd:
            continue
        # Skip if not composable with current pipeline
        if not _is_composable(selected, tool):
            continue
        # Skip if it adds no new coverage
        new_properties = tool.provides - covered_properties
        new_adversary = tool.defends_against - covered_adversary
        if not new_properties and not new_adversary:
            continue

        selected.append(tool)
        total_latency += tool.latency_ms
        total_cost += tool.cost_per_query_usd
        covered_properties |= tool.provides
        covered_adversary |= tool.defends_against

    # Build pipeline
    steps = [PipelineStep(tool=tool) for tool in selected]

    # Calculate combined utility (multiplicative)
    utility = 1.0
    for tool in selected:
        utility *= tool.utility_retention

    # Identify residual risks
    unmet_properties = threat.protect - covered_properties
    unmet_adversary = threat.adversary - covered_adversary
    residual_risks = []
    if unmet_properties:
        residual_risks.append(
            f"Unmet privacy properties: {', '.join(p.name for p in unmet_properties)}"
        )
    if unmet_adversary:
        residual_risks.append(
            f"Undefended adversary capabilities: {', '.join(a.name for a in unmet_adversary)}"
        )
    if PrivacyProperty.SEMANTIC_HIDING in threat.protect and \
       PrivacyProperty.SEMANTIC_HIDING not in covered_properties:
        residual_risks.append(
            "Semantic leaks possible — regex-only sanitization is format-bounded"
        )

    return CompiledPipeline(
        steps=steps,
        threat_model=threat,
        constraints=constraints,
        provides=covered_properties,
        defends_against=covered_adversary,
        total_latency_ms=total_latency,
        total_cost_per_query_usd=total_cost,
        estimated_utility_retention=round(utility, 4),
        residual_risks=residual_risks,
        unmet_requirements=[p.name for p in unmet_properties],
    )


def print_pipeline(pipeline: CompiledPipeline):
    """Pretty-print a compiled pipeline."""
    print("=" * 60)
    print("COMPILED PRIVACY PIPELINE")
    print("=" * 60)

    if not pipeline.steps:
        print("  No pipeline could be compiled.")
        print(f"  Residual risks: {pipeline.residual_risks}")
        return

    print(f"\n  Threat model:")
    print(f"    Adversary: {', '.join(a.name for a in pipeline.threat_model.adversary)}")
    print(f"    Protect: {', '.join(p.name for p in pipeline.threat_model.protect)}")

    print(f"\n  Pipeline ({len(pipeline.steps)} steps):")
    for i, step in enumerate(pipeline.steps):
        t = step.tool
        print(f"    {i+1}. [{t.layer.name}] {t.name}")
        print(f"       {t.description[:80]}...")
        print(f"       Provides: {', '.join(p.name for p in t.provides)}")
        print(f"       Latency: {t.latency_ms}ms | Utility: {t.utility_retention:.0%}")

    print(f"\n  Combined guarantees:")
    print(f"    Properties: {', '.join(p.name for p in pipeline.provides)}")
    print(f"    Defends: {', '.join(a.name for a in pipeline.defends_against)}")
    print(f"    Latency: {pipeline.total_latency_ms}ms")
    print(f"    Utility: {pipeline.estimated_utility_retention:.0%}")
    print(f"    Cost/query: ${pipeline.total_cost_per_query_usd:.4f}")

    if pipeline.residual_risks:
        print(f"\n  Residual risks:")
        for risk in pipeline.residual_risks:
            print(f"    - {risk}")

    if pipeline.unmet_requirements:
        print(f"\n  Unmet requirements:")
        for req in pipeline.unmet_requirements:
            print(f"    - {req}")

    print("=" * 60)
