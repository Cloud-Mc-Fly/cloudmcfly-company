"""Airtable CRM integration.

Phase 1: Stub - logs actions, returns placeholders.
Phase 4: Full implementation reusing patterns from cloudmcfly-agent.
"""

import logging

from config import settings

logger = logging.getLogger(__name__)


class AirtableClient:
    """Airtable CRM client for task tracking and reporting."""

    def __init__(self) -> None:
        self.pat = settings.airtable_pat
        self.base_id = settings.airtable_base_id
        self.configured = bool(self.pat and self.base_id)
        if not self.configured:
            logger.warning("Airtable integration not configured (missing PAT/base ID)")

    async def log_task(self, task_data: dict) -> str | None:
        """Log a completed task to Airtable.

        Args:
            task_data: Dict with task_id, status, departments, summary, etc.

        Returns:
            Airtable record ID or None.
        """
        logger.info(
            "[STUB] AirtableClient.log_task: task=%s status=%s",
            task_data.get("task_id", "?")[:8],
            task_data.get("status", "?"),
        )
        # Phase 4: pyairtable create record
        return None

    async def update_task_status(self, record_id: str, status: str) -> bool:
        """Update task status in Airtable.

        Args:
            record_id: Airtable record ID.
            status: New status value.

        Returns:
            True if updated successfully.
        """
        logger.info("[STUB] AirtableClient.update_task_status: %s -> %s", record_id, status)
        return True

    async def get_active_tasks(self) -> list[dict]:
        """Fetch all active (non-completed) tasks from Airtable.

        Returns:
            List of task records.
        """
        logger.info("[STUB] AirtableClient.get_active_tasks")
        return []
