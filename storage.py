# Разделяемое in-memory хранилище между хэндлерами.
# При необходимости можно заменить на Redis/БД без изменения интерфейса.

# user_id пользователей, уже подавших заявку
submitted_users: set[int] = set()

# user_id -> данные анкеты (для получения никнейма при одобрении)
pending_applications: dict[int, dict] = {}

# user_id -> unix timestamp момента отказа
rejected_users: dict[int, float] = {}

# все пользователи, когда-либо запустившие бота (для рассылки)
all_users: set[int] = set()
