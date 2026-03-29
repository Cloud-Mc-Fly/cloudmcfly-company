"""Microsoft Teams integration via Graph API.

Phase 1: Stub - logs actions, returns placeholders.
Phase 4: Full implementation with MSAL auth + Graph API calls.
"""

import logging

from config import settings

logger = logging.getLogger(__name__)


class TeamsClient:
    """Send and receive messages via Microsoft Teams / Graph API."""

    def __init__(self) -> None:
        self.tenant_id = settings.teams_tenant_id
        self.client_id = settings.teams_client_id
        self.configured = bool(self.tenant_id and self.client_id)
        if not self.configured:
            logger.warning("Teams integration not configured (missing tenant/client ID)")

    async def send_message(self, message: str, chat_id: str | None = None) -> bool:
        """Send a message to the CEO via Teams.

        Args:
            message: The message text to send.
            chat_id: Optional specific chat/channel ID. Defaults to CEO chat.

        Returns:
            True if sent successfully.
        """
        logger.info(
            "[STUB] TeamsClient.send_message: %s chars to chat=%s",
            len(message),
            chat_id or "ceo_default",
        )
        # Phase 4: MSAL auth + POST to Graph API /chats/{chat_id}/messages
        return True

    async def send_question(self, task_id: str, question: str) -> bool:
        """Send a clarifying question to the CEO.

        Args:
            task_id: The task this question belongs to.
            question: The question text.

        Returns:
            True if sent successfully.
        """
        formatted = f"[Task {task_id[:8]}] Rueckfrage:\n\n{question}"
        return await self.send_message(formatted)

    async def send_result(self, task_id: str, result: str) -> bool:
        """Send the final task result to the CEO.

        Args:
            task_id: The completed task ID.
            result: The final formatted result.

        Returns:
            True if sent successfully.
        """
        formatted = f"[Task {task_id[:8]}] Ergebnis:\n\n{result}"
        return await self.send_message(formatted)
