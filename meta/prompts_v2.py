"""
LLM prompts for the meta-framework profile generation pipeline.

Mirrors e_AI's meta/prompts.py pattern. Each prompt is a template that
the analyzer fills with context from the dataset.
"""

HEURISTIC_EXTRACTION = """Analyze these blockchain transaction incidents and identify recurring deanonymization or risk heuristics.

For each heuristic found, provide:
- name: short descriptive name
- description: what the heuristic detects (1-2 sentences)
- severity: critical / high / medium / low
- incidents_matched: how many of the incidents below match this heuristic

Incidents:
{incidents}

Respond with a JSON array of heuristic objects. Example:
[
  {{
    "name": "timing correlation",
    "description": "Spending from a private address shortly after receiving narrows the anonymity set",
    "severity": "critical",
    "incidents_matched": 5
  }}
]"""

SIGNAL_EXTRACTION = """For the heuristic "{heuristic_name}" ({heuristic_description}), extract detection signals from these examples.

Each signal should have:
- name: short identifier (snake_case)
- description: what data pattern to look for
- data_needed: list of data fields required
- confidence: probability that this signal correctly identifies the risk (0.0-1.0)

Examples of this heuristic in practice:
{examples}

Respond with a JSON array of signal objects. Aim for 2-4 signals per heuristic."""

RECOMMENDATION_GENERATION = """For the heuristic "{heuristic_name}" ({heuristic_description}), generate countermeasure recommendations.

Detection signals for this heuristic:
{signals}

Each recommendation should have:
- action: short identifier (snake_case)
- description: what the user should do (1 sentence)
- effectiveness: estimated risk reduction (0.0-1.0)
- user_cost: "none" / "low" / "medium" / "high"
- skill_required: name of automated tool needed (or null if manual)

Respond with a JSON array of recommendation objects. Include both automated and manual countermeasures."""

SEVERITY_CLASSIFICATION = """Classify the severity of this heuristic: "{heuristic_name}"

Description: {heuristic_description}
Detection signals: {signals}

Severity levels:
- critical: deterministic deanonymization or high-confidence identity reveal
- high: significant privacy degradation, narrows anonymity set substantially
- medium: partial information leak, requires combination with other heuristics
- low: minor metadata leak, unlikely to lead to deanonymization alone

Respond with a single JSON object: {{"severity": "critical|high|medium|low", "reason": "..."}}"""

SKILL_EXTRACTION = """Define these privacy/security tools that can be used as countermeasures:

Skill names: {skill_names}

For each skill, provide:
- tool: what system/API it uses
- description: what it does (1 sentence)
- parameters: key configuration parameters as a JSON object

Respond with a JSON object where keys are skill names and values are skill definitions."""
