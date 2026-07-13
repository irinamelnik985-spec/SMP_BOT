import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.storage.memory import MemoryStorage

import db
import storage
from config import BOT_TOKEN, PROXY_URL
from handlers import admin, form, moderation, panel, review, rules, start, suggest, ticket, welcome
from monitor import monitoring_loop
from middlewares.membership import MembershipMiddleware
from middlewares.throttle import ThrottleMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


async def main() -> None:
    db.init()
    storage.all_users = db.get_all_users()
    logger.info("Загружено пользователей из БД: %d", len(storage.all_users))
    if PROXY_URL:
        session = AiohttpSession(proxy=PROXY_URL)
        bot = Bot(token=BOT_TOKEN, session=session)
        logger.info("Прокси: %s", PROXY_URL)
    else:
        bot = Bot(token=BOT_TOKEN)

    dp = Dispatcher(storage=MemoryStorage())

    dp.update.outer_middleware(MembershipMiddleware())
    dp.update.outer_middleware(ThrottleMiddleware())

    dp.include_router(start.router)
    dp.include_router(rules.router)
    dp.include_router(form.router)
    dp.include_router(ticket.router)
    dp.include_router(review.router)
    dp.include_router(suggest.router)
    dp.include_router(admin.router)
    dp.include_router(moderation.router)
    dp.include_router(panel.router)
    dp.include_router(welcome.router)

    asyncio.create_task(monitoring_loop(bot))

    logger.info("Бот запущен")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
