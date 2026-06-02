"""
Throttle middleware: rate-limit на действия в боте.

Защищает от спама во время рейда:
- N запросов за окно WINDOW_SEC от одного user_id → ответ "❌ слишком часто"
- Кеш чистится автоматически (LRU-style: храним последние MAX_USERS юзеров).

Применяется ПОСЛЕ MembershipMiddleware. То есть юзер уже прошёл проверку
группы — теперь не должен спамить.
"""

import time
from collections import deque
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Update

from config import ADMIN_ID

# Параметры rate-limit
WINDOW_SEC = 5.0       # окно в секундах
MAX_HITS = 8           # максимум событий в окне
MAX_USERS = 5000       # ограничение размера кеша

# user_id → deque[timestamps]
_HITS: dict[int, deque] = {}

THROTTLE_MSG = "❌ Слишком часто. Подожди 5 секунд."


def _hit(user_id: int) -> bool:
    """True если можно пропустить, False если throttle сработал."""
    now = time.monotonic()
    q = _HITS.get(user_id)
    if q is None:
        if len(_HITS) >= MAX_USERS:
            # LRU-урон: убираем случайного старого
            try:
                _HITS.pop(next(iter(_HITS)))
            except StopIteration:
                pass
        q = deque()
        _HITS[user_id] = q
    # Чистим старые
    while q and now - q[0] > WINDOW_SEC:
        q.popleft()
    if len(q) >= MAX_HITS:
        return False
    q.append(now)
    return True


class ThrottleMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Update, dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: dict[str, Any],
    ) -> Any:
        # Пропускаем те же что в MembershipMiddleware
        if event.chat_member is not None or event.my_chat_member is not None:
            return await handler(event, data)

        user = None
        if event.message:
            user = event.message.from_user
        elif event.callback_query:
            user = event.callback_query.from_user
        elif event.inline_query:
            user = event.inline_query.from_user

        if user is None:
            return await handler(event, data)
        if user.id == ADMIN_ID:
            return await handler(event, data)

        if _hit(user.id):
            return await handler(event, data)

        # Throttled
        if event.callback_query:
            await event.callback_query.answer(THROTTLE_MSG, show_alert=False)
        elif event.message:
            # Молча игнорируем повторы чтобы не залить чат сами
            pass
        return None
