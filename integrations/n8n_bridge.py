"""n8n Webhook Bridge - simple HTTP relay.

n8n acts ONLY as a webhook listener for MS Teams and a relay back.
No complex AI logic in n8n - all intelligence stays in Python.

Sends HTTP POST to n8n webhooks for notifications.
"""

from __future__ import annotations

import logging

import httpx

from config import settings

logger = logging.getLogger(__name__)


class N8nBridge:
    """Bridge to n8n for simple webhook-based integrations."""

    def __init__(self) -> None:
        self.webhook_url = settings.n8n_webhook_url
        self.api_key = settings.n8n_api_key
        self.configured = bool(self.webhook_url)
        if not self.configured:
            logger.warning("n8n bridge not configured (missing webhook URL)")

    async def _post(self, payload: dict) -> bool:
        """Send a POST request to the n8n webhook."""
        if not self.configured:
            logger.warning("[NOT CONFIGURED] N8nBridge._post")
            return False

        try:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["X-N8N-API-Key"] = self.api_key

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    self.webhook_url,
                    headers=headers,
                    json=payload,
                )

            if resp.status_code in (200, 201):
                logger.info("n8n webhook OK: %d", resp.status_code)
                return True

            logger.error("n8n webhook failed: %d %s", resp.status_code, resp.text[:200])
            return False

        except Exception as e:
            logger.error("n8n webhook error: %s", e)
            return False

    async def notify_result(self, task_id: str, result: str, options: list[dict] | None = None) -> bool:
        """Send task result to n8n for forwarding to MS Teams.

        Args:
            task_id: The completed task ID.
            result: The formatted result text.
            options: Optional solution options.

        Returns:
            True if n8n accepted the webhook.
        """
        return await self._post({
            "type": "result",
            "task_id": task_id,
            "result": result,
            "options": options or [],
        })

    async def notify_question(self, task_id: str, questions: list[dict]) -> bool:
        """Send clarifying questions via n8n to MS Teams.

        Args:
            task_id: The task requiring CEO input.
            questions: List of question dicts.

        Returns:
            True if n8n accepted the webhook.
        """
        return await self._post({
            "type": "question",
            "task_id": task_id,
            "questions": questions,
        })
