import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ConversationRead(BaseModel):
    id: uuid.UUID
    channel: str
    external_chat_id: str
    user_id: uuid.UUID
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
