from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.database import get_db
from dependencies.services import get_jira_service
from services.jira_service import JiraService
from services.jira_sync_service import JiraSyncService

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.post("/jsm")
async def sync_jsm(
    db: Session = Depends(get_db),
    jira_service: JiraService = Depends(get_jira_service),
) -> dict:
    sync_service = JiraSyncService(jira_service)
    result = await sync_service.sync_jira_organizations_and_users(db)
    return {"status": "ok", "result": result}


@router.post("/tickets")
async def sync_tickets(
    db: Session = Depends(get_db),
    jira_service: JiraService = Depends(get_jira_service),
) -> dict:
    sync_service = JiraSyncService(jira_service)
    result = await sync_service.sync_jira_tickets(db)
    return {"status": "ok", "result": result}
