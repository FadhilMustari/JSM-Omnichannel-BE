import asyncio
import re

from sqlalchemy.orm import Session

from schemas.message import IncomingMessage
from services.ai_service import AIService
from services.auth_service import AuthService
from services.email_service import EmailService
from services.jira_service import JiraService
from services.message_service import MessageService
from services.outbox_service import OutboxService
from services.session_service import SessionService

class WebhookService:
    def __init__(
        self,
        session_service: SessionService,
        message_service: MessageService,
        auth_service: AuthService,
        email_service: EmailService,
        ai_service: AIService,
        jira_service: JiraService,
        outbox_service: OutboxService,
    ):
        self.session_service = session_service
        self.message_service = message_service
        self.auth_service = auth_service
        self.email_service = email_service
        self.ai_service = ai_service
        self.jira_service = jira_service
        self.outbox_service = outbox_service

    async def handle_incoming_message(self, db: Session, message: IncomingMessage) -> None:
        # Cek ke db apakah ada session untuk platform + external_user_id, jika belum ada, buat baru
        session = self.session_service.get_or_create_session(
            db,
            message.platform,
            message.external_user_id,
        )
        if self.message_service.is_duplicate(db, session.id, message.message_id):
            return
        # Simpan message ke db
        self.message_service.save_user_message(
            db,
            session.id,
            message.text,
            external_message_id=message.message_id,
        )
        
        if session.auth_status == "authenticated":
            await self._handle_business_flow(db, session, message)
        elif session.auth_status == "pending_verification":
            self._handle_pending_verification(db, session)
        else:
            email = message.text.strip()
            if self._is_valid_email(email):
                await self._handle_auth_flow(db, session, message)
            else:
                intent = await self.ai_service.classify_intent(message.text)
                if intent == "sensitive":
                    await self._handle_auth_flow(db, session, message)
                else:
                    await self._handle_business_flow(db, session, message)
        db.commit()
    
    async def _handle_business_flow(self, db, session, message: IncomingMessage):
        # Example: call AI service
        reply = await self.ai_service.generate_reply(
            session=session,
            user_message=message.text,
        )
        self.message_service.save_system_message(
            db,
            session.id,
            reply,
        )
        self._reply(db, session, message, reply)

    
    async def _handle_auth_flow(self, db, session, message: IncomingMessage):
        email = message.text.strip()

        if not self._is_valid_email(email):
            reply_text = "This action requires access to Jira. Please verify your company email to continue."
            self.message_service.save_system_message(
                db,
                session.id,
                reply_text,
            )
            self._reply(db, session, message, reply_text)
            return

        if not await self.jira_service.email_exists(email):
            self._reply(db, session, message, "This email address is not registered in Jira.")
            return

        token = self.auth_service.start_email_verification(db, session, email)
        verify_link = self.auth_service.build_verify_link(token)
        await asyncio.to_thread(self.email_service.send_verification_email, email, verify_link)

        reply_text = (
            "📧 We have sent a verification email.\n"
            "Please check your inbox and click the link to continue."
        )
        self._save_and_reply(db, session, message, reply_text)

    def _handle_pending_verification(self, db, session, message: IncomingMessage):
        reply_text = (
            "Your email verification is still pending.\n"
            "Please check your inbox and click the verification link to continue."
        )
        self._save_and_reply(db, session, message, reply_text)

    def _save_and_reply(self, db, session, message: IncomingMessage, text: str) -> None:
        self.message_service.save_system_message(db, session.id, text)
        self._reply(db, session, message, text)
    
    def _reply(self, db, session, message: IncomingMessage, text: str) -> None:
        self.outbox_service.enqueue_reply(
            db,
            session.id,
            message.platform,
            message.external_user_id,
            text,
        )

    def _is_valid_email(self, email: str) -> bool:
        return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) is not None
