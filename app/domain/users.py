import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DomainUser:
    id: uuid.UUID
    channel: str
    external_user_id: str
    username: str | None
    first_name: str | None
    last_name: str | None
    created_at: datetime
    updated_at: datetime
