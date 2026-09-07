import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.message import Message


class MessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def exists_incoming(
        self, channel: str, external_chat_id: str, external_message_id: str
    ) -> bool:
        stmt = select(Message.id).where(
            Message.channel == channel,
            Message.external_chat_id == external_chat_id,
            Message.external_message_id == external_message_id,
            Message.direction == "incoming",
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def get_by_external_id(
        self, channel: str, external_chat_id: str, external_message_id: str, direction: str
    ) -> Message | None:
        stmt = select(Message).where(
            Message.channel == channel,
            Message.external_chat_id == external_chat_id,
            Message.external_message_id == external_message_id,
            Message.direction == direction,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        conversation_id: uuid.UUID,
        channel: str,
        external_chat_id: str,
        external_message_id: str,
        direction: str,
        message_type: str,
        text: str | None,
        status: str,
    ) -> Message:
        message = Message(
            conversation_id=conversation_id,
            channel=channel,
            external_chat_id=external_chat_id,
            external_message_id=external_message_id,
            direction=direction,
            message_type=message_type,
            text=text,
            status=status,
        )
        self.session.add(message)
        await self.session.flush()
        return message
