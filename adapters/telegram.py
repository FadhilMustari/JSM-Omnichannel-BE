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
