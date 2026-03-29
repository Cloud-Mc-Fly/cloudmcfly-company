"""CloudMcFly Company - Pydantic V2 State Models & LangGraph TypedDict Bridge."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, TypedDict

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TaskStatus(str, Enum):
    PENDING = "pending"
    ROUTING = "routing"
    IN_PROGRESS = "in_progress"
    AWAITING_REPLY = "awaiting_reply"
    COMPLETED = "completed"
    FAILED = "failed"
    ESCALATED = "escalated"


class Priority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class TaskType(str, Enum):
    STRATEGY = "strategy"
    CONTENT = "content"
    AUTOMATION = "automation"
    SALES = "sales"
    CONSULTING = "consulting"
    DELIVERY = "delivery"
    FINANCE = "finance"
    GENERAL = "general"
    MULTI = "multi"


class DepartmentName(str, Enum):
    MARKETING = "marketing"
    SALES = "sales"
    CONSULTING = "consulting"
    DELIVERY = "delivery"
    AUTOMATION = "automation"
    FINANCE = "finance"


class ColorAgent(str, Enum):
    YELLOW = "yellow"
    BLUE = "blue"
    GREEN = "green"
    RED = "red"


class QuestionStatus(str, Enum):
    PENDING = "pending"
    ANSWERED = "answered"


class DepartmentStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ESCALATED = "escalated"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _short_id() -> str:
    return uuid.uuid4().hex[:8]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Sub-Models
# ---------------------------------------------------------------------------

class Question(BaseModel):
    """A clarifying question from any agent level back to the CEO."""
    question_id: str = Field(default_factory=_short_id)
    asked_by: str = ""  # e.g. "router", "head_marketing", "yellow_sales"
    question: str = ""
    context: str = ""
    answer: str | None = None
    status: QuestionStatus = QuestionStatus.PENDING
    asked_at: datetime = Field(default_factory=_utcnow)
    answered_at: datetime | None = None


class AgentResponse(BaseModel):
    """Output from a single color agent."""
    agent_color: ColorAgent
    department: DepartmentName
    content: str = ""
    key_points: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    confidence: float = 0.0  # 0.0 to 1.0
    created_at: datetime = Field(default_factory=_utcnow)


class SolutionOption(BaseModel):
    """A concrete solution option presented to the CEO."""
    title: str = ""
    description: str = ""
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    estimated_effort: str = ""  # e.g. "2 Tage"
    estimated_cost: str = ""  # e.g. "500 EUR"
    risk_level: str = "medium"  # low, medium, high
    recommended: bool = False


class SubTask(BaseModel):
    """Work package assigned by Router to a department."""
    subtask_id: str = Field(default_factory=_short_id)
    department: DepartmentName
    objective: str = ""
    context: str = ""
    constraints: list[str] = Field(default_factory=list)
    deliverables: list[str] = Field(default_factory=list)
    priority: Priority = Priority.NORMAL


class DepartmentResult(BaseModel):
    """Aggregated output from a department pipeline."""
    department: DepartmentName
    status: DepartmentStatus = DepartmentStatus.PENDING
    agent_responses: list[AgentResponse] = Field(default_factory=list)
    iteration_count: int = 0
    options: list[SolutionOption] = Field(default_factory=list)
    summary: str = ""
    questions: list[Question] = Field(default_factory=list)
    completed_at: datetime | None = None


# ---------------------------------------------------------------------------
# Main State Model
# ---------------------------------------------------------------------------

class TaskState(BaseModel):
    """Full state of a CEO task flowing through the agent hierarchy."""
    task_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    source: str = "ceo"
    original_request: str = ""
    ceo_replies: list[str] = Field(default_factory=list)

    task_type: TaskType = TaskType.GENERAL
    priority: Priority = Priority.NORMAL
    departments: list[DepartmentName] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING

    # Router output
    sub_tasks: list[SubTask] = Field(default_factory=list)
    routing_reasoning: str = ""

    # Department outputs
    department_results: dict[str, DepartmentResult] = Field(default_factory=dict)

    # Questions (escalated to CEO)
    questions: list[Question] = Field(default_factory=list)

    # Final output
    final_response: str | None = None
    options: list[SolutionOption] = Field(default_factory=list)

    # Graph control
    current_department: str | None = None
    current_agent: str | None = None  # ColorAgent value
    department_index: int = 0  # tracks which dept is being processed

    # Error
    error: str | None = None

    # Timestamps
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


# ---------------------------------------------------------------------------
# LangGraph TypedDict Bridge
# ---------------------------------------------------------------------------
# LangGraph requires TypedDict for state, not Pydantic.
# We maintain both and convert at the boundary.

class GraphState(TypedDict, total=False):
    task_id: str
    source: str
    original_request: str
    ceo_replies: list[str]
    task_type: str
    priority: str
    departments: list[str]
    status: str
    sub_tasks: list[dict[str, Any]]
    routing_reasoning: str
    department_results: dict[str, dict[str, Any]]
    questions: list[dict[str, Any]]
    final_response: str | None
    options: list[dict[str, Any]]
    current_department: str | None
    current_agent: str | None
    department_index: int
    error: str | None
    created_at: str
    updated_at: str


def task_state_to_graph(state: TaskState) -> GraphState:
    """Convert Pydantic TaskState to LangGraph-compatible dict."""
    data = state.model_dump(mode="json")
    return GraphState(**data)


def graph_to_task_state(graph_state: dict[str, Any]) -> TaskState:
    """Convert LangGraph dict back to validated Pydantic TaskState."""
    return TaskState.model_validate(graph_state)
