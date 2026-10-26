"""Test for app/bot/polling.py: the Dispatcher wiring. It never connects to Telegram."""

import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

from aiogram import Bot
from aiogram.methods import SendMessage
from aiogram.types import Chat, File, Message, Update, User, Voice

from app.bot.polling import build_dispatcher

FAKE_USER_ID = 123456789  # a made-up Telegram user ID


# Keep this the only test that calls build_dispatcher(): aiogram lets our router
# join only one Dispatcher per process (a second call raises RuntimeError).
def test_dispatcher_gives_voice_values_to_the_handler(tmp_path: Path) -> None:
    dp = build_dispatcher(tmp_path, frozenset({FAKE_USER_ID}))
    message = Message(
        message_id=1,
        date=datetime.now(),
        chat=Chat(id=FAKE_USER_ID, type="private"),
        from_user=User(id=FAKE_USER_ID, is_bot=False, first_name="Fake"),
        voice=Voice(file_id="fake-file-id", file_unique_id="fake", duration=7, file_size=4),
    )
    fake_file = File(file_id="fake-file-id", file_unique_id="fake", file_path="voice/file_1.oga")

    async def download_file(file_path: str, destination: Path) -> None:
        destination.write_bytes(b"OggS")

    async def feed() -> None:
        bot = Bot(token="123456:FAKE-token")  # fake token; every network call is mocked below
        await dp.feed_update(bot, Update(update_id=1, message=message))
        await bot.session.close()

    with (
        patch.object(Bot, "get_file", AsyncMock(return_value=fake_file)),
        patch.object(Bot, "download_file", AsyncMock(side_effect=download_file)),
        patch.object(Bot, "__call__", AsyncMock()) as sent,  # sending the reply
    ):
        asyncio.run(feed())

    # aiogram chose save_voice and gave it our temporary folder and the allowed IDs
    assert [path.read_bytes() for path in tmp_path.glob("*.ogg")] == [b"OggS"]
    reply = sent.await_args.args[0]
    assert isinstance(reply, SendMessage)
    assert reply.text.startswith("Voice note saved")
