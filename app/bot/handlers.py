"""Bot handlers for Step 1.4: /start says hello, any other text is echoed back."""

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message

router = Router(name=__name__)

# English + Egyptian Arabic in one message (CLAUDE.md section 13, D3 A).
# Sent as plain text: the Bot has no parse mode, so nothing here is read as HTML.
GREETING = (
    "Hello! I'm the Service Request Bot.\n"
    "Soon you can report a maintenance problem in your unit here, by text or voice note, "
    "in English or Arabic. I'll ask for any missing details and give you a ticket number.\n"
    "Right now I'm in test mode: I repeat your text messages.\n"
    "\n"
    "أهلاً! أنا بوت طلبات الصيانة.\n"
    "قريب هتقدر تبلّغ عن أي مشكلة صيانة في وحدتك من هنا، بالكتابة أو برسالة صوتية، "
    "بالعربي أو بالإنجليزي. هسألك عن أي تفاصيل ناقصة وهديك رقم تذكرة.\n"
    "دلوقتي أنا في وضع التجربة: بكرر رسايلك النصية."
)


# Order matters: the first matching handler wins. "/start" is also text,
# so this handler must be registered before echo().
@router.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(GREETING)


@router.message(F.text)  # F.text: the message has text that is not empty
async def echo(message: Message) -> None:
    await message.answer(message.text)
