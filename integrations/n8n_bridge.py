"""n8n Webhook Bridge - simple HTTP relay.

n8n acts ONLY as a webhook listener for MS Teams and a relay back.
No complex AI logic in n8n - all intelligence stays in Python.

Phase 1: Stub - logs actions, returns placeholders.
Phase 4: Full implementation with httpx POST to n8n webhooks.
"""

import logging

from config import settings

logger = logging.getLogger(__name__)


class N8nBridge:
    """Bridge to n8n for simple webhook-based integrations."""

    def __init__(self) -> None:
        self.webhook_url = settings.n8n_webhook_url
        self.configured = bool(self.webhook_url)
        if not self.configured:
            logger.warning("n8n bridge not configured (missing webhook URL)")

    async def notify_result(self, task_id: str, result: str) -> bool:
        """Send task result to n8n, which posts it to MS Teams.

        Args:
            task_id: The completed task ID.
            result: The formatted result text.

        Returns:
            True if n8n accepted the webhook.
        """
        logger.info(
            "[STUB] N8nBridge.notify_result: task=%s, %s chars",
            task_id[:8],
            len(result),
        )
        # Phase 4: httpx.post(self.webhook_url, json={...})
        return True

    async def notify_question(self, task_id: str, question: str) -> bool:
        """Send a clarifying question via n8n to MS Teams.

        Args:
            task_id: The task requiring CEO input.
            question: The question text.

        Returns:
            True if n8n accepted the webhook.
        """
        logger.info(
            "[STUB] N8nBridge.notify_question: task=%s",
            task_id[:8],
        )
        return True
