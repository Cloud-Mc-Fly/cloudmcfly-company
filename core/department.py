"""Level 3: Head of Department - Orchestrates the 4 color agents.

The Head receives a SubTask from the Router, runs Yellow > Blue > Green > Red,
reviews results with Claude, and produces 1-2 final SolutionOptions.
Max 3 iterations with review loop.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from importlib import import_module

from config import COLOR_AGENT_ORDER, DEPARTMENTS, MAX_DEPARTMENT_ITERATIONS
from core.agent import ColorAgentRunner
from core.llm import call_claude, call_claude_json
from core.state import (
    AgentResponse,
    ColorAgent,
    DepartmentName,
    DepartmentResult,
    DepartmentStatus,
    SolutionOption,
    SubTask,
)

logger = logging.getLogger(__name__)


class DepartmentHead:
    """Orchestrates a department's 4 color agents with Claude-powered review."""

    def __init__(self, department: DepartmentName) -> None:
        self.department = department
        self.agents = {
            color: ColorAgentRunner(ColorAgent(color), department)
            for color in COLOR_AGENT_ORDER
        }
        self.max_iterations = MAX_DEPARTMENT_ITERATIONS
        self.dept_config = DEPARTMENTS.get(department.value, {})

    async def run_pipeline(self, sub_task: SubTask) -> DepartmentResult:
        """Run the full department pipeline for a sub-task.

        Sequence: Yellow (ideation) > Blue (critique) > Green (UX) > Red (execution)
        Head reviews after each full cycle. Max 3 iterations.

        Args:
            sub_task: The work package from the Router.

        Returns:
            Aggregated DepartmentResult with 1-2 solution options.
        """
        logger.info(
            "Department %s: Starting pipeline for: %.80s...",
            self.department.value,
            sub_task.objective,
        )

        result = DepartmentResult(
            department=self.department,
            status=DepartmentStatus.IN_PROGRESS,
        )

        for iteration in range(self.max_iterations):
            result.iteration_count = iteration + 1
            responses: list[AgentResponse] = []

            # Run agents in DISC order: Yellow > Blue > Green > Red
            for color_name in COLOR_AGENT_ORDER:
                agent = self.agents[color_name]
                response = await agent.execute(
                    objective=sub_task.objective,
                    context=sub_task.context,
                    previous_responses=responses,
                )
                responses.append(response)

            result.agent_responses = responses

            # Head reviews the team's output
            review = await self._review_responses(sub_task, responses, iteration)

            if review["quality_sufficient"]:
                logger.info(
                    "Department %s: Review passed after iteration %d",
                    self.department.value,
                    iteration + 1,
                )
                break

            if iteration < self.max_iterations - 1:
                logger.info(
                    "Department %s: Review failed, iteration %d/%d. Feedback: %s",
                    self.department.value,
                    iteration + 1,
                    self.max_iterations,
                    review.get("feedback", ""),
                )
                # Update context with review feedback for next iteration
                sub_task = SubTask(
                    subtask_id=sub_task.subtask_id,
                    department=sub_task.department,
                    objective=sub_task.objective,
                    context=(
                        f"{sub_task.context}\n\n"
                        f"FEEDBACK AUS REVIEW (Iteration {iteration + 1}): "
                        f"{review.get('feedback', '')}"
                    ),
                    constraints=sub_task.constraints,
                    deliverables=sub_task.deliverables,
                    priority=sub_task.priority,
                )

        # Synthesize final options
        result.options = await self._synthesize_options(sub_task, result.agent_responses)
        result.summary = await self._create_summary(sub_task, result)
        result.status = DepartmentStatus.COMPLETED
        result.completed_at = datetime.now(timezone.utc)

        logger.info(
            "Department %s: Pipeline complete (%d iterations, %d options)",
            self.department.value,
            result.iteration_count,
            len(result.options),
        )
        return result

    async def _review_responses(
        self,
        sub_task: SubTask,
        responses: list[AgentResponse],
        iteration: int,
    ) -> dict:
        """Head reviews the team's responses using Claude.

        Returns dict with 'quality_sufficient' (bool) and 'feedback' (str).
        """
        head_persona = self.dept_config.get("head_persona", "")

        agent_summary = "\n\n".join(
            f"### {r.agent_color.value.upper()} Agent (Konfidenz: {r.confidence:.0%}):\n"
            f"{r.content}\n"
            f"Kernpunkte: {', '.join(r.key_points)}\n"
            f"Bedenken: {', '.join(r.concerns)}\n"
            f"Empfehlungen: {', '.join(r.recommendations)}"
            for r in responses
        )

        try:
            result = await call_claude_json(
                system_prompt=(
                    f"{head_persona}\n\n"
                    f"Du reviewst gerade die Arbeit deines 4-Farben-Teams. "
                    f"Pruefe ob die Analysen die Aufgabe ausreichend abdecken, "
                    f"ob es Widersprueche gibt, und ob die Qualitaet fuer den CEO reicht. "
                    f"Dies ist Iteration {iteration + 1} von maximal {self.max_iterations}."
                ),
                user_prompt=(
                    f"## Aufgabe\n{sub_task.objective}\n\n"
                    f"## Team-Ergebnisse\n{agent_summary}\n\n"
                    f"Bewerte die Qualitaet. Antworte als JSON:\n"
                    f'{{"quality_sufficient": true/false,\n'
                    f' "feedback": "<konkretes Feedback falls nicht ausreichend>",\n'
                    f' "strengths": ["<was gut war>"],\n'
                    f' "gaps": ["<was fehlt>"]}}'
                ),
                temperature=0.3,
            )
            return {
                "quality_sufficient": result.get("quality_sufficient", True),
                "feedback": result.get("feedback", ""),
                "strengths": result.get("strengths", []),
                "gaps": result.get("gaps", []),
            }

        except Exception as e:
            logger.warning("Review failed, accepting results: %s", e)
            return {"quality_sufficient": True, "feedback": ""}

    async def _synthesize_options(
        self,
        sub_task: SubTask,
        responses: list[AgentResponse],
    ) -> list[SolutionOption]:
        """Synthesize agent responses into 1-2 solution options using Claude."""
        head_persona = self.dept_config.get("head_persona", "")

        agent_summary = "\n\n".join(
            f"**{r.agent_color.value.upper()}:** {r.content}\n"
            f"Empfehlungen: {', '.join(r.recommendations)}"
            for r in responses
        )

        try:
            result = await call_claude_json(
                system_prompt=(
                    f"{head_persona}\n\n"
                    f"Erstelle aus den Team-Analysen 1-2 konkrete Loesungsoptionen "
                    f"fuer den CEO. Jede Option muss Pro/Contra, Aufwand, Kosten "
                    f"und Risikoniveau enthalten."
                ),
                user_prompt=(
                    f"## Aufgabe\n{sub_task.objective}\n\n"
                    f"## Team-Analysen\n{agent_summary}\n\n"
                    f"Antworte als JSON:\n"
                    f'{{"options": [\n'
                    f'  {{"title": "<Optionstitel>",\n'
                    f'   "description": "<Beschreibung>",\n'
                    f'   "pros": ["<Vorteil>"],\n'
                    f'   "cons": ["<Nachteil>"],\n'
                    f'   "estimated_effort": "<z.B. 3-5 Tage>",\n'
                    f'   "estimated_cost": "<z.B. 2.000 EUR>",\n'
                    f'   "risk_level": "<low|medium|high>",\n'
                    f'   "recommended": true/false}}\n'
                    f"]}}"
                ),
                temperature=0.4,
                max_tokens=2048,
            )

            options = []
            for opt_data in result.get("options", []):
                options.append(
                    SolutionOption(
                        title=opt_data.get("title", ""),
                        description=opt_data.get("description", ""),
                        pros=opt_data.get("pros", []),
                        cons=opt_data.get("cons", []),
                        estimated_effort=opt_data.get("estimated_effort", ""),
                        estimated_cost=opt_data.get("estimated_cost", ""),
                        risk_level=opt_data.get("risk_level", "medium"),
                        recommended=opt_data.get("recommended", False),
                    )
                )
            return options if options else [self._fallback_option(sub_task)]

        except Exception as e:
            logger.warning("Option synthesis failed: %s", e)
            return [self._fallback_option(sub_task)]

    def _fallback_option(self, sub_task: SubTask) -> SolutionOption:
        return SolutionOption(
            title=f"Standardloesung - {self.department.value.title()}",
            description=f"Manuelle Bearbeitung von: {sub_task.objective[:80]}",
            pros=["Sofort umsetzbar"],
            cons=["Automatisierte Analyse fehlgeschlagen"],
            estimated_effort="Manuell zu bewerten",
            risk_level="medium",
        )

    async def _create_summary(
        self,
        sub_task: SubTask,
        result: DepartmentResult,
    ) -> str:
        """Create executive summary from department results using Claude."""
        head_persona = self.dept_config.get("head_persona", "")

        agent_highlights = "\n".join(
            f"- {r.agent_color.value.upper()}: {', '.join(r.key_points[:2])}"
            for r in result.agent_responses
            if r.key_points
        )

        option_titles = ", ".join(o.title for o in result.options)

        try:
            summary = await call_claude(
                system_prompt=(
                    f"{head_persona}\n\n"
                    f"Fasse die Ergebnisse deiner Abteilung in 2-3 praegnanten "
                    f"Saetzen fuer den CEO zusammen. Kurz, klar, handlungsorientiert."
                ),
                user_prompt=(
                    f"Aufgabe: {sub_task.objective}\n"
                    f"Team-Highlights:\n{agent_highlights}\n"
                    f"Erstellte Optionen: {option_titles}\n"
                    f"Iterationen: {result.iteration_count}\n\n"
                    f"Schreibe die Zusammenfassung."
                ),
                temperature=0.4,
                max_tokens=512,
            )
            return summary

        except Exception as e:
            logger.warning("Summary creation failed: %s", e)
            return (
                f"Department {self.department.value}: "
                f"{len(result.agent_responses)} Agenten analysiert, "
                f"{len(result.options)} Option(en) erstellt, "
                f"{result.iteration_count} Iteration(en)."
            )
