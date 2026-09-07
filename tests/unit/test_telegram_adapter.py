import httpx
import pytest

from app.config.settings import Settings
from app.telegram.sender import TelegramAdapter


@pytest.mark.asyncio
async def test_adapter_successful_send() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 999}})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        settings = Settings(telegram_bot_token="dummy_token")
        adapter = TelegramAdapter(settings=settings, http_client=client)
        result = await adapter.send_text(chat_id="123", text="Hello")

    assert result.success is True
    assert result.external_message_id == "999"


@pytest.mark.asyncio
async def test_adapter_api_error_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400, json={"ok": False, "error_code": 400, "description": "Bad Request: chat not found"}
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        settings = Settings(telegram_bot_token="dummy_token")
        adapter = TelegramAdapter(settings=settings, http_client=client)
        result = await adapter.send_text(chat_id="123", text="Hello")

    assert result.success is False
    assert result.error_code == "400"
    assert result.error_message == "Bad Request: chat not found"


@pytest.mark.asyncio
async def test_adapter_malformed_non_json_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="<html><body>502 Bad Gateway</body></html>")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        settings = Settings(telegram_bot_token="dummy_token")
        adapter = TelegramAdapter(settings=settings, http_client=client)
        result = await adapter.send_text(chat_id="123", text="Hello")

    assert result.success is False
    assert result.error_code == "HTTP_502"
    assert "Non-JSON" in (result.error_message or "")


@pytest.mark.asyncio
async def test_adapter_timeout_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("Connection timed out")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        settings = Settings(telegram_bot_token="dummy_token")
        adapter = TelegramAdapter(settings=settings, http_client=client)
        result = await adapter.send_text(chat_id="123", text="Hello")

    assert result.success is False
    assert result.error_code == "TIMEOUT"


@pytest.mark.asyncio
async def test_adapter_network_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.NetworkError("Failed to connect")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        settings = Settings(telegram_bot_token="dummy_token")
        adapter = TelegramAdapter(settings=settings, http_client=client)
        result = await adapter.send_text(chat_id="123", text="Hello")

    assert result.success is False
    assert result.error_code == "NETWORK_ERROR"
