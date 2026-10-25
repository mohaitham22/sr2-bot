"""Tests for the bot handlers and the logging middleware. They never connect to Telegram."""

import asyncio
import logging
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.dispatcher.middlewares.user_context import EVENT_CONTEXT_KEY, EventContext
from aiogram.types import Chat, Message, Update

from app.bot.handlers import GREETING, echo, start
from app.bot.middlewares import log_update

# Fake personal data only: a made-up name, phone and unit
FAKE_TEXT = "FAKE Ahmed 01000000000 unit B-204"


def fake_message(text: str) -> SimpleNamespace:
    """A stand-in for aiogram's Message: only .text, and an .answer() that records its calls."""
    return SimpleNamespace(text=text, answer=AsyncMock())


def test_echo_repeats_the_text() -> None:
    message = fake_message("My kitchen sink is leaking")

    asyncio.run(echo(message))  # D2 A: run the coroutine inside a normal test

    message.answer.assert_awaited_once_with("My kitchen sink is leaking")


def test_start_sends_the_greeting() -> None:
    message = fake_message("/start")

    asyncio.run(start(message))

    message.answer.assert_awaited_once_with(GREETING)


def test_log_has_length_but_not_text(caplog: pytest.LogCaptureFixture) -> None:
    chat = Chat(id=111222333, type="private")
    message = Message(message_id=1, date=datetime.now(), chat=chat, text=FAKE_TEXT)
    update = Update(update_id=1, message=message)
    data = {EVENT_CONTEXT_KEY: EventContext(chat=chat)}
    next_step = AsyncMock(return_value="handled")  # stands in for the handlers

    with caplog.at_level(logging.INFO):
        result = asyncio.run(log_update(next_step, update, data))

    # The update was passed on to the handlers
    assert result == "handled"
    next_step.assert_awaited_once_with(update, data)
    # The log has the type, the chat ID and the length...
    assert "type=message" in caplog.text
    assert "chat_id=111222333" in caplog.text
    assert f"length={len(FAKE_TEXT)}" in caplog.text
    # ...but no part of the text
    for part in ["Ahmed", "01000000000", "B-204"]:
        assert part not in caplog.text
