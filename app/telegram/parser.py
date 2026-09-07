from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from app.domain.messages import IncomingMessage
from app.telegram.models import TelegramUpdate
from app.utils.logging import get_logger

logger = get_logger(__name__)


def parse_telegram_update(payload: dict[str, Any]) -> IncomingMessage | None:
    """
    Parses a raw Telegram update dictionary.
    Returns normalized IncomingMessage if update is a supported private text message,
    or None if the update is unsupported or non-private.
    """
    try:
        update = TelegramUpdate.model_validate(payload)
    except ValidationError as e:
        logger.debug("Received malformed Telegram update: %s", str(e))
        return None

    # Check if update contains a message
    if update.message is None:
        logger.debug("Ignored update %s: no message field", update.update_id)
        return None

    msg = update.message

    # MVP scope: Only private chats supported
    if msg.chat.type != "private":
        logger.debug(
            "Ignored message %s: non-private chat type '%s'", msg.message_id, msg.chat.type
        )
        return None

    # MVP scope: Only text messages supported
    if msg.text is None or not msg.text.strip():
        logger.debug("Ignored message %s: message has no text", msg.message_id)
        return None

    from_user = msg.from_user
    external_user_id = str(from_user.id) if from_user else str(msg.chat.id)
    user_first_name = from_user.first_name if from_user else msg.chat.first_name
    user_last_name = from_user.last_name if from_user else msg.chat.last_name
    username = from_user.username if from_user else msg.chat.username

    msg_timestamp = datetime.fromtimestamp(msg.date, tz=UTC)

    logger.debug(
        "Successfully normalized Telegram message %s from chat %s",
        msg.message_id,
        msg.chat.id,
    )

    return IncomingMessage(
        channel="telegram",
        external_message_id=str(msg.message_id),
        external_chat_id=str(msg.chat.id),
        external_user_id=external_user_id,
        user_first_name=user_first_name,
        user_last_name=user_last_name,
        username=username,
        message_type="text",
        text=msg.text,
        timestamp=msg_timestamp,
        update_id=update.update_id,
    )
