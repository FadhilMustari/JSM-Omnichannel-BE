from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from models.models import ChannelSession, JiraTicket, Organization, TicketLink, User
from schemas.admin import AdminCommentCreate
from services.jira_service import JiraService
from dependencies.services import get_jira_service

router = APIRouter(prefix="/api", tags=["tickets"])


@router.get("/tickets")
async def list_tickets(
    q: Optional[str] = None,
    organization_id: Optional[str] = None,
    channel: Optional[str] = None,
    status: str = "all",
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> list[dict]:
    query = (
        db.query(JiraTicket, TicketLink, User, Organization, ChannelSession)
        .outerjoin(TicketLink, JiraTicket.ticket_key == TicketLink.ticket_key)
        .outerjoin(ChannelSession, TicketLink.session_id == ChannelSession.id)
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
                JiraTicket.ticket_key.ilike(like),
                JiraTicket.summary.ilike(like),
                User.email.ilike(like),
            )
        )

    rows = (
        query.order_by(desc(JiraTicket.created_at))
        .limit(limit)
        .offset(offset)
        .all()
    )

    results = []
    for ticket, link, user, org, session in rows:
        issue_status = (ticket.status or "").lower()
        if status == "open" and "done" in issue_status:
            continue
        if status == "closed" and "done" not in issue_status:
            continue

        results.append(
            {
                "ticket_key": ticket.ticket_key,
                "summary": ticket.summary,
                "status": ticket.status,
                "priority": ticket.priority,
                "channel": link.platform if link else None,
                "user": {"email": user.email, "jsm_account_id": user.jsm_account_id} if user else None,
                "organization": (
                    {"id": str(org.id), "name": org.name} if org else None
                ),
                "session_id": str(session.id) if session else None,
                "created_at": ticket.created_at,
                "updated_at": ticket.updated_at,
                "source": "platform" if link else "portal",
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
        "user": {"email": user.email, "jsm_account_id": user.jsm_account_id} if user else None,
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
