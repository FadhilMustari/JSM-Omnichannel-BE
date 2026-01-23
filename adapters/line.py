import requests

from adapters.base import BaseAdapter
from core.config import settings
from schemas.message import IncomingMessage

class LineAdapter(BaseAdapter):

    def parse(self, payload: dict) -> IncomingMessage:
        # LINE bisa kirim banyak event, ambil yang pertama
        event = payload["events"][0]
        message = event["message"]

        if message["type"] != "text":
            raise ValueError("Unsupported LINE message type")

        return IncomingMessage(
            platform="line",
            external_user_id=event["source"]["userId"],
            text=message["text"],
            raw_payload=payload,
        )

    def send_reply(self, message: IncomingMessage, reply_text: str) -> None:
        if not settings.line_channel_access_token:
            raise RuntimeError("LINE channel access token is not configured.")

        url = "https://api.line.me/v2/bot/message/push"
        payload = {
            "to": message.external_user_id,
            "messages": [{"type": "text", "text": reply_text}],
        }
        headers = {"Authorization": f"Bearer {settings.line_channel_access_token}"}
        requests.post(url, json=payload, headers=headers, timeout=10)
