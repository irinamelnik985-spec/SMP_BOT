import asyncio
import logging
import os
import re
from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

import storage
from config import ADMIN_ID, BACKUP_ROOT, RCON_HOST, RCON_PASS, RCON_PORT
from keyboards import (
    admin_panel_keyboard, admin_players_keyboard, admin_server_keyboard,
    broadcast_confirm_keyboard, main_keyboard,
)
from monitor import get_system_status
from rcon import rcon as rcon_cmd
from states import PanelStates

router = Router()
logger = logging.getLogger(__name__)

PANEL_TEXT = "🎛 <b>Админ-панель</b>\n\nВыбери действие:"


async def rcon(cmd: str) -> str:
    return await rcon_cmd(RCON_HOST, RCON_PASS, cmd, RCON_PORT)


def _strip_mc(text: str) -> str:
    return re.sub(r"§.", "", text)


def _parse_online(raw: str) -> str:
    clean = _strip_mc(raw)
    lines = [l.strip() for l in clean.strip().splitlines() if l.strip()]
    if not lines:
        return f"Не удалось распарсить ответ:\n{raw}"

    # Russian format: "Сейчас N из M игроков на сервере."
    m = re.search(r"Сейчас\s+(\d+)\s+из\s+(\d+)", lines[0])
    if not m:
        # English vanilla format
        m = re.search(r"There are (\d+) of a max of (\d+) players online[:\s]*(.*)", clean, re.IGNORECASE)
        if not m:
            return f"Не удалось распарсить ответ:\n{raw}"
        online, maxp = m.group(1), m.group(2)
        players = [n.strip() for n in m.group(3).split(",") if n.strip()]
        header = f"👥 <b>Онлайн: {online}/{maxp}</b>"
        if players:
            return f"{header}\n\n" + "\n".join(f"  • {p}" for p in players)
        return f"{header}\n\n<i>Никого нет онлайн</i>"

    online, maxp = m.group(1), m.group(2)
    header = f"👥 <b>Онлайн: {online}/{maxp}</b>"

    if online == "0":
        return f"{header}\n\n<i>Никого нет онлайн</i>"

    rows = []
    for line in lines[1:]:
        if ":" in line:
            group, names_part = line.split(":", 1)
            group = group.strip()
            for chunk in names_part.split(","):
                name_m = re.match(r"\s*(\w+)", chunk)
                if name_m:
                    rows.append(f"  • {name_m.group(1)} <i>({group})</i>")
        else:
            for chunk in line.split(","):
                name_m = re.match(r"\s*(\w+)", chunk)
                if name_m:
                    rows.append(f"  • {name_m.group(1)}")

    return (f"{header}\n\n" + "\n".join(rows)) if rows else f"{header}\n\n<i>Никого нет онлайн</i>"


def _parse_whitelist(raw: str) -> str:
    if re.search(r"no whitelisted players", raw, re.IGNORECASE):
        return "📋 <b>Вайтлист пуст</b>"
    match = re.search(r"There are (\d+) whitelisted players?[:\s]*(.*)", raw, re.IGNORECASE | re.DOTALL)
    if not match:
        return f"Не удалось распарсить ответ:\n{raw}"
    count, names_raw = match.group(1), match.group(2).strip()
    players = [n.strip() for n in names_raw.replace("\n", " ").split(",") if n.strip()]
    header = f"📋 <b>Вайтлист ({count} игр.):</b>"
    if players:
        return f"{header}\n\n" + "\n".join(f"  • {p}" for p in players)
    return header


def _parse_plugins(raw: str) -> str:
    match = re.search(r"Plugins?\s*\((\d+)\)[:\s]*(.*)", raw, re.IGNORECASE | re.DOTALL)
    if not match:
        if "unknown command" in raw.lower() or "incorrect argument" in raw.lower():
            return (
                "🔌 <b>Команда plugins недоступна</b>\n\n"
                "<i>Работает только на Bukkit/Spigot/Paper.\n"
                "На ванильном сервере список плагинов недоступен.</i>"
            )
        return f"Не удалось распарсить ответ:\n{raw}"
    count, names_raw = match.group(1), match.group(2).strip()
    plugins = []
    for chunk in names_raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        # §a/§2 = green = enabled, §c/§4 = red = disabled
        if re.match(r"§[ac24]", chunk):
            status = "✅" if chunk[1] in "a2" else "❌"
        else:
            status = "✅"
        name = _strip_mc(chunk).strip()
        if name:
            plugins.append(f"  • {status} {name}")
    header = f"🔌 <b>Плагины ({count}):</b>"
    if plugins:
        return f"{header}\n\n" + "\n".join(plugins)
    return header


def _is_admin(message: Message) -> bool:
    return message.from_user.id == ADMIN_ID


@router.message(F.text == "🎛 Админ-панель")
async def open_panel(message: Message, state: FSMContext) -> None:
    if not _is_admin(message):
        return
    await state.clear()
    await message.answer(PANEL_TEXT, reply_markup=admin_panel_keyboard(), parse_mode="HTML")


@router.message(F.text == "◀ Назад")
async def panel_back(message: Message, state: FSMContext) -> None:
    if not _is_admin(message):
        return
    await state.clear()
    await message.answer("Главное меню", reply_markup=main_keyboard(is_admin=True))


@router.message(F.text == "🔙 В панель")
async def panel_to_main(message: Message, state: FSMContext) -> None:
    if not _is_admin(message):
        return
    await state.clear()
    await message.answer(PANEL_TEXT, reply_markup=admin_panel_keyboard(), parse_mode="HTML")


@router.message(F.text == "👥 Игроки")
async def panel_players_tab(message: Message, state: FSMContext) -> None:
    if not _is_admin(message):
        return
    await state.clear()
    await message.answer("👥 <b>Игроки</b>", reply_markup=admin_players_keyboard(), parse_mode="HTML")


@router.message(F.text == "🖥 Сервер")
async def panel_server_tab(message: Message, state: FSMContext) -> None:
    if not _is_admin(message):
        return
    await state.clear()
    await message.answer("🖥 <b>Сервер</b>", reply_markup=admin_server_keyboard(), parse_mode="HTML")


@router.message(F.text == "📢 Рассылка")
async def panel_broadcast_start(message: Message, state: FSMContext) -> None:
    if not _is_admin(message):
        return
    await state.set_state(PanelStates.waiting_broadcast_text)
    await message.answer(
        f"📢 <b>Рассылка</b>\n\n"
        f"Получателей: <b>{len(storage.all_users)}</b>\n\n"
        f"Напиши текст сообщения. Отправь /cancel для отмены.",
        parse_mode="HTML",
    )


@router.message(PanelStates.waiting_broadcast_text)
async def panel_broadcast_text(message: Message, state: FSMContext) -> None:
    if not _is_admin(message):
        return
    if message.text and message.text.strip() == "/cancel":
        await state.clear()
        await message.answer(PANEL_TEXT, reply_markup=admin_panel_keyboard(), parse_mode="HTML")
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("Текст не может быть пустым.")
        return
    await state.update_data(broadcast_text=text)
    await message.answer(
        f"📋 <b>Превью сообщения:</b>\n\n{text}\n\n"
        f"Разослать <b>{len(storage.all_users)}</b> пользователям?",
        reply_markup=broadcast_confirm_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "broadcast_yes")
async def panel_broadcast_confirm(callback, state: FSMContext, bot) -> None:
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Нет прав.", show_alert=True)
        return
    data = await state.get_data()
    text = data.get("broadcast_text", "")
    await state.clear()
    await callback.message.edit_reply_markup(reply_markup=None)

    sent, failed = 0, 0
    for user_id in storage.all_users:
        try:
            await bot.send_message(user_id, text)
            sent += 1
        except Exception:
            failed += 1

    await callback.message.answer(
        f"✅ Рассылка завершена.\nОтправлено: {sent}, не доставлено: {failed}",
        reply_markup=admin_panel_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "broadcast_no")
async def panel_broadcast_cancel(callback, state: FSMContext) -> None:
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Нет прав.", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("Рассылка отменена.", reply_markup=admin_panel_keyboard())
    await callback.answer()


@router.message(F.text == "👥 Онлайн")
async def panel_online(message: Message) -> None:
    if not _is_admin(message):
        return
    try:
        raw = await rcon("list")
        text = _parse_online(raw)
    except Exception as e:
        text = f"❌ Ошибка RCON:\n<code>{e}</code>"
    await message.answer(text, parse_mode="HTML")


@router.message(F.text == "📋 Вайтлист")
async def panel_whitelist(message: Message) -> None:
    if not _is_admin(message):
        return
    try:
        raw = await rcon("whitelist list")
        text = _parse_whitelist(raw)
    except Exception as e:
        text = f"❌ Ошибка RCON:\n<code>{e}</code>"
    await message.answer(text, parse_mode="HTML")


@router.message(F.text == "🔌 Плагины")
async def panel_plugins(message: Message) -> None:
    if not _is_admin(message):
        return
    try:
        raw = await rcon("plugins")
        text = _parse_plugins(raw)
    except Exception as e:
        text = f"❌ Ошибка RCON:\n<code>{e}</code>"
    await message.answer(text, parse_mode="HTML")


def _fmt_size(n: int) -> str:
    if n >= 1024 ** 3:
        return f"{n / 1024 ** 3:.1f} GB"
    if n >= 1024 ** 2:
        return f"{n / 1024 ** 2:.0f} MB"
    return f"{n / 1024:.0f} KB"


def _dir_size(path: str) -> int:
    total = 0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            try:
                total += os.path.getsize(os.path.join(dirpath, f))
            except OSError:
                pass
    return total


def _read_backups() -> str:
    try:
        if not os.path.isdir(BACKUP_ROOT):
            return "💾 <b>Папка бэкапов не найдена</b>"

        entries = []
        for name in os.listdir(BACKUP_ROOT):
            path = os.path.join(BACKUP_ROOT, name)
            if name.endswith(".tar.gz"):
                try:
                    dt = datetime.strptime(name, "%Y-%m-%d_%H-%M.tar.gz")
                    entries.append((dt, os.path.getsize(path)))
                except ValueError:
                    pass
            elif os.path.isdir(path):
                try:
                    dt = datetime.strptime(name, "%Y-%m-%d_%H-%M")
                    entries.append((dt, _dir_size(path)))
                except ValueError:
                    pass

        if not entries:
            return "💾 <b>Бэкапов пока нет</b>"

        entries.sort(reverse=True)
        now = datetime.now()
        lines = []
        total = 0

        for i, (dt, size) in enumerate(entries, 1):
            total += size
            delta = int((now - dt).total_seconds())
            if delta < 3600:
                ago = f"{delta // 60} мин назад"
            elif delta < 86400:
                ago = f"{delta // 3600} ч назад"
            else:
                ago = f"{delta // 86400} д назад"
            lines.append(f"<b>{i}.</b> {dt.strftime('%d.%m %H:%M')} · {_fmt_size(size)} · <i>{ago}</i>")

        return (
            f"💾 <b>Бэкапы ({len(entries)} шт.)</b>\n\n"
            + "\n".join(lines)
            + f"\n\n📦 <b>Всего:</b> {_fmt_size(total)}"
        )
    except Exception as e:
        return f"❌ Ошибка:\n<code>{e}</code>"


@router.message(F.text == "📊 Статус системы")
async def panel_status(message: Message) -> None:
    if not _is_admin(message):
        return
    wait = await message.answer("⏳ Собираю данные...")
    text = await get_system_status()
    await wait.edit_text(text, parse_mode="HTML")


@router.message(F.text == "💾 Бэкапы")
async def panel_backups(message: Message) -> None:
    if not _is_admin(message):
        return
    text = await asyncio.to_thread(_read_backups)
    await message.answer(text, parse_mode="HTML")


@router.message(F.text == "💬 /me в чат")
async def panel_me_start(message: Message, state: FSMContext) -> None:
    if not _is_admin(message):
        return
    await state.set_state(PanelStates.waiting_me_text)
    await message.answer(
        "💬 <b>Отправить /me в чат</b>\n\n"
        "Напиши текст — он появится в игровом чате как:\n"
        "<code>* CONSOLE &lt;твой текст&gt;</code>\n\n"
        "Отправь /cancel для отмены.",
        parse_mode="HTML",
    )


@router.message(F.text == "➕ Добавить в вайтлист")
async def panel_wl_add_start(message: Message, state: FSMContext) -> None:
    if not _is_admin(message):
        return
    await state.set_state(PanelStates.waiting_wl_add)
    await message.answer("➕ Введи ник игрока для добавления в вайтлист.\n\nОтправь /cancel для отмены.")


@router.message(PanelStates.waiting_wl_add)
async def panel_wl_add_send(message: Message, state: FSMContext) -> None:
    if not _is_admin(message):
        return
    if message.text and message.text.strip() == "/cancel":
        await state.clear()
        await message.answer(PANEL_TEXT, reply_markup=admin_panel_keyboard(), parse_mode="HTML")
        return
    nick = (message.text or "").strip()
    if not re.match(r"^[a-zA-Z0-9_]{3,16}$", nick):
        await message.answer("Некорректный ник. Только латиница, цифры и _, 3–16 символов. Попробуй ещё раз или /cancel.")
        return
    try:
        raw = await rcon("whitelist list")
        import re as _re
        if _re.search(rf"\b{_re.escape(nick)}\b", raw, _re.IGNORECASE):
            await message.answer(f"⚠️ <b>{nick}</b> уже в вайтлисте.", parse_mode="HTML")
            await state.clear()
            return
        await rcon(f"whitelist add {nick}")
        await message.answer(f"✅ <b>{nick}</b> добавлен в вайтлист.", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Ошибка RCON:\n<code>{e}</code>", parse_mode="HTML")
    await state.clear()


@router.message(F.text == "➖ Убрать из вайтлиста")
async def panel_wl_remove_start(message: Message, state: FSMContext) -> None:
    if not _is_admin(message):
        return
    await state.set_state(PanelStates.waiting_wl_remove)
    await message.answer("➖ Введи ник игрока для удаления из вайтлиста.\n\nОтправь /cancel для отмены.")


@router.message(PanelStates.waiting_wl_remove)
async def panel_wl_remove_send(message: Message, state: FSMContext) -> None:
    if not _is_admin(message):
        return
    if message.text and message.text.strip() == "/cancel":
        await state.clear()
        await message.answer(PANEL_TEXT, reply_markup=admin_panel_keyboard(), parse_mode="HTML")
        return
    nick = (message.text or "").strip()
    if not re.match(r"^[a-zA-Z0-9_]{3,16}$", nick):
        await message.answer("Некорректный ник. Только латиница, цифры и _, 3–16 символов. Попробуй ещё раз или /cancel.")
        return
    try:
        raw = await rcon("whitelist list")
        import re as _re
        if not _re.search(rf"\b{_re.escape(nick)}\b", raw, _re.IGNORECASE):
            await message.answer(f"⚠️ <b>{nick}</b> нет в вайтлисте.", parse_mode="HTML")
            await state.clear()
            return
        await rcon(f"whitelist remove {nick}")
        await message.answer(f"✅ <b>{nick}</b> убран из вайтлиста.", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Ошибка RCON:\n<code>{e}</code>", parse_mode="HTML")
    await state.clear()


@router.message(PanelStates.waiting_me_text)
async def panel_me_send(message: Message, state: FSMContext) -> None:
    if not _is_admin(message):
        return
    if message.text and message.text.strip() == "/cancel":
        await state.clear()
        await message.answer(PANEL_TEXT, reply_markup=admin_panel_keyboard(), parse_mode="HTML")
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("Текст не может быть пустым. Попробуй ещё раз или отправь /cancel.")
        return
    try:
        await rcon(f"me {text}")
        await message.answer(
            f"✅ Отправлено:\n<code>* CONSOLE {text}</code>",
            parse_mode="HTML",
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка RCON:\n<code>{e}</code>", parse_mode="HTML")
    await state.clear()
