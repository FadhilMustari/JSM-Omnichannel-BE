from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import desc, func, or_, text
from sqlalchemy.orm import Session

from adapters.registry import send_reply
from core.database import get_db
from models.models import ChannelSession, Message, Organization, TicketLink, User
from schemas.admin import AdminMessageCreate
from schemas.message import IncomingMessage
from services.message_service import MessageService

router = APIRouter(prefix="/api", tags=["conversations"])


def _admin_context(request: Request) -> dict:
    admin = getattr(request.state, "admin", None)
    if isinstance(admin, dict):
        return admin
    return {"id": None, "name": None, "role": "admin", "org_scope": "all"}


@router.get("/me")
def admin_me(request: Request) -> dict:
    return _admin_context(request)


@router.get("/conversations")
def list_conversations(
    q: Optional[str] = None,
    organization_id: Optional[str] = None,
    channel: Optional[str] = None,
    unread_only: Optional[bool] = False,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> list[dict]:
    last_message_sub = (
        db.query(
            Message.session_id.label("session_id"),
            Message.content.label("text"),
            Message.role.label("role"),
            Message.created_at.label("created_at"),
            func.row_number()
            .over(
                partition_by=Message.session_id,
                order_by=(Message.created_at.desc(), Message.id.desc()),
            )
            .label("rn"),
        )
        .subquery()
    )

    last_message = (
        db.query(last_message_sub)
        .filter(last_message_sub.c.rn == 1)
        .subquery()
    )

    epoch = text("'1970-01-01'::timestamptz")
    unread_sub = (
        db.query(
            Message.session_id.label("session_id"),
            func.count(Message.id).label("unread_count"),
        )
        .join(ChannelSession, ChannelSession.id == Message.session_id)
        .filter(Message.role == "user")
        .filter(Message.created_at > func.coalesce(ChannelSession.last_read_at, epoch))
        .group_by(Message.session_id)
        .subquery()
    )

    query = (
        db.query(
            ChannelSession,
            User,
            Organization,
            last_message.c.text.label("last_text"),
            last_message.c.role.label("last_role"),
            last_message.c.created_at.label("last_created_at"),
            unread_sub.c.unread_count.label("unread_count"),
        )
        .outerjoin(User, ChannelSession.user_id == User.id)
        .outerjoin(Organization, User.organization_id == Organization.id)
        .outerjoin(last_message, last_message.c.session_id == ChannelSession.id)
        .outerjoin(unread_sub, unread_sub.c.session_id == ChannelSession.id)
    )

    if organization_id:
        query = query.filter(User.organization_id == organization_id)
    if channel:
        query = query.filter(ChannelSession.platform == channel)
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                User.name.ilike(like),
                User.email.ilike(like),
                ChannelSession.external_user_id.ilike(like),
                last_message.c.text.ilike(like),
            )
        )
    if unread_only:
        query = query.filter(func.coalesce(unread_sub.c.unread_count, 0) > 0)

    rows = (
        query.order_by(desc(ChannelSession.updated_at), desc(ChannelSession.created_at))
        .limit(limit)
        .offset(offset)
        .all()
    )

    results: list[dict] = []
    for session, user, org, last_text, last_role, last_created_at, unread_count in rows:
        results.append(
            {
                "session_id": str(session.id),
                "user_name": user.name if user else None,
                "user_email": user.email if user else None,
                "organization": (
                    {"id": str(org.id), "name": org.name} if org else None
                ),
                "channel": session.platform,
                "last_message": (
                    {
                        "text": last_text,
                        "from": last_role,
                        "created_at": last_created_at,
                    }
                    if last_text
                    else None
                ),
                "unread_count": int(unread_count or 0),
                "updated_at": session.updated_at or session.created_at,
            }
        )
    return results


@router.get("/conversations/{session_id}")
def get_conversation(
    session_id: str,
    db: Session = Depends(get_db),
) -> dict:
    session = db.get(ChannelSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    user = db.get(User, session.user_id) if session.user_id else None
    org = db.get(Organization, user.organization_id) if user else None
    return {
        "session_id": str(session.id),
        "user": (
            {"id": str(user.id), "name": user.name, "email": user.email} if user else None
        ),
        "organization": {"id": str(org.id), "name": org.name} if org else None,
        "channel": session.platform,
        "created_at": session.created_at,
        "auth_status": session.auth_status,
    }


@router.get("/conversations/{session_id}/messages")
def list_conversation_messages(
    session_id: str,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> list[dict]:
    session = db.get(ChannelSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = (
        db.query(Message)
        .filter(Message.session_id == session_id)
        .order_by(desc(Message.created_at), desc(Message.id))
        .limit(limit)
        .offset(offset)
        .all()
    )

    session.last_read_at = datetime.now(timezone.utc)
    db.add(session)
    db.commit()

    return [
        {
            "message_id": str(message.id),
            "role": message.role,
            "text": message.content,
            "created_at": message.created_at,
            "platform_message_id": message.external_message_id,
        }
        for message in reversed(messages)
    ]


@router.post("/conversations/{session_id}/messages")
def send_admin_message(
    session_id: str,
    body: AdminMessageCreate,
    db: Session = Depends(get_db),
) -> dict:
    session = db.get(ChannelSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    MessageService().save_employee_message(db, session.id, body.text)
    db.commit()
    outgoing = IncomingMessage(
        platform=session.platform,
        external_user_id=session.external_user_id,
        message_id="",
        text="",
        raw_payload={},
    )
    send_reply(outgoing, body.text)
    return {"status": "ok"}


@router.post("/conversations/{session_id}/link-ticket")
def link_ticket(
    session_id: str,
    body: dict,
    db: Session = Depends(get_db),
) -> dict:
    ticket_key = body.get("ticket_key")
    if not ticket_key:
        raise HTTPException(status_code=400, detail="ticket_key is required")

    session = db.get(ChannelSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    user = db.get(User, session.user_id) if session.user_id else None
    if not user:
        raise HTTPException(status_code=400, detail="Session is not linked to a user")

    link = db.query(TicketLink).filter(TicketLink.ticket_key == ticket_key).first()
    if link:
        link.session_id = session.id
        link.organization_id = user.organization_id
        link.platform = session.platform
    else:
        link = TicketLink(
            ticket_key=ticket_key,
            session_id=session.id,
            organization_id=user.organization_id,
            platform=session.platform,
        )
    db.add(link)
    db.commit()
    return {"status": "ok"}
