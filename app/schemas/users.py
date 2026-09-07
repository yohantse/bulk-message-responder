import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserRead(BaseModel):
    id: uuid.UUID
    channel: str
    external_user_id: str
    username: str | None
    first_name: str | None
    last_name: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
