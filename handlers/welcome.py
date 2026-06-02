import html
import logging

from aiogram import Bot, Router
from aiogram.types import ChatMemberUpdated
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter, IS_NOT_MEMBER, IS_MEMBER

from config import REVIEWS_GROUP_ID, CHATIK_TOPIC_ID

router = Router()
logger = logging.getLogger(__name__)


@router.chat_member(ChatMemberUpdatedFilter(member_status_changed=IS_NOT_MEMBER >> IS_MEMBER))
async def on_new_member(event: ChatMemberUpdated, bot: Bot) -> None:
    if REVIEWS_GROUP_ID and event.chat.id != REVIEWS_GROUP_ID:
        return

    user = event.new_chat_member.user
    if user.is_bot:
        return

    name = html.escape(user.full_name or "друг")
    mention = f'<a href="tg://user?id={user.id}">{name}</a>'

    text = (
        f"👋 Привет, {mention}! Добро пожаловать в <b>Warden SMP</b>!\n\n"
        f"🤖 Бот: @WSMP_white_bot\n"
        f"🌐 IP: <code>wardensmp.fun</code>\n"
        f"📦 Версия: <b>1.21 и новее</b>"
    )

    try:
        await bot.send_message(
            event.chat.id,
            text,
            parse_mode="HTML",
            message_thread_id=CHATIK_TOPIC_ID or None,
            disable_web_page_preview=True,
        )
        logger.info("Приветствие отправлено user_id=%d", user.id)
    except Exception as e:
        logger.warning("Не удалось отправить приветствие: %s", e)
