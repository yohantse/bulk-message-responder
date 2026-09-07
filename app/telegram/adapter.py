from typing import Protocol

from pydantic import BaseModel


class SendResult(BaseModel):
    success: bool
    external_message_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class ChannelAdapter(Protocol):
    """
    Generic channel adapter protocol.
    Future adapters for WhatsApp, Instagram, etc. implement this interface.
    """

    async def send_text(
        self,
        chat_id: str,
        text: str,
    ) -> SendResult: ...
