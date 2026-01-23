from typing import Dict, Any
from pydantic import BaseModel

class IncomingMessage(BaseModel):
    platform: str
    external_user_id: str
    text: str
    raw_payload: Dict[str, Any]
