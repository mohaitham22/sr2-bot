"""Tests for the bot handlers and the logging middleware. They never connect to Telegram."""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.dispatcher.middlewares.user_context import EVENT_CONTEXT_KEY, EventContext
from aiogram.types import Chat, Message, Update

from app.bot.handlers import (
    GREETING,
    UNSUPPORTED,
    VOICE_NOT_AVAILABLE,
    VOICE_TOO_BIG,
    echo,
    router,
    save_voice,
    start,
    unsupported,
)
from app.bot.middlewares import log_update
from app.bot.voice_files import MAX_DOWNLOAD_BYTES

# Fake personal data only: a made-up name, phone and unit
FAKE_TEXT = "FAKE Ahmed 01000000000 unit B-204"
# Fake Telegram user IDs: one on the voice allowlist, one not
FAKE_USER_ID = 123456789
OTHER_USER_ID = 987654321


def fake_message(text: str) -> SimpleNamespace:
    """A stand-in for aiogram's Message: only .text, and an .answer() that records its calls."""
    return SimpleNamespace(text=text, answer=AsyncMock())


def fake_voice_message(file_size: int | None = 2048) -> SimpleNamespace:
    """A stand-in for a voice Message from FAKE_USER_ID: 75 seconds long."""
    voice = SimpleNamespace(file_id="fake-file-id", duration=75, file_size=file_size)
    return SimpleNamespace(
        voice=voice, from_user=SimpleNamespace(id=FAKE_USER_ID), answer=AsyncMock()
    )


def fake_bot(audio: bytes = b"x" * 2048) -> SimpleNamespace:
    """A stand-in for aiogram's Bot: get_file() gives a path, download_file() writes `audio`."""

    async def download_file(file_path: str, destination: Path) -> None:
        destination.write_bytes(audio)

    return SimpleNamespace(
        get_file=AsyncMock(return_value=SimpleNamespace(file_path="voice/file_1.oga")),
        download_file=AsyncMock(side_effect=download_file),
    )


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


def test_handler_order() -> None:
    # The first matching handler wins: the catch-all (no filter) must be last
    names = [handler.callback.__name__ for handler in router.message.handlers]

    assert names == ["start", "echo", "save_voice", "unsupported"]


def test_voice_is_saved_and_reply_has_name_duration_size(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    message = fake_voice_message()
    bot = fake_bot(audio=b"x" * 2048)

    with caplog.at_level(logging.INFO):
        asyncio.run(save_voice(message, bot, tmp_path, frozenset({FAKE_USER_ID})))

    # One file, with exactly the downloaded bytes
    saved = list(tmp_path.glob("*.ogg"))
    assert len(saved) == 1
    assert saved[0].read_bytes() == b"x" * 2048
    # The two Telegram steps: getFile, then download into the reserved file
    bot.get_file.assert_awaited_once_with("fake-file-id")
    bot.download_file.assert_awaited_once_with("voice/file_1.oga", destination=saved[0])
    # The reply has the file name, the duration (75 s) and the size
    reply = message.answer.await_args.args[0]
    for part in [saved[0].name, "Duration: 1:15", "2.0 KB", "2,048 bytes"]:
        assert part in reply
    # The log has the file name, but not the user ID
    assert f"voice saved file={saved[0].name}" in caplog.text
    assert str(FAKE_USER_ID) not in caplog.text


@pytest.mark.parametrize("allowed_ids", [None, frozenset(), frozenset({OTHER_USER_ID})])
def test_voice_from_unlisted_user_is_not_downloaded(
    tmp_path: Path, allowed_ids: frozenset[int] | None
) -> None:
    message = fake_voice_message()
    bot = fake_bot()

    asyncio.run(save_voice(message, bot, tmp_path, allowed_ids))

    bot.get_file.assert_not_awaited()
    assert list(tmp_path.iterdir()) == []
    message.answer.assert_awaited_once_with(VOICE_NOT_AVAILABLE)


def test_too_big_voice_is_not_downloaded(tmp_path: Path) -> None:
    message = fake_voice_message(file_size=MAX_DOWNLOAD_BYTES + 1)
    bot = fake_bot()

    asyncio.run(save_voice(message, bot, tmp_path, frozenset({FAKE_USER_ID})))

    bot.get_file.assert_not_awaited()
    assert list(tmp_path.iterdir()) == []
    message.answer.assert_awaited_once_with(VOICE_TOO_BIG)


def test_failed_download_leaves_no_file(tmp_path: Path) -> None:
    message = fake_voice_message()
    bot = fake_bot()

    async def half_download(file_path: str, destination: Path) -> None:
        destination.write_bytes(b"half a file")  # some bytes arrive, then the network fails
        raise TimeoutError("fake network error")

    bot.download_file.side_effect = half_download

    with pytest.raises(TimeoutError):
        asyncio.run(save_voice(message, bot, tmp_path, frozenset({FAKE_USER_ID})))

    assert list(tmp_path.iterdir()) == []  # the half-written file was deleted
    message.answer.assert_not_awaited()


def test_unsupported_message_gets_polite_reply(caplog: pytest.LogCaptureFixture) -> None:
    # A photo whose caption has (fake) personal data
    message = SimpleNamespace(content_type="photo", caption=FAKE_TEXT, answer=AsyncMock())

    with caplog.at_level(logging.INFO):
        asyncio.run(unsupported(message))

    message.answer.assert_awaited_once_with(UNSUPPORTED)
    assert "content_type=photo" in caplog.text
    for part in ["Ahmed", "01000000000", "B-204"]:
        assert part not in caplog.text
