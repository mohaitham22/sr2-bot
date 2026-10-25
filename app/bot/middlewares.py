"""Bot middlewares: code that runs around every update, before the handlers."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram.dispatcher.middlewares.user_context import EVENT_CONTEXT_KEY
from aiogram.types import TelegramObject, Update

logger = logging.getLogger(__name__)


async def log_update(
    handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
    event: TelegramObject,
    data: dict[str, Any],
) -> Any:
    """Log the update type, the chat ID and the text length. Never the text itself.

    The text can contain names and phone numbers (CLAUDE.md section 9).
    Register it on the Dispatcher: dp.update.outer_middleware(log_update)
    """
    if isinstance(event, Update):
        # aiogram's own UserContextMiddleware runs before this one and finds the chat
        context = data.get(EVENT_CONTEXT_KEY)
        chat_id = context.chat_id if context else None
        text = getattr(event.event, "text", None)  # None for updates without text
        logger.info(
            "update type=%s chat_id=%s length=%d", event.event_type, chat_id, len(text or "")
        )
    return await handler(event, data)  # pass the update on to the next step (the handlers)
