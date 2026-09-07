import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.messages import IncomingMessage
from app.repositories.messages import MessageRepository
from app.services.conversation_service import ConversationService
from app.services.user_service import UserService
from app.telegram.adapter import ChannelAdapter, SendResult
from app.utils.logging import get_logger

logger = get_logger(__name__)


class MessageService:
    def __init__(self, session: AsyncSession, channel_adapter: ChannelAdapter) -> None:
        self.session = session
        self.channel_adapter = channel_adapter
        self.message_repo = MessageRepository(session)
        self.user_service = UserService(session)
        self.conversation_service = ConversationService(session)

    def _determine_automated_response(self, text: str | None) -> str:
        """
        Determines the automated response for MVP.
        - /start -> Welcome! How can we help you?
        - Other text (including 'Hello') -> Hello! Thanks for contacting us. How can we help you?
        """
        if not text:
            return "Hello! Thanks for contacting us. How can we help you?"

        clean_text = text.strip()
        if clean_text == "/start":
            return "Welcome! How can we help you?"
        return "Hello! Thanks for contacting us. How can we help you?"

    async def handle_incoming_message(self, incoming: IncomingMessage) -> bool:
        """
        Processes an incoming message in 3 explicit decoupled phases:
        Phase 1: Persist incoming message & state, commit DB transaction.
        Phase 2: Generate response & invoke external Telegram API call outside DB transaction.
        Phase 3: Persist outgoing message result in a separate DB transaction.

        Returns:
            bool: True if processed successfully, False if duplicate detected.
        """
        # --- Pre-check Optimization ---
        is_duplicate = await self.message_repo.exists_incoming(
            incoming.channel, incoming.external_chat_id, incoming.external_message_id
        )
        if is_duplicate:
            logger.info(
                "Duplicate message detected via pre-check",
                extra={
                    "extra_fields": {
                        "channel": incoming.channel,
                        "external_chat_id": incoming.external_chat_id,
                        "external_message_id": incoming.external_message_id,
                    }
                },
            )
            return False

        # --- Phase 1: Ingest Incoming Message (DB Transaction) ---
        try:
            # Find or create user
            user, _ = await self.user_service.get_or_create_user(
                channel=incoming.channel,
                external_user_id=incoming.external_user_id,
                username=incoming.username,
                first_name=incoming.user_first_name,
                last_name=incoming.user_last_name,
            )

            # Find or create conversation
            conversation, _ = await self.conversation_service.get_or_create_conversation(
                channel=incoming.channel,
                external_chat_id=incoming.external_chat_id,
                user_id=user.id,
            )

            # Store incoming message
            incoming_msg_record = await self.message_repo.create(
                conversation_id=conversation.id,
                channel=incoming.channel,
                external_chat_id=incoming.external_chat_id,
                external_message_id=incoming.external_message_id,
                direction="incoming",
                message_type=incoming.message_type,
                text=incoming.text,
                status="received",
            )
            await self.session.commit()

            logger.info(
                "Message stored",
                extra={
                    "extra_fields": {
                        "message_id": str(incoming_msg_record.id),
                        "direction": "incoming",
                        "status": "received",
                        "channel": incoming.channel,
                        "external_chat_id": incoming.external_chat_id,
                        "external_message_id": incoming.external_message_id,
                    }
                },
            )

        except IntegrityError:
            await self.session.rollback()
            # Authoritative idempotency guarantee: check if duplicate incoming message now exists
            if await self.message_repo.exists_incoming(
                incoming.channel, incoming.external_chat_id, incoming.external_message_id
            ):
                logger.info(
                    "Concurrent duplicate message detected via unique constraint",
                    extra={
                        "extra_fields": {
                            "channel": incoming.channel,
                            "external_chat_id": incoming.external_chat_id,
                            "external_message_id": incoming.external_message_id,
                        }
                    },
                )
                return False
            logger.exception("IntegrityError during Phase 1 persistence")
            raise
        except Exception:
            await self.session.rollback()
            logger.exception("Phase 1 incoming message persistence failed")
            raise

        # --- Phase 2: External Telegram API Call (Outside DB Transaction) ---
        response_text = self._determine_automated_response(incoming.text)
        try:
            send_result = await self.channel_adapter.send_text(
                chat_id=incoming.external_chat_id,
                text=response_text,
            )
        except Exception as e:
            logger.exception("Unexpected exception from channel adapter in Phase 2")
            send_result = SendResult(
                success=False,
                error_code="UNHANDLED_ADAPTER_ERROR",
                error_message=str(e),
            )

        if send_result.success:
            outgoing_status = "sent"
            outgoing_ext_id = send_result.external_message_id or str(uuid.uuid4())
            logger.info(
                "Message sent",
                extra={
                    "extra_fields": {
                        "channel": incoming.channel,
                        "external_chat_id": incoming.external_chat_id,
                        "external_message_id": outgoing_ext_id,
                    }
                },
            )
        else:
            outgoing_status = "failed"
            outgoing_ext_id = f"fail_{incoming.external_message_id}_{uuid.uuid4().hex[:8]}"
            logger.error(
                "Message failed",
                extra={
                    "extra_fields": {
                        "channel": incoming.channel,
                        "external_chat_id": incoming.external_chat_id,
                        "error_code": send_result.error_code,
                        "error_message": send_result.error_message,
                    }
                },
            )

        # --- Phase 3: Outgoing Message Record (Separate DB Transaction) ---
        try:
            outgoing_msg_record = await self.message_repo.create(
                conversation_id=conversation.id,
                channel=incoming.channel,
                external_chat_id=incoming.external_chat_id,
                external_message_id=outgoing_ext_id,
                direction="outgoing",
                message_type="text",
                text=response_text,
                status=outgoing_status,
            )
            await self.session.commit()

            logger.info(
                "Message stored",
                extra={
                    "extra_fields": {
                        "message_id": str(outgoing_msg_record.id),
                        "direction": "outgoing",
                        "status": outgoing_status,
                        "channel": incoming.channel,
                        "external_chat_id": incoming.external_chat_id,
                        "external_message_id": outgoing_ext_id,
                    }
                },
            )
        except Exception:
            await self.session.rollback()
            logger.exception("Phase 3 outgoing message persistence failed")
            raise

        return True
