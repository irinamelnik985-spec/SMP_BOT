import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.storage.memory import MemoryStorage

import db
import storage
from config import BOT_TOKEN, PROXY_URL
from handlers import admin, form, panel, review, rules, start, ticket
from monitor import log_watcher_loop, monitoring_loop

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

    dp.include_router(start.router)
    dp.include_router(rules.router)
    dp.include_router(form.router)
    dp.include_router(admin.router)
    dp.include_router(panel.router)
    dp.include_router(ticket.router)
    dp.include_router(review.router)

    asyncio.create_task(monitoring_loop(bot))
    asyncio.create_task(log_watcher_loop(bot))

    logger.info("Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
