"""Level 4: Color Agent - Worker agent with DISC personality.

Each color agent evaluates a task from its unique perspective using Claude API.
Falls back to placeholder responses if Claude is unavailable.
"""

from __future__ import annotations

import logging
from importlib import import_module

from core.llm import call_claude_json
from core.state import AgentResponse, ColorAgent, DepartmentName

logger = logging.getLogger(__name__)


def _load_persona(color: str) -> dict:
    """Load persona config and system prompt for a color agent."""
    module = import_module(f"personas.{color}")
    return {
        "system_prompt": module.SYSTEM_PROMPT,
        "config": module.AGENT_CONFIG,
    }


def _load_department_context(department: str, color: str) -> str:
    """Load department-specific context for a color agent."""
    try:
        module = import_module(f"departments.{department}")
        return module.DEPARTMENT_CONFIG.get("color_agent_context", {}).get(color, "")
    except (ImportError, AttributeError):
        return ""


class ColorAgentRunner:
    """Runs a single color agent against a task objective."""

    def __init__(self, color: ColorAgent, department: DepartmentName) -> None:
        self.color = color
        self.department = department
        self.persona = _load_persona(color.value)
        self.dept_context = _load_department_context(department.value, color.value)

    async def execute(
        self,
        objective: str,
        context: str = "",
        previous_responses: list[AgentResponse] | None = None,
    ) -> AgentResponse:
        """Execute the agent on a given objective.

        Args:
            objective: What the agent should work on.
            context: Additional context from the Head of Department.
            previous_responses: Responses from agents that ran before this one.

        Returns:
            The agent's response with key points, concerns, and recommendations.
        """
        logger.info(
            "ColorAgent %s/%s executing: %.80s...",
            self.color.value,
            self.department.value,
            objective,
        )

        # Build system prompt
        system = self.persona["system_prompt"]
        if self.dept_context:
            system += f"\n\nDein Abteilungskontext: {self.dept_context}"

        # Build user prompt with previous agent responses
        user_parts = [
            f"## Aufgabe\n{objective}",
        ]

        if context:
            user_parts.append(f"\n## Zusaetzlicher Kontext\n{context}")

        if previous_responses:
            user_parts.append("\n## Bisherige Team-Analysen")
            for resp in previous_responses:
                user_parts.append(
                    f"\n### {resp.agent_color.value.upper()} Agent:\n"
                    f"{resp.content}\n"
                    f"Kernpunkte: {', '.join(resp.key_points)}\n"
                    f"Bedenken: {', '.join(resp.concerns)}"
                )

        user_parts.append(
            "\n## Dein Output\n"
            "Analysiere die Aufgabe aus deiner Perspektive. "
            "Beruecksichtige die bisherigen Analysen deiner Teamkollegen.\n\n"
            "Antworte als JSON:\n"
            '{"content": "<deine ausfuehrliche Analyse>",\n'
            ' "key_points": ["<Kernpunkt 1>", "<Kernpunkt 2>", ...],\n'
            ' "concerns": ["<Bedenken 1>", ...],\n'
            ' "recommendations": ["<Empfehlung 1>", ...],\n'
            ' "confidence": <0.0 bis 1.0>}'
        )

        config = self.persona["config"]

        try:
            result = await call_claude_json(
                system_prompt=system,
                user_prompt="\n".join(user_parts),
                temperature=config.get("temperature", 0.7),
                max_tokens=config.get("max_tokens", 2048),
            )

            return AgentResponse(
                agent_color=self.color,
                department=self.department,
                content=result.get("content", ""),
                key_points=result.get("key_points", []),
                concerns=result.get("concerns", []),
                recommendations=result.get("recommendations", []),
                confidence=min(1.0, max(0.0, float(result.get("confidence", 0.7)))),
            )

        except Exception as e:
            logger.warning(
                "ColorAgent %s/%s failed, returning fallback: %s",
                self.color.value,
                self.department.value,
                e,
            )
            return AgentResponse(
                agent_color=self.color,
                department=self.department,
                content=f"[FEHLER] Agent {self.color.value} konnte nicht antworten: {e}",
                key_points=[],
                concerns=[f"Agent-Fehler: {e}"],
                recommendations=["Erneut versuchen oder manuell bearbeiten"],
                confidence=0.0,
            )
