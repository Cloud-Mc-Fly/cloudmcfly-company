"""CloudMcFly Company - Task Repository (CRUD operations)."""

from datetime import datetime, timezone

from sqlalchemy import func, select

from core.state import TaskState
from db.models import QuestionRecord, TaskRecord, async_session


class TaskRepository:
    """Static repository for TaskRecord CRUD operations."""

    @staticmethod
    async def create(state: TaskState) -> TaskRecord:
        """Persist a new TaskState to the database."""
        data = state.model_dump(mode="json")
        record = TaskRecord(
            task_id=data["task_id"],
            source=data["source"],
            original_request=data["original_request"],
            task_type=data["task_type"],
            priority=data["priority"],
            status=data["status"],
            departments=data["departments"],
            sub_tasks=data["sub_tasks"],
            routing_reasoning=data["routing_reasoning"],
            department_results=data["department_results"],
            questions=data["questions"],
            ceo_replies=data["ceo_replies"],
            options=data["options"],
            final_response=data.get("final_response"),
            error=data.get("error"),
        )
        async with async_session() as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)
        return record

    @staticmethod
    async def get(task_id: str) -> TaskRecord | None:
        """Fetch a single task by ID."""
        async with async_session() as session:
            return await session.get(TaskRecord, task_id)

    @staticmethod
    async def update_from_state(state: TaskState) -> None:
        """Update an existing TaskRecord from a TaskState."""
        data = state.model_dump(mode="json")
        async with async_session() as session:
            record = await session.get(TaskRecord, data["task_id"])
            if record is None:
                return
            record.status = data["status"]
            record.task_type = data["task_type"]
            record.priority = data["priority"]
            record.departments = data["departments"]
            record.sub_tasks = data["sub_tasks"]
            record.routing_reasoning = data["routing_reasoning"]
            record.department_results = data["department_results"]
            record.questions = data["questions"]
            record.ceo_replies = data["ceo_replies"]
            record.options = data["options"]
            record.final_response = data.get("final_response")
            record.error = data.get("error")
            record.updated_at = datetime.now(timezone.utc)
            await session.commit()

    @staticmethod
    async def list_tasks(
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[TaskRecord], int]:
        """Return filtered, paginated task list with total count."""
        async with async_session() as session:
            query = select(TaskRecord)
            count_query = select(func.count()).select_from(TaskRecord)

            if status:
                query = query.where(TaskRecord.status == status)
                count_query = count_query.where(TaskRecord.status == status)

            query = query.order_by(TaskRecord.created_at.desc())
            query = query.limit(limit).offset(offset)

            result = await session.execute(query)
            records = list(result.scalars().all())

            count_result = await session.execute(count_query)
            total = count_result.scalar_one()

            return records, total

    @staticmethod
    async def save_question(task_id: str, question_data: dict) -> None:
        """Persist a Question to the questions table."""
        record = QuestionRecord(
            question_id=question_data["question_id"],
            task_id=task_id,
            asked_by=question_data.get("asked_by", ""),
            question=question_data.get("question", ""),
            context=question_data.get("context", ""),
            status="pending",
        )
        async with async_session() as session:
            session.add(record)
            await session.commit()
