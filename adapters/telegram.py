import logging
import time
import requests
from core.config import settings
from adapters.base import BaseAdapter
from schemas.message import IncomingMessage

class TelegramAdapter(BaseAdapter):

    def parse(self, payload: dict) -> IncomingMessage:
        message = payload["message"]

        return IncomingMessage(
            platform="telegram",
            external_user_id=str(message["from"]["id"]),
            message_id=str(message["message_id"]),
            text=message["text"],
            raw_payload=payload
        )
        
    def send_reply(self, message: IncomingMessage, reply_text: str) -> None:
            url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
            payload = {
                "chat_id": message.external_user_id,
                "text": reply_text,
            }
            if any(tag in reply_text for tag in ("<b>", "<i>", "<code>", "<pre>", "<a ")):
                payload["parse_mode"] = "HTML"
            logger = logging.getLogger(__name__)
            start = time.perf_counter()
            try:
                response = requests.post(url, json=payload, timeout=10)
                elapsed = time.perf_counter() - start
                logger.info(
                    "Telegram send_reply completed",
                    extra={
                        "status_code": response.status_code,
                        "elapsed_s": round(elapsed, 3),
                    },
                )
                response.raise_for_status()
            except requests.exceptions.RequestException:
                elapsed = time.perf_counter() - start
                logger.exception(
                    "Telegram send_reply failed",
                    extra={"elapsed_s": round(elapsed, 3)},
                )
                raise
