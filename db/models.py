"""CloudMcFly Company - SQLAlchemy async models and engine setup."""

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Index, String, Text
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from config import settings


# ---------------------------------------------------------------------------
# Engine & Session
# ---------------------------------------------------------------------------

engine = create_async_engine(
    settings.database_url,
    echo=(not settings.is_production),
    future=True,
)

async_session = async_sessionmaker(engine, expire_on_commit=False)


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class Base(AsyncAttrs, DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TaskRecord(Base):
    __tablename__ = "tasks"

    task_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="ceo")
    original_request: Mapped[str] = mapped_column(Text, nullable=False, default="")
    task_type: Mapped[str] = mapped_column(String(50), default="general")
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")

    departments: Mapped[dict | list] = mapped_column(JSON, default=list)
    sub_tasks: Mapped[dict | list] = mapped_column(JSON, default=list)
    routing_reasoning: Mapped[str] = mapped_column(Text, default="")
    department_results: Mapped[dict] = mapped_column(JSON, default=dict)
    questions: Mapped[dict | list] = mapped_column(JSON, default=list)
    ceo_replies: Mapped[dict | list] = mapped_column(JSON, default=list)
    options: Mapped[dict | list] = mapped_column(JSON, default=list)
    final_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        Index("ix_tasks_status", "status"),
        Index("ix_tasks_created_at", "created_at"),
    )


class QuestionRecord(Base):
    __tablename__ = "questions"

    question_id: Mapped[str] = mapped_column(String(8), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(36), nullable=False)
    asked_by: Mapped[str] = mapped_column(String(100), default="")
    question: Mapped[str] = mapped_column(Text, default="")
    context: Mapped[str] = mapped_column(Text, default="")
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    asked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    answered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_questions_task_id", "task_id"),
        Index("ix_questions_status", "status"),
    )


# ---------------------------------------------------------------------------
# DB Lifecycle
# ---------------------------------------------------------------------------

async def init_db() -> None:
    """Create all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Dispose engine."""
    await engine.dispose()
