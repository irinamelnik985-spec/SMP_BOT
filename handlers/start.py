from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import db
import storage
from config import ADMIN_ID
from keyboards import confirm_restart_keyboard, main_keyboard, start_form_keyboard

router = Router()

WARNING_TEXT = (
    "⚠️ Внимание!\n\n"
    "Если тебе меньше 14 лет — ты не будешь допущен(а) на сервер.\n"
    "Если возраст окажется ложью — ты также потеряешь доступ навсегда.\n\n"
    "Готов(а)? Нажми кнопку ниже 👇"
)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    storage.all_users.add(message.from_user.id)
    db.add_user(message.from_user.id)
    is_admin = message.from_user.id == ADMIN_ID
    await message.answer(
        "Привет! Это бот вайтлиста Warden SMP.\n"
        "Нажми кнопку ниже, чтобы подать заявку.",
        reply_markup=main_keyboard(is_admin=is_admin),
    )


@router.message(F.text == "📋 Подать заявку на вайтлист")
async def apply_whitelist(message: Message, state: FSMContext) -> None:
    if message.from_user.id in storage.submitted_users:
        await message.answer(
            "Ты уже подавал(а) заявку ранее. Хочешь подать новую?",
            reply_markup=confirm_restart_keyboard(),
        )
        return

    await message.answer(WARNING_TEXT, reply_markup=start_form_keyboard())


@router.callback_query(F.data == "confirm_restart")
async def confirm_restart(callback: CallbackQuery, state: FSMContext) -> None:
    user_id = callback.from_user.id
    storage.submitted_users.discard(user_id)
    storage.pending_applications.pop(user_id, None)
    await callback.message.edit_text(WARNING_TEXT, reply_markup=start_form_keyboard())
    await callback.answer()


@router.callback_query(F.data == "cancel_restart")
async def cancel_restart(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "Окей, заявка не изменена. Если передумаешь — нажми кнопку снова."
    )
    await callback.answer()
