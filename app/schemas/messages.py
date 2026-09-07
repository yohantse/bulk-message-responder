import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MessageRead(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    channel: str
    external_chat_id: str
    external_message_id: str
    direction: str
    message_type: str
    text: str | None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
