from sqlalchemy.orm import Session
from models.models import Message

class MessageService:
    def save_user_message(self, db: Session, session_id, text: str) -> Message:
        message = Message(session_id=session_id, role="user", content=text)
        db.add(message)
        db.flush()  # penting, belum commit
        return message

    def save_system_message(self, db: Session, session_id, text: str) -> Message:
        message = Message(session_id=session_id, role="system", content=text)
        db.add(message)
        db.flush()
        return message
