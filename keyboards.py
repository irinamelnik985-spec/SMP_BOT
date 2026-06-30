from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)


def main_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="📋 Подать заявку на вайтлист")],
        [KeyboardButton(text="📢 Жалоба / Вопрос")],
        [KeyboardButton(text="⭐ Оставить отзыв"), KeyboardButton(text="📖 Отзывы")],
    ]
    if is_admin:
        buttons.append([KeyboardButton(text="🎛 Админ-панель")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def admin_panel_keyboard(is_owner: bool = False) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text="👥 Игроки"), KeyboardButton(text="🖥 Сервер")]]
    if is_owner:
        rows.append([KeyboardButton(text="📢 Рассылка")])  # только главный
    rows.append([KeyboardButton(text="◀ Назад")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def admin_players_keyboard(is_owner: bool = False) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text="👥 Онлайн")]]
    if is_owner:  # управление вайтлистом — только главный
        rows[0].append(KeyboardButton(text="📋 Вайтлист"))
        rows.append([KeyboardButton(text="➕ Добавить в вайтлист"), KeyboardButton(text="➖ Убрать из вайтлиста")])
    rows.append([KeyboardButton(text="🔙 В панель")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


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


def rules_keyboard(page: int, total: int) -> InlineKeyboardMarkup:
    row = []
    if page > 0:
        row.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"rules_{page - 1}"))
    if page < total - 1:
        row.append(InlineKeyboardButton(text="Далее ▶️", callback_data=f"rules_{page + 1}"))
    else:
        row.append(InlineKeyboardButton(text="📋 Заполнить анкету", callback_data="rules_done"))
    return InlineKeyboardMarkup(inline_keyboard=[row])


def ticket_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Отменить обращение", callback_data="ticket_cancel")]]
    )


def ticket_photo_skip_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Пропустить ➡️", callback_data="ticket_photo_skip")],
            [InlineKeyboardButton(text="❌ Отменить обращение", callback_data="ticket_cancel")],
        ]
    )


def ticket_photos_done_keyboard(count: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"✅ Отправить ({count}/6)", callback_data="ticket_photos_done")],
            [InlineKeyboardButton(text="❌ Отменить обращение", callback_data="ticket_cancel")],
        ]
    )


def ticket_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚨 Жалоба на игрока", callback_data="ticket_complaint")],
            [InlineKeyboardButton(text="❓ Вопрос администратору", callback_data="ticket_question")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="ticket_cancel")],
        ]
    )


def ticket_admin_keyboard(user_id: int, ticket_type: str) -> InlineKeyboardMarkup:
    if ticket_type == "complaint":
        rows = [
            [
                InlineKeyboardButton(text="✅ Принято", callback_data=f"ticket_ack_{user_id}"),
                InlineKeyboardButton(text="💬 Ответить", callback_data=f"ticket_reply_{user_id}"),
            ],
            [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"ticket_decline_{user_id}")],
        ]
    else:
        rows = [[
            InlineKeyboardButton(text="💬 Ответить", callback_data=f"ticket_reply_{user_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"ticket_decline_{user_id}"),
        ]]
    return InlineKeyboardMarkup(inline_keyboard=rows)


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

def review_rating_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐", callback_data="review_rate_1"),
            InlineKeyboardButton(text="⭐⭐", callback_data="review_rate_2"),
            InlineKeyboardButton(text="⭐⭐⭐", callback_data="review_rate_3"),
        ],
        [
            InlineKeyboardButton(text="⭐⭐⭐⭐", callback_data="review_rate_4"),
            InlineKeyboardButton(text="⭐⭐⭐⭐⭐", callback_data="review_rate_5"),
        ],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="review_cancel")],
    ])


def review_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Отменить", callback_data="review_cancel")
    ]])


def review_edit_keyboard(review_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"review_edit_{review_id}"),
    ]])


def review_admin_keyboard(review_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💬 Ответить", callback_data=f"review_reply_{review_id}"),
    ]])

