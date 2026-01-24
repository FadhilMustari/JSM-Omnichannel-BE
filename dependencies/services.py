from fastapi import Depends
from services.ai_service import AIService
from services.auth_service import AuthService
from services.email_service import EmailService
from services.jira_service import JiraService
from services.message_service import MessageService
from services.outbox_service import OutboxService
from services.session_service import SessionService
from services.webhook_service import WebhookService

def get_session_service() -> SessionService:
    return SessionService()

def get_message_service() -> MessageService:
    return MessageService()

def get_outbox_service() -> OutboxService:
    return OutboxService()

def get_ai_service() -> AIService:
    return AIService()

def get_auth_service() -> AuthService:
    return AuthService()

def get_email_service() -> EmailService:
    return EmailService()

def get_jira_service() -> JiraService:
    return JiraService()

def get_webhook_service(
    session_service: SessionService = Depends(get_session_service),
    message_service: MessageService = Depends(get_message_service),
    auth_service: AuthService = Depends(get_auth_service),
    email_service: EmailService = Depends(get_email_service),
    ai_service: AIService = Depends(get_ai_service),
    jira_service: JiraService = Depends(get_jira_service),
    outbox_service: OutboxService = Depends(get_outbox_service),
) -> WebhookService:
    return WebhookService(
        session_service=session_service,
        message_service=message_service,
        auth_service=auth_service,
        email_service=email_service,
        ai_service=ai_service,
        jira_service=jira_service,
        outbox_service=outbox_service,
    )
