"""Bot handlers: /start says hello, text is echoed back (Step 1.4), voice notes are saved
for testing (Step 1.5), and every other message type gets a polite reply."""

import logging
from datetime import date
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.bot.voice_files import MAX_DOWNLOAD_BYTES, next_voice_path

logger = logging.getLogger(__name__)
router = Router(name=__name__)

# Replies: English + Egyptian Arabic in one message (CLAUDE.md section 13, D3 A).
# Sent as plain text: the Bot has no parse mode, so nothing here is read as HTML.
GREETING = (
    "Hello! I'm the Service Request Bot.\n"
    "Soon you can report a maintenance problem in your unit here, by text or voice note, "
    "in English or Arabic. I'll ask for any missing details and give you a ticket number.\n"
    "Right now I'm in test mode: I repeat your text messages. "
    "Voice notes are saved only for the test team.\n"
    "\n"
    "أهلاً! أنا بوت طلبات الصيانة.\n"
    "قريب هتقدر تبلّغ عن أي مشكلة صيانة في وحدتك من هنا، بالكتابة أو برسالة صوتية، "
    "بالعربي أو بالإنجليزي. هسألك عن أي تفاصيل ناقصة وهديك رقم تذكرة.\n"
    "دلوقتي أنا في وضع التجربة: بكرر رسايلك النصية. "
    "الرسايل الصوتية بتتحفظ لفريق التجربة بس."
)

VOICE_NOT_AVAILABLE = (
    "Sorry, I can't take voice notes yet. Please type your message.\n"
    "\n"
    "معلش، لسه مش بقدر أستقبل رسايل صوتية. اكتب رسالتك من فضلك."
)

VOICE_TOO_BIG = (
    "Sorry, this voice note is too big (over 20 MB). Please send a shorter one.\n"
    "\n"
    "معلش، الرسالة الصوتية دي كبيرة أوي (أكتر من 20 ميجا). ابعت رسالة أقصر."
)

UNSUPPORTED = (
    "Sorry, I can only read text messages and voice notes. "
    "Please type your message or send a voice note.\n"
    "\n"
    "معلش، أنا بفهم الرسايل النصية والرسايل الصوتية بس. اكتب رسالتك أو ابعت رسالة صوتية."
)


def voice_saved_reply(file_name: str, duration: int, size: int) -> str:
    """The reply after saving, e.g. duration 75 -> "1:15", size 12345 -> "12.1 KB"."""
    minutes, seconds = divmod(duration, 60)
    return (
        "Voice note saved ✅\n"
        "تم حفظ الرسالة الصوتية ✅\n"
        "\n"
        f"File: {file_name}\n"
        f"Duration: {minutes}:{seconds:02d}\n"
        f"Size: {size / 1024:.1f} KB ({size:,} bytes)"
    )


# Order matters: the first matching handler wins. "/start" is also text,
# so this handler must be registered before echo().
@router.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(GREETING)


@router.message(F.text)  # F.text: the message has text that is not empty
async def echo(message: Message) -> None:
    await message.answer(message.text)


@router.message(F.voice)  # F.voice: recorded with the microphone button (not a music file)
async def save_voice(
    message: Message,
    bot: Bot,
    voice_dir: Path,
    voice_save_user_ids: frozenset[int] | None,
) -> None:
    """Save the voice note in voice_dir and reply with its file name, duration and size.

    aiogram passes bot itself; voice_dir and voice_save_user_ids come from polling.py
    (dependency injection), so the tests can pass a temporary folder instead.
    """
    voice = message.voice
    user = message.from_user
    # D2 A: only the IDs in .env; for anyone else nothing is downloaded
    if not voice_save_user_ids or user is None or user.id not in voice_save_user_ids:
        logger.info("voice not saved: sender not in VOICE_SAVE_USER_IDS")
        await message.answer(VOICE_NOT_AVAILABLE)
        return
    # Check before downloading: Telegram refuses files over 20 MB anyway
    if voice.file_size is not None and voice.file_size > MAX_DOWNLOAD_BYTES:
        logger.info("voice not saved: too big, size=%d", voice.file_size)
        await message.answer(VOICE_TOO_BIG)
        return

    path = next_voice_path(voice_dir, date.today())  # reserve the name before the first await
    try:
        file = await bot.get_file(voice.file_id)  # 1. getFile: file_id -> file_path
        await bot.download_file(file.file_path, destination=path)  # 2. download (30 s timeout)
    except BaseException:
        # BaseException also catches Ctrl+C. Step 1.6 must never read a half-written file.
        path.unlink(missing_ok=True)
        raise  # aiogram logs the error (token hidden by our logging setup)

    size = path.stat().st_size  # what we really saved on disk, not Telegram's number
    logger.info("voice saved file=%s duration=%d size=%d", path.name, voice.duration, size)
    await message.answer(voice_saved_reply(path.name, voice.duration, size))


# No filter: catches every message the handlers above did not take (photo, sticker, file...).
# Must stay the last handler in this file.
@router.message()
async def unsupported(message: Message) -> None:
    logger.info("unsupported message content_type=%s", message.content_type)
    await message.answer(UNSUPPORTED)
