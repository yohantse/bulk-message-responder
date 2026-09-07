import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.conversation import Conversation


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_channel_and_chat_id(
        self, channel: str, external_chat_id: str
    ) -> Conversation | None:
        stmt = select(Conversation).where(
            Conversation.channel == channel,
            Conversation.external_chat_id == external_chat_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        channel: str,
        external_chat_id: str,
        user_id: uuid.UUID,
        status: str = "active",
    ) -> Conversation:
        conversation = Conversation(
            channel=channel,
            external_chat_id=external_chat_id,
            user_id=user_id,
            status=status,
        )
        self.session.add(conversation)
        await self.session.flush()
        return conversation

    async def get_or_create(
        self,
        channel: str,
        external_chat_id: str,
        user_id: uuid.UUID,
    ) -> Conversation:
        conversation = await self.get_by_channel_and_chat_id(channel, external_chat_id)
        if conversation is None:
            conversation = await self.create(channel, external_chat_id, user_id)
        return conversation
