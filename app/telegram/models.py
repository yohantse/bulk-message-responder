from pydantic import BaseModel, Field


class TelegramUser(BaseModel):
    id: int
    is_bot: bool | None = None
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None


class TelegramChat(BaseModel):
    id: int
    type: str  # "private", "group", "supergroup", "channel"
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None


class TelegramMessage(BaseModel):
    message_id: int
    from_user: TelegramUser | None = Field(default=None, alias="from")
    chat: TelegramChat
    date: int
    text: str | None = None


class TelegramUpdate(BaseModel):
    update_id: int
    message: TelegramMessage | None = None
    edited_message: dict | None = None
    channel_post: dict | None = None
    edited_channel_post: dict | None = None
    callback_query: dict | None = None

    model_config = {"extra": "ignore", "populate_by_name": True}
