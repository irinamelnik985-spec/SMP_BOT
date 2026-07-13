import html
import logging
import re
import time

from aiogram import Bot, F, Router
from aiogram.types import ChatPermissions, Message

from config import ADMIN_ID, ADMIN_IDS, REVIEWS_GROUP_ID, is_admin, is_owner

router = Router()
logger = logging.getLogger(__name__)

UNIT_SEC = {
    "с": 1, "сек": 1, "s": 1,
    "м": 60, "мин": 60, "минут": 60, "m": 60,
    "ч": 3600, "час": 3600, "часа": 3600, "часов": 3600, "h": 3600,
    "д": 86400, "дн": 86400, "день": 86400, "дня": 86400, "дней": 86400, "d": 86400,
    "нед": 604800, "недель": 604800, "неделя": 604800, "w": 604800,
    "год": 31536000, "года": 31536000, "лет": 31536000, "y": 31536000,
}
MAX_SECONDS = 366 * 86400
_DUR_RE = re.compile(r"^(\d+)\s*([a-zA-Zа-яА-Я]+)", re.UNICODE)
_CMD_RE = re.compile(r"^!(бан|мут|кик|размут|разбан|анмут|анбан)\b\s*(.*)$",
                     re.IGNORECASE | re.DOTALL)

MUTE_OFF = ChatPermissions(can_send_messages=False)
MUTE_ON = ChatPermissions(
    can_send_messages=True, can_send_audios=True, can_send_documents=True,
    can_send_photos=True, can_send_videos=True, can_send_video_notes=True,
    can_send_voice_notes=True, can_send_polls=True, can_send_other_messages=True,
    can_add_web_page_previews=True, can_invite_users=True,
)


def _human(sec):
    for div, label in ((604800, "нед."), (86400, "дн."), (3600, "ч."), (60, "мин."), (1, "сек.")):
        if sec >= div and sec % div == 0:
            return f"{sec // div} {label}"
    return f"{sec} сек."


def _parse_duration(text):
    # -> (seconds|None, human|None, reason, error|None)
    text = text.strip()
    m = _DUR_RE.match(text)
    if m:
        unit = m.group(2).lower()
        if unit not in UNIT_SEC:
            return None, None, text, f"не понял срок «{html.escape(m.group(0))}»"
        seconds = min(int(m.group(1)) * UNIT_SEC[unit], MAX_SECONDS)
        return seconds, _human(seconds), text[m.end():].strip(), None
    if re.match(r"^\d", text):
        return None, None, text, "не понял срок"
    return None, None, text, None


def _m_user(user):
    name = html.escape(user.full_name or str(user.id))
    return f'<a href="tg://user?id={user.id}">{name}</a>'


def _m_id(uid, name=None):
    return f'<a href="tg://user?id={uid}">{html.escape(name or str(uid))}</a>'


async def _is_chat_admin(bot, chat_id, user_id):
    try:
        m = await bot.get_chat_member(chat_id, user_id)
        return m.status in ("administrator", "creator")
    except Exception:
        return False


# returns (target_id, display, cleaned_args, reply_or_None) | (None, err_text, None, None)
async def _resolve(message, bot, args, args_start):
    r = message.reply_to_message
    if r and r.from_user:
        return r.from_user.id, _m_user(r.from_user), args, r
    text = message.text or ""
    for ent in (message.entities or []):
        if ent.offset < args_start:
            continue
        rel = ent.offset - args_start
        cleaned = (args[:rel] + args[rel + ent.length:]).strip()
        if ent.type == "text_mention" and ent.user:
            return ent.user.id, _m_user(ent.user), cleaned, None
        if ent.type == "mention":
            uname = text[ent.offset:ent.offset + ent.length]
            try:
                ch = await bot.get_chat(uname)
                return ch.id, _m_id(ch.id, getattr(ch, "full_name", None) or uname), cleaned, None
            except Exception:
                return None, f"Не нашёл {uname} — он должен был хоть раз писать в группу или боту.", None, None
    m = re.match(r"^(\d{5,})\b", args)
    if m:
        uid = int(m.group(1))
        rest = args[m.end():].strip()
        try:
            ch = await bot.get_chat(uid)
            return uid, _m_id(uid, getattr(ch, "full_name", None)), rest, None
        except Exception:
            return uid, _m_id(uid), rest, None
    return None, "↩️ Ответь на сообщение, или укажи @юзера / id.", None, None


@router.message(F.chat.type.in_({"group", "supergroup"}),
                F.text.regexp(r"^!(бан|мут|кик|размут|разбан|анмут|анбан)"))
async def moderate(message: Message, bot: Bot) -> None:
    if REVIEWS_GROUP_ID and message.chat.id != REVIEWS_GROUP_ID:
        return
    m = _CMD_RE.match(message.text or "")
    if not m:
        return
    cmd = m.group(1).lower()
    args = m.group(2)
    args_start = m.start(2)

    if not is_admin(message.from_user.id):
        await message.reply("❌ Модерировать могут только админы сервера.")
        return

    target_id, disp, cleaned, reply = await _resolve(message, bot, args, args_start)
    if target_id is None:
        await message.reply(disp)
        return
    if target_id == bot.id:
        await message.reply("Это я, бот. Себя не трогаем.")
        return
    if target_id == ADMIN_ID:
        await message.reply("👑 Владельца не трогаем.")
        return
    if target_id in ADMIN_IDS and not is_owner(message.from_user.id):
        await message.reply("⛔ Админов может мутить/банить только владелец.")
        return

    chat_id = message.chat.id
    thread = message.message_thread_id
    seconds, human, reason, err = _parse_duration((cleaned or "").strip())
    if err:
        await message.reply(
            f"⚠️ {err}.\n"
            "Примеры срока: <code>10м</code> <code>2ч</code> <code>3д</code> <code>1нед</code>. "
            "Или без срока — тогда навсегда.",
            parse_mode="HTML",
        )
        return
    reason = reason or "не указана"

    async def say(text):
        await bot.send_message(chat_id, text, parse_mode="HTML",
                               message_thread_id=thread, disable_web_page_preview=True)

    try:
        if cmd in ("размут", "анмут"):
            await bot.restrict_chat_member(chat_id, target_id, permissions=MUTE_ON)
            await say(f"🔊 {disp} размучен.")
            return
        if cmd in ("разбан", "анбан"):
            await bot.unban_chat_member(chat_id, target_id, only_if_banned=True)
            await say(f"✅ {disp} разбанен.")
            return

        if reply is not None:
            try:
                await reply.delete()
            except Exception:
                pass

        until = None
        srok = "навсегда"
        if seconds:
            until = int(time.time()) + max(seconds, 31)
            srok = human

        if cmd == "мут":
            await bot.restrict_chat_member(chat_id, target_id, permissions=MUTE_OFF, until_date=until)
            action = "🔇 <b>Мут</b>"
        elif cmd == "бан":
            await bot.ban_chat_member(chat_id, target_id, until_date=until)
            action = "🔨 <b>Бан</b>"
        elif cmd == "кик":
            await bot.ban_chat_member(chat_id, target_id)
            await bot.unban_chat_member(chat_id, target_id, only_if_banned=True)
            action = "👢 <b>Кик</b>"
            srok = "—"
        else:
            return

        await say(
            f"{action}\n"
            f"Кого: {disp}\n"
            f"Срок: {srok}\n"
            f"Причина: {html.escape(reason)}\n"
            f"Модератор: {_m_user(message.from_user)}"
        )
        logger.info("MOD %s by %s -> %s (%s) %s",
                    cmd, message.from_user.id, target_id, srok, reason)
    except Exception as e:
        logger.warning("Ошибка модерации %s: %s", cmd, e)
        es = str(e).lower()
        if "administrator" in es or "not enough rights" in es or "chat_admin" in es:
            await message.reply(
                "⚠️ У этого юзера стоит звезда администратора в Telegram — "
                "бота выше него нет, поэтому тронуть его невозможно.\n"
                "Сними ему звезду админа в группе, тогда бот сможет мутить/банить."
            )
        else:
            await message.reply(
                f"⚠️ Не вышло: {html.escape(str(e))}\n"
                "Проверь, что у бота есть права админа (бан/мут/удаление сообщений)."
            )
