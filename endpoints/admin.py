from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, desc, or_, text
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from models.models import (
    ChannelSession,
    Message,
    Organization,
    TicketLink,
    User,
)
from adapters.registry import send_reply
from schemas.message import IncomingMessage
from services.jira_service import JiraService
from dependencies.services import get_jira_service
from schemas.admin import (
    AdminCommentCreate,
    AdminMessageCreate,
    OrganizationCreate,
    OrganizationUpdate,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


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

    message = Message(
        session_id=session.id,
        role="agent",
        content=body.text,
    )
    db.add(message)
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


@router.get("/tickets")
async def list_tickets(
    q: Optional[str] = None,
    organization_id: Optional[str] = None,
    channel: Optional[str] = None,
    status: str = "all",
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    jira_service: JiraService = Depends(get_jira_service),
) -> list[dict]:
    query = (
        db.query(TicketLink, User, Organization, ChannelSession)
        .join(ChannelSession, TicketLink.session_id == ChannelSession.id)
        .outerjoin(User, ChannelSession.user_id == User.id)
        .outerjoin(Organization, TicketLink.organization_id == Organization.id)
    )

    if organization_id:
        query = query.filter(TicketLink.organization_id == organization_id)
    if channel:
        query = query.filter(TicketLink.platform == channel)
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                TicketLink.ticket_key.ilike(like),
                User.email.ilike(like),
                User.name.ilike(like),
            )
        )

    rows = (
        query.order_by(desc(TicketLink.created_at))
        .limit(limit)
        .offset(offset)
        .all()
    )

    ticket_keys = [row[0].ticket_key for row in rows]
    issues_list = await jira_service.get_issues_by_keys(ticket_keys)
    issues = {item["ticket_key"]: item for item in issues_list}

    results = []
    for link, user, org, session in rows:
        issue = issues.get(link.ticket_key, {})
        issue_status = (issue.get("status") or "").lower()
        if status == "open" and "done" in issue_status:
            continue
        if status == "closed" and "done" not in issue_status:
            continue

        summary = issue.get("summary")
        if q and summary and q.lower() not in summary.lower():
            if link.ticket_key.lower().find(q.lower()) == -1 and (user and user.email and q.lower() not in user.email.lower()):
                continue

        results.append(
            {
                "ticket_key": link.ticket_key,
                "summary": issue.get("summary"),
                "status": issue.get("status"),
                "priority": issue.get("priority"),
                "channel": link.platform,
                "user": {"name": user.name, "email": user.email} if user else None,
                "organization": (
                    {"id": str(org.id), "name": org.name} if org else None
                ),
                "session_id": str(session.id) if session else None,
                "created_at": issue.get("created_at"),
                "updated_at": issue.get("updated_at"),
            }
        )
    return results


@router.get("/tickets/{ticket_key}")
async def get_ticket(
    ticket_key: str,
    db: Session = Depends(get_db),
    jira_service: JiraService = Depends(get_jira_service),
) -> dict:
    link = db.query(TicketLink).filter(TicketLink.ticket_key == ticket_key).first()
    if not link:
        raise HTTPException(status_code=404, detail="Ticket not linked")

    session = db.get(ChannelSession, link.session_id)
    user = db.get(User, session.user_id) if session and session.user_id else None
    org = db.get(Organization, link.organization_id) if link.organization_id else None

    detail = await jira_service.get_ticket_detail(ticket_key)

    return {
        "ticket_key": ticket_key,
        "summary": detail.get("summary"),
        "description": detail.get("description"),
        "status": detail.get("status"),
        "priority": detail.get("priority"),
        "assignee": detail.get("assignee"),
        "reporter_email": detail.get("reporter_email"),
        "organization": {"id": str(org.id), "name": org.name} if org else None,
        "channel": link.platform,
        "linked_session_id": str(link.session_id),
        "jira_url": f"{settings.jira_base.rstrip('/')}/browse/{ticket_key}",
        "created_at": detail.get("created_at"),
        "updated_at": detail.get("updated_at"),
        "user": {"name": user.name, "email": user.email} if user else None,
    }


@router.post("/tickets/{ticket_key}/comment")
async def add_ticket_comment(
    ticket_key: str,
    body: AdminCommentCreate,
    db: Session = Depends(get_db),
    jira_service: JiraService = Depends(get_jira_service),
) -> dict:
    if not body.text:
        raise HTTPException(status_code=400, detail="Comment text is required")
    await jira_service.add_comment(ticket_key, body.text)
    return {"status": "ok"}


@router.get("/organizations")
def list_organizations(
    q: Optional[str] = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    org_query = db.query(Organization)
    if q:
        like = f"%{q}%"
        org_query = org_query.filter(Organization.name.ilike(like))

    orgs = org_query.order_by(Organization.name).all()
    org_ids = [org.id for org in orgs]

    user_counts = dict(
        db.query(User.organization_id, func.count(User.id))
        .filter(User.organization_id.in_(org_ids))
        .group_by(User.organization_id)
        .all()
    )

    convo_counts = dict(
        db.query(Organization.id, func.count(ChannelSession.id))
        .join(User, User.organization_id == Organization.id)
        .join(ChannelSession, ChannelSession.user_id == User.id)
        .filter(Organization.id.in_(org_ids))
        .group_by(Organization.id)
        .all()
    )

    ticket_counts = dict(
        db.query(TicketLink.organization_id, func.count(TicketLink.id))
        .filter(TicketLink.organization_id.in_(org_ids))
        .group_by(TicketLink.organization_id)
        .all()
    )

    results = []
    for org in orgs:
        results.append(
            {
                "organization_id": str(org.id),
                "name": org.name,
                "domain": org.domain,
                "user_count": int(user_counts.get(org.id, 0)),
                "conversation_count": int(convo_counts.get(org.id, 0)),
                "ticket_count": int(ticket_counts.get(org.id, 0)),
            }
        )
    return results


@router.get("/organizations/{organization_id}")
def get_organization(
    organization_id: str,
    db: Session = Depends(get_db),
) -> dict:
    org = db.get(Organization, organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    users = (
        db.query(User)
        .filter(User.organization_id == organization_id)
        .order_by(User.name)
        .all()
    )
    convo_count = (
        db.query(func.count(ChannelSession.id))
        .join(User, ChannelSession.user_id == User.id)
        .filter(User.organization_id == organization_id)
        .scalar()
        or 0
    )
    ticket_count = (
        db.query(func.count(TicketLink.id))
        .filter(TicketLink.organization_id == organization_id)
        .scalar()
        or 0
    )
    return {
        "organization_id": str(org.id),
        "name": org.name,
        "domain": org.domain,
        "users": [{"id": str(user.id), "name": user.name, "email": user.email} for user in users],
        "stats": {"conversations": int(convo_count), "tickets": int(ticket_count)},
    }


@router.post("/organizations")
def create_organization(
    body: OrganizationCreate,
    db: Session = Depends(get_db),
) -> dict:
    if not body.domain:
        raise HTTPException(status_code=400, detail="Domain is required")

    org = Organization(name=body.name, domain=body.domain)
    db.add(org)

    db.commit()
    return {"organization_id": str(org.id)}


@router.patch("/organizations/{organization_id}")
def update_organization(
    organization_id: str,
    body: OrganizationUpdate,
    db: Session = Depends(get_db),
) -> dict:
    org = db.get(Organization, organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    if body.name:
        org.name = body.name
    if body.domain is not None:
        if not body.domain:
            raise HTTPException(status_code=400, detail="domain cannot be empty")
        org.domain = body.domain

    db.add(org)
    db.commit()
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


@router.get("/stats")
def admin_stats(db: Session = Depends(get_db)) -> dict:
    total_conversations = db.query(func.count(ChannelSession.id)).scalar() or 0
    open_tickets = db.query(func.count(TicketLink.id)).scalar() or 0
    active_organizations = db.query(func.count(Organization.id)).scalar() or 0
    return {
        "total_conversations": int(total_conversations),
        "open_tickets": int(open_tickets),
        "active_organizations": int(active_organizations),
    }
