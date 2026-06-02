"""
Outer-middleware: проверка членства в группе для всех команд бота.

- Пропускаются:
    * админ (ADMIN_ID)
    * chat_member / my_chat_member события (для welcome handler)
    * не-private чаты (бот в группе не должен фильтровать сам себя)
- Не в группе → краткий алерт и блок дальнейшей обработки.
- Cache на 30 секунд чтобы не дёргать TG API на каждое нажатие.
"""

import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Update

from config import ADMIN_ID, REVIEWS_GROUP_ID

_CACHE: dict[int, tuple[bool, float]] = {}
_CACHE_TTL = 30.0  # сек

NOT_IN_GROUP_MSG = (
    "❌ Доступно только участникам группы @warden_smp.\n"
    "Подпишись и нажми ещё раз."
)


async def _is_member(bot, user_id: int) -> bool:
    now = time.monotonic()
    cached = _CACHE.get(user_id)
    if cached and (now - cached[1]) < _CACHE_TTL:
        return cached[0]
    try:
        m = await bot.get_chat_member(chat_id=REVIEWS_GROUP_ID, user_id=user_id)
        ok = m.status not in ("left", "kicked", "banned")
    except Exception:
        # Если TG API упал — пропускаем (лучше пустить чем сломать UX).
        ok = True
    _CACHE[user_id] = (ok, now)
    return ok


class MembershipMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Update, dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: dict[str, Any],
    ) -> Any:
        # chat_member события — для welcome handler, не трогаем
        if event.chat_member is not None or event.my_chat_member is not None:
            return await handler(event, data)

        # Извлекаем user и chat в зависимости от типа update'а
        user = None
        chat = None
        if event.message:
            user = event.message.from_user
            chat = event.message.chat
        elif event.callback_query:
            user = event.callback_query.from_user
            chat = event.callback_query.message.chat if event.callback_query.message else None
        elif event.inline_query:
            user = event.inline_query.from_user
        elif event.edited_message:
            user = event.edited_message.from_user
            chat = event.edited_message.chat

        if user is None:
            return await handler(event, data)

        # Сообщения в группах/каналах (не личке) — не блокируем
        if chat is not None and chat.type != "private":
            return await handler(event, data)

        # Админ всегда пропускается
        if user.id == ADMIN_ID:
            return await handler(event, data)

        bot = data["bot"]
        if await _is_member(bot, user.id):
            return await handler(event, data)

        # Не в группе — короткий алерт + блок
        if event.callback_query:
            await event.callback_query.answer(NOT_IN_GROUP_MSG, show_alert=True)
        elif event.message:
            await event.message.answer(NOT_IN_GROUP_MSG)
        return None
