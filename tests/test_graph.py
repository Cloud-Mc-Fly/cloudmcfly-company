"""Tests for LangGraph state machine."""

import pytest

from core.graph import build_company_graph, company_graph
from core.state import GraphState, Priority, TaskState, TaskStatus, task_state_to_graph


class TestGraphCompilation:
    def test_graph_compiles(self):
        """The graph should compile without errors."""
        graph = build_company_graph()
        assert graph is not None

    def test_module_level_graph_exists(self):
        """The module-level compiled graph should exist."""
        assert company_graph is not None


@pytest.mark.asyncio
async def test_graph_full_pipeline():
    """Run a complete task through the stubbed graph."""
    state = TaskState(
        original_request="Erstelle ein Konzept fuer eine Workday-AI-Integration",
        priority=Priority.NORMAL,
    )

    initial = task_state_to_graph(state)
    result = await company_graph.ainvoke(initial)

    # Should have completed
    assert result["status"] in [
        TaskStatus.COMPLETED.value,
        TaskStatus.AWAITING_REPLY.value,
    ]

    # Should have routed to at least one department
    assert len(result.get("departments", [])) > 0

    # Should have department results
    assert len(result.get("department_results", {})) > 0

    # If completed, should have final response
    if result["status"] == TaskStatus.COMPLETED.value:
        assert result.get("final_response") is not None


@pytest.mark.asyncio
async def test_graph_multi_department():
    """Test routing to multiple departments."""
    state = TaskState(
        original_request="Erstelle LinkedIn Content und einen n8n Workflow fuer Lead-Generierung",
        priority=Priority.HIGH,
    )

    initial = task_state_to_graph(state)
    result = await company_graph.ainvoke(initial)

    departments = result.get("departments", [])
    # Should route to marketing (linkedin/content) and automation (n8n/workflow)
    assert len(departments) >= 2


@pytest.mark.asyncio
async def test_graph_priority_detection():
    """Test priority keywords are detected."""
    state = TaskState(
        original_request="DRINGEND: Erstelle sofort ein Angebot fuer Kunde X",
    )

    initial = task_state_to_graph(state)
    result = await company_graph.ainvoke(initial)

    assert result.get("priority") in ["high", "critical"]
