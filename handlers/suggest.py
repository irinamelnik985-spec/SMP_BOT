import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import ADMIN_ID, is_admin
from keyboards import suggest_admin_keyboard, suggest_cancel_keyboard, suggest_collect_keyboard
from states import SuggestStates

router = Router()
logger = logging.getLogger(__name__)

MAX_ITEMS = 10


# ─── Пользователь предлагает новость ──────────────────────────────────────────

@router.message(F.text == "📰 Предложить новость")
async def suggest_start(message: Message, state: FSMContext) -> None:
    await state.set_state(SuggestStates.collecting)
    await state.update_data(items=[])
    await message.answer(
        "📰 <b>Предложить новость</b>\n\n"
        "Пришли свою новость: текст, фото, видео, гиф или аудио. "
        "Можно несколькими сообщениями. Когда всё готово — нажми «Отправить».",
        parse_mode="HTML",
        reply_markup=suggest_cancel_keyboard(),
    )


@router.message(SuggestStates.collecting, F.text.lower().in_({"отмена", "/cancel"}))
async def suggest_cancel_text(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Предложка отменена.")


@router.callback_query(F.data == "suggest_cancel", SuggestStates.collecting)
async def suggest_cancel_cb(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("Предложка отменена.")
    await callback.answer()


@router.message(SuggestStates.collecting)
async def suggest_collect(message: Message, state: FSMContext) -> None:
    if not (message.text or message.photo or message.video or message.animation
            or message.audio or message.voice or message.document):
        await message.answer("Пришли текст или медиа (фото / видео / гиф / аудио).")
        return
    data = await state.get_data()
    items = data.get("items", [])
    if len(items) >= MAX_ITEMS:
        await message.answer("Достаточно, нажми «Отправить».")
        return
    items.append(message.message_id)
    await state.update_data(items=items)
    await message.answer(
        f"✅ Принято ({len(items)}). Отправь ещё или нажми «Отправить».",
        reply_markup=suggest_collect_keyboard(),
    )


@router.callback_query(F.data == "suggest_send", SuggestStates.collecting)
async def suggest_send(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    items = data.get("items", [])
    if not items:
        await callback.answer("Сначала пришли новость.", show_alert=True)
        return
    user = callback.from_user
    username = f"@{user.username}" if user.username else f"id{user.id}"
    await callback.message.edit_reply_markup(reply_markup=None)

    await bot.send_message(
        ADMIN_ID,
        f"📰 <b>Новая предложка</b>\nОт: {username} (id: <code>{user.id}</code>)",
        parse_mode="HTML",
    )
    # копируем контент как есть — copy_message тянет любой тип (текст/фото/видео/гиф/аудио)
    for mid in items:
        try:
            await bot.copy_message(chat_id=ADMIN_ID, from_chat_id=user.id, message_id=mid)
        except Exception:
            logger.warning("не удалось скопировать предложку msg %s от %s", mid, user.id)
    await bot.send_message(
        ADMIN_ID,
        f"👆 Предложка от {username}. Что делаем?",
        reply_markup=suggest_admin_keyboard(user.id),
    )

    await bot.send_message(user.id, "✅ Твоя новость отправлена на модерацию. Ожидай решения!")
    await state.clear()
    logger.info("Предложка от %d (%d вложений)", user.id, len(items))


# ─── Действия главного админа ─────────────────────────────────────────────────

@router.callback_query(F.data.startswith("sug_accept_"))
async def sug_accept(callback: CallbackQuery, bot: Bot) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет прав.", show_alert=True)
        return
    uid = int(callback.data.split("_")[2])
    try:
        await bot.send_message(
            uid,
            "🎉 <b>Твою новость приняли!</b>\n\nСкоро она появится в канале. "
            "Спасибо, что делишься!",
            parse_mode="HTML",
        )
    except Exception:
        pass
    await callback.message.edit_text("✅ Принято. Автору отправлен алерт. Публикуй в канал вручную.")
    await callback.answer("Принято")


@router.callback_query(F.data.startswith("sug_reject_"))
async def sug_reject(callback: CallbackQuery, bot: Bot) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет прав.", show_alert=True)
        return
    uid = int(callback.data.split("_")[2])
    try:
        await bot.send_message(
            uid,
            "❌ <b>Твою новость отклонили.</b>\n\nНе расстраивайся — попробуй предложить что-то ещё!",
            parse_mode="HTML",
        )
    except Exception:
        pass
    await callback.message.edit_text("❌ Отклонено. Автору отправлен алерт.")
    await callback.answer("Отклонено")


@router.callback_query(F.data.startswith("sug_reply_"))
async def sug_reply_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет прав.", show_alert=True)
        return
    uid = int(callback.data.split("_")[2])
    await state.set_state(SuggestStates.waiting_reply)
    await state.update_data(reply_to=uid)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        f"✏️ Напиши ответ автору предложки (id <code>{uid}</code>):", parse_mode="HTML"
    )
    await callback.answer()


@router.message(SuggestStates.waiting_reply)
async def sug_reply_send(message: Message, state: FSMContext, bot: Bot) -> None:
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    uid = data["reply_to"]
    text = (message.text or "").strip()
    try:
        await bot.send_message(
            uid, f"📩 <b>Ответ по твоей новости:</b>\n\n{text}", parse_mode="HTML"
        )
        await message.answer(f"✅ Ответ отправлен автору {uid}.")
    except Exception:
        await message.answer(f"❌ Не удалось отправить сообщение {uid}.")
    await state.clear()
    logger.info("Админ ответил автору предложки %d", uid)
