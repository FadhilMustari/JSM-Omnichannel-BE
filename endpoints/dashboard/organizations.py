from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.database import get_db
from models.models import ChannelSession, Organization, TicketLink, User
from schemas.admin import OrganizationCreate, OrganizationUpdate

router = APIRouter(prefix="/api", tags=["organizations"])


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
