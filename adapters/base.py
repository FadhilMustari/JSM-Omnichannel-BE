from abc import ABC, abstractmethod
from schemas.message import IncomingMessage

class BaseAdapter(ABC):

    @abstractmethod
    def parse(self, payload: dict) -> IncomingMessage:
        pass
