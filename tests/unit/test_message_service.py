from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.conversation import Conversation
from app.database.models.message import Message
from app.database.models.user import User
from app.domain.messages import IncomingMessage
from app.services.message_service import MessageService
from tests.conftest import MockChannelAdapter


@pytest.mark.asyncio
async def test_new_user_message_flow(db_session: AsyncSession) -> None:
    adapter = MockChannelAdapter(should_succeed=True)
    service = MessageService(session=db_session, channel_adapter=adapter)

    incoming = IncomingMessage(
        channel="telegram",
        external_message_id="msg_101",
        external_chat_id="chat_101",
        external_user_id="user_101",
        user_first_name="Alice",
        user_last_name="Smith",
        username="alicesmith",
        message_type="text",
        text="Hello",
        timestamp=datetime.now(UTC),
    )

    processed = await service.handle_incoming_message(incoming)
    assert processed is True

    # Verify User created
    users = (await db_session.execute(select(User))).scalars().all()
    assert len(users) == 1
    assert users[0].external_user_id == "user_101"
    assert users[0].first_name == "Alice"
    assert users[0].username == "alicesmith"

    # Verify Conversation created
    conversations = (await db_session.execute(select(Conversation))).scalars().all()
    assert len(conversations) == 1
    assert conversations[0].external_chat_id == "chat_101"
    assert conversations[0].user_id == users[0].id
    assert conversations[0].status == "active"

    # Verify Messages created (1 incoming, 1 outgoing)
    messages = (
        (await db_session.execute(select(Message).order_by(Message.created_at.asc())))
        .scalars()
        .all()
    )
    assert len(messages) == 2

    # Incoming message check
    assert messages[0].direction == "incoming"
    assert messages[0].external_message_id == "msg_101"
    assert messages[0].text == "Hello"
    assert messages[0].status == "received"

    # Outgoing message check
    assert messages[1].direction == "outgoing"
    assert messages[1].status == "sent"
    assert messages[1].text == "Hello! Thanks for contacting us. How can we help you?"

    # Adapter verify
    assert len(adapter.sent_messages) == 1
    assert adapter.sent_messages[0]["chat_id"] == "chat_101"
    assert (
        adapter.sent_messages[0]["text"] == "Hello! Thanks for contacting us. How can we help you?"
    )


@pytest.mark.asyncio
async def test_existing_user_second_message(db_session: AsyncSession) -> None:
    adapter = MockChannelAdapter(should_succeed=True)
    service = MessageService(session=db_session, channel_adapter=adapter)

    msg1 = IncomingMessage(
        channel="telegram",
        external_message_id="msg_201",
        external_chat_id="chat_200",
        external_user_id="user_200",
        user_first_name="Bob",
        user_last_name=None,
        username="bob200",
        message_type="text",
        text="Hello",
        timestamp=datetime.now(UTC),
    )
    await service.handle_incoming_message(msg1)

    msg2 = IncomingMessage(
        channel="telegram",
        external_message_id="msg_202",
        external_chat_id="chat_200",
        external_user_id="user_200",
        user_first_name="Bob",
        user_last_name="Updated",
        username="bob200",
        message_type="text",
        text="What is your pricing?",
        timestamp=datetime.now(UTC),
    )
    await service.handle_incoming_message(msg2)

    # Verify only 1 User and 1 Conversation exist
    users = (await db_session.execute(select(User))).scalars().all()
    assert len(users) == 1
    assert users[0].last_name == "Updated"

    conversations = (await db_session.execute(select(Conversation))).scalars().all()
    assert len(conversations) == 1

    # 4 messages total: 2 incoming, 2 outgoing
    messages = (await db_session.execute(select(Message))).scalars().all()
    assert len(messages) == 4


@pytest.mark.asyncio
async def test_start_command_response(db_session: AsyncSession) -> None:
    adapter = MockChannelAdapter(should_succeed=True)
    service = MessageService(session=db_session, channel_adapter=adapter)

    incoming = IncomingMessage(
        channel="telegram",
        external_message_id="msg_301",
        external_chat_id="chat_300",
        external_user_id="user_300",
        user_first_name="Charlie",
        user_last_name=None,
        username="charlie",
        message_type="text",
        text="/start",
        timestamp=datetime.now(UTC),
    )
    await service.handle_incoming_message(incoming)

    assert len(adapter.sent_messages) == 1
    assert adapter.sent_messages[0]["text"] == "Welcome! How can we help you?"


@pytest.mark.asyncio
async def test_idempotency_duplicate_message_ignored(db_session: AsyncSession) -> None:
    adapter = MockChannelAdapter(should_succeed=True)
    service = MessageService(session=db_session, channel_adapter=adapter)

    incoming = IncomingMessage(
        channel="telegram",
        external_message_id="duplicate_id_42",
        external_chat_id="chat_400",
        external_user_id="user_400",
        user_first_name="Dave",
        user_last_name=None,
        username="dave",
        message_type="text",
        text="Hello",
        timestamp=datetime.now(UTC),
    )

    first_result = await service.handle_incoming_message(incoming)
    assert first_result is True

    # Send the exact same message ID again
    second_result = await service.handle_incoming_message(incoming)
    assert second_result is False

    # Adapter should still have been called ONLY once
    assert len(adapter.sent_messages) == 1

    # Messages table should have only 1 incoming and 1 outgoing
    incoming_msgs = (
        (await db_session.execute(select(Message).where(Message.direction == "incoming")))
        .scalars()
        .all()
    )
    assert len(incoming_msgs) == 1

    outgoing_msgs = (
        (await db_session.execute(select(Message).where(Message.direction == "outgoing")))
        .scalars()
        .all()
    )
    assert len(outgoing_msgs) == 1


@pytest.mark.asyncio
async def test_send_failure_handled(db_session: AsyncSession) -> None:
    failing_adapter = MockChannelAdapter(should_succeed=False)
    service = MessageService(session=db_session, channel_adapter=failing_adapter)

    incoming = IncomingMessage(
        channel="telegram",
        external_message_id="msg_501",
        external_chat_id="chat_500",
        external_user_id="user_500",
        user_first_name="Eve",
        user_last_name=None,
        username="eve",
        message_type="text",
        text="Hello",
        timestamp=datetime.now(UTC),
    )

    processed = await service.handle_incoming_message(incoming)
    assert processed is True

    # Phase 1: Incoming message must remain committed and received
    incoming_msg = (
        (await db_session.execute(select(Message).where(Message.direction == "incoming")))
        .scalars()
        .one()
    )
    assert incoming_msg.status == "received"
    assert incoming_msg.external_chat_id == "chat_500"
    assert incoming_msg.external_message_id == "msg_501"

    # Phase 3: Outgoing message must be recorded with status failed
    outgoing = (
        (await db_session.execute(select(Message).where(Message.direction == "outgoing")))
        .scalars()
        .one()
    )
    assert outgoing.status == "failed"
    assert outgoing.external_chat_id == "chat_500"


@pytest.mark.asyncio
async def test_database_failure_triggers_rollback(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = MockChannelAdapter(should_succeed=True)
    service = MessageService(session=db_session, channel_adapter=adapter)

    incoming = IncomingMessage(
        channel="telegram",
        external_message_id="msg_fail_db",
        external_chat_id="chat_fail_db",
        external_user_id="user_fail_db",
        user_first_name="Frank",
        user_last_name=None,
        username="frank",
        message_type="text",
        text="Hello",
        timestamp=datetime.now(UTC),
    )

    # Simulate database failure during message persistence
    async def mock_create_error(*args, **kwargs):
        raise RuntimeError("Simulated Database Error")

    monkeypatch.setattr(service.message_repo, "create", mock_create_error)

    with pytest.raises(RuntimeError, match="Simulated Database Error"):
        await service.handle_incoming_message(incoming)

    # Verify no records were committed due to rollback
    users = (
        (await db_session.execute(select(User).where(User.external_user_id == "user_fail_db")))
        .scalars()
        .all()
    )
    assert len(users) == 0


@pytest.mark.asyncio
async def test_chat_scoped_message_uniqueness(db_session: AsyncSession) -> None:
    """
    Ensures message IDs are scoped to chats: same message_id in different chats
    must not collide.
    """
    adapter = MockChannelAdapter(should_succeed=True)
    service = MessageService(session=db_session, channel_adapter=adapter)

    msg_chat_a = IncomingMessage(
        channel="telegram",
        external_message_id="same_msg_id",
        external_chat_id="chat_AAA",
        external_user_id="user_AAA",
        user_first_name="UserA",
        user_last_name=None,
        username="userA",
        message_type="text",
        text="Hello from chat A",
        timestamp=datetime.now(UTC),
    )
    msg_chat_b = IncomingMessage(
        channel="telegram",
        external_message_id="same_msg_id",
        external_chat_id="chat_BBB",
        external_user_id="user_BBB",
        user_first_name="UserB",
        user_last_name=None,
        username="userB",
        message_type="text",
        text="Hello from chat B",
        timestamp=datetime.now(UTC),
    )

    res_a = await service.handle_incoming_message(msg_chat_a)
    res_b = await service.handle_incoming_message(msg_chat_b)

    assert res_a is True
    assert res_b is True

    # Both incoming messages must exist in the database
    incoming_msgs = (
        (await db_session.execute(select(Message).where(Message.direction == "incoming")))
        .scalars()
        .all()
    )
    assert len(incoming_msgs) == 2
    chat_ids = {m.external_chat_id for m in incoming_msgs}
    assert chat_ids == {"chat_AAA", "chat_BBB"}


@pytest.mark.asyncio
async def test_idempotency_concurrent_race_condition_handled(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Simulates a race condition where the pre-check passes concurrently for two workers,
    but the database unique constraint raises IntegrityError for the second.
    Verifies that the service treats it as duplicate and returns False without failing.
    """
    from sqlalchemy.exc import IntegrityError

    adapter = MockChannelAdapter(should_succeed=True)
    service = MessageService(session=db_session, channel_adapter=adapter)

    incoming = IncomingMessage(
        channel="telegram",
        external_message_id="race_msg_1",
        external_chat_id="chat_race",
        external_user_id="user_race",
        user_first_name="Racer",
        user_last_name=None,
        username="racer",
        message_type="text",
        text="Hello",
        timestamp=datetime.now(UTC),
    )

    # First request processes normally
    first_res = await service.handle_incoming_message(incoming)
    assert first_res is True
    assert len(adapter.sent_messages) == 1

    # For second request, pretend pre-check passed (returned False) to simulate race
    monkeypatch.setattr(service.message_repo, "exists_incoming", lambda *args, **kwargs: False)

    # When trying to create in DB, unique constraint throws IntegrityError
    real_create = service.message_repo.create

    async def mock_create_race(*args, **kwargs):
        if kwargs.get("direction") == "incoming":
            raise IntegrityError(
                "duplicate key value violates unique constraint", params={}, orig=Exception()
            )
        return await real_create(*args, **kwargs)

    monkeypatch.setattr(service.message_repo, "create", mock_create_race)

    # Re-enable real exists_incoming for the error recovery handler to verify duplicate exists
    async def mock_exists_after_race(channel, chat_id, msg_id):
        return True

    # Second invocation should catch IntegrityError, verify duplicate, and return False safely
    monkeypatch.setattr(service.message_repo, "exists_incoming", mock_exists_after_race)
    second_res = await service.handle_incoming_message(incoming)
    assert second_res is False

    # Adapter should NOT have been called a second time
    assert len(adapter.sent_messages) == 1
