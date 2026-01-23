from fastapi import Depends
from services.session_service import SessionService
from services.webhook_service import WebhookService

def get_session_service() -> SessionService:
    return SessionService()

def get_webhook_service(session_service: SessionService = Depends(get_session_service)) -> WebhookService:
    return WebhookService(session_service)
