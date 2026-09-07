from app.telegram.parser import parse_telegram_update


def test_parse_valid_private_text_message() -> None:
    payload = {
        "update_id": 123456,
        "message": {
            "message_id": 42,
            "from": {
                "id": 98765,
                "is_bot": False,
                "first_name": "John",
                "last_name": "Doe",
                "username": "johndoe",
            },
            "chat": {
                "id": 98765,
                "type": "private",
                "first_name": "John",
                "last_name": "Doe",
                "username": "johndoe",
            },
            "date": 1757241000,
            "text": "Hi, I want to know the price.",
        },
    }

    result = parse_telegram_update(payload)
    assert result is not None
    assert result.channel == "telegram"
    assert result.external_message_id == "42"
    assert result.external_chat_id == "98765"
    assert result.external_user_id == "98765"
    assert result.user_first_name == "John"
    assert result.user_last_name == "Doe"
    assert result.username == "johndoe"
    assert result.message_type == "text"
    assert result.text == "Hi, I want to know the price."
    assert result.timestamp.timestamp() == 1757241000
    assert result.update_id == 123456


def test_parse_group_message_ignored() -> None:
    payload = {
        "update_id": 123457,
        "message": {
            "message_id": 43,
            "from": {"id": 98765, "first_name": "John"},
            "chat": {"id": -100123456789, "type": "supergroup", "title": "Test Group"},
            "date": 1757241000,
            "text": "Hello group",
        },
    }
    result = parse_telegram_update(payload)
    assert result is None


def test_parse_photo_message_without_text_ignored() -> None:
    payload = {
        "update_id": 123458,
        "message": {
            "message_id": 44,
            "from": {"id": 98765, "first_name": "John"},
            "chat": {"id": 98765, "type": "private"},
            "date": 1757241000,
            # No text, e.g. photo update
        },
    }
    result = parse_telegram_update(payload)
    assert result is None


def test_parse_callback_query_ignored() -> None:
    payload = {
        "update_id": 123459,
        "callback_query": {
            "id": "cb_123",
            "from": {"id": 98765, "first_name": "John"},
            "data": "button_clicked",
        },
    }
    result = parse_telegram_update(payload)
    assert result is None


def test_parse_edited_message_ignored() -> None:
    payload = {
        "update_id": 123460,
        "edited_message": {
            "message_id": 42,
            "chat": {"id": 98765, "type": "private"},
            "text": "Edited text",
            "date": 1757241010,
        },
    }
    result = parse_telegram_update(payload)
    assert result is None


def test_parse_whitespace_text_ignored() -> None:
    payload = {
        "update_id": 123461,
        "message": {
            "message_id": 45,
            "chat": {"id": 98765, "type": "private"},
            "date": 1757241000,
            "text": "   ",
        },
    }
    result = parse_telegram_update(payload)
    assert result is None
