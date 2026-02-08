import asyncio
import logging
import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from adapters.registry import send_reply
from schemas.message import IncomingMessage
from services.ai_service import AIService
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
        ai_service: AIService,
        jira_service: JiraService,
    ):
        self.session_service = session_service
        self.message_service = message_service
        self.auth_service = auth_service
        self.email_service = email_service
        self.ai_service = ai_service
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
        
        if session.auth_status == "authenticated":
            self.logger.info(
                "Auth status: authenticated",
                extra={"session_id": str(session.id)},
            )
            await self._handle_business_flow(db, session, message, saved_user_message.id)
        elif session.auth_status == "pending_verification":
            self.logger.info(
                "Auth status: pending_verification",
                extra={"session_id": str(session.id)},
            )
            await self._handle_pending_verification(db, session, message)
        else:
            self.logger.info(
                "Auth status: anonymous",
                extra={"session_id": str(session.id)},
            )
            email = message.text.strip()
            if self._is_valid_email(email):
                await self._handle_auth_flow(db, session, message)
            else:
                intent = await self.ai_service.classify_intent(message.text)
                self.logger.info(
                    "Classified intent",
                    extra={"session_id": str(session.id), "intent": intent},
                )
                if intent == "sensitive":
                    await self._handle_auth_flow(db, session, message)
                else:
                    await self._handle_business_flow(db, session, message, saved_user_message.id)
        db.commit()
    
    async def _handle_business_flow(self, db, session, message: IncomingMessage, exclude_message_id):
        history = self._build_ai_history(db, session.id, exclude_message_id, limit=8)
        action = await self.ai_service.parse_jira_action(
            message.text,
            session.draft_ticket,
            history=history,
        )
        intent = (action.get("intent") or "general").lower()
        self.logger.info(
            "Parsed Jira action",
            extra={"session_id": str(session.id), "intent": intent},
        )

        if intent in {"update_draft_ticket", "revise_draft_ticket"}:
            patch = action.get("patch") or {}
            reply = self._update_draft(db, session, patch)
        elif intent == "confirm_create_ticket":
            reply = await self._confirm_create_ticket(db, session)
        elif intent == "add_jira_comment":
            reply = await self._add_jira_comment(db, session, action)
        elif intent == "get_jira_ticket_status":
            reply = await self._get_jira_ticket_status(db, session, action)
        elif intent == "get_jira_comments":
            reply = await self._get_jira_comments(db, session, action)
        elif intent == "list_jira_tickets":
            reply = await self._list_jira_tickets(db, session, action)
        else:
            reply = await self.ai_service.generate_reply(
                session=session,
                user_message=message.text,
                history=history,
            )

        self.message_service.save_system_message(db, session.id, reply)
        await self._reply(db, session, message, reply)
   
    async def _handle_auth_flow(self, db, session, message: IncomingMessage):
        email = message.text.strip()

        if not self._is_valid_email(email):
            self.logger.info(
                "Invalid email in auth flow",
                extra={"session_id": str(session.id)},
            )
            reply_text = "This action requires access to Jira. Please verify your company email to continue."
            self.message_service.save_system_message(
                db,
                session.id,
                reply_text,
            )
            await self._reply(db, session, message, reply_text)
            return

        if not await self.jira_service.email_exists(email):
            self.logger.warning(
                "Email not found in Jira",
                extra={"session_id": str(session.id)},
            )
            await self._reply(db, session, message, "This email address is not registered in Jira.")
            return

        token = self.auth_service.start_email_verification(db, session, email)
        verify_link = self.auth_service.build_verify_link(token)
        await asyncio.to_thread(self.email_service.send_verification_email, email, verify_link)
        self.logger.info(
            "Sent verification email",
            extra={"session_id": str(session.id)},
        )

        reply_text = (
            "📧 We have sent a verification email.\n"
            "Please check your inbox and click the link to continue."
        )
        await self._save_and_reply(db, session, message, reply_text)

    async def _handle_pending_verification(self, db, session, message: IncomingMessage):
        self.logger.info(
            "Pending verification reminder",
            extra={"session_id": str(session.id)},
        )
        reply_text = (
            "Your email verification is still pending.\n"
            "Please check your inbox and click the verification link to continue."
        )
        await self._save_and_reply(db, session, message, reply_text)

    async def _save_and_reply(self, db, session, message: IncomingMessage, text: str) -> None:
        self.message_service.save_system_message(db, session.id, text)
        await self._reply(db, session, message, text)
    
    async def _reply(self, db, session, message: IncomingMessage, text: str) -> None:
        await asyncio.to_thread(send_reply, message, text)

    def _is_valid_email(self, email: str) -> bool:
        return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) is not None

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

    def _update_draft(self, db, session, patch: dict) -> str:
        draft = session.draft_ticket or {}
        allowed = {"summary", "description", "priority", "start_date"}
        for key, value in patch.items():
            if key in allowed and value:
                draft[key] = value

        missing = [field for field in allowed if not draft.get(field)]
        draft["status"] = "preview" if not missing else "collecting"
        draft["last_update"] = datetime.now(timezone.utc).isoformat()
        session.draft_ticket = draft
        db.add(session)

        if missing:
            fields = ", ".join(missing)
            self.logger.info(
                "Draft missing fields",
                extra={"session_id": str(session.id), "missing": fields},
            )
            return f"I still need: {fields}. Please provide them."

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
        required = ["summary", "description", "priority", "start_date"]
        missing = [field for field in required if not draft.get(field)]
        if missing:
            fields = ", ".join(missing)
            self.logger.info(
                "Cannot create ticket, missing fields",
                extra={"session_id": str(session.id), "missing": fields},
            )
            return f"I still need: {fields}. Please provide them."

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
