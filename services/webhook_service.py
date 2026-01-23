from sqlalchemy.orm import Session

from schemas.message import IncomingMessage
from models.models import Message
from services.session_service import SessionService

class WebhookService:
    def __init__(self, session_service: SessionService):
        self.session_service = session_service

    def handle_incoming_message(self, db: Session, message: IncomingMessage) -> None:
        session = self.session_service.get_or_create_session(
            db,
            message.platform,
            message.external_user_id,
        )
        self.session_service.touch(db, session)
        db_message = Message(
            session_id=session.id,
            role="user",
            content=message.text,
        )
        db.add(db_message)
        db.commit()
