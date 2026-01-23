from adapters.base import BaseAdapter
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
