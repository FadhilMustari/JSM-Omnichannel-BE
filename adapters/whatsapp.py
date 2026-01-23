from adapters.base import BaseAdapter
from schemas.message import IncomingMessage

class WhatsAppAdapter(BaseAdapter):

    def parse(self, payload: dict) -> IncomingMessage:
        # struktur WhatsApp itu nested & ribet
        entry = payload["entry"][0]
        change = entry["changes"][0]
        value = change["value"]
        message = value["messages"][0]

        if message["type"] != "text":
            raise ValueError("Unsupported WhatsApp message type")

        return IncomingMessage(
            platform="whatsapp",
            external_user_id=message["from"],
            text=message["text"]["body"],
            raw_payload=payload,
        )
