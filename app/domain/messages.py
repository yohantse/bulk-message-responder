from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class IncomingMessage:
    channel: str
    external_message_id: str
    external_chat_id: str
    external_user_id: str
    user_first_name: str | None
    user_last_name: str | None
    username: str | None
    message_type: str
    text: str | None
    timestamp: datetime
    update_id: int | None = None
