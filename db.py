import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "bot_data.db")


def init() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)"
        )


def add_user(user_id: int) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT OR IGNORE INTO users VALUES (?)", (user_id,))


def get_all_users() -> set[int]:
    with sqlite3.connect(DB_PATH) as conn:
        return {row[0] for row in conn.execute("SELECT user_id FROM users")}
