import logging
import re
import time

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import storage
from config import ADMIN_ID, RCON_HOST, RCON_PASS, RCON_PORT
from rcon import rcon as rcon_cmd
from states import PanelStates

router = Router()
logger = logging.getLogger(__name__)


async def _rcon_whitelist_add(nickname: str) -> str:
    return await rcon_cmd(RCON_HOST, RCON_PASS, f"whitelist add {nickname}", RCON_PORT)


async def _is_whitelisted(nickname: str) -> bool:
    raw = await rcon_cmd(RCON_HOST, RCON_PASS, "whitelist list", RCON_PORT)
    return bool(re.search(rf"\b{re.escape(nickname)}\b", raw, re.IGNORECASE))



@router.callback_query(F.data.startswith("approve_"))
async def approve_application(callback: CallbackQuery, bot: Bot) -> None:
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("У тебя нет прав для этого действия.", show_alert=True)
        return

    user_id = int(callback.data.split("_")[1])
    app_data = storage.pending_applications.get(user_id, {})
    nickname = app_data.get("nickname", "неизвестный")

    # Добавляем в вайтлист через RCON
    rcon_ok = False
    try:
        response = await _rcon_whitelist_add(nickname)
        rcon_ok = True
        logger.info("RCON whitelist add %s: %s", nickname, response)
    except Exception:
        logger.exception("Ошибка RCON при добавлении %s в вайтлист", nickname)

    # Уведомляем пользователя
    if rcon_ok:
        user_text = (
            f"🎉 Поздравляем! Твоя заявка на Warden SMP одобрена.\n"
            f"Ник {nickname} добавлен в вайтлист — можешь заходить!"
        )
        admin_text = f"✅ Заявка одобрена, {nickname} добавлен в вайтлист."
    else:
        user_text = (
            f"🎉 Поздравляем! Твоя заявка на Warden SMP одобрена.\n"
            f"Ник {nickname} будет добавлен в вайтлист в ближайшее время."
        )
        admin_text = f"✅ Заявка одобрена, но RCON недоступен — добавь {nickname} вручную."

    try:
        await bot.send_message(user_id, user_text)
    except Exception:
        logger.exception("Не удалось отправить сообщение пользователю %d", user_id)

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(admin_text)
    await callback.answer("Заявка одобрена!")
    logger.info(
        "Заявка пользователя %d одобрена администратором %d",
        user_id,
        callback.from_user.id,
    )


@router.callback_query(F.data.startswith("reject_"))
async def reject_application(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("У тебя нет прав для этого действия.", show_alert=True)
        return

    user_id = int(callback.data.split("_")[1])
    await state.set_state(PanelStates.waiting_reject_reason)
    await state.update_data(reject_user_id=user_id)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        f"✏️ Укажи причину отказа для пользователя <code>{user_id}</code>:",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(PanelStates.waiting_reject_reason)
async def reject_with_reason(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.from_user.id != ADMIN_ID:
        return

    data = await state.get_data()
    user_id = data["reject_user_id"]
    reason = (message.text or "").strip()

    storage.rejected_users[user_id] = time.time()
    storage.submitted_users.discard(user_id)
    storage.pending_applications.pop(user_id, None)

    try:
        await bot.send_message(
            user_id,
            f"😔 Твоя заявка на Warden SMP отклонена.\n\n"
            f"<b>Причина:</b> {reason}\n\n"
            f"Повторно подать заявку можно через 24 часа.",
            parse_mode="HTML",
        )
    except Exception:
        logger.exception("Не удалось отправить сообщение пользователю %d", user_id)

    await state.clear()
    await message.answer(f"❌ Заявка пользователя {user_id} отклонена.\nПричина: {reason}")
    logger.info("Заявка пользователя %d отклонена, причина: %s", user_id, reason)
