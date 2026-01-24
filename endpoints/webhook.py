from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session

from adapters.registry import ADAPTERS
from dependencies.services import get_webhook_service
from services.webhook_service import WebhookService
from core.database import get_db

router = APIRouter()

@router.post("/webhook/{platform}")
async def webhook(
    platform: str,
    request: Request,
    db: Session = Depends(get_db),
    webhook_service: WebhookService = Depends(get_webhook_service),
):
    adapter = ADAPTERS.get(platform)
    if not adapter:
        raise HTTPException(status_code=400, detail="Unsupported platform")
    payload = await request.json()
    normalized_message = adapter.parse(payload)
    await webhook_service.handle_incoming_message(db, normalized_message)
    return {"status": "ok"}
