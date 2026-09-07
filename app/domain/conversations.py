import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DomainConversation:
    id: uuid.UUID
    channel: str
    external_chat_id: str
    user_id: uuid.UUID
    status: str
    created_at: datetime
    updated_at: datetime
