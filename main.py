"""CloudMcFly Company - FastAPI Application.

Headless API server that receives tasks from the CEO (via n8n/MS Teams),
processes them through the LangGraph agent hierarchy, and returns results.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

from config import DEPARTMENTS, settings
from core.graph import company_graph
from core.state import (
    Priority,
    TaskState,
    TaskStatus,
    graph_to_task_state,
    task_state_to_graph,
)
from db.models import close_db, init_db
from db.repository import TaskRepository

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("cloudmcfly")


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    logger.info("CloudMcFly Company starting (env=%s)", settings.app_env.value)

    # Create data directories
    data_dir = Path(settings.data_dir)
    for subdir in ["ceo_desk", "router_inbox"]:
        (data_dir / subdir).mkdir(parents=True, exist_ok=True)
    for dept in DEPARTMENTS:
        (data_dir / "departments" / dept).mkdir(parents=True, exist_ok=True)

    # Init database
    await init_db()
    logger.info("Database initialized")

    yield

    await close_db()
    logger.info("CloudMcFly Company shut down")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="CloudMcFly Company",
    description="Virtual AI Company - Multi-Agent Hierarchy",
    version="0.1.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(key: str | None = Depends(api_key_header)) -> str:
    if not key or key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return key


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------

class TaskCreateRequest(BaseModel):
    message: str
    source: str = "ceo"
    priority: Priority = Priority.NORMAL


class ReplyRequest(BaseModel):
    message: str


class QuestionOut(BaseModel):
    question_id: str
    asked_by: str = ""
    question: str = ""
    status: str = "pending"


class OptionOut(BaseModel):
    title: str = ""
    description: str = ""
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    estimated_effort: str = ""
    estimated_cost: str = ""
    risk_level: str = "medium"
    recommended: bool = False


class TaskResponse(BaseModel):
    task_id: str
    status: str
    task_type: str = "general"
    priority: str = "normal"
    departments: list[str] = Field(default_factory=list)
    final_response: str | None = None
    options: list[OptionOut] = Field(default_factory=list)
    questions: list[QuestionOut] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


class TaskListResponse(BaseModel):
    tasks: list[TaskResponse]
    total: int


class DepartmentInfo(BaseModel):
    name: str
    display_name: str
    focus: str
    active_tasks: int = 0


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str


# ---------------------------------------------------------------------------
# Background graph execution
# ---------------------------------------------------------------------------

async def run_graph_background(task_id: str, initial_state: dict) -> None:
    """Run the LangGraph in background and persist results."""
    try:
        logger.info("Background graph started for task %s", task_id[:8])
        result = await company_graph.ainvoke(initial_state)
        final_state = graph_to_task_state(result)
        await TaskRepository.update_from_state(final_state)
        logger.info(
            "Background graph completed for task %s (status=%s)",
            task_id[:8],
            final_state.status.value,
        )
    except Exception:
        logger.exception("Background graph FAILED for task %s", task_id[:8])
        # Update task to failed
        try:
            record = await TaskRepository.get(task_id)
            if record:
                from core.state import TaskState as TS

                state = TS(
                    task_id=task_id,
                    status=TaskStatus.FAILED,
                    original_request=record.original_request,
                    error="Graph execution failed - check logs",
                )
                await TaskRepository.update_from_state(state)
        except Exception:
            logger.exception("Failed to update task status to FAILED")


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _record_to_response(record) -> TaskResponse:
    """Convert a TaskRecord to a TaskResponse."""
    questions = []
    for q in (record.questions or []):
        questions.append(
            QuestionOut(
                question_id=q.get("question_id", ""),
                asked_by=q.get("asked_by", ""),
                question=q.get("question", ""),
                status=q.get("status", "pending"),
            )
        )

    options = []
    for o in (record.options or []):
        options.append(
            OptionOut(
                title=o.get("title", ""),
                description=o.get("description", ""),
                pros=o.get("pros", []),
                cons=o.get("cons", []),
                estimated_effort=o.get("estimated_effort", ""),
                estimated_cost=o.get("estimated_cost", ""),
                risk_level=o.get("risk_level", "medium"),
                recommended=o.get("recommended", False),
            )
        )

    created = record.created_at.isoformat() if record.created_at else ""
    updated = record.updated_at.isoformat() if record.updated_at else ""

    return TaskResponse(
        task_id=record.task_id,
        status=record.status,
        task_type=record.task_type or "general",
        priority=record.priority or "normal",
        departments=record.departments or [],
        final_response=record.final_response,
        options=options,
        questions=questions,
        created_at=created,
        updated_at=updated,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint (unauthenticated)."""
    return HealthResponse(
        status="ok",
        version="0.1.0",
        environment=settings.app_env.value,
    )


@app.post("/api/v1/task", response_model=TaskResponse, status_code=202)
async def create_task(
    body: TaskCreateRequest,
    _key: str = Depends(verify_api_key),
):
    """Create a new task from the CEO."""
    state = TaskState(
        source=body.source,
        original_request=body.message,
        priority=body.priority,
    )

    # Persist to DB
    await TaskRepository.create(state)
    logger.info("Task created: %s (priority=%s)", state.task_id[:8], body.priority.value)

    # Launch graph in background
    graph_state = task_state_to_graph(state)
    asyncio.create_task(run_graph_background(state.task_id, graph_state))

    # Return immediately
    record = await TaskRepository.get(state.task_id)
    return _record_to_response(record)


@app.get("/api/v1/task/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    _key: str = Depends(verify_api_key),
):
    """Get task status and results."""
    record = await TaskRepository.get(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return _record_to_response(record)


@app.post("/api/v1/task/{task_id}/reply", response_model=TaskResponse)
async def reply_to_task(
    task_id: str,
    body: ReplyRequest,
    _key: str = Depends(verify_api_key),
):
    """CEO replies to a clarifying question."""
    record = await TaskRepository.get(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Task not found")

    if record.status != TaskStatus.AWAITING_REPLY.value:
        raise HTTPException(
            status_code=400,
            detail=f"Task is not awaiting reply (status={record.status})",
        )

    # Rebuild state, add reply, and re-run graph from process_reply
    state = TaskState(
        task_id=record.task_id,
        source=record.source,
        original_request=record.original_request,
        ceo_replies=(record.ceo_replies or []) + [body.message],
        task_type=record.task_type or "general",
        priority=record.priority or "normal",
        departments=record.departments or [],
        status=TaskStatus.ROUTING,
        sub_tasks=record.sub_tasks or [],
        routing_reasoning=record.routing_reasoning or "",
        department_results=record.department_results or {},
        questions=record.questions or [],
    )

    # Mark questions as answered
    for q in state.questions:
        if hasattr(q, "status") and q.status == "pending":
            q.status = "answered"
            q.answered_at = datetime.now(timezone.utc)

    await TaskRepository.update_from_state(state)

    # Re-launch graph
    graph_state = task_state_to_graph(state)
    asyncio.create_task(run_graph_background(state.task_id, graph_state))

    record = await TaskRepository.get(state.task_id)
    return _record_to_response(record)


@app.get("/api/v1/tasks", response_model=TaskListResponse)
async def list_tasks(
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _key: str = Depends(verify_api_key),
):
    """List all tasks with optional filtering."""
    records, total = await TaskRepository.list_tasks(
        status=status, limit=limit, offset=offset
    )
    return TaskListResponse(
        tasks=[_record_to_response(r) for r in records],
        total=total,
    )


@app.get("/api/v1/departments")
async def list_departments(_key: str = Depends(verify_api_key)):
    """List all departments with their configuration."""
    result = []
    for slug, info in DEPARTMENTS.items():
        result.append(
            DepartmentInfo(
                name=slug,
                display_name=info["name"],
                focus=info["focus"],
                active_tasks=0,  # Phase 4: count from DB
            )
        )
    return result


@app.post("/api/v1/webhook/teams", status_code=202)
async def teams_webhook(
    body: dict,
    _key: str = Depends(verify_api_key),
):
    """Receive MS Teams webhook from n8n.

    Expected payload: {"message": "...", "sender": "...", "task_id": "..."}
    """
    message = body.get("message") or body.get("text", "")
    task_id = body.get("task_id")

    if not message:
        raise HTTPException(status_code=400, detail="No message in payload")

    # If task_id present, treat as reply
    if task_id:
        record = await TaskRepository.get(task_id)
        if record and record.status == TaskStatus.AWAITING_REPLY.value:
            return await reply_to_task(
                task_id=task_id,
                body=ReplyRequest(message=message),
            )

    # Otherwise create new task
    return await create_task(
        body=TaskCreateRequest(message=message, source="teams"),
    )
