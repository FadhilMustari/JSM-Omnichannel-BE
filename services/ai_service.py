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

import requests

from core.config import settings

class AIService:
    def generate_reply(self, session, user_message: str) -> str:
        if not settings.llm_api_key:
            return f"AI reply for: {user_message}"

        url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": settings.llm_model,
            "messages": [
                {
                    "role": "system",
                    "content": PROMPT_REPLY,
                },
                {"role": "user", "content": user_message},
            ],
            "temperature": 0.4,
            "max_tokens": 300,
        }
        headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        content = (
            response.json()
            .get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        return content or f"AI reply for: {user_message}"

    def classify_intent(self, user_message: str) -> str:
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
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        content = (
            response.json()
            .get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
            .lower()
        )

        if "sensitive" in content:
            return "sensitive"
        if "general" in content:
            return "general"
        return "general"
