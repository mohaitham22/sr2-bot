"""Run the bot on this laptop with long polling: uv run python -m app.bot.polling

Polling needs no public URL, so it works locally. Phase 5 switches to a webhook.
Stop it with Ctrl+C.
"""

import asyncio
import logging
from contextlib import suppress

from aiogram import Bot, Dispatcher

from app.bot.handlers import router
from app.bot.middlewares import log_update
from app.config import get_settings
from app.logging_setup import setup_logging

# A fixed name: with "python -m", __name__ would be "__main__" (CLAUDE.md section 13, D6 B)
logger = logging.getLogger("app.bot.polling")


async def run_bot(token: str) -> None:
    bot = Bot(token=token)  # no default parse mode: replies are plain text
    dp = Dispatcher()
    dp.update.outer_middleware(log_update)  # runs for every update, before the handlers
    dp.include_router(router)
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
    # Ctrl+C ends as KeyboardInterrupt on Windows; on Linux aiogram stops polling by itself
    with suppress(KeyboardInterrupt):
        asyncio.run(run_bot(token))  # start the event loop
    logger.info("Bot stopped")


if __name__ == "__main__":
    main()
