import json
import logging
import httpx
from core.config import settings
from core.http_client import get_async_client

logger = logging.getLogger(__name__)

PROMPT_CLASSIFIER="""
You are an intent classifier for a customer support chatbot.

Your task:
Classify the user's message into exactly ONE category.

Categories:
- sensitive: requests Jira tickets, issues, customers, users, organizations, internal systems, or any company-specific or personal data.
- general: greetings, small talk, how-to questions, or general information that does NOT require Jira or internal data.

Rules:
- Respond with ONLY ONE WORD.
- The response MUST be either: sensitive or general.
- Do NOT explain your reasoning.
- If the intent is unclear or ambiguous, respond with: sensitive.

Examples:
User: "Hi"
Answer: general

User: "Check ticket SUPPORT-123"
Answer: sensitive

User: "What can you help me with?"
Answer: general
"""

PROMPT_REPLY="""
You are a customer support assistant.

Context:
- You do NOT have access to Jira, tickets, customer records, or internal company systems.
- You must NOT invent or assume any Jira or internal data.
- If the user asks for Jira-related or account-specific information, politely ask them to verify their company email.

Guidelines:
- Be concise and helpful.
- Use the same language as the user.
- If verification is required, clearly explain why.

Tone:
- Professional
- Friendly
- Clear
"""

PROMPT_JIRA_ACTION = """
You are a Jira support assistant. Your task is to output ONE JSON object only.

Decide the user's intent and extract fields. Allowed intents:
- start_create_ticket
- update_draft_ticket
- confirm_create_ticket
- revise_draft_ticket
- add_jira_comment
- get_jira_ticket_status
- get_jira_comments
- list_jira_tickets
- general

If the user is providing information for a new ticket, use update_draft_ticket with a patch.
If the user wants to create or start a new ticket (but has not provided details yet), use start_create_ticket.
If the user confirms to create a ticket, use confirm_create_ticket.
If the user asks to check status, use get_jira_ticket_status with ticket_key.
If the user asks to add a comment, use add_jira_comment with ticket_key and comment.
If the user asks to show comments, use get_jira_comments with ticket_key.
If the user asks to list tickets, use list_jira_tickets with optional status (open|closed|all).

Patch fields allowed: summary, description, priority (P1-P4), start_date (YYYY-MM-DD).
Ticket key format: SUPPORT-123.

If you cannot determine, use intent general.

Respond with JSON only. No extra text.
"""

class AIService:
    async def generate_reply(self, session, user_message: str, history: list[dict] | None = None) -> str:
        if not settings.llm_api_key:
            return f"AI reply for: {user_message}"

        url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"
        messages = [{"role": "system", "content": PROMPT_REPLY}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})
        payload = {
            "model": settings.llm_model,
            "messages": messages,
            "temperature": 0.4,
            "max_tokens": 300,
        }
        headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
        client = get_async_client()
        try:
            response = await client.post(
                url,
                json=payload,
                headers=headers,
                timeout=15.0,
            )
            response.raise_for_status()
            content = (
                response.json()
                .get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
        except httpx.HTTPStatusError as exc:
            body = exc.response.text if exc.response is not None else ""
            request_id = exc.response.headers.get("x-request-id") if exc.response is not None else None
            logger.error(
                "AI generate_reply request failed with status=%s request_id=%s body=%s",
                exc.response.status_code if exc.response is not None else "unknown",
                request_id,
                body[:1000],
            )
            return f"AI reply for: {user_message}"
        except httpx.RequestError:
            logger.exception("AI generate_reply request failed")
            return f"AI reply for: {user_message}"
        return content or f"AI reply for: {user_message}"

    async def classify_intent(self, user_message: str) -> str:
        if not settings.llm_api_key:
            return "general"

        url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": settings.llm_model,
            "messages": [
                {
                    "role": "system",
                    "content": PROMPT_CLASSIFIER,
                },
                {"role": "user", "content": user_message},
            ],
            "temperature": 0,
            "max_tokens": 2,
        }
        headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
        client = get_async_client()
        try:
            response = await client.post(
                url,
                json=payload,
                headers=headers,
                timeout=10.0,
            )
            response.raise_for_status()
            content = (
                response.json()
                .get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
                .lower()
            )
        except httpx.HTTPStatusError as exc:
            body = exc.response.text if exc.response is not None else ""
            request_id = exc.response.headers.get("x-request-id") if exc.response is not None else None
            logger.error(
                "AI classify_intent request failed with status=%s request_id=%s body=%s",
                exc.response.status_code if exc.response is not None else "unknown",
                request_id,
                body[:1000],
            )
            return "sensitive"
        except httpx.RequestError:
            logger.exception("AI classify_intent request failed")
            return "sensitive"

        if "sensitive" in content:
            return "sensitive"
        if "general" in content:
            return "general"
        return "general"

    async def parse_jira_action(
        self,
        user_message: str,
        draft: dict | None,
        history: list[dict] | None = None,
    ) -> dict:
        if not settings.llm_api_key:
            return {"intent": "general"}

        url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"
        messages = [{"role": "system", "content": PROMPT_JIRA_ACTION}]
        if history:
            messages.extend(history)
        messages.append(
            {
                "role": "user",
                "content": (
                    f"Current draft: {draft}\\n"
                    f"User message: {user_message}"
                ),
            }
        )
        payload = {
            "model": settings.llm_model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": 200,
        }
        headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
        client = get_async_client()
        try:
            response = await client.post(
                url,
                json=payload,
                headers=headers,
                timeout=15.0,
            )
            response.raise_for_status()
            content = (
                response.json()
                .get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            return json.loads(content)
        except (httpx.RequestError, httpx.HTTPStatusError, json.JSONDecodeError):
            logger.exception("AI parse_jira_action failed")
            return {"intent": "general"}
