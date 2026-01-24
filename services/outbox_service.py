import json
from datetime import datetime, timedelta, timezone
from typing import List
from sqlalchemy.orm import Session
from models.models import OutboxMessage, OutboxStatus

class OutboxService:
    def enqueue_reply(
        self,
        db: Session,
        session_id,
        platform: str,
        external_user_id: str,
        reply_text: str,
    ) -> OutboxMessage:
        payload = json.dumps({"reply_text": reply_text})
        message = OutboxMessage(
            session_id=session_id,
            platform=platform,
            external_user_id=external_user_id,
            payload=payload,
            status=OutboxStatus.pending.value,
        )
        db.add(message)
        db.flush()
        return message

    def fetch_pending(self, db: Session, limit: int = 50) -> List[OutboxMessage]:
        now = datetime.now(timezone.utc)
        return (
            db.query(OutboxMessage)
            .filter(
                (OutboxMessage.status == OutboxStatus.pending.value)
                | (
                    (OutboxMessage.status == OutboxStatus.failed.value)
                    & (OutboxMessage.next_retry_at <= now)
                )
            )
            .order_by(OutboxMessage.created_at)
            .limit(limit)
            .all()
        )

    def mark_sent(self, db: Session, message: OutboxMessage) -> None:
        message.status = OutboxStatus.sent.value
        message.attempts += 1
        message.last_error = None
        message.next_retry_at = None
        db.add(message)

    def mark_failed(self, db: Session, message: OutboxMessage, error: str) -> None:
        message.status = OutboxStatus.failed.value
        message.attempts += 1
        message.last_error = error
        message.next_retry_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        db.add(message)
