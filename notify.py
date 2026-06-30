"""Оповещение админов о действиях по заявкам/жалобам/вопросам."""

from aiogram import Bot

from config import ADMIN_IDS


def _actor(user) -> str:
    if getattr(user, "username", None):
        return f"@{user.username}"
    return getattr(user, "full_name", None) or f"id{user.id}"


async def close_admin_broadcast(bot: Bot, records, actor, action: str) -> None:
    """Один админ взялся за заявку/тикет:
    1) стираем инлайн-кнопки у ВСЕХ разосланных копий (records: список (chat_id, message_id)),
    2) оповещаем всех ОСТАЛЬНЫХ админов, кто именно взялся — чтобы не дублировали.
    """
    for chat_id, message_id in records:
        try:
            await bot.edit_message_reply_markup(
                chat_id=chat_id, message_id=message_id, reply_markup=None
            )
        except Exception:
            pass
    text = f"☑️ <b>{_actor(actor)}</b> {action}"
    for admin_id in ADMIN_IDS:
        if admin_id == actor.id:
            continue
        try:
            await bot.send_message(admin_id, text, parse_mode="HTML")
        except Exception:
            pass
