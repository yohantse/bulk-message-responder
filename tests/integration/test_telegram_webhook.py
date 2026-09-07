import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.conversation import Conversation
from app.database.models.message import Message
from app.database.models.user import User
from tests.conftest import MockChannelAdapter


@pytest.mark.asyncio
async def test_health_check(test_client: AsyncClient) -> None:
    response = await test_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_webhook_missing_secret(test_client: AsyncClient) -> None:
    payload = {"update_id": 1}
    response = await test_client.post("/webhooks/telegram", json=payload)
    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid webhook secret token"


@pytest.mark.asyncio
async def test_webhook_invalid_secret(test_client: AsyncClient) -> None:
    payload = {"update_id": 1}
    headers = {"X-Telegram-Bot-Api-Secret-Token": "wrong_secret"}
    response = await test_client.post("/webhooks/telegram", json=payload, headers=headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid webhook secret token"


@pytest.mark.asyncio
async def test_webhook_unsupported_update(
    test_client: AsyncClient, db_session: AsyncSession
) -> None:
    payload = {
        "update_id": 999,
        "callback_query": {"id": "cb_1", "data": "button"},
    }
    headers = {"X-Telegram-Bot-Api-Secret-Token": "test_webhook_secret"}
    response = await test_client.post("/webhooks/telegram", json=payload, headers=headers)

    assert response.status_code == 200
    assert response.json() == {"ok": True, "ignored": True}

    # Verify no DB records created
    users = (await db_session.execute(select(User))).scalars().all()
    assert len(users) == 0


@pytest.mark.asyncio
async def test_webhook_valid_message_flow(
    test_client: AsyncClient,
    db_session: AsyncSession,
    mock_adapter: MockChannelAdapter,
) -> None:
    payload = {
        "update_id": 10001,
        "message": {
            "message_id": 777,
            "from": {
                "id": 55555,
                "first_name": "Integration",
                "last_name": "Tester",
                "username": "tester55",
            },
            "chat": {
                "id": 55555,
                "type": "private",
            },
            "date": 1757241000,
            "text": "Hello, is this available?",
        },
    }
    headers = {"X-Telegram-Bot-Api-Secret-Token": "test_webhook_secret"}

    # First delivery
    response = await test_client.post("/webhooks/telegram", json=payload, headers=headers)
    assert response.status_code == 200
    assert response.json() == {"ok": True, "processed": True}

    # Verify DB state
    users = (await db_session.execute(select(User))).scalars().all()
    assert len(users) == 1
    assert users[0].external_user_id == "55555"

    conversations = (await db_session.execute(select(Conversation))).scalars().all()
    assert len(conversations) == 1
    assert conversations[0].external_chat_id == "55555"

    messages = (await db_session.execute(select(Message))).scalars().all()
    assert len(messages) == 2
    assert all(m.external_chat_id == "55555" for m in messages)

    # Second delivery (Duplicate Telegram update)
    dup_response = await test_client.post("/webhooks/telegram", json=payload, headers=headers)
    assert dup_response.status_code == 200
    assert dup_response.json() == {"ok": True, "processed": False}

    # DB messages should still be 2 (no duplicate created)
    messages_after = (await db_session.execute(select(Message))).scalars().all()
    assert len(messages_after) == 2
