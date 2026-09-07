import hmac
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings, get_settings
from app.database.session import get_db_session
from app.services.message_service import MessageService
from app.telegram.adapter import ChannelAdapter
from app.telegram.parser import parse_telegram_update
from app.telegram.sender import TelegramAdapter
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def get_telegram_adapter(settings: Settings = Depends(get_settings)) -> ChannelAdapter:
    return TelegramAdapter(settings=settings)


def verify_telegram_secret(
    x_telegram_bot_api_secret_token: str | None = Header(
        None, alias="X-Telegram-Bot-Api-Secret-Token"
    ),
    settings: Settings = Depends(get_settings),
) -> None:
    expected_secret = settings.telegram_webhook_secret
    if not expected_secret:
        if settings.app_env.lower() == "production":
            logger.error(
                "Rejecting webhook: TELEGRAM_WEBHOOK_SECRET is not configured in production"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Webhook secret authentication is mandatory in production",
            )
        # If no secret configured in non-production environment, allow requests (e.g. testing)
        return

    if not x_telegram_bot_api_secret_token or not hmac.compare_digest(
        x_telegram_bot_api_secret_token, expected_secret
    ):
        logger.warning("Unauthorized webhook request: secret token mismatch")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid webhook secret token",
        )


@router.post("/telegram", status_code=status.HTTP_200_OK)
async def telegram_webhook(
    payload: dict[str, Any],
    _: None = Depends(verify_telegram_secret),
    session: AsyncSession = Depends(get_db_session),
    adapter: ChannelAdapter = Depends(get_telegram_adapter),
) -> dict[str, Any]:
    logger.info("Webhook received")

    incoming = parse_telegram_update(payload)
    if incoming is None:
        logger.debug("Unsupported or ignored Telegram update")
        return {"ok": True, "ignored": True}

    logger.info(
        "Update parsed and normalized",
        extra={
            "extra_fields": {
                "channel": incoming.channel,
                "external_message_id": incoming.external_message_id,
                "external_chat_id": incoming.external_chat_id,
            }
        },
    )

    try:
        service = MessageService(session=session, channel_adapter=adapter)
        processed = await service.handle_incoming_message(incoming)
        return {"ok": True, "processed": processed}
    except Exception:
        logger.exception("Unexpected error during webhook processing")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from None
