import httpx

from app.config.settings import Settings, get_settings
from app.telegram.adapter import ChannelAdapter, SendResult
from app.utils.logging import get_logger

logger = get_logger(__name__)


class TelegramAdapter(ChannelAdapter):
    """
    Telegram-specific channel adapter implementation.
    Sends text messages via Telegram Bot API sendMessage endpoint.
    """

    def __init__(
        self, settings: Settings | None = None, http_client: httpx.AsyncClient | None = None
    ) -> None:
        self.settings = settings or get_settings()
        self.http_client = http_client
        self.base_url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}"

    async def send_text(self, chat_id: str, text: str) -> SendResult:
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
        }

        # Do not log token or message text
        logger.info("Sending Telegram message", extra={"extra_fields": {"chat_id": chat_id}})

        try:
            if self.http_client:
                response = await self.http_client.post(url, json=payload, timeout=10.0)
            else:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(url, json=payload)

            try:
                data = response.json()
            except ValueError:
                logger.error(
                    "Non-JSON or malformed response received from Telegram Bot API",
                    extra={"extra_fields": {"status_code": response.status_code}},
                )
                return SendResult(
                    success=False,
                    error_code=f"HTTP_{response.status_code}",
                    error_message=f"Non-JSON response from Telegram API (HTTP {response.status_code})",
                )

            if response.status_code == 200 and data.get("ok"):
                message_id = str(data["result"]["message_id"])
                logger.info(
                    "Telegram message sent successfully",
                    extra={"extra_fields": {"chat_id": chat_id, "external_message_id": message_id}},
                )
                return SendResult(
                    success=True,
                    external_message_id=message_id,
                )

            error_code = str(data.get("error_code", response.status_code))
            error_description = data.get("description", "Unknown Telegram API error")
            logger.error(
                "Telegram API error response",
                extra={
                    "extra_fields": {
                        "error_code": error_code,
                        "error_description": error_description,
                    }
                },
            )
            return SendResult(
                success=False,
                error_code=error_code,
                error_message=error_description,
            )

        except httpx.TimeoutException as e:
            logger.error(
                "Timeout sending message to Telegram", extra={"extra_fields": {"error": str(e)}}
            )
            return SendResult(
                success=False,
                error_code="TIMEOUT",
                error_message=f"Request timed out: {e}",
            )
        except httpx.RequestError as e:
            logger.error(
                "Network error sending message to Telegram",
                extra={"extra_fields": {"error": str(e)}},
            )
            return SendResult(
                success=False,
                error_code="NETWORK_ERROR",
                error_message=f"Network error: {e}",
            )
        except Exception as e:  # noqa: BLE001 - Prevent leaking raw external transport exceptions
            logger.error(
                "Unexpected error sending message to Telegram",
                extra={"extra_fields": {"error": str(e)}},
            )
            return SendResult(
                success=False,
                error_code="INTERNAL_ERROR",
                error_message=f"Unexpected error: {e}",
            )
