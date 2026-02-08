import base64
import hashlib
import hmac
import json
import logging
import time
from collections import deque
from typing import Deque, Dict
from fastapi import APIRouter, Request, HTTPException, Depends, Response
from sqlalchemy.orm import Session
from adapters.registry import ADAPTERS
from core.config import settings
from dependencies.services import get_webhook_service
from services.webhook_service import WebhookService
from core.database import get_db

router = APIRouter()
logger = logging.getLogger(__name__)

_rate_limit_store: Dict[str, Deque[float]] = {}

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
    body = await request.body()
    try:
        _verify_signature(platform, request, body)
    except HTTPException:
        logger.warning(
            "Webhook signature verification failed",
            extra={"platform": platform, "body_len": len(body)},
        )
        raise
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        logger.warning(
            "Webhook invalid JSON payload",
            extra={"platform": platform, "body_len": len(body)},
        )
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    try:
        normalized_message = adapter.parse(payload)
    except ValueError:
        logger.info(
            "Webhook ignored non-text event",
            extra={"platform": platform},
        )
        return Response(status_code=204)
    except KeyError:
        logger.warning(
            "Webhook invalid payload structure",
            extra={"platform": platform},
        )
        raise HTTPException(status_code=400, detail="Invalid webhook payload")
    _enforce_rate_limit(f"{platform}:{normalized_message.external_user_id}")
    try:
        await webhook_service.handle_incoming_message(db, normalized_message)
    except Exception:
        logger.exception(
            "Webhook handling failed",
            extra={
                "platform": platform,
                "external_user_id": normalized_message.external_user_id,
                "message_id": normalized_message.message_id,
            },
        )
        raise
    return {"status": "ok"}

def _enforce_rate_limit(key: str) -> None:
    now = time.monotonic()
    window = settings.rate_limit_window_seconds
    limit = settings.rate_limit_max
    bucket = _rate_limit_store.setdefault(key, deque())

    while bucket and bucket[0] <= now - window:
        bucket.popleft()

    if len(bucket) >= limit:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    bucket.append(now)


def _verify_telegram(request: Request) -> None:
    secret = settings.telegram_webhook_secret
    if not secret:
        raise HTTPException(status_code=500, detail="Telegram webhook secret not configured")

    header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if not header or not hmac.compare_digest(header, secret):
        raise HTTPException(status_code=401, detail="Invalid Telegram webhook signature")


def _verify_line(request: Request, body: bytes) -> None:
    secret = settings.line_channel_secret
    if not secret:
        raise HTTPException(status_code=500, detail="LINE channel secret not configured")

    signature = request.headers.get("X-Line-Signature", "")
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode("utf-8")
    if not signature or not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="Invalid LINE webhook signature")


def _verify_whatsapp(request: Request, body: bytes) -> None:
    secret = settings.whatsapp_app_secret
    if not secret:
        raise HTTPException(status_code=500, detail="WhatsApp app secret not configured")

    signature = request.headers.get("X-Hub-Signature-256", "")
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    expected = f"sha256={digest}"
    if not signature or not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="Invalid WhatsApp webhook signature")


def _verify_signature(platform: str, request: Request, body: bytes) -> None:
    if platform == "telegram":
        _verify_telegram(request)
    elif platform == "line":
        _verify_line(request, body)
    elif platform == "whatsapp":
        _verify_whatsapp(request, body)

