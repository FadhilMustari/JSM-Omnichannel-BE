from typing import Optional

from sqlalchemy.orm import Session
from models.models import Message

class MessageService:
    def save_user_message(
        self,
        db: Session,
        session_id,
        text: str,
        external_message_id: Optional[str] = None,
    ) -> Message:
        message = Message(
            session_id=session_id,
            role="user",
            content=text,
            external_message_id=external_message_id,
        )
        db.add(message)
        db.flush()  # penting, belum commit
        return message

    def save_system_message(self, db: Session, session_id, text: str) -> Message:
        message = Message(session_id=session_id, role="system", content=text)
        db.add(message)
        db.flush()
        return message

    def is_duplicate(
        self,
        db: Session,
        session_id,
        external_message_id: Optional[str],
    ) -> bool:
        if not external_message_id:
            return False
        return (
            db.query(Message)
            .filter(
                Message.session_id == session_id,
                Message.external_message_id == external_message_id,
            )
            .first()
            is not None
        )
