"""Level 2: Central Router - Task classification, routing, and aggregation.

The Router is NOT a domain expert. It classifies tasks, creates sub-tasks,
routes to departments, and aggregates results.

Uses Claude API for intelligent classification and aggregation.
Falls back to keyword-based routing if Claude API is unavailable.
"""

from __future__ import annotations

import logging

from config import DEPARTMENTS
from core.llm import call_claude, call_claude_json
from core.state import (
    DepartmentName,
    Priority,
    Question,
    SolutionOption,
    SubTask,
    TaskType,
)

logger = logging.getLogger(__name__)

# Keyword fallback (used when Claude API is unavailable)
_KEYWORD_ROUTES: dict[str, DepartmentName] = {
    "linkedin": DepartmentName.MARKETING,
    "content": DepartmentName.MARKETING,
    "post": DepartmentName.MARKETING,
    "branding": DepartmentName.MARKETING,
    "lead": DepartmentName.SALES,
    "outreach": DepartmentName.SALES,
    "angebot": DepartmentName.SALES,
    "pitch": DepartmentName.SALES,
    "kunde": DepartmentName.SALES,
    "strategie": DepartmentName.CONSULTING,
    "konzept": DepartmentName.CONSULTING,
    "workshop": DepartmentName.CONSULTING,
    "workday": DepartmentName.CONSULTING,
    "beratung": DepartmentName.CONSULTING,
    "projekt": DepartmentName.DELIVERY,
    "meilenstein": DepartmentName.DELIVERY,
    "umsetzung": DepartmentName.DELIVERY,
    "qa": DepartmentName.DELIVERY,
    "n8n": DepartmentName.AUTOMATION,
    "api": DepartmentName.AUTOMATION,
    "integration": DepartmentName.AUTOMATION,
    "workflow": DepartmentName.AUTOMATION,
    "agent": DepartmentName.AUTOMATION,
    "rechnung": DepartmentName.FINANCE,
    "vertrag": DepartmentName.FINANCE,
    "invoice": DepartmentName.FINANCE,
    "buchhaltung": DepartmentName.FINANCE,
}

_ROUTER_SYSTEM = """\
Du bist der Central Router bei CloudMcFly, einem Premium-Beratungsunternehmen \
fuer AI-Strategie, Workday-Architektur und n8n-Automatisierung. \
CEO ist Alex Ruetz.

Deine Rolle: Du bist KEIN Fachexperte. Du klassifizierst Anfragen, \
leitest sie an die richtigen Abteilungen weiter und aggregierst Ergebnisse.

Verfuegbare Abteilungen:
- marketing: Content, LinkedIn, Positionierung, Kampagnen
- sales: Lead-Qualifizierung, Outreach, Angebote, Follow-up
- consulting: Konzepte, AI-Strategie, Kundenloesungen, Workshops
- delivery: Projektsteuerung, Umsetzung, QA, Meilensteine
- automation: n8n, Integrationen, interne Tools, Agent-Building
- finance: Rechnungen, Vertraege, Dokumente, Backoffice
"""


class RouterAgent:
    """Central Router - classifies, routes, and aggregates."""

    async def classify_task(
        self, request: str
    ) -> tuple[TaskType, Priority, list[DepartmentName]]:
        """Classify a CEO request into type, priority, and target departments."""
        logger.info("RouterAgent.classify_task: %.80s...", request)

        try:
            result = await call_claude_json(
                system_prompt=_ROUTER_SYSTEM,
                user_prompt=(
                    f"Analysiere diese Anfrage vom CEO und klassifiziere sie.\n\n"
                    f"Anfrage: \"{request}\"\n\n"
                    f"Antworte als JSON mit genau diesen Feldern:\n"
                    f'{{"task_type": "<strategy|content|automation|sales|consulting|delivery|finance|general|multi>",\n'
                    f' "priority": "<critical|high|normal|low>",\n'
                    f' "departments": ["<department_name>", ...],\n'
                    f' "reasoning": "<kurze Begruendung>"}}'
                ),
                temperature=0.2,
            )

            task_type = TaskType(result.get("task_type", "general"))
            priority = Priority(result.get("priority", "normal"))
            departments = [
                DepartmentName(d)
                for d in result.get("departments", ["consulting"])
                if d in [dn.value for dn in DepartmentName]
            ]

            if not departments:
                departments = [DepartmentName.CONSULTING]

            logger.info(
                "Classified: type=%s, priority=%s, depts=%s",
                task_type.value,
                priority.value,
                [d.value for d in departments],
            )
            return task_type, priority, departments

        except Exception as e:
            logger.warning("Claude classification failed, using keyword fallback: %s", e)
            return self._classify_fallback(request)

    def _classify_fallback(
        self, request: str
    ) -> tuple[TaskType, Priority, list[DepartmentName]]:
        """Keyword-based fallback classification."""
        request_lower = request.lower()
        departments: set[DepartmentName] = set()

        for keyword, dept in _KEYWORD_ROUTES.items():
            if keyword in request_lower:
                departments.add(dept)

        if not departments:
            departments.add(DepartmentName.CONSULTING)

        task_type = TaskType.MULTI if len(departments) > 1 else TaskType.GENERAL
        priority = Priority.NORMAL

        if any(w in request_lower for w in ["dringend", "urgent", "asap", "sofort"]):
            priority = Priority.HIGH
        if any(w in request_lower for w in ["kritisch", "critical", "notfall"]):
            priority = Priority.CRITICAL

        return task_type, priority, sorted(departments, key=lambda d: d.value)

    async def check_completeness(self, request: str) -> list[Question]:
        """Check if the CEO's request has enough information to proceed."""
        logger.info("RouterAgent.check_completeness: %.80s...", request)

        try:
            result = await call_claude_json(
                system_prompt=_ROUTER_SYSTEM,
                user_prompt=(
                    f"Pruefe ob diese CEO-Anfrage genuegend Informationen enthaelt, "
                    f"um sie an die Fachabteilungen weiterzuleiten.\n\n"
                    f"Anfrage: \"{request}\"\n\n"
                    f"Falls Informationen fehlen, erstelle Rueckfragen. "
                    f"Falls alles klar ist, gib eine leere Liste zurueck.\n\n"
                    f"Antworte als JSON:\n"
                    f'{{"complete": true/false,\n'
                    f' "questions": [\n'
                    f'   {{"question": "<Rueckfrage>", "context": "<warum wichtig>"}}\n'
                    f" ]}}"
                ),
                temperature=0.3,
            )

            if result.get("complete", True):
                return []

            questions = []
            for q_data in result.get("questions", []):
                questions.append(
                    Question(
                        asked_by="router",
                        question=q_data.get("question", ""),
                        context=q_data.get("context", ""),
                    )
                )
            return questions

        except Exception as e:
            logger.warning("Completeness check failed: %s", e)
            return []  # Proceed without questions on error

    async def create_subtasks(
        self,
        request: str,
        departments: list[DepartmentName],
        priority: Priority,
    ) -> list[SubTask]:
        """Break the CEO request into department-specific sub-tasks."""
        logger.info("RouterAgent.create_subtasks for %d depts", len(departments))

        dept_descriptions = "\n".join(
            f"- {d.value}: {DEPARTMENTS[d.value]['focus']}"
            for d in departments
        )

        try:
            result = await call_claude_json(
                system_prompt=_ROUTER_SYSTEM,
                user_prompt=(
                    f"Erstelle fuer jede Abteilung ein spezifisches Aufgabenpaket.\n\n"
                    f"CEO-Anfrage: \"{request}\"\n"
                    f"Prioritaet: {priority.value}\n"
                    f"Zustaendige Abteilungen:\n{dept_descriptions}\n\n"
                    f"Antworte als JSON:\n"
                    f'{{"subtasks": [\n'
                    f'  {{"department": "<name>",\n'
                    f'   "objective": "<klares Ziel fuer die Abteilung>",\n'
                    f'   "context": "<relevanter Kontext>",\n'
                    f'   "constraints": ["<Einschraenkung>"],\n'
                    f'   "deliverables": ["<erwartetes Ergebnis>"]}}\n'
                    f"]}}"
                ),
                temperature=0.3,
            )

            sub_tasks = []
            for st_data in result.get("subtasks", []):
                dept_name = st_data.get("department", "")
                if dept_name not in [d.value for d in departments]:
                    continue
                sub_tasks.append(
                    SubTask(
                        department=DepartmentName(dept_name),
                        objective=st_data.get("objective", request),
                        context=st_data.get("context", ""),
                        constraints=st_data.get("constraints", []),
                        deliverables=st_data.get("deliverables", []),
                        priority=priority,
                    )
                )

            # Ensure every department has a sub-task
            assigned = {st.department for st in sub_tasks}
            for dept in departments:
                if dept not in assigned:
                    sub_tasks.append(
                        SubTask(
                            department=dept,
                            objective=request,
                            context=f"Department-Fokus: {DEPARTMENTS[dept.value]['focus']}",
                            deliverables=["Analyse", "1-2 Loesungsoptionen"],
                            priority=priority,
                        )
                    )

            return sub_tasks

        except Exception as e:
            logger.warning("SubTask creation failed, using fallback: %s", e)
            return [
                SubTask(
                    department=dept,
                    objective=request,
                    context=f"Department-Fokus: {DEPARTMENTS[dept.value]['focus']}",
                    deliverables=["Analyse", "1-2 Loesungsoptionen mit Pro/Contra"],
                    priority=priority,
                )
                for dept in departments
            ]

    async def aggregate_results(
        self,
        original_request: str,
        department_results: dict,
        options: list[dict],
    ) -> str:
        """Aggregate all department results into a final CEO response."""
        logger.info("RouterAgent.aggregate_results from %d depts", len(department_results))

        # Build context from department summaries
        dept_summaries = []
        for dept_name, result in department_results.items():
            summary = result.get("summary", "")
            dept_options = result.get("options", [])
            dept_summaries.append(
                f"### {dept_name.upper()}\n"
                f"{summary}\n"
                f"Optionen: {len(dept_options)}"
            )

        options_text = ""
        for i, opt in enumerate(options, 1):
            options_text += (
                f"\n**Option {i}: {opt.get('title', '')}**\n"
                f"- Beschreibung: {opt.get('description', '')}\n"
                f"- Pro: {', '.join(opt.get('pros', []))}\n"
                f"- Contra: {', '.join(opt.get('cons', []))}\n"
                f"- Aufwand: {opt.get('estimated_effort', '?')}\n"
                f"- Kosten: {opt.get('estimated_cost', '?')}\n"
                f"- Risiko: {opt.get('risk_level', '?')}\n"
                f"- Empfohlen: {'Ja' if opt.get('recommended') else 'Nein'}\n"
            )

        try:
            response = await call_claude(
                system_prompt=(
                    f"{_ROUTER_SYSTEM}\n\n"
                    f"Du fasst jetzt die Ergebnisse aller Abteilungen fuer den CEO zusammen. "
                    f"Schreibe ein klares, strukturiertes Executive Summary auf Deutsch. "
                    f"Beginne mit einer kurzen Zusammenfassung, dann die wichtigsten Ergebnisse "
                    f"pro Abteilung, und ende mit einer klaren Handlungsempfehlung."
                ),
                user_prompt=(
                    f"CEO-Anfrage: \"{original_request}\"\n\n"
                    f"Abteilungsergebnisse:\n{'---'.join(dept_summaries)}\n\n"
                    f"Loesungsoptionen:\n{options_text}\n\n"
                    f"Erstelle ein Executive Summary fuer CEO Alex Ruetz."
                ),
                temperature=0.4,
                max_tokens=2048,
            )
            return response

        except Exception as e:
            logger.warning("Aggregation failed, using simple format: %s", e)
            parts = [f"Ergebnis fuer: {original_request[:100]}\n"]
            for dept_name, result in department_results.items():
                summary = result.get("summary", "Keine Zusammenfassung")
                parts.append(f"\n--- {dept_name.upper()} ---\n{summary}")
            return "\n".join(parts)
