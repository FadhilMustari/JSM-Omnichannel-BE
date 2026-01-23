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
            text=message["text"],
            raw_payload=payload
        )
        
    def send_reply(self, message: IncomingMessage, reply_text: str) -> None:
            url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
            payload = {
                "chat_id": message.external_user_id,
                "text": reply_text,
            }
            requests.post(url, json=payload, timeout=10)