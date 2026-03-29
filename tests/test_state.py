"""Tests for Pydantic state models."""

import pytest

from core.state import (
    AgentResponse,
    ColorAgent,
    DepartmentName,
    DepartmentResult,
    DepartmentStatus,
    GraphState,
    Priority,
    Question,
    QuestionStatus,
    SolutionOption,
    SubTask,
    TaskState,
    TaskStatus,
    TaskType,
    graph_to_task_state,
    task_state_to_graph,
)


class TestEnums:
    def test_task_status_values(self):
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.COMPLETED == "completed"

    def test_department_names(self):
        assert len(DepartmentName) == 6
        assert DepartmentName.MARKETING == "marketing"

    def test_color_agents(self):
        assert len(ColorAgent) == 4
        assert ColorAgent.YELLOW == "yellow"


class TestQuestion:
    def test_defaults(self):
        q = Question(question="Was ist das Budget?", asked_by="router")
        assert q.status == QuestionStatus.PENDING
        assert q.answer is None
        assert len(q.question_id) == 8

    def test_answer(self):
        q = Question(question="Test?", asked_by="head_marketing")
        q.answer = "10.000 EUR"
        q.status = QuestionStatus.ANSWERED
        assert q.status == QuestionStatus.ANSWERED


class TestSubTask:
    def test_creation(self):
        st = SubTask(
            department=DepartmentName.CONSULTING,
            objective="Erstelle AI-Strategie",
            priority=Priority.HIGH,
        )
        assert st.department == DepartmentName.CONSULTING
        assert len(st.subtask_id) == 8


class TestAgentResponse:
    def test_creation(self):
        r = AgentResponse(
            agent_color=ColorAgent.YELLOW,
            department=DepartmentName.MARKETING,
            content="Kreative Idee",
            confidence=0.85,
        )
        assert r.confidence == 0.85
        assert r.agent_color == ColorAgent.YELLOW


class TestSolutionOption:
    def test_creation(self):
        opt = SolutionOption(
            title="Option A",
            pros=["Schnell", "Guenstig"],
            cons=["Begrenzt"],
            recommended=True,
        )
        assert opt.recommended is True
        assert len(opt.pros) == 2


class TestDepartmentResult:
    def test_defaults(self):
        r = DepartmentResult(department=DepartmentName.SALES)
        assert r.status == DepartmentStatus.PENDING
        assert r.iteration_count == 0
        assert r.agent_responses == []


class TestTaskState:
    def test_defaults(self):
        state = TaskState(original_request="Test task")
        assert state.status == TaskStatus.PENDING
        assert state.source == "ceo"
        assert len(state.task_id) == 32  # hex UUID without dashes
        assert state.departments == []

    def test_full_state(self):
        state = TaskState(
            original_request="Erstelle LinkedIn Strategie",
            priority=Priority.HIGH,
            departments=[DepartmentName.MARKETING, DepartmentName.SALES],
            task_type=TaskType.MULTI,
        )
        assert len(state.departments) == 2
        assert state.task_type == TaskType.MULTI


class TestGraphStateBridge:
    def test_roundtrip(self):
        """TaskState -> GraphState -> TaskState preserves data."""
        original = TaskState(
            original_request="Test roundtrip",
            priority=Priority.HIGH,
            departments=[DepartmentName.CONSULTING],
            status=TaskStatus.IN_PROGRESS,
        )

        graph_state = task_state_to_graph(original)
        assert isinstance(graph_state, dict)
        assert graph_state["priority"] == "high"

        restored = graph_to_task_state(graph_state)
        assert restored.task_id == original.task_id
        assert restored.priority == Priority.HIGH
        assert restored.departments == [DepartmentName.CONSULTING]

    def test_with_nested_models(self):
        """Roundtrip with nested sub-tasks and questions."""
        original = TaskState(
            original_request="Complex task",
            sub_tasks=[
                SubTask(
                    department=DepartmentName.MARKETING,
                    objective="Content erstellen",
                )
            ],
            questions=[
                Question(question="Budget?", asked_by="router")
            ],
        )

        graph_state = task_state_to_graph(original)
        restored = graph_to_task_state(graph_state)
        assert len(restored.sub_tasks) == 1
        assert restored.sub_tasks[0].department == DepartmentName.MARKETING
        assert len(restored.questions) == 1
        assert restored.questions[0].asked_by == "router"
