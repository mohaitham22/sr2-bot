"""Run the bot on this laptop with long polling: uv run python -m app.bot.polling

Polling needs no public URL, so it works locally. Phase 5 switches to a webhook.
Stop it with Ctrl+C.
"""

import asyncio
import logging
from contextlib import suppress
from pathlib import Path

from aiogram import Bot, Dispatcher

from app.bot.handlers import router
from app.bot.middlewares import log_update
from app.bot.voice_files import VOICE_DIR
from app.config import get_settings
from app.logging_setup import setup_logging

# A fixed name: with "python -m", __name__ would be "__main__" (CLAUDE.md section 13, D6 B)
logger = logging.getLogger("app.bot.polling")


def build_dispatcher(voice_dir: Path, voice_save_user_ids: frozenset[int] | None) -> Dispatcher:
    """Create the Dispatcher: handler values, the logging middleware and our router.

    A separate function, so a test can check the wiring without Telegram.
    Call it once per process: aiogram lets a router join only one Dispatcher.
    """
    dp = Dispatcher()
    # Values for the handlers: aiogram passes each one to every handler that has
    # a parameter with the same name (dependency injection)
    dp["voice_dir"] = voice_dir
    dp["voice_save_user_ids"] = voice_save_user_ids
    dp.update.outer_middleware(log_update)  # runs for every update, before the handlers
    dp.include_router(router)
    return dp


async def run_bot(token: str, voice_save_user_ids: frozenset[int] | None) -> None:
    bot = Bot(token=token)  # no default parse mode: replies are plain text
    dp = build_dispatcher(VOICE_DIR, voice_save_user_ids)
    # allowed_updates: ask Telegram only for the update types our handlers use (now: "message")
    polling = asyncio.create_task(
        dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    )
    # On Windows aiogram can't catch Ctrl+C itself, so asyncio cancels this function instead.
    # shield: that cancel stops here and does not reach the polling task (D5 B).
    try:
        await asyncio.shield(polling)
    except asyncio.CancelledError:
        await dp.stop_polling()  # aiogram's clean stop: polling first, then the connection
        raise  # let asyncio finish stopping as usual


def main() -> None:
    settings = get_settings()
    settings.require("telegram_bot_token")  # fail fast with a clear message if .env misses it
    token = settings.telegram_bot_token.get_secret_value()
    setup_logging(secrets=[token])
    # Not an error: the bot still works, it just saves no voice notes (D2 A safe default)
    if not settings.voice_save_user_ids:
        logger.warning("VOICE_SAVE_USER_IDS is not set in .env: no voice notes will be saved")
    else:  # how many IDs, never the IDs themselves
        count = len(settings.voice_save_user_ids)
        logger.info("Voice notes from %d user ID(s) are saved to %s", count, VOICE_DIR)
    # Ctrl+C ends as KeyboardInterrupt on Windows; on Linux aiogram stops polling by itself
    with suppress(KeyboardInterrupt):
        asyncio.run(run_bot(token, settings.voice_save_user_ids))  # start the event loop
    logger.info("Bot stopped")


if __name__ == "__main__":
    main()
