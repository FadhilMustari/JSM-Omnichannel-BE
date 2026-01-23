from adapters.line import LineAdapter
from adapters.whatsapp import WhatsAppAdapter
from adapters.telegram import TelegramAdapter
from schemas.message import IncomingMessage

ADAPTERS = {
    "whatsapp": WhatsAppAdapter(),
    "telegram": TelegramAdapter(),
    "line": LineAdapter(),
}

def send_reply(message: IncomingMessage, reply_text: str) -> None:
    adapter = ADAPTERS.get(message.platform)
    if not adapter:
        raise RuntimeError(f"No adapter found for platform: {message.platform}")

    adapter.send_reply(message, reply_text)
