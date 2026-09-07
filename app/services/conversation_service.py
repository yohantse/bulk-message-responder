import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.conversation import Conversation
from app.repositories.conversations import ConversationRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ConversationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.conversation_repo = ConversationRepository(session)

    async def get_or_create_conversation(
        self,
        channel: str,
        external_chat_id: str,
        user_id: uuid.UUID,
    ) -> tuple[Conversation, bool]:
        """
        Returns (conversation, created).
        """
        existing = await self.conversation_repo.get_by_channel_and_chat_id(
            channel, external_chat_id
        )
        if existing is not None:
            return existing, False

        conversation = await self.conversation_repo.create(
            channel=channel,
            external_chat_id=external_chat_id,
            user_id=user_id,
            status="active",
        )
        logger.info(
            "Conversation created",
            extra={
                "extra_fields": {
                    "conversation_id": str(conversation.id),
                    "channel": channel,
                    "external_chat_id": external_chat_id,
                    "user_id": str(user_id),
                }
            },
        )
        return conversation, True
