"""CloudMcFly Company - LangGraph State Machine.

The main graph implements the 4-level hierarchy:
  CEO task -> Router -> Fan-out to Departments -> Fan-in -> Aggregate -> Response

Phase 1: All nodes wired with stubs. Full pipeline testable without LLM.
Phase 2: Replace stubs with Claude API calls.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from config import DEPARTMENTS
from core.department import DepartmentHead
from core.router import RouterAgent
from core.state import (
    DepartmentName,
    DepartmentResult,
    DepartmentStatus,
    GraphState,
    TaskStatus,
)
from integrations.teams import TeamsClient
from integrations.n8n_bridge import N8nBridge

logger = logging.getLogger(__name__)

# Shared integration clients
_teams = TeamsClient()
_n8n = N8nBridge()

# Shared instances (stateless, safe to reuse)
_router = RouterAgent()
_department_heads: dict[str, DepartmentHead] = {
    name: DepartmentHead(DepartmentName(name)) for name in DEPARTMENTS
}


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------

async def receive_task(state: GraphState) -> dict[str, Any]:
    """Node 1: Validate incoming task, set status to routing."""
    logger.info("Graph node: receive_task (task=%s)", state.get("task_id", "?")[:8])
    return {
        "status": TaskStatus.ROUTING.value,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


async def route_task(state: GraphState) -> dict[str, Any]:
    """Node 2: Classify task and create sub-tasks for departments."""
    logger.info("Graph node: route_task")

    request = state.get("original_request", "")
    ceo_replies = state.get("ceo_replies", [])

    # Include CEO replies as additional context
    full_context = request
    if ceo_replies:
        full_context += "\n\nCEO-Antworten:\n" + "\n".join(ceo_replies)

    # Classify
    task_type, priority, departments = await _router.classify_task(full_context)

    # Check completeness (may generate questions)
    questions = await _router.check_completeness(full_context)

    # Create sub-tasks
    sub_tasks = await _router.create_subtasks(full_context, departments, priority)

    # Initialize department results
    dept_results = state.get("department_results", {})
    for dept in departments:
        if dept.value not in dept_results:
            dept_results[dept.value] = DepartmentResult(
                department=dept,
                status=DepartmentStatus.PENDING,
            ).model_dump(mode="json")

    return {
        "task_type": task_type.value,
        "priority": priority.value,
        "departments": [d.value for d in departments],
        "sub_tasks": [st.model_dump(mode="json") for st in sub_tasks],
        "routing_reasoning": f"Routed to {[d.value for d in departments]}",
        "questions": [q.model_dump(mode="json") for q in questions]
        + state.get("questions", []),
        "department_results": dept_results,
        "department_index": 0,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


async def check_questions(state: GraphState) -> dict[str, Any]:
    """Node 3: Check if there are pending questions for the CEO."""
    logger.info("Graph node: check_questions")
    # No state mutation needed - routing is handled by conditional edge
    return {}


async def wait_for_reply(state: GraphState) -> dict[str, Any]:
    """Node 4: Pause execution - waiting for CEO answer via API.

    Sends pending questions to the CEO via Teams and n8n.
    """
    logger.info("Graph node: wait_for_reply (task paused)")

    task_id = state.get("task_id", "")
    questions = [
        q for q in state.get("questions", [])
        if q.get("status") == "pending"
    ]

    # Notify CEO via Teams (1:1 chat)
    if questions:
        try:
            await _teams.send_question(task_id, questions)
        except Exception as e:
            logger.warning("Teams notification failed: %s", e)

        # Also notify via n8n (backup channel)
        try:
            await _n8n.notify_question(task_id, questions)
        except Exception as e:
            logger.warning("n8n notification failed: %s", e)

    return {
        "status": TaskStatus.AWAITING_REPLY.value,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


async def process_reply(state: GraphState) -> dict[str, Any]:
    """Node 5: Incorporate CEO reply and reset to routing."""
    logger.info("Graph node: process_reply")
    # Mark all pending questions as answered
    questions = state.get("questions", [])
    for q in questions:
        if q.get("status") == "pending":
            q["status"] = "answered"
            q["answered_at"] = datetime.now(timezone.utc).isoformat()

    return {
        "questions": questions,
        "status": TaskStatus.ROUTING.value,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


async def fan_out_departments(state: GraphState) -> dict[str, Any]:
    """Node 6: Initialize department processing."""
    logger.info("Graph node: fan_out_departments")
    return {
        "status": TaskStatus.IN_PROGRESS.value,
        "department_index": 0,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


async def run_department(state: GraphState) -> dict[str, Any]:
    """Node 7: Run one department's pipeline (Yellow > Blue > Green > Red).

    Phase 1: Processes departments sequentially via department_index.
    Phase 2: Will use LangGraph Send() for true parallelism.
    """
    departments = state.get("departments", [])
    dept_index = state.get("department_index", 0)

    if dept_index >= len(departments):
        logger.warning("run_department: index %d out of range", dept_index)
        return {}

    dept_name = departments[dept_index]
    logger.info("Graph node: run_department (%s, index=%d)", dept_name, dept_index)

    # Find the sub-task for this department
    sub_tasks = state.get("sub_tasks", [])
    sub_task_data = next(
        (st for st in sub_tasks if st.get("department") == dept_name), None
    )

    if sub_task_data is None:
        logger.warning("No sub-task found for department %s", dept_name)
        return {"department_index": dept_index + 1}

    # Run department pipeline
    from core.state import SubTask

    sub_task = SubTask.model_validate(sub_task_data)
    head = _department_heads.get(dept_name)

    if head is None:
        logger.warning("No department head for %s", dept_name)
        return {"department_index": dept_index + 1}

    result = await head.run_pipeline(sub_task)

    # Update department results
    dept_results = dict(state.get("department_results", {}))
    dept_results[dept_name] = result.model_dump(mode="json")

    return {
        "department_results": dept_results,
        "department_index": dept_index + 1,
        "current_department": dept_name,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


async def fan_in_results(state: GraphState) -> dict[str, Any]:
    """Node 8: Check if all departments are done."""
    logger.info("Graph node: fan_in_results")
    # No mutation needed - conditional edge handles routing
    return {}


async def aggregate_response(state: GraphState) -> dict[str, Any]:
    """Node 9: Router aggregates all department results into final CEO response."""
    logger.info("Graph node: aggregate_response")

    dept_results = state.get("department_results", {})
    original = state.get("original_request", "")

    # Collect all options from all departments
    all_options = []
    for dept_data in dept_results.values():
        for opt in dept_data.get("options", []):
            all_options.append(opt)

    final_response = await _router.aggregate_results(
        original_request=original,
        department_results=dept_results,
        options=all_options,
    )

    # Notify CEO via Teams with the final result
    task_id = state.get("task_id", "")
    try:
        await _teams.send_result(task_id, final_response, all_options)
    except Exception as e:
        logger.warning("Teams result notification failed: %s", e)

    try:
        await _n8n.notify_result(task_id, final_response, all_options)
    except Exception as e:
        logger.warning("n8n result notification failed: %s", e)

    return {
        "final_response": final_response,
        "options": all_options,
        "status": TaskStatus.COMPLETED.value,
        "current_department": None,
        "current_agent": None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Conditional edge functions
# ---------------------------------------------------------------------------

def should_ask_questions(state: GraphState) -> Literal["wait_for_reply", "fan_out_departments"]:
    """Route based on whether there are pending questions."""
    questions = state.get("questions", [])
    has_pending = any(q.get("status") == "pending" for q in questions)
    if has_pending:
        logger.info("Conditional: pending questions -> wait_for_reply")
        return "wait_for_reply"
    logger.info("Conditional: no questions -> fan_out_departments")
    return "fan_out_departments"


def are_all_departments_done(
    state: GraphState,
) -> Literal["run_department", "aggregate_response"]:
    """Route based on whether all departments have completed."""
    departments = state.get("departments", [])
    dept_index = state.get("department_index", 0)

    if dept_index < len(departments):
        logger.info("Conditional: dept %d/%d -> run_department", dept_index + 1, len(departments))
        return "run_department"

    logger.info("Conditional: all departments done -> aggregate_response")
    return "aggregate_response"


# ---------------------------------------------------------------------------
# Graph Construction
# ---------------------------------------------------------------------------

def build_company_graph() -> StateGraph:
    """Build and compile the CloudMcFly company state graph.

    Returns:
        Compiled LangGraph StateGraph.
    """
    graph = StateGraph(GraphState)

    # Add nodes
    graph.add_node("receive_task", receive_task)
    graph.add_node("route_task", route_task)
    graph.add_node("check_questions", check_questions)
    graph.add_node("wait_for_reply", wait_for_reply)
    graph.add_node("process_reply", process_reply)
    graph.add_node("fan_out_departments", fan_out_departments)
    graph.add_node("run_department", run_department)
    graph.add_node("fan_in_results", fan_in_results)
    graph.add_node("aggregate_response", aggregate_response)

    # Add edges
    graph.add_edge(START, "receive_task")
    graph.add_edge("receive_task", "route_task")
    graph.add_edge("route_task", "check_questions")

    # Conditional: questions pending?
    graph.add_conditional_edges(
        "check_questions",
        should_ask_questions,
        {
            "wait_for_reply": "wait_for_reply",
            "fan_out_departments": "fan_out_departments",
        },
    )

    # wait_for_reply is a terminal node (graph pauses here)
    graph.add_edge("wait_for_reply", END)

    # process_reply re-enters routing
    graph.add_edge("process_reply", "route_task")

    # Department processing loop
    graph.add_edge("fan_out_departments", "run_department")
    graph.add_edge("run_department", "fan_in_results")

    # Conditional: all departments done?
    graph.add_conditional_edges(
        "fan_in_results",
        are_all_departments_done,
        {
            "run_department": "run_department",
            "aggregate_response": "aggregate_response",
        },
    )

    graph.add_edge("aggregate_response", END)

    return graph.compile()


# Module-level compiled graph
company_graph = build_company_graph()
