import os
from collections.abc import AsyncGenerator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Ensure testing environment variables
os.environ["APP_ENV"] = "test"
os.environ["TELEGRAM_BOT_TOKEN"] = "test_bot_token"
os.environ["TELEGRAM_WEBHOOK_SECRET"] = "test_webhook_secret"
os.environ["LOG_LEVEL"] = "DEBUG"

from app.api.webhooks.telegram import get_telegram_adapter
from app.database.base import Base
from app.database.session import get_db_session
from app.main import app
from app.telegram.adapter import ChannelAdapter, SendResult


class MockChannelAdapter(ChannelAdapter):
    def __init__(self, should_succeed: bool = True) -> None:
        self.should_succeed = should_succeed
        self.sent_messages: list[dict[str, Any]] = []

    async def send_text(self, chat_id: str, text: str) -> SendResult:
        self.sent_messages.append({"chat_id": chat_id, "text": text})
        if self.should_succeed:
            return SendResult(
                success=True,
                external_message_id=f"tg_out_{len(self.sent_messages)}",
            )
        return SendResult(
            success=False,
            error_code="TEST_ERROR",
            error_message="Simulated Telegram API error",
        )


@pytest.fixture
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with session_factory() as session:
        yield session


@pytest.fixture
def mock_adapter() -> MockChannelAdapter:
    return MockChannelAdapter(should_succeed=True)


@pytest.fixture
async def test_client(
    db_session: AsyncSession, mock_adapter: MockChannelAdapter
) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    def override_get_telegram_adapter() -> ChannelAdapter:
        return mock_adapter

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_telegram_adapter] = override_get_telegram_adapter

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
