from abc import ABC, abstractmethod
from schemas.message import IncomingMessage

class BaseAdapter(ABC):

    @abstractmethod
    def parse(self, payload: dict) -> IncomingMessage:
        pass

    @abstractmethod
    def send_reply(self, message: IncomingMessage, reply_text: str) -> None:
        """Deliver response back to the originating platform."""