import logging
import re

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InputMediaPhoto, Message

import storage
from config import ADMIN_ID, RCON_HOST, RCON_PASS, RCON_PORT
from keyboards import (
    ticket_admin_keyboard,
    ticket_cancel_keyboard,
    ticket_photo_skip_keyboard,
    ticket_photos_done_keyboard,
    ticket_type_keyboard,
)
from rcon import rcon as rcon_cmd
from states import TicketStates

router = Router()
logger = logging.getLogger(__name__)

MAX_PHOTOS = 6


@router.message(F.text == "📢 Жалоба / Вопрос")
async def ticket_start(message: Message, state: FSMContext) -> None:
    await state.set_state(TicketStates.choosing_type)
    await message.answer("Выбери тип обращения:", reply_markup=ticket_type_keyboard())


@router.callback_query(F.data == "ticket_cancel")
async def ticket_cancel_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("Отменено.")
    await callback.answer()


@router.message(
    StateFilter(
        TicketStates.waiting_offender,
        TicketStates.waiting_complaint_text,
        TicketStates.waiting_complaint_photo,
        TicketStates.waiting_question_text,
        TicketStates.waiting_question_photo,
    ),
    F.text.lower().in_({"отмена", "/cancel"}),
)
async def ticket_cancel_text(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Обращение отменено.")


# ─── Жалоба ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "ticket_complaint", TicketStates.choosing_type)
async def ticket_complaint(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(ticket_type="complaint")
    await state.set_state(TicketStates.waiting_offender)
    await callback.message.edit_text(
        "Введи ник нарушителя:\n\n<i>Напиши «Отмена» чтобы прервать.</i>",
        parse_mode="HTML",
        reply_markup=ticket_cancel_keyboard(),
    )
    await callback.answer()


@router.message(TicketStates.waiting_offender)
async def process_offender(message: Message, state: FSMContext) -> None:
    nickname = (message.text or "").strip()
    if not re.match(r"^[a-zA-Z0-9_]{3,16}$", nickname):
        await message.answer("Некорректный ник. Только латиница, цифры и _, от 3 до 16 символов.")
        return
    try:
        wl_raw = await rcon_cmd(RCON_HOST, RCON_PASS, "whitelist list", RCON_PORT)
        if not re.search(rf"\b{re.escape(nickname)}\b", wl_raw, re.IGNORECASE):
            await message.answer(
                f"❌ Игрок <b>{nickname}</b> не найден в вайтлисте. Проверь ник и попробуй снова.",
                parse_mode="HTML",
            )
            return
    except Exception:
        pass
    await state.update_data(offender=nickname)
    await state.set_state(TicketStates.waiting_complaint_text)
    await message.answer(
        f"Ник <b>{nickname}</b> найден. Опиши нарушение подробно — что случилось, когда, при каких обстоятельствах:\n\n"
        f"<i>Напиши «Отмена» чтобы прервать.</i>",
        parse_mode="HTML",
        reply_markup=ticket_cancel_keyboard(),
    )


@router.message(TicketStates.waiting_complaint_text)
async def process_complaint_text(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if len(text) < 20:
        await message.answer("Слишком коротко. Опиши подробнее (минимум 20 символов).")
        return
    await state.update_data(complaint_text=text, complaint_photos=[])
    await state.set_state(TicketStates.waiting_complaint_photo)
    await message.answer(
        "📸 Прикрепи скриншоты нарушения.\n"
        "Максимум 6 фото, только фото — не файлы.\n"
        "Когда отправишь все — нажми кнопку «Отправить».\n\n"
        "<i>Напиши «Отмена» чтобы прервать.</i>",
        parse_mode="HTML",
        reply_markup=ticket_cancel_keyboard(),
    )


@router.message(TicketStates.waiting_complaint_photo)
async def process_complaint_photo(message: Message, state: FSMContext, bot: Bot) -> None:
    if not message.photo:
        await message.answer("❌ Нужно именно фото, не файл и не текст.")
        return

    data = await state.get_data()
    photos: list = data.get("complaint_photos", [])
    photos.append(message.photo[-1].file_id)
    await state.update_data(complaint_photos=photos)

    count = len(photos)
    if count >= MAX_PHOTOS:
        await _send_complaint(message, state, bot)
        return

    await message.answer(
        f"✅ Скриншот {count}/6 принят. Отправь ещё или нажми «Отправить».",
        reply_markup=ticket_photos_done_keyboard(count),
    )


@router.callback_query(F.data == "ticket_photos_done", TicketStates.waiting_complaint_photo)
async def complaint_photos_done(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    if not data.get("complaint_photos"):
        await callback.answer("Сначала отправь хотя бы один скриншот.", show_alert=True)
        return
    await callback.message.edit_reply_markup(reply_markup=None)
    await _send_complaint(callback.message, state, bot, user=callback.from_user)
    await callback.answer()


async def _send_complaint(message: Message, state: FSMContext, bot: Bot, user=None) -> None:
    if user is None:
        user = message.from_user
    data = await state.get_data()
    offender = data.get("offender", "?")
    text = data.get("complaint_text", "")
    photos: list = data.get("complaint_photos", [])
    username = f"@{user.username}" if user.username else f"id{user.id}"

    storage.pending_tickets[user.id] = {"type": "complaint", "offender": offender, "text": text}

    caption = (
        f"🚨 <b>Жалоба на игрока</b>\n\n"
        f"👤 От: {username} (id: {user.id})\n"
        f"🎯 Нарушитель: <b>{offender}</b>\n\n"
        f"📝 {text}"
    )

    if len(photos) == 1:
        await bot.send_photo(
            ADMIN_ID,
            photo=photos[0],
            caption=caption,
            parse_mode="HTML",
            reply_markup=ticket_admin_keyboard(user.id, "complaint"),
        )
    else:
        media = [InputMediaPhoto(media=photos[0], caption=caption, parse_mode="HTML")]
        media += [InputMediaPhoto(media=fid) for fid in photos[1:]]
        await bot.send_media_group(ADMIN_ID, media=media)
        await bot.send_message(
            ADMIN_ID,
            f"👆 Жалоба выше ({len(photos)} скрина)",
            reply_markup=ticket_admin_keyboard(user.id, "complaint"),
        )

    await bot.send_message(user.id, "✅ Жалоба со скриншотами отправлена администратору. Ожидай ответа.")
    await state.clear()
    logger.info("Жалоба от %d на %s (%d фото)", user.id, offender, len(photos))


# ─── Вопрос ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "ticket_question", TicketStates.choosing_type)
async def ticket_question(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(ticket_type="question")
    await state.set_state(TicketStates.waiting_question_text)
    await callback.message.edit_text(
        "Напиши свой вопрос:\n\n<i>Напиши «Отмена» чтобы прервать.</i>",
        parse_mode="HTML",
        reply_markup=ticket_cancel_keyboard(),
    )
    await callback.answer()


@router.message(TicketStates.waiting_question_text)
async def process_question_text(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if len(text) < 10:
        await message.answer("Слишком коротко. Напиши подробнее.")
        return
    await state.update_data(question_text=text, question_photos=[])
    await state.set_state(TicketStates.waiting_question_photo)
    await message.answer(
        "📎 Хочешь прикрепить скриншоты? Это необязательно.\n"
        "Максимум 6 фото, только фото — не файлы.\n"
        "Когда отправишь все — нажми «Отправить». Или пропусти.\n\n"
        "<i>Напиши «Отмена» чтобы прервать.</i>",
        parse_mode="HTML",
        reply_markup=ticket_photo_skip_keyboard(),
    )


@router.callback_query(F.data == "ticket_photo_skip", TicketStates.waiting_question_photo)
async def question_photo_skip(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await callback.message.edit_reply_markup(reply_markup=None)
    await _send_question(bot, state, user=callback.from_user, photos=[])
    await callback.answer()


@router.callback_query(F.data == "ticket_photos_done", TicketStates.waiting_question_photo)
async def question_photos_done(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    if not data.get("question_photos"):
        await callback.answer("Сначала отправь хотя бы один скриншот.", show_alert=True)
        return
    await callback.message.edit_reply_markup(reply_markup=None)
    await _send_question(bot, state, user=callback.from_user, photos=data["question_photos"])
    await callback.answer()


@router.message(TicketStates.waiting_question_photo)
async def process_question_photo(message: Message, state: FSMContext, bot: Bot) -> None:
    if not message.photo:
        await message.answer("❌ Нужно фото, не файл. Или нажми «Пропустить».")
        return

    data = await state.get_data()
    photos: list = data.get("question_photos", [])
    photos.append(message.photo[-1].file_id)
    await state.update_data(question_photos=photos)

    count = len(photos)
    if count >= MAX_PHOTOS:
        await _send_question(bot, state, user=message.from_user, photos=photos)
        return

    await message.answer(
        f"✅ Скриншот {count}/6 принят. Отправь ещё или нажми «Отправить».",
        reply_markup=ticket_photos_done_keyboard(count),
    )


async def _send_question(bot: Bot, state: FSMContext, user, photos: list) -> None:
    data = await state.get_data()
    text = data.get("question_text", "")
    username = f"@{user.username}" if user.username else f"id{user.id}"

    storage.pending_tickets[user.id] = {"type": "question", "text": text}

    msg_text = (
        f"❓ <b>Вопрос администратору</b>\n\n"
        f"👤 От: {username} (id: {user.id})\n\n"
        f"📝 {text}"
    )

    if not photos:
        await bot.send_message(ADMIN_ID, msg_text, parse_mode="HTML",
                               reply_markup=ticket_admin_keyboard(user.id, "question"))
    elif len(photos) == 1:
        await bot.send_photo(ADMIN_ID, photo=photos[0], caption=msg_text, parse_mode="HTML",
                             reply_markup=ticket_admin_keyboard(user.id, "question"))
    else:
        media = [InputMediaPhoto(media=photos[0], caption=msg_text, parse_mode="HTML")]
        media += [InputMediaPhoto(media=fid) for fid in photos[1:]]
        await bot.send_media_group(ADMIN_ID, media=media)
        await bot.send_message(ADMIN_ID, f"👆 Вопрос выше ({len(photos)} скрина)",
                               reply_markup=ticket_admin_keyboard(user.id, "question"))

    await bot.send_message(user.id, "✅ Вопрос отправлен администратору. Ожидай ответа.")
    await state.clear()
    logger.info("Вопрос от %d", user.id)


# ─── Действия админа ──────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("ticket_decline_"))
async def ticket_decline(callback: CallbackQuery, bot: Bot) -> None:
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Нет прав.", show_alert=True)
        return
    user_id = int(callback.data.split("_")[2])
    try:
        await bot.send_message(
            user_id,
            "❌ <b>Твоё обращение отклонено.</b>\n\nАдминистрация рассмотрела его и не нашла оснований для принятия мер.",
            parse_mode="HTML",
        )
    except Exception:
        pass
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(f"❌ Обращение пользователя {user_id} отклонено.")
    await callback.answer()


@router.callback_query(F.data.startswith("ticket_ack_"))
async def ticket_ack(callback: CallbackQuery) -> None:
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Нет прав.", show_alert=True)
        return
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("✅ Обращение принято к сведению.")
    await callback.answer()


@router.callback_query(F.data.startswith("ticket_reply_"))
async def ticket_reply_start(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Нет прав.", show_alert=True)
        return
    user_id = int(callback.data.split("_")[2])
    await state.set_state(TicketStates.waiting_reply_text)
    await state.update_data(reply_to=user_id)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        f"✏️ Напиши ответ для пользователя <code>{user_id}</code>:", parse_mode="HTML"
    )
    await callback.answer()


@router.message(TicketStates.waiting_reply_text)
async def ticket_reply_send(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.from_user.id != ADMIN_ID:
        return
    data = await state.get_data()
    user_id = data["reply_to"]
    reply_text = (message.text or "").strip()
    try:
        await bot.send_message(
            user_id,
            f"📩 <b>Ответ администратора:</b>\n\n{reply_text}",
            parse_mode="HTML",
        )
        await message.answer(f"✅ Ответ отправлен пользователю {user_id}.")
    except Exception:
        await message.answer(f"❌ Не удалось отправить сообщение пользователю {user_id}.")
    await state.clear()
    logger.info("Администратор ответил пользователю %d", user_id)
