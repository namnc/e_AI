"""
LLM-powered transaction risk analyzer.

Mirrors e_AI's llm_backend.py + analyzer pattern. The LLM reads the domain
profile and user's transaction context, then produces natural language risk
assessments that go beyond rule-based checks.

The rule-based analyzer (analyzer.py) catches known patterns.
The LLM analyzer catches behavioral patterns, temporal correlations,
and provides natural language explanations.

Usage:
    from core.llm_analyzer import LLMAnalyzer

    analyzer = LLMAnalyzer(profile, backend="ollama", model="qwen2.5:7b")
    result = analyzer.analyze(tx, user_history)
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

log = logging.getLogger("e_ai.llm_analyzer")


class LLMAnalyzer:
    """LLM-powered risk analysis for stealth address transactions."""

    def __init__(
        self,
        profile: dict,
        backend: str = "ollama",
        model: str | None = None,
    ):
        self.profile = profile
        self.backend = backend
        self.model = model or self._default_model(backend)
        self._client = None
        self.available = False
        self.unavailable_reason: str | None = None

    def is_available(self) -> bool:
        """Whether the LLM backend is reachable. Returns False after a failed connect()."""
        return self.available

    def _default_model(self, backend: str) -> str:
        if backend == "ollama":
            return "qwen2.5:7b"
        elif backend == "anthropic":
            return "claude-haiku-4-5-20251001"
        else:
            raise ValueError(f"Unknown backend: {backend}")

    def connect(self, raise_on_failure: bool = False) -> bool:
        """Initialize the LLM backend connection.

        Returns True on success, False on graceful degradation. With
        raise_on_failure=True, retains pre-2026-05-07 behavior of raising
        RuntimeError. Default is graceful: callers check is_available() and
        analyze() falls back to a rule-based-only result.
        """
        if self.backend == "ollama":
            import httpx
            try:
                resp = httpx.get("http://localhost:11434/api/tags", timeout=5)
                resp.raise_for_status()
                available_models = [m["name"] for m in resp.json().get("models", [])]
            except (httpx.HTTPError, OSError) as e:
                # Network / daemon unreachable.
                msg = f"Cannot reach Ollama at localhost:11434 ({e}). Try: ollama serve"
                log.warning(msg)
                self.unavailable_reason = msg
                if raise_on_failure:
                    raise RuntimeError(msg)
                return False

            if not any(self.model in name for name in available_models):
                msg = f"Model '{self.model}' not found in Ollama. Available: {available_models}. Try: ollama pull {self.model}"
                log.warning(msg)
                self.unavailable_reason = msg
                if raise_on_failure:
                    raise RuntimeError(msg)
                return False

            self._client = httpx.Client(timeout=120)

        elif self.backend == "anthropic":
            try:
                import anthropic
                api_key = os.environ.get("ANTHROPIC_API_KEY")
                if not api_key:
                    msg = "ANTHROPIC_API_KEY not set"
                    log.warning(msg)
                    self.unavailable_reason = msg
                    if raise_on_failure:
                        raise RuntimeError(msg)
                    return False
                self._client = anthropic.Anthropic(api_key=api_key)
            except ImportError as e:
                msg = f"anthropic SDK not installed ({e})"
                log.warning(msg)
                self.unavailable_reason = msg
                if raise_on_failure:
                    raise RuntimeError(msg)
                return False

        self.available = True
        log.info(f"LLM backend: {self.backend} | Model: {self.model}")
        return True

    def analyze(
        self,
        tx: dict,
        user_history: list[dict] | None = None,
        rule_based_alerts: list[dict] | None = None,
    ) -> dict:
        """Analyze a transaction using the LLM.

        Args:
            tx: Transaction data (amount, addresses, timestamps, gas, etc.)
            user_history: Optional list of prior transactions for behavioral analysis
            rule_based_alerts: Optional alerts from the rule-based analyzer

        Returns:
            Dict with: risk_level, explanation, recommendations, behavioral_notes,
            and degraded_mode (True if LLM unavailable; result is rule-based-only).
        """
        if not self.available:
            return self._degraded_result(rule_based_alerts)

        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(tx, user_history, rule_based_alerts)

        try:
            response = self._call_llm(system_prompt, user_prompt)
        except Exception as e:
            log.warning(f"LLM call failed mid-flight ({e}); returning degraded result")
            self.available = False
            self.unavailable_reason = str(e)
            return self._degraded_result(rule_based_alerts)

        result = self._parse_response(response)
        result["degraded_mode"] = False
        return result

    def _degraded_result(self, rule_based_alerts: list[dict] | None) -> dict:
        """Synthesize a result from rule-based alerts when LLM is unavailable.

        The contract is preserved (same keys); the caller can detect degraded
        mode via the degraded_mode key. risk_level is the highest severity from
        the rule-based alerts; recommendations are pulled directly.
        """
        severity_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        risk = "unknown"
        recs: list[str] = []
        explanation = "LLM analysis unavailable; showing rule-based detection only."

        if rule_based_alerts:
            top = max(
                rule_based_alerts,
                key=lambda a: severity_order.get(a.get("severity", "").lower(), 0),
                default=None,
            )
            if top is not None:
                risk = top.get("severity", "unknown").lower()
            for a in rule_based_alerts:
                rec = a.get("recommendation")
                if rec and rec not in recs:
                    recs.append(rec)
            if recs:
                explanation = f"Rule-based detection found {len(rule_based_alerts)} alert(s); LLM behavioral analysis unavailable."

        return {
            "risk_level": risk,
            "explanation": explanation,
            "recommendations": recs,
            "behavioral_notes": "skipped (LLM unavailable)",
            "raw_response": "",
            "degraded_mode": True,
            "degraded_reason": self.unavailable_reason or "LLM backend not available",
        }

    def _build_system_prompt(self) -> str:
        """Build system prompt from profile."""
        meta = self.profile.get("meta", {})
        heuristics = self.profile.get("heuristics", {})

        heuristic_descriptions = []
        for hname, h in heuristics.items():
            heuristic_descriptions.append(
                f"- {h['id']} ({h['name']}): {h['description']} "
                f"[severity: {h['severity']}]"
            )

        return f"""You are a privacy advisor for Ethereum stealth address transactions.
Your role is to analyze transactions BEFORE they are submitted and flag privacy risks.

Domain: {meta.get('domain_name', 'stealth_address_ops')}
Source: {meta.get('source_paper', 'arxiv 2308.01703')}
Baseline deanonymization rate: {meta.get('baseline_deanon_rate', 0.485):.1%}

You check for these deanonymization heuristics:
{chr(10).join(heuristic_descriptions)}

Rules:
1. Be specific. Say WHAT is wrong and WHY it matters.
2. Give actionable recommendations. Say WHAT to do, not just "be careful."
3. If multiple heuristics combine, explain the compound risk.
4. Note fundamental limitations honestly (e.g., small anonymity set).
5. Keep responses under 200 words.

Output format:
RISK: <critical|high|medium|low>
EXPLANATION: <what's wrong, 1-2 sentences>
RECOMMENDATIONS: <numbered list>
BEHAVIORAL: <any patterns from history, or "none">"""

    def _build_user_prompt(
        self,
        tx: dict,
        user_history: list[dict] | None,
        rule_based_alerts: list[dict] | None,
    ) -> str:
        """Build user prompt from transaction + context."""
        parts = [f"Analyze this stealth address transaction:\n{json.dumps(tx, indent=2)}"]

        if rule_based_alerts:
            parts.append(f"\nRule-based alerts already triggered:\n{json.dumps(rule_based_alerts, indent=2)}")

        if user_history:
            parts.append(f"\nUser's recent transaction history ({len(user_history)} txs):\n{json.dumps(user_history[-10:], indent=2)}")

        return "\n".join(parts)

    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """Call the LLM backend."""
        if not self._client:
            raise RuntimeError("Call connect() first")

        if self.backend == "ollama":
            resp = self._client.post(
                "http://localhost:11434/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "stream": False,
                },
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"]

        elif self.backend == "anthropic":
            message = self._client.messages.create(
                model=self.model,
                max_tokens=500,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return message.content[0].text

    def _parse_response(self, response: str) -> dict:
        """Parse LLM response into structured output."""
        result = {
            "risk_level": "unknown",
            "explanation": "",
            "recommendations": [],
            "behavioral_notes": "",
            "raw_response": response,
        }

        for line in response.strip().split("\n"):
            line = line.strip()
            if line.startswith("RISK:"):
                result["risk_level"] = line.split(":", 1)[1].strip().lower()
            elif line.startswith("EXPLANATION:"):
                result["explanation"] = line.split(":", 1)[1].strip()
            elif line.startswith("BEHAVIORAL:"):
                result["behavioral_notes"] = line.split(":", 1)[1].strip()
            elif line and line[0].isdigit() and "." in line[:3]:
                result["recommendations"].append(line.split(".", 1)[1].strip())

        return result
