import logging
import re
import time
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import storage
from config import ADMIN_ID, RCON_HOST, RCON_PASS, RCON_PORT
from keyboards import admin_keyboard, experience_keyboard, skip_keyboard
from rcon import rcon as rcon_cmd
from states import FormStates

COOLDOWN_SECONDS = 86400
MIN_LEN = 30
MAX_LEN = 200

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "start_form")
async def start_form(callback: CallbackQuery, state: FSMContext) -> None:
    user_id = callback.from_user.id
    if user_id in storage.rejected_users:
        elapsed = time.time() - storage.rejected_users[user_id]
        if elapsed < COOLDOWN_SECONDS:
            remaining = int((COOLDOWN_SECONDS - elapsed) / 3600) + 1
            await callback.answer(
                f"Повторная заявка доступна через {remaining} ч.", show_alert=True
            )
            return
        del storage.rejected_users[user_id]
    await state.set_state(FormStates.waiting_age)
    await callback.message.edit_text("1️⃣ Сколько тебе лет?")
    await callback.answer()


@router.message(FormStates.waiting_age)
async def process_age(message: Message, state: FSMContext) -> None:
    text = message.text.strip()

    if not text.isdigit():
        await message.answer("Пожалуйста, введи возраст цифрами.")
        return

    age = int(text)

    if age < 14:
        await message.answer(
            "😔 К сожалению, для участия в Warden SMP необходимо быть не младше 14 лет.\n"
            "До встречи!"
        )
        await state.clear()
        return

    if age > 100:
        await message.answer("Пожалуйста, введи реальный возраст.")
        return

    await state.update_data(age=age)
    await state.set_state(FormStates.waiting_nickname)
    await message.answer("2️⃣ Твой никнейм в Minecraft?")


@router.message(FormStates.waiting_playtime)
async def process_playtime(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Напиши хотя бы пару слов.")
        return
    await state.update_data(playtime=text)
    await state.set_state(FormStates.waiting_experience)
    await message.answer(
        "4️⃣ Есть ли опыт игры на подобных проектах?",
        reply_markup=experience_keyboard(),
    )


@router.message(FormStates.waiting_nickname)
async def process_nickname(message: Message, state: FSMContext) -> None:
    nickname = message.text.strip()

    if not nickname or not re.match(r"^[a-zA-Z0-9_]{3,16}$", nickname):
        await message.answer("Некорректный никнейм. Только латиница, цифры и _, от 3 до 16 символов. Попробуй ещё раз.")
        return

    try:
        wl_raw = await rcon_cmd(RCON_HOST, RCON_PASS, "whitelist list", RCON_PORT)
        if re.search(rf"\b{re.escape(nickname)}\b", wl_raw, re.IGNORECASE):
            await message.answer(
                f"❌ Ник <b>{nickname}</b> уже есть в вайтлисте.\n"
                f"Если это твой ник — обратись к администратору.",
                parse_mode="HTML",
            )
            return
    except Exception:
        pass

    await state.update_data(nickname=nickname)
    await state.set_state(FormStates.waiting_playtime)
    await message.answer("3️⃣ Как долго играешь в Minecraft?")


@router.callback_query(
    FormStates.waiting_experience,
    F.data.in_({"experience_yes", "experience_no"}),
)
async def process_experience_callback(
    callback: CallbackQuery, state: FSMContext
) -> None:
    experience = "есть" if callback.data == "experience_yes" else "нет"
    await state.update_data(experience=experience)
    await state.set_state(FormStates.waiting_plans)
    await callback.message.edit_text(
        "5️⃣ Чем конкретно планируешь заниматься? Строительство, PvP, торговля, фермы — расскажи подробнее."
    )
    await callback.answer()


@router.message(FormStates.waiting_experience)
async def process_experience_text(message: Message, state: FSMContext) -> None:
    text = message.text.strip().lower()
    if text in ("есть", "да", "yes", "y", "+"):
        experience = "есть"
    elif text in ("нет", "no", "n", "-"):
        experience = "нет"
    else:
        await message.answer(
            "Пожалуйста, выбери ответ с помощью кнопок или напиши «есть» / «нет».",
            reply_markup=experience_keyboard(),
        )
        return

    await state.update_data(experience=experience)
    await state.set_state(FormStates.waiting_plans)
    await message.answer(
        "5️⃣ Чем конкретно планируешь заниматься? Строительство, PvP, торговля, фермы — расскажи подробнее."
    )


@router.message(FormStates.waiting_plans)
async def process_plans(message: Message, state: FSMContext) -> None:
    text = message.text.strip() if message.text else ""
    if len(text) < MIN_LEN:
        await message.answer(f"Слишком коротко ({len(text)} симв.). Напиши хотя бы {MIN_LEN} символов.")
        return
    if len(text) > MAX_LEN:
        await message.answer(f"Слишком длинно ({len(text)} симв.). Уложись в {MAX_LEN} символов.")
        return
    await state.update_data(plans=text)
    await state.set_state(FormStates.waiting_source)
    await message.answer("6️⃣ Откуда узнал(а) о сервере?")


@router.message(FormStates.waiting_source)
async def process_source(message: Message, state: FSMContext, bot: Bot) -> None:
    text = message.text.strip() if message.text else ""
    if len(text) < 15:
        await message.answer(f"Слишком коротко ({len(text)} симв.). Напиши хотя бы 15 символов.")
        return
    if len(text) > MAX_LEN:
        await message.answer(f"Слишком длинно ({len(text)} симв.). Уложись в {MAX_LEN} символов.")
        return
    await state.update_data(source=text)
    data = await state.get_data()
    await _finalize_application(bot, message.from_user, data)
    await message.answer("✅ Заявка отправлена! Ожидай решения администратора.")
    await state.clear()


async def _finalize_application(bot: Bot, user, data: dict) -> None:
    storage.submitted_users.add(user.id)
    storage.pending_applications[user.id] = data
    await _send_to_admin(bot, user, data)


async def _send_to_admin(bot: Bot, user, data: dict) -> None:
    username = f"@{user.username}" if user.username else f"id{user.id}"
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    plans = data.get("plans") or "—"
    source = data.get("source") or "—"

    playtime = data.get("playtime") or "—"
    text = (
        f"📋 Новая заявка на вайтлист Warden SMP\n\n"
        f"👤 Пользователь: {username} (id: {user.id})\n\n"
        f"1️⃣ Возраст: {data['age']}\n"
        f"2️⃣ Никнейм: {data['nickname']}\n"
        f"3️⃣ Стаж в MC: {playtime}\n"
        f"4️⃣ Опыт на SMP: {data['experience']}\n"
        f"5️⃣ Планы: {plans}\n"
        f"6️⃣ Откуда узнал: {source}\n\n"
        f"🕐 {now}"
    )

    await bot.send_message(ADMIN_ID, text, reply_markup=admin_keyboard(user.id))
    logger.info("Заявка от пользователя %d отправлена администратору", user.id)
