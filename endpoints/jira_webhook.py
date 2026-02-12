import asyncio
import json
import logging
import hmac
from fastapi import APIRouter, Request, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from adapters.registry import send_reply
from models.models import ChannelSession, TicketLink
from schemas.message import IncomingMessage
from services.message_service import MessageService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/webhook/jira")
async def jira_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    body = await request.body()
    _verify_jira_webhook(request)
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        logger.warning("Jira webhook invalid JSON payload", extra={"body_len": len(body)})
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    if payload.get("webhookEvent") != "comment_created":
        return Response(status_code=204)

    await _handle_comment_created(db, payload)
    return {"status": "ok"}


def _verify_jira_webhook(request: Request) -> None:
    secret = settings.jira_webhook_secret
    if not secret:
        return
    header = (
        request.headers.get("X-Atlassian-Webhook-Secret")
        or request.headers.get("X-Jira-Webhook-Secret")
    )
    if not header or not hmac.compare_digest(header, secret):
        raise HTTPException(status_code=401, detail="Invalid Jira webhook secret")


async def _handle_comment_created(db: Session, payload: dict) -> None:
    issue = payload.get("issue") or {}
    comment = payload.get("comment") or {}
    ticket_key = issue.get("key")
    if not ticket_key or not comment:
        logger.info(
            "Jira webhook missing issue/comment",
            extra={"ticket_key": ticket_key},
        )
        return

    if _is_internal_comment(comment):
        logger.info(
            "Jira webhook ignored internal comment",
            extra={"ticket_key": ticket_key},
        )
        return

    author = comment.get("author") or {}
    author_email = (author.get("emailAddress") or "").lower()
    if settings.jira_email and author_email == settings.jira_email.lower():
        logger.info(
            "Jira webhook ignored integration author",
            extra={"ticket_key": ticket_key},
        )
        return

    link = (
        db.query(TicketLink)
        .filter(TicketLink.ticket_key == ticket_key)
        .first()
    )
    if not link:
        logger.info(
            "Jira webhook ticket not linked",
            extra={"ticket_key": ticket_key},
        )
        return

    session = db.get(ChannelSession, link.session_id)
    if not session:
        logger.warning(
            "Jira webhook missing session",
            extra={"ticket_key": ticket_key, "session_id": str(link.session_id)},
        )
        return

    author_name = author.get("displayName") or author.get("name") or "Someone"
    body = _extract_comment_body(comment.get("body"))
    if not body:
        body = "(no content)"

    reply_text = f"New comment on {ticket_key} from {author_name}:\n{body}"
    MessageService().save_system_message(db, session.id, reply_text)
    outgoing = IncomingMessage(
        platform=session.platform,
        external_user_id=session.external_user_id,
        message_id="",
        text="",
        raw_payload={},
    )
    await asyncio.to_thread(send_reply, outgoing, reply_text)
    db.commit()


def _is_internal_comment(comment: dict) -> bool:
    if "public" in comment:
        return comment.get("public") is False
    if "jsdPublic" in comment:
        return comment.get("jsdPublic") is False
    if "internal" in comment:
        return comment.get("internal") is True
    return False


def _extract_comment_body(body) -> str:
    if body is None:
        return ""
    if isinstance(body, str):
        return body.strip()
    if isinstance(body, list):
        return " ".join(filter(None, (_extract_comment_body(item) for item in body))).strip()
    if isinstance(body, dict):
        if body.get("type") == "text":
            return (body.get("text") or "").strip()
        content = body.get("content")
        if isinstance(content, list):
            parts = []
            for item in content:
                text = _extract_comment_body(item)
                if text:
                    parts.append(text)
            return "\n".join(parts).strip()
    return ""
