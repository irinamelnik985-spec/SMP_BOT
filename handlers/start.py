from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import db
import storage
from config import is_admin
from handlers.rules import RULES_PAGES, TOTAL, WARNING_TEXT, _page_header
from keyboards import confirm_restart_keyboard, main_keyboard, rules_keyboard, start_form_keyboard
from states import RulesStates

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    storage.all_users.add(message.from_user.id)
    db.add_user(message.from_user.id)
    admin_user = is_admin(message.from_user.id)
    await message.answer(
        "Привет! Это бот вайтлиста Warden SMP.\n"
        "Нажми кнопку ниже, чтобы подать заявку.",
        reply_markup=main_keyboard(is_admin=admin_user),
    )


@router.message(F.text == "📋 Подать заявку на вайтлист")
async def apply_whitelist(message: Message, state: FSMContext) -> None:
    if message.from_user.id in storage.submitted_users:
        await message.answer(
            "Ты уже подавал(а) заявку ранее. Хочешь подать новую?",
            reply_markup=confirm_restart_keyboard(),
        )
        return

    await state.set_state(RulesStates.reading)
    await state.update_data(page=0)
    await message.answer(
        _page_header(0) + RULES_PAGES[0],
        reply_markup=rules_keyboard(0, TOTAL),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "confirm_restart")
async def confirm_restart(callback: CallbackQuery, state: FSMContext) -> None:
    user_id = callback.from_user.id
    storage.submitted_users.discard(user_id)
    storage.pending_applications.pop(user_id, None)
    await state.set_state(RulesStates.reading)
    await state.update_data(page=0)
    await callback.message.edit_text(
        _page_header(0) + RULES_PAGES[0],
        reply_markup=rules_keyboard(0, TOTAL),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "cancel_restart")
async def cancel_restart(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "Окей, заявка не изменена. Если передумаешь — нажми кнопку снова."
    )
    await callback.answer()
