from adapters.whatsapp import WhatsAppAdapter
from adapters.telegram import TelegramAdapter

ADAPTERS = {
    "whatsapp": WhatsAppAdapter(),
    "telegram": TelegramAdapter(),
}
