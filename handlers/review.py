import html
import logging
import time
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import db
from config import ADMIN_ID, REVIEWS_GROUP_ID, is_admin
from keyboards import (
    review_admin_keyboard,
    review_cancel_keyboard,
    review_edit_keyboard,
    review_rating_keyboard,
)
from states import ReviewStates

router = Router()
logger = logging.getLogger(__name__)

COOLDOWN = 3600  # секунд
STARS = {1: "⭐", 2: "⭐⭐", 3: "⭐⭐⭐", 4: "⭐⭐⭐⭐", 5: "⭐⭐⭐⭐⭐"}


def _fmt_cooldown(seconds: float) -> str:
    m, s = int(seconds // 60), int(seconds % 60)
    return f"{m} мин. {s} сек." if m else f"{s} сек."


def _created_at_ts(created_at: str) -> float:
    try:
        return datetime.fromisoformat(created_at).timestamp()
    except Exception:
        return 0.0


def _last_action_ts(created_at: str, edited_at) -> float:
    return edited_at if edited_at else _created_at_ts(created_at)


async def _is_member(bot: Bot, user_id: int) -> bool:
    if not REVIEWS_GROUP_ID:
        return True
    try:
        member = await bot.get_chat_member(chat_id=REVIEWS_GROUP_ID, user_id=user_id)
        return member.status not in ("left", "kicked", "banned")
    except Exception:
        return False


# ─── Написать / посмотреть отзыв ─────────────────────────────────────────────

@router.message(F.text == "⭐ Оставить отзыв")
async def review_open(message: Message, state: FSMContext, bot: Bot) -> None:
    user_id = message.from_user.id
    await state.clear()

    if not await _is_member(bot, user_id):
        await message.answer(
            "❌ Оставлять отзывы могут только участники нашей группы.\n"
            "Вступи и попробуй снова."
        )
        return

    row = db.get_user_review(user_id)

    if row is None:
        await state.set_state(ReviewStates.waiting_rating)
        await state.update_data(is_edit=False)
        await message.answer(
            "⭐ <b>Новый отзыв</b>\n\nОцени сервер:",
            reply_markup=review_rating_keyboard(),
            parse_mode="HTML",
        )
        return

    review_id, rating, text, created_at, edited_at = row
    time_left = COOLDOWN - (time.time() - _last_action_ts(created_at, edited_at))
    body = f"{STARS[rating]}\n\n{html.escape(text)}"

    if time_left > 0:
        await message.answer(
            f"📝 <b>Твой отзыв:</b>\n\n{body}\n\n"
            f"⏳ Редактирование доступно через <b>{_fmt_cooldown(time_left)}</b>",
            parse_mode="HTML",
        )
    else:
        await message.answer(
            f"📝 <b>Твой отзыв:</b>\n\n{body}",
            reply_markup=review_edit_keyboard(review_id),
            parse_mode="HTML",
        )


@router.callback_query(F.data.startswith("review_edit_"))
async def review_edit_start(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    user_id = callback.from_user.id

    if not await _is_member(bot, user_id):
        await callback.answer("Ты больше не в группе.", show_alert=True)
        return

    review_id = int(callback.data.split("_")[2])
    row = db.get_user_review(user_id)

    if row is None or row[0] != review_id:
        await callback.answer("Отзыв не найден.", show_alert=True)
        return

    _, _, _, created_at, edited_at = row
    time_left = COOLDOWN - (time.time() - _last_action_ts(created_at, edited_at))

    if time_left > 0:
        await callback.answer(
            f"Подожди ещё {_fmt_cooldown(time_left)}",
            show_alert=True,
        )
        return

    await state.set_state(ReviewStates.waiting_rating)
    await state.update_data(is_edit=True, review_id=review_id)
    await callback.message.edit_text(
        "✏️ <b>Редактирование отзыва</b>\n\nВыбери новую оценку:",
        reply_markup=review_rating_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "review_cancel")
async def review_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("Отзыв отменён.")
    await callback.answer()


@router.callback_query(ReviewStates.waiting_rating, F.data.startswith("review_rate_"))
async def review_rated(callback: CallbackQuery, state: FSMContext) -> None:
    rating = int(callback.data.split("_")[2])
    data = await state.get_data()
    await state.update_data(rating=rating)
    await state.set_state(ReviewStates.waiting_text)

    prefix = "✏️" if data.get("is_edit") else "⭐"
    await callback.message.edit_text(
        f"{prefix} <b>Оценка: {STARS[rating]}</b>\n\nТеперь напиши текст отзыва:",
        reply_markup=review_cancel_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(ReviewStates.waiting_text)
async def review_text_received(message: Message, state: FSMContext, bot: Bot) -> None:
    text = (message.text or "").strip()
    if len(text) < 10:
        await message.answer(
            "Слишком коротко. Напиши хотя бы 10 символов.",
            reply_markup=review_cancel_keyboard(),
        )
        return
    if len(text) > 2000:
        await message.answer(
            "Слишком длинно. Максимум 2000 символов.",
            reply_markup=review_cancel_keyboard(),
        )
        return

    data = await state.get_data()
    rating = data["rating"]
    is_edit = data.get("is_edit", False)
    user = message.from_user
    username = f"@{user.username}" if user.username else user.full_name
    now = time.time()

    if is_edit:
        review_id = data["review_id"]
        db.update_review(review_id, rating, text, now)
        label = "✅ Отзыв обновлён!"
        logger.info("Отзыв #%d обновлён user_id=%d rating=%d", review_id, user.id, rating)
    else:
        review_id = db.add_review(user.id, username, rating, text)
        label = "✅ Отзыв опубликован!"
        stars = STARS[rating]
        user_link = f'<a href="tg://user?id={user.id}">{html.escape(username)}</a>'
        admin_msg = (
            f"📝 <b>Новый отзыв</b> #{review_id}\n"
            f"От: {user_link} (<code>{user.id}</code>)\n"
            f"Оценка: {stars}\n\n"
            f"{html.escape(text)}"
        )
        try:
            await bot.send_message(
                ADMIN_ID, admin_msg,
                parse_mode="HTML",
                reply_markup=review_admin_keyboard(review_id),
            )
        except Exception as e:
            logger.warning("Не удалось отправить отзыв админу: %s", e)
        logger.info("Отзыв #%d от user_id=%d rating=%d", review_id, user.id, rating)

    await state.clear()
    await message.answer(
        f"{label}\n\n{STARS[rating]}\n\n{html.escape(text)}\n\n"
        f"<i>Следующее редактирование будет доступно через 1 час.</i>",
        parse_mode="HTML",
    )


# ─── Ответ админа ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("review_reply_"))
async def review_reply_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет прав.", show_alert=True)
        return
    review_id = int(callback.data.split("_")[2])
    row = db.get_review(review_id)
    if not row:
        await callback.answer("Отзыв не найден.", show_alert=True)
        return
    await state.set_state(ReviewStates.waiting_admin_reply)
    await state.update_data(review_id=review_id, user_id=row[1])
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(f"✏️ Напиши ответ на отзыв #{review_id}:")
    await callback.answer()


@router.message(ReviewStates.waiting_admin_reply)
async def review_reply_send(message: Message, state: FSMContext, bot: Bot) -> None:
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    review_id = data["review_id"]
    user_id = data["user_id"]
    reply_text = (message.text or "").strip()
    db.set_review_reply(review_id, reply_text)
    try:
        await bot.send_message(
            user_id,
            f"📩 <b>Админ ответил на твой отзыв #{review_id}:</b>\n\n{html.escape(reply_text)}",
            parse_mode="HTML",
        )
        await message.answer(f"✅ Ответ доставлен автору отзыва #{review_id}.")
    except Exception as e:
        await message.answer(f"❌ Не удалось доставить: {e}")
    await state.clear()
    logger.info("Админ ответил на отзыв #%d", review_id)


# ─── Листалка отзывов ─────────────────────────────────────────────────────────

def _format_review_page(rows: list, index: int, is_admin: bool) -> tuple[str, InlineKeyboardMarkup | None]:
    if not rows:
        return "📭 Отзывов пока нет.", None
    total = len(rows)
    index = max(0, min(index, total - 1))
    review_id, user_id, username, rating, text, created_at, admin_reply = rows[index]
    stars = STARS.get(rating, "⭐" * rating)
    try:
        date_str = datetime.fromisoformat(created_at).strftime("%d.%m.%Y %H:%M")
    except Exception:
        date_str = created_at

    safe_username = html.escape(username or "user")
    author = (
        f'<a href="tg://user?id={user_id}">{safe_username}</a> (<code>{user_id}</code>)'
        if is_admin else safe_username
    )
    body = (
        f"📝 <b>Отзыв #{review_id}</b>  ({index + 1}/{total})\n"
        f"От: {author}\n"
        f"Дата: {date_str}\n"
        f"Оценка: {stars}\n\n"
        f"{html.escape(text)}"
    )
    if admin_reply:
        body += f"\n\n💬 <b>Ответ админа:</b>\n{html.escape(admin_reply)}"

    nav = []
    if index > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"reviewnav_{index - 1}"))
    nav.append(InlineKeyboardButton(text=f"{index + 1}/{total}", callback_data="reviewnav_noop"))
    if index < total - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"reviewnav_{index + 1}"))

    kb_rows = [nav]
    if is_admin:
        admin_row = []
        if not admin_reply:
            admin_row.append(InlineKeyboardButton(
                text="💬 Ответить", callback_data=f"review_reply_{review_id}"
            ))
        admin_row.append(InlineKeyboardButton(
            text="🗑 Удалить", callback_data=f"reviewdel_{review_id}_{index}"
        ))
        kb_rows.append(admin_row)
    kb_rows.append([InlineKeyboardButton(text="❌ Закрыть", callback_data="reviewnav_close")])

    return body, InlineKeyboardMarkup(inline_keyboard=kb_rows)


@router.message(F.text == "📖 Отзывы")
async def reviews_list_open(message: Message) -> None:
    rows = db.list_reviews(limit=10000)
    admin_view = is_admin(message.from_user.id)
    body, kb = _format_review_page(rows, 0, admin_view)
    await message.answer(body, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)


@router.callback_query(F.data.startswith("reviewnav_"))
async def reviews_nav(callback: CallbackQuery) -> None:
    arg = callback.data.split("_", 1)[1]
    if arg == "noop":
        await callback.answer()
        return
    if arg == "close":
        await callback.message.delete()
        await callback.answer()
        return
    try:
        index = int(arg)
    except ValueError:
        await callback.answer()
        return
    rows = db.list_reviews(limit=10000)
    admin_view = is_admin(callback.from_user.id)
    body, kb = _format_review_page(rows, index, admin_view)
    try:
        await callback.message.edit_text(body, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("reviewdel_"))
async def reviews_delete(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Только админ.", show_alert=True)
        return
    parts = callback.data.split("_")
    review_id, index = int(parts[1]), int(parts[2])
    deleted = db.delete_review(review_id)
    await callback.answer("🗑 Удалён." if deleted else "Уже удалён.")
    rows = db.list_reviews(limit=10000)
    index = min(index, max(0, len(rows) - 1))
    body, kb = _format_review_page(rows, index, True)
    try:
        await callback.message.edit_text(body, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
    except Exception:
        pass
