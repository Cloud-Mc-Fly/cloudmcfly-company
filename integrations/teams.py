"""Microsoft Teams integration via Graph API.

Sends 1:1 chat messages to the CEO using Microsoft Graph API
with MSAL app-only authentication (client credentials flow).
"""

from __future__ import annotations

import logging

import httpx
from msal import ConfidentialClientApplication

from config import settings

logger = logging.getLogger(__name__)

# Graph API base
GRAPH_URL = "https://graph.microsoft.com/v1.0"


class TeamsClient:
    """Send messages to the CEO via Microsoft Teams 1:1 chat."""

    def __init__(self) -> None:
        self.tenant_id = settings.ms365_tenant_id
        self.client_id = settings.ms365_client_id
        self.client_secret = settings.ms365_client_secret
        self.sender_email = settings.ms365_sender_email
        self.ceo_email = settings.agent_email

        self.configured = bool(
            self.tenant_id and self.client_id and self.client_secret
        )

        self._token: str | None = None
        self._msal_app: ConfidentialClientApplication | None = None

        if not self.configured:
            logger.warning("Teams integration not configured (missing MS365 credentials)")

    def _get_msal_app(self) -> ConfidentialClientApplication:
        """Lazy-init MSAL app."""
        if self._msal_app is None:
            self._msal_app = ConfidentialClientApplication(
                client_id=self.client_id,
                client_credential=self.client_secret,
                authority=f"https://login.microsoftonline.com/{self.tenant_id}",
            )
        return self._msal_app

    def _get_token(self) -> str:
        """Get or refresh access token via client credentials flow."""
        app = self._get_msal_app()
        result = app.acquire_token_for_client(
            scopes=["https://graph.microsoft.com/.default"]
        )
        if "access_token" in result:
            self._token = result["access_token"]
            return self._token
        error = result.get("error_description", result.get("error", "Unknown"))
        raise RuntimeError(f"MSAL auth failed: {error}")

    def _headers(self) -> dict:
        """Get auth headers."""
        token = self._get_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    async def send_message(self, message: str, chat_id: str | None = None) -> bool:
        """Send a message to the CEO via Teams 1:1 chat.

        Uses Graph API: POST /users/{user-id}/chats -> find/create chat -> send message

        Args:
            message: The message text (supports HTML).
            chat_id: Optional existing chat ID. If None, sends via user chat.

        Returns:
            True if sent successfully.
        """
        if not self.configured:
            logger.warning("[NOT CONFIGURED] TeamsClient.send_message: %d chars", len(message))
            return False

        try:
            headers = self._headers()

            if chat_id:
                # Send to existing chat
                url = f"{GRAPH_URL}/chats/{chat_id}/messages"
            else:
                # Send as chat message from the app to the CEO user
                # Using the /users/{id}/sendMail or /communications approach
                # Simplest: use /users/{sender}/chats and find/create 1:1 chat
                chat_id = await self._get_or_create_chat(headers)
                if not chat_id:
                    logger.error("Could not create/find 1:1 chat with CEO")
                    return False
                url = f"{GRAPH_URL}/chats/{chat_id}/messages"

            payload = {
                "body": {
                    "contentType": "html",
                    "content": message,
                }
            }

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(url, headers=headers, json=payload)

            if resp.status_code in (200, 201):
                logger.info("Teams message sent (%d chars)", len(message))
                return True
            else:
                logger.error(
                    "Teams send failed: %d %s", resp.status_code, resp.text[:200]
                )
                return False

        except Exception as e:
            logger.error("Teams send error: %s", e)
            return False

    async def _get_or_create_chat(self, headers: dict) -> str | None:
        """Find or create a 1:1 chat between sender and CEO.

        Returns chat ID or None.
        """
        try:
            # List existing chats for the sender
            url = f"{GRAPH_URL}/users/{self.sender_email}/chats"
            params = {"$filter": "chatType eq 'oneOnOne'", "$top": "50"}

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url, headers=headers, params=params)

            if resp.status_code == 200:
                chats = resp.json().get("value", [])
                # Find existing 1:1 chat with CEO
                for chat in chats:
                    chat_id = chat.get("id")
                    if chat_id:
                        # Check members
                        members_url = f"{GRAPH_URL}/chats/{chat_id}/members"
                        async with httpx.AsyncClient(timeout=15) as client:
                            m_resp = await client.get(members_url, headers=headers)
                        if m_resp.status_code == 200:
                            members = m_resp.json().get("value", [])
                            emails = [
                                m.get("email", "").lower()
                                for m in members
                            ]
                            if self.ceo_email.lower() in emails:
                                logger.info("Found existing chat: %s", chat_id)
                                return chat_id

            # Create new 1:1 chat
            create_url = f"{GRAPH_URL}/chats"
            create_payload = {
                "chatType": "oneOnOne",
                "members": [
                    {
                        "@odata.type": "#microsoft.graph.aadUserConversationMember",
                        "roles": ["owner"],
                        "user@odata.bind": f"{GRAPH_URL}/users('{self.sender_email}')",
                    },
                    {
                        "@odata.type": "#microsoft.graph.aadUserConversationMember",
                        "roles": ["owner"],
                        "user@odata.bind": f"{GRAPH_URL}/users('{self.ceo_email}')",
                    },
                ],
            }

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(create_url, headers=headers, json=create_payload)

            if resp.status_code in (200, 201):
                chat_id = resp.json().get("id")
                logger.info("Created new 1:1 chat: %s", chat_id)
                return chat_id

            logger.error("Chat creation failed: %d %s", resp.status_code, resp.text[:200])
            return None

        except Exception as e:
            logger.error("Chat lookup/creation error: %s", e)
            return None

    async def send_question(self, task_id: str, questions: list[dict]) -> bool:
        """Send clarifying questions to the CEO in a formatted message.

        Args:
            task_id: The task ID.
            questions: List of question dicts with 'question' and 'context' keys.

        Returns:
            True if sent successfully.
        """
        short_id = task_id[:8]
        lines = [f"<b>CloudMcFly Router - Rueckfragen</b> [Task {short_id}]<br><br>"]
        lines.append("Bevor ich deine Anfrage bearbeiten kann, brauche ich noch Klarheit:<br><br>")

        for i, q in enumerate(questions, 1):
            question_text = q.get("question", "")
            lines.append(f"<b>{i}.</b> {question_text}<br>")

        lines.append(f"<br><i>Antworte hier im Chat. Referenz: Task {short_id}</i>")

        return await self.send_message("".join(lines))

    async def send_result(self, task_id: str, result: str, options: list[dict] | None = None) -> bool:
        """Send the final task result to the CEO.

        Args:
            task_id: The completed task ID.
            result: The executive summary text.
            options: Optional list of solution options.

        Returns:
            True if sent successfully.
        """
        short_id = task_id[:8]
        lines = [f"<b>CloudMcFly - Ergebnis</b> [Task {short_id}]<br><br>"]
        lines.append(result.replace("\n", "<br>"))

        if options:
            lines.append("<br><br><b>Loesungsoptionen:</b><br>")
            for i, opt in enumerate(options, 1):
                title = opt.get("title", f"Option {i}")
                recommended = " (EMPFOHLEN)" if opt.get("recommended") else ""
                lines.append(f"<br><b>Option {i}: {title}{recommended}</b><br>")
                if opt.get("pros"):
                    lines.append(f"Pro: {', '.join(opt['pros'])}<br>")
                if opt.get("cons"):
                    lines.append(f"Contra: {', '.join(opt['cons'])}<br>")
                if opt.get("estimated_effort"):
                    lines.append(f"Aufwand: {opt['estimated_effort']}<br>")

        return await self.send_message("".join(lines))
