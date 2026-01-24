import json
import time
from datetime import datetime, timezone
from core.database import SessionLocal
from schemas.message import IncomingMessage
from adapters.registry import send_reply
from services.outbox_service import OutboxService

def process_outbox(limit: int = 50) -> int:
    outbox_service = OutboxService()
    processed = 0

    db = SessionLocal()
    try:
        messages = outbox_service.fetch_pending(db, limit=limit)
        for message in messages:
            try:
                payload = json.loads(message.payload)
                reply_text = payload.get("reply_text", "")
                if not reply_text:
                    outbox_service.mark_failed(db, message, "Missing reply_text in payload")
                    db.commit()
                    continue

                outgoing = IncomingMessage(
                    platform=message.platform,
                    external_user_id=message.external_user_id,
                    message_id="",
                    text="",
                    raw_payload={},
                )
                send_reply(outgoing, reply_text)
                outbox_service.mark_sent(db, message)
                db.commit()
                processed += 1
            except Exception as exc:
                outbox_service.mark_failed(db, message, str(exc))
                db.commit()
    finally:
        db.close()

    return processed


if __name__ == "__main__":
    print(f"[{datetime.now(timezone.utc).isoformat()}] outbox worker started")
    while True:
        processed = process_outbox(limit=10)
        if processed > 0:
            print(
                f"[{datetime.now(timezone.utc).isoformat()}] processed {processed} message(s)"
            )
        time.sleep(1 if processed == 0 else 0.1)
