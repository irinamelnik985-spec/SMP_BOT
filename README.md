# Warden SMP — Whitelist Bot

Telegram-бот для управления вайтлистом Minecraft-сервера. Принимает заявки от игроков, даёт администратору инструменты для модерации и следит за состоянием сервера.

## Возможности

**Для игроков**
- Обязательное чтение правил сервера (9 страниц) перед подачей заявки
- Подача заявки на вайтлист через пошаговую форму (ник, возраст, планы, откуда узнал, сколько играешь)
- Проверка ника через RCON — нельзя подать заявку с уже вайтлистнутым ником
- Запрет повторной подачи в течение 24 часов после отказа

**Для администратора**
- Одобрение/отклонение заявок с обязательным указанием причины отказа
- Автоматическое добавление ника в вайтлист через RCON при одобрении
- Рассылка сообщений всем пользователям бота
- Листинг бэкапов сервера
- Статус системы: CPU, RAM, диск, аптайм, TPS сервера, частота процессора
- Уведомления о заходе/выходе игроков в реальном времени
- Уведомления о падении сервера с определением возможной причины (OOM, сбой питания, нет интернета)

## Структура

```
├── bot.py               # точка входа
├── config.py            # конфиг из .env
├── db.py                # SQLite — хранение пользователей
├── storage.py           # in-memory состояние
├── states.py            # FSM-состояния
├── keyboards.py         # клавиатуры
├── rcon.py              # RCON-клиент
├── monitor.py           # мониторинг сервера и лога
├── handlers/
│   ├── start.py         # /start, кнопка заявки
│   ├── rules.py         # пролистывание правил перед анкетой
│   ├── form.py          # форма заявки
│   ├── admin.py         # одобрение/отклонение
│   └── panel.py         # админ-панель
├── start_all.sh         # запуск сервера + бота + бэкапов
├── .env.example         # шаблон переменных окружения
└── requirements.txt
```

## Установка

**1. Клонировать репозиторий**
```bash
git clone https://github.com/irinamelnik985-spec/SMP_BOT.git
cd SMP_BOT
```

**2. Создать виртуальное окружение и установить зависимости**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**3. Создать `.env` на основе примера**
```bash
cp .env.example .env
```
Заполнить `.env`:
```
BOT_TOKEN=токен_от_BotFather
ADMIN_ID=твой_telegram_id
RCON_HOST=127.0.0.1
RCON_PORT=25575
RCON_PASS=пароль_rcon
PROXY_URL=                         # socks5://127.0.0.1:40000 если нужен прокси
MC_LOG_PATH=/path/to/minecraft/logs/latest.log
BACKUP_ROOT=/path/to/minecraft_backups
```

**4. Запустить**
```bash
python bot.py
```

Или через systemd (рекомендуется):
```bash
sudo systemctl enable --now whitelist-bot.service
```

## Запуск сервера

Скрипт `start_all.sh` запускает всё разом: оптимизации системы, бэкап-цикл, бот через systemd, сам Minecraft-сервер с автоперезапуском при краше.

Скопируй и настрой под себя:
```bash
cp start_all.sh.example start_all.sh
# отредактируй SERVER_DIR, RCON_PASS, пути к venv
bash start_all.sh
```

Бэкапы создаются каждые 40 минут в виде `.tar.gz`, хранятся последние 15 штук (~10 часов отката).

## Зависимости

- Python 3.11+
- [aiogram](https://github.com/aiogram/aiogram) 3.x
- [psutil](https://github.com/giampaolo/psutil)
- [python-dotenv](https://github.com/theskumar/python-dotenv)
- [aiohttp-socks](https://github.com/romis2012/aiohttp-socks) — для Tor/SOCKS5 прокси
- [rconclt](https://github.com/n0la/rconclt) — RCON-клиент (устанавливается отдельно)
