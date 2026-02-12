import asyncio
import json
import logging
import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from agents import Agent, Runner, function_tool

from adapters.registry import send_reply
from schemas.message import IncomingMessage
from core.config import settings
from services.auth_service import AuthService
from services.email_service import EmailService
from services.jira_service import JiraService
from services.message_service import MessageService
from services.session_service import SessionService
from models.models import User, TicketLink

class WebhookService:
    def __init__(
        self,
        session_service: SessionService,
        message_service: MessageService,
        auth_service: AuthService,
        email_service: EmailService,
        jira_service: JiraService,
    ):
        self.session_service = session_service
        self.message_service = message_service
        self.auth_service = auth_service
        self.email_service = email_service
        self.jira_service = jira_service
        self.logger = logging.getLogger(__name__)

    async def handle_incoming_message(self, db: Session, message: IncomingMessage) -> None:
        self.logger.info(
            "WebhookService received message",
            extra={
                "platform": message.platform,
                "external_user_id": message.external_user_id,
                "message_id": message.message_id,
            },
        )
        # Cek ke db apakah ada session untuk platform + external_user_id, jika belum ada, buat baru
        session = self.session_service.get_or_create_session(
            db,
            message.platform,
            message.external_user_id,
        )
        self._enforce_auth_expiry(db, session)
        if self.message_service.is_duplicate(db, session.id, message.message_id):
            self.logger.info(
                "Duplicate message ignored",
                extra={"session_id": str(session.id), "message_id": message.message_id},
            )
            return
        # Simpan message ke db
        saved_user_message = self.message_service.save_user_message(
            db,
            session.id,
            message.text,
            external_message_id=message.message_id,
        )

        if self._is_reset_message(message.text):
            reply_text = self._reset_draft(db, session)
            self.message_service.save_system_message(db, session.id, reply_text)
            await self._reply(db, session, message, reply_text)
            db.commit()
            return

        if self._is_confirm_message(message.text) and session.draft_ticket:
            missing = self._missing_draft_fields(session.draft_ticket or {})
            if missing:
                reply_text = self._prompt_next_missing_field(session.draft_ticket or {})
            else:
                blocked = self._require_authenticated(session)
                reply_text = blocked or await self._confirm_create_ticket(db, session)
            self.message_service.save_system_message(db, session.id, reply_text)
            await self._reply(db, session, message, reply_text)
            db.commit()
            return

        reply_text = await self._run_agent(db, session, message, saved_user_message.id)
        self.message_service.save_system_message(db, session.id, reply_text)
        await self._reply(db, session, message, reply_text)
        db.commit()
    
    async def _reply(self, db, session, message: IncomingMessage, text: str) -> None:
        await asyncio.to_thread(send_reply, message, text)

    def _is_valid_email(self, email: str) -> bool:
        return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) is not None

    def _is_confirm_message(self, text: str) -> bool:
        normalized = (text or "").strip().lower()
        if not normalized:
            return False
        direct = {"yes", "ok", "okay", "submit", "confirm", "ya", "iya", "oke", "lanjut", "lanjutkan"}
        if normalized in direct:
            return True
        return bool(re.search(r"\b(yes|ok|okay|submit|confirm|ya|iya|oke|lanjut|lanjutkan)\b", normalized))

    def _is_reset_message(self, text: str) -> bool:
        normalized = (text or "").strip().lower()
        if not normalized:
            return False
        direct = {"reset", "start over", "startover", "batal"}
        if normalized in direct:
            return True
        return bool(re.search(r"\b(reset|start\s*over|batal)\b", normalized))

    def _enforce_auth_expiry(self, db, session) -> None:
        if not session.auth_expires_at:
            return
        expires_at = session.auth_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            session.auth_status = "anonymous"
            session.user_id = None
            session.auth_expires_at = None
            db.add(session)

    def _build_ai_history(self, db, session_id, exclude_message_id, limit: int = 8) -> list[dict]:
        messages = self.message_service.get_recent_messages(db, session_id, limit=limit + 1)
        history = []
        for message in messages:
            if message.id == exclude_message_id:
                continue
            role = "assistant" if message.role == "system" else "user"
            if message.content:
                history.append({"role": role, "content": message.content})
            if len(history) >= limit:
                break
        history.reverse()
        return history

    def _require_authenticated(self, session) -> str | None:
        if session.auth_status != "authenticated":
            return "This action requires access to Jira. Please verify your company email to continue."
        return None

    def _normalize_priority(self, value: str | None) -> str | None:
        if not value:
            return None
        normalized = value.strip().upper()
        mapping = {
            "URGENT": "P1",
            "HIGH": "P2",
            "MEDIUM": "P3",
            "LOW": "P4",
        }
        if normalized in mapping:
            return mapping[normalized]
        if normalized in {"P1", "P2", "P3", "P4"}:
            return normalized
        return value.strip()

    def _coerce_start_date(self, value: str | None) -> str | None:
        if not value:
            return None
        normalized = value.strip()
        if re.match(r"^\d{4}-\d{2}-\d{2}$", normalized):
            return normalized
        match = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", normalized)
        if match:
            day, month, year = match.groups()
            return f"{year}-{month}-{day}"
        return normalized

    def _build_agent_input(self, context: dict, history: list[dict], user_message: str) -> str:
        history_lines = []
        for item in history:
            role = item.get("role", "user")
            content = item.get("content") or ""
            history_lines.append(f"{role}: {content}")
        history_text = "\n".join(history_lines) if history_lines else "none"

        return (
            "Context (json):\n"
            f"{json.dumps(context, ensure_ascii=True, indent=2)}\n\n"
            "Recent conversation (oldest to newest):\n"
            f"{history_text}\n\n"
            "User message:\n"
            f"{user_message}"
        )

    async def _run_agent(self, db, session, message: IncomingMessage, exclude_message_id):
        if not settings.openai_api_key:
            return "AI is not configured. Please set OPENAI_API_KEY."

        if self._is_confirm_message(message.text) and session.draft_ticket:
            missing = self._missing_draft_fields(session.draft_ticket or {})
            if not missing:
                blocked = self._require_authenticated(session)
                if blocked:
                    return blocked
                self.logger.info(
                    "Confirm shortcut triggered session_id=%s",
                    str(session.id),
                )
                return await self._confirm_create_ticket(db, session)
            self.logger.info(
                "Confirm received but draft missing fields session_id=%s missing=%s",
                str(session.id),
                ", ".join(missing),
            )
            return self._prompt_next_missing_field(session.draft_ticket or {})

        user = db.get(User, session.user_id) if session.user_id else None
        history = self._build_ai_history(db, session.id, exclude_message_id, limit=8)
        context = {
            "auth_status": session.auth_status,
            "platform": session.platform,
            "external_user_id": session.external_user_id,
            "draft_ticket": session.draft_ticket,
            "user": {
                "id": str(user.id),
                "name": user.name,
                "email": user.email,
            } if user else None,
        }

        instructions = (
            "You are the orchestrator for an omnichannel customer support assistant.\n"
            "Decide whether to call tools or reply directly.\n\n"
            "RULES:\n"
            "- Detect the language of the user automatically.\n"
            "- Always respond in the same language as the current user message.\n"
            "- Support any language.\n"
            "- If the user mixes languages, respond naturally following their style.\n"
            "- If auth_status is pending_verification: call send_verification_reminder and do not call Jira tools.\n"
            "- If auth_status is anonymous and the user requests Jira/internal/customer-specific data: "
            "ask for a company email, or call start_email_verification if the email is provided.\n"
            "- Jira tools require authenticated status.\n"
            "- If the user asks general/non-sensitive questions, reply directly without Jira tools.\n"
            "- If a tool returns a user-facing message, reply with that exact message only.\n\n"
            "JIRA WORKFLOWS:\n"
            "MODE A: CHECK TICKET STATUS\n"
            "- Trigger: user asks status of a ticket (e.g., SUPPORT-123).\n"
            "- Action: call get_jira_ticket_status(ticket_key).\n\n"
            "MODE B: CREATE NEW TICKET\n"
            "- Required fields: summary, description, priority (P1-P4, default P3), start_date (YYYY-MM-DD, default today).\n"
            "- Use start_ticket_flow or update_ticket_draft to collect missing fields.\n"
            "- Once all fields are collected, ask for confirmation. If confirmed, call confirm_create_ticket.\n\n"
            "MODE B-RESET: RESET TICKET DRAFT\n"
            "- Trigger: user asks to reset/start over/cancel the draft.\n"
            "- Action: call reset_ticket_draft().\n\n"
            "MODE C: ADD COMMENT\n"
            "- Trigger: user wants to add a comment to an existing ticket.\n"
            "- Action: call add_jira_comment(ticket_key, comment).\n\n"
            "MODE D: VIEW COMMENTS\n"
            "- Trigger: user asks to see comments/history of a ticket.\n"
            "- Action: call get_jira_comments(ticket_key).\n\n"
            "MODE E: LIST TICKETS\n"
            "- Trigger: user asks to list tickets.\n"
            "- Action: call list_jira_tickets(status) where status is open|closed|all (default all).\n"
        )

        @function_tool
        async def start_email_verification(email: str) -> str:
            """Start email verification for the provided company email."""
            if session.auth_status == "authenticated":
                return "Your email is already verified."
            if not self._is_valid_email(email):
                return "Please provide a valid company email address."
            if not await self.jira_service.email_exists(email):
                self.logger.warning(
                    "Email not found in Jira",
                    extra={"session_id": str(session.id)},
                )
                return "This email address is not registered in Jira."

            token = self.auth_service.start_email_verification(db, session, email)
            verify_link = self.auth_service.build_verify_link(token)
            await asyncio.to_thread(self.email_service.send_verification_email, email, verify_link)
            self.logger.info(
                "Sent verification email",
                extra={"session_id": str(session.id)},
            )
            return (
                "📧 We have sent a verification email.\n"
                "Please check your inbox and click the link to continue."
            )

        @function_tool
        async def send_verification_reminder() -> str:
            """Remind the user that email verification is pending."""
            return (
                "Your email verification is still pending.\n"
                "Please check your inbox and click the verification link to continue."
            )

        @function_tool
        async def start_ticket_flow(
            summary: str | None = None,
            description: str | None = None,
            priority: str | None = None,
            start_date: str | None = None,
        ) -> str:
            """Start a new Jira ticket flow and collect missing fields."""
            blocked = self._require_authenticated(session)
            if blocked:
                return blocked
            patch = {
                "summary": summary,
                "description": description,
                "priority": self._normalize_priority(priority),
                "start_date": self._coerce_start_date(start_date),
            }
            patch = {k: v for k, v in patch.items() if v}
            return self._start_ticket_flow(db, session, patch)

        @function_tool
        async def update_ticket_draft(
            summary: str | None = None,
            description: str | None = None,
            priority: str | None = None,
            start_date: str | None = None,
        ) -> str:
            """Update the current Jira ticket draft with provided fields."""
            blocked = self._require_authenticated(session)
            if blocked:
                return blocked
            patch = {
                "summary": summary,
                "description": description,
                "priority": self._normalize_priority(priority),
                "start_date": self._coerce_start_date(start_date),
            }
            patch = {k: v for k, v in patch.items() if v}
            if not patch:
                return self._prompt_next_missing_field(session.draft_ticket or {})
            return self._update_draft(db, session, patch)

        @function_tool
        async def confirm_create_ticket() -> str:
            """Create the Jira ticket from the current draft."""
            blocked = self._require_authenticated(session)
            if blocked:
                return blocked
            return await self._confirm_create_ticket(db, session)

        @function_tool
        async def reset_ticket_draft() -> str:
            """Clear the current Jira ticket draft and restart the flow."""
            return self._reset_draft(db, session)

        @function_tool
        async def add_jira_comment(ticket_key: str, comment: str) -> str:
            """Add a comment to an existing Jira ticket."""
            blocked = self._require_authenticated(session)
            if blocked:
                return blocked
            return await self._add_jira_comment(
                db,
                session,
                {"ticket_key": ticket_key, "comment": comment},
            )

        @function_tool
        async def get_jira_ticket_status(ticket_key: str) -> str:
            """Get the status of a Jira ticket."""
            blocked = self._require_authenticated(session)
            if blocked:
                return blocked
            return await self._get_jira_ticket_status(
                db,
                session,
                {"ticket_key": ticket_key},
            )

        @function_tool
        async def get_jira_comments(ticket_key: str) -> str:
            """Get the latest public comments of a Jira ticket."""
            blocked = self._require_authenticated(session)
            if blocked:
                return blocked
            return await self._get_jira_comments(
                db,
                session,
                {"ticket_key": ticket_key},
            )

        @function_tool
        async def list_jira_tickets(status: str | None = None) -> str:
            """List Jira tickets for the authenticated user."""
            blocked = self._require_authenticated(session)
            if blocked:
                return blocked
            return await self._list_jira_tickets(
                db,
                session,
                {"status": status},
            )

        draft = session.draft_ticket or {}
        missing_fields = self._missing_draft_fields(draft) if draft else []
        is_confirm = self._is_confirm_message(message.text)

        tools = [
            start_email_verification,
            send_verification_reminder,
            update_ticket_draft,
            reset_ticket_draft,
            add_jira_comment,
            get_jira_ticket_status,
            get_jira_comments,
            list_jira_tickets,
        ]
        if not draft:
            tools.insert(2, start_ticket_flow)
        if draft and not missing_fields and is_confirm:
            tools.append(confirm_create_ticket)

        agent = Agent(
            name="Omnichannel Orchestrator",
            instructions=instructions,
            model=settings.llm_model,
            tools=tools,
        )

        prompt = self._build_agent_input(context, history, message.text)
        try:
            result = await Runner.run(agent, input=prompt)
            output = (result.final_output or "").strip()
            if not output:
                return "Sorry, I could not process that."
            return output
        except Exception:
            self.logger.exception("Agent run failed")
            return "Sorry, I could not process that."

    def _update_draft(self, db, session, patch: dict) -> str:
        draft = session.draft_ticket or {}
        allowed = {"summary", "description", "priority", "start_date"}
        for key, value in patch.items():
            if key in allowed and value:
                draft[key] = value
        self.logger.info(
            "Draft updated session_id=%s draft=%s",
            str(session.id),
            json.dumps(draft, ensure_ascii=False),
        )

        missing = self._missing_draft_fields(draft)
        draft["status"] = "preview" if not missing else "collecting"
        draft["last_update"] = datetime.now(timezone.utc).isoformat()
        session.draft_ticket = draft
        db.add(session)
        db.commit()

        if missing:
            self.logger.info(
                "Draft missing fields",
                extra={"session_id": str(session.id), "missing": ", ".join(missing)},
            )
            return self._prompt_next_missing_field(draft)

        return (
            "Here is your ticket draft:\n"
            f"Summary: {draft.get('summary')}\n"
            f"Description: {draft.get('description')}\n"
            f"Priority: {draft.get('priority')}\n"
            f"Start Date: {draft.get('start_date')}\n\n"
            "Reply with yes/ok/submit to create the ticket, or tell me what to change."
        )

    async def _confirm_create_ticket(self, db, session) -> str:
        draft = session.draft_ticket or {}
        if not draft.get("priority"):
            draft["priority"] = "P3"
        if not draft.get("start_date"):
            draft["start_date"] = datetime.now(timezone.utc).date().isoformat()
        session.draft_ticket = draft
        db.add(session)

        required = ["summary", "description", "priority", "start_date"]
        missing = self._missing_draft_fields(draft)
        if missing:
            self.logger.info(
                "Cannot create ticket, missing fields session_id=%s missing=%s draft=%s",
                str(session.id),
                ", ".join(missing),
                json.dumps(draft, ensure_ascii=False),
            )
            return self._prompt_next_missing_field(draft)

        user = db.get(User, session.user_id) if session.user_id else None
        if not user:
            self.logger.warning(
                "Session not linked to user",
                extra={"session_id": str(session.id)},
            )
            return "Your account is not linked to a user profile yet."

        try:
            result = await self.jira_service.create_ticket(
                summary=draft["summary"],
                description=draft["description"],
                priority_key=draft["priority"],
                start_date=draft["start_date"],
                reporter_email=user.email,
            )
        except RuntimeError:
            self.logger.exception(
                "Jira create_ticket failed",
                extra={"session_id": str(session.id)},
            )
            return "Sorry, I could not create the ticket. Please try again."

        session.draft_ticket = None
        db.add(session)

        issue_key = result.get("issue_key")
        self.logger.info(
            "Ticket created",
            extra={"session_id": str(session.id), "issue_key": issue_key},
        )
        if issue_key and user.organization_id:
            link = TicketLink(
                ticket_key=issue_key,
                session_id=session.id,
                organization_id=user.organization_id,
                platform=session.platform,
            )
            db.add(link)
        return f"Ticket created: {issue_key}"

    async def _add_jira_comment(self, db, session, action: dict) -> str:
        ticket_key = action.get("ticket_key")
        comment = action.get("comment")
        if not ticket_key or not comment:
            self.logger.info(
                "Add comment missing data",
                extra={"session_id": str(session.id)},
            )
            return "Please include the ticket key and the comment text."

        user = db.get(User, session.user_id) if session.user_id else None
        if not user:
            self.logger.warning(
                "Session not linked to user",
                extra={"session_id": str(session.id)},
            )
            return "Your account is not linked to a user profile yet."

        try:
            detail = await self.jira_service.get_ticket_detail(ticket_key)
        except RuntimeError:
            self.logger.exception(
                "Jira get_ticket_detail failed",
                extra={"session_id": str(session.id), "ticket_key": ticket_key},
            )
            return "I could not find that ticket."

        if (detail.get("reporter_email") or "").lower() != user.email.lower():
            self.logger.warning(
                "User not reporter for ticket",
                extra={"session_id": str(session.id), "ticket_key": ticket_key},
            )
            return "You are not the reporter of this ticket."

        try:
            await self.jira_service.add_comment(
                ticket_key,
                comment,
                author={"name": user.name, "email": user.email},
            )
        except RuntimeError:
            self.logger.exception(
                "Jira add_comment failed",
                extra={"session_id": str(session.id), "ticket_key": ticket_key},
            )
            return "Sorry, I could not add your comment."

        self.logger.info(
            "Comment added",
            extra={"session_id": str(session.id), "ticket_key": ticket_key},
        )
        return f"Comment added to {ticket_key}."

    async def _get_jira_ticket_status(self, db, session, action: dict) -> str:
        ticket_key = action.get("ticket_key")
        if not ticket_key:
            self.logger.info(
                "Get ticket status missing ticket_key",
                extra={"session_id": str(session.id)},
            )
            return "Please provide the ticket key."

        user = db.get(User, session.user_id) if session.user_id else None
        if not user:
            self.logger.warning(
                "Session not linked to user",
                extra={"session_id": str(session.id)},
            )
            return "Your account is not linked to a user profile yet."

        try:
            detail = await self.jira_service.get_ticket_detail(ticket_key)
        except RuntimeError:
            self.logger.exception(
                "Jira get_ticket_detail failed",
                extra={"session_id": str(session.id), "ticket_key": ticket_key},
            )
            return "I could not find that ticket."

        if (detail.get("reporter_email") or "").lower() != user.email.lower():
            self.logger.warning(
                "User not reporter for ticket",
                extra={"session_id": str(session.id), "ticket_key": ticket_key},
            )
            return "You are not the reporter of this ticket."

        return (
            f"{ticket_key} status: {detail.get('status')}\n"
            f"Assignee: {detail.get('assignee') or 'Unassigned'}\n"
            f"Priority: {detail.get('priority')}"
        )

    async def _get_jira_comments(self, db, session, action: dict) -> str:
        ticket_key = action.get("ticket_key")
        if not ticket_key:
            self.logger.info(
                "Get comments missing ticket_key",
                extra={"session_id": str(session.id)},
            )
            return "Please provide the ticket key."

        user = db.get(User, session.user_id) if session.user_id else None
        if not user:
            self.logger.warning(
                "Session not linked to user",
                extra={"session_id": str(session.id)},
            )
            return "Your account is not linked to a user profile yet."

        try:
            detail = await self.jira_service.get_ticket_detail(ticket_key)
        except RuntimeError:
            self.logger.exception(
                "Jira get_ticket_detail failed",
                extra={"session_id": str(session.id), "ticket_key": ticket_key},
            )
            return "I could not find that ticket."

        if (detail.get("reporter_email") or "").lower() != user.email.lower():
            self.logger.warning(
                "User not reporter for ticket",
                extra={"session_id": str(session.id), "ticket_key": ticket_key},
            )
            return "You are not the reporter of this ticket."

        try:
            comments = await self.jira_service.get_public_comments(ticket_key, limit=5)
        except RuntimeError:
            self.logger.exception(
                "Jira get_public_comments failed",
                extra={"session_id": str(session.id), "ticket_key": ticket_key},
            )
            return "Sorry, I could not fetch comments."

        if not comments:
            return "No public comments yet."

        formatted = []
        for comment in comments:
            author = comment.get("author") or "Unknown"
            body = comment.get("body") or ""
            formatted.append(f"- {author}: {body}")
        return "Latest comments:\n" + "\n".join(formatted)

    async def _list_jira_tickets(self, db, session, action: dict) -> str:
        user = db.get(User, session.user_id) if session.user_id else None
        if not user:
            self.logger.warning(
                "Session not linked to user",
                extra={"session_id": str(session.id)},
            )
            return "Your account is not linked to a user profile yet."

        status_filter = (action.get("status") or "all").lower()
        if status_filter not in {"open", "closed", "all"}:
            status_filter = "all"

        try:
            tickets = await self.jira_service.list_tickets_by_reporter(
                user.email,
                status_filter=status_filter,
            )
        except RuntimeError:
            self.logger.exception(
                "Jira list_tickets_by_reporter failed",
                extra={"session_id": str(session.id)},
            )
            return "Sorry, I could not list your tickets."

        if not tickets:
            return "No tickets found."

        def status_emoji(status: str | None) -> str:
            text = (status or "").lower()
            if any(key in text for key in ["done", "closed", "resolved"]):
                return "⚪"
            if any(key in text for key in ["progress", "review", "blocked"]):
                return "🟡"
            return "🟢"

        lines = []
        for ticket in tickets:
            status = ticket.get("status") or "Unknown"
            priority = ticket.get("priority") or "-"
            summary = ticket.get("summary") or "-"
            lines.append(
                f"{status_emoji(status)} {ticket.get('ticket_key')}\n"
                f"{summary}\n"
                f"Status   : {status}\n"
                f"Priority : {priority}"
            )

        header = (
            "📋 Here’s your ticket:"
            if len(tickets) == 1
            else f"📋 Here are your tickets: ({len(tickets)})"
        )
        return header + "\n\n" + "\n\n".join(lines)

    def _reset_draft(self, db, session) -> str:
        if not session.draft_ticket:
            return "No active draft to reset."
        session.draft_ticket = None
        db.add(session)
        self.logger.info(
            "Draft reset session_id=%s",
            str(session.id),
        )
        return "Draft reset. Tell me the new issue to create a ticket."

    def _start_ticket_flow(self, db, session, patch: dict) -> str:
        if patch:
            self.logger.info(
                "Start ticket flow with patch session_id=%s patch=%s",
                str(session.id),
                json.dumps(patch, ensure_ascii=False),
            )
            return self._update_draft(db, session, patch)

        draft = session.draft_ticket or {}
        draft["status"] = "collecting"
        draft["last_update"] = datetime.now(timezone.utc).isoformat()
        session.draft_ticket = draft
        db.add(session)
        db.commit()
        self.logger.info(
            "Start ticket flow initialized session_id=%s draft=%s",
            str(session.id),
            json.dumps(draft, ensure_ascii=False),
        )
        return self._prompt_next_missing_field(draft)

    def _missing_draft_fields(self, draft: dict) -> list[str]:
        ordered_fields = ["summary", "description", "priority", "start_date"]
        return [field for field in ordered_fields if not draft.get(field)]

    def _prompt_next_missing_field(self, draft: dict) -> str:
        missing = self._missing_draft_fields(draft)
        if not missing:
            return "All required fields are present. Please reply yes/ok/submit to create the ticket."

        next_field = missing[0]
        prompts = {
            "summary": "Please provide a short summary for the ticket.",
            "description": "Please describe the issue in more detail.",
            "priority": "What priority is this? (P1/P2/P3/P4)",
            "start_date": "What is the start date? (YYYY-MM-DD)",
        }
        return prompts.get(next_field, "Please provide a short summary for the ticket.")
