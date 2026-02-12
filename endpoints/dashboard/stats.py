from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.database import get_db
from models.models import ChannelSession, Organization, TicketLink

router = APIRouter(prefix="/api", tags=["stats"])


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
