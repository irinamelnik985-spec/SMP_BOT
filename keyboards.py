from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)


def main_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    buttons = [[KeyboardButton(text="📋 Подать заявку на вайтлист")]]
    if is_admin:
        buttons.append([KeyboardButton(text="🎛 Админ-панель")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def admin_panel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👥 Игроки"), KeyboardButton(text="🖥 Сервер")],
            [KeyboardButton(text="📢 Рассылка")],
            [KeyboardButton(text="◀ Назад")],
        ],
        resize_keyboard=True,
    )


def admin_players_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👥 Онлайн"), KeyboardButton(text="📋 Вайтлист")],
            [KeyboardButton(text="➕ Добавить в вайтлист"), KeyboardButton(text="➖ Убрать из вайтлиста")],
            [KeyboardButton(text="🔙 В панель")],
        ],
        resize_keyboard=True,
    )


def admin_server_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Статус системы"), KeyboardButton(text="💾 Бэкапы")],
            [KeyboardButton(text="🔌 Плагины"), KeyboardButton(text="💬 /me в чат")],
            [KeyboardButton(text="🔙 В панель")],
        ],
        resize_keyboard=True,
    )


def broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="✅ Да, разослать", callback_data="broadcast_yes"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="broadcast_no"),
        ]]
    )


def start_form_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Начать!", callback_data="start_form")]
        ]
    )


def skip_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Пропустить ⏭", callback_data="skip")]
        ]
    )


def experience_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Есть", callback_data="experience_yes"),
                InlineKeyboardButton(text="❌ Нет", callback_data="experience_no"),
            ]
        ]
    )


def admin_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Принять", callback_data=f"approve_{user_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить", callback_data=f"reject_{user_id}"
                ),
            ]
        ]
    )


def confirm_restart_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, подать новую", callback_data="confirm_restart"
                ),
                InlineKeyboardButton(
                    text="❌ Нет, отмена", callback_data="cancel_restart"
                ),
            ]
        ]
    )
