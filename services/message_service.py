from typing import Optional
import html
import re

from sqlalchemy.orm import Session
from sqlalchemy import desc
from models.models import Message

class MessageService:
    def _sanitize_for_storage(self, text: str) -> str:
        if not text:
            return text
        sanitized = re.sub(r"(?i)<br\s*/?>", "\n", text)
        sanitized = re.sub(r"<[^>]+>", "", sanitized)
        sanitized = html.unescape(sanitized)
        return sanitized.strip()

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
        message = Message(
            session_id=session_id,
            role="agent",
            content=self._sanitize_for_storage(text),
        )
        db.add(message)
        db.flush()
        return message

    def save_employee_message(self, db: Session, session_id, text: str) -> Message:
        message = Message(
            session_id=session_id,
            role="employee",
            content=self._sanitize_for_storage(text),
        )
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

    def get_recent_messages(
        self,
        db: Session,
        session_id,
        limit: int = 8,
    ) -> list[Message]:
        return (
            db.query(Message)
            .filter(Message.session_id == session_id)
            .order_by(desc(Message.created_at), desc(Message.id))
            .limit(limit)
            .all()
        )
