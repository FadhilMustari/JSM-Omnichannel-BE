import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from adapters.registry import send_reply
from core.database import get_db
from models.models import ChannelSession, ChannelStatus
from schemas.admin import BroadcastCreate
from schemas.message import IncomingMessage
from services.message_service import MessageService

router = APIRouter(prefix="/api", tags=["broadcast"])


def _normalize_platform(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = value.strip().lower()
    if not normalized:
        return None
    return normalized


async def _broadcast_message(
    db: Session,
    body: BroadcastCreate,
) -> dict:
    message = (body.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    platform = _normalize_platform(body.platform)
    if platform and platform not in {"whatsapp", "telegram", "line"}:
        raise HTTPException(status_code=400, detail="platform must be WHATSAPP, TELEGRAM, or LINE")

    query = db.query(ChannelSession).filter(ChannelSession.status == ChannelStatus.active.value)
    if platform:
        query = query.filter(ChannelSession.platform == platform)

    sessions = query.all()
    message_service = MessageService()
    outgoing_messages = []
    for session in sessions:
        message_service.save_employee_message(db, session.id, message)
        outgoing_messages.append(
            IncomingMessage(
                platform=session.platform,
                external_user_id=session.external_user_id,
                message_id="",
                text="",
                raw_payload={},
            )
        )
    db.commit()

    tasks = [asyncio.to_thread(send_reply, outgoing, message) for outgoing in outgoing_messages]
    if tasks:
        await asyncio.gather(*tasks)

    return {"status": "ok", "sent": len(outgoing_messages)}


@router.post("/broadcast")
async def broadcast_api(
    body: BroadcastCreate,
    db: Session = Depends(get_db),
) -> dict:
    return await _broadcast_message(db, body)

