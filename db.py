import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "bot_data.db")


def init() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)"
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                rating INTEGER NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                admin_reply TEXT,
                admin_replied_at TEXT,
                edited_at REAL
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                type TEXT NOT NULL,
                offender TEXT,
                text TEXT NOT NULL,
                media_count INTEGER DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'open',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                admin_reply TEXT,
                admin_replied_at TEXT
            )"""
        )
        try:
            conn.execute("ALTER TABLE reviews ADD COLUMN edited_at REAL")
        except Exception:
            pass


def add_user(user_id: int) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT OR IGNORE INTO users VALUES (?)", (user_id,))


def get_all_users() -> set[int]:
    with sqlite3.connect(DB_PATH) as conn:
        return {row[0] for row in conn.execute("SELECT user_id FROM users")}


def add_review(user_id: int, username: str | None, rating: int, text: str) -> int:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "INSERT INTO reviews (user_id, username, rating, text) VALUES (?, ?, ?, ?)",
            (user_id, username, rating, text),
        )
        return cur.lastrowid


def set_review_reply(review_id: int, reply: str) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE reviews SET admin_reply = ?, admin_replied_at = datetime('now') WHERE id = ?",
            (reply, review_id),
        )


def get_review(review_id: int) -> tuple | None:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT id, user_id, username, rating, text, created_at, admin_reply, admin_replied_at FROM reviews WHERE id = ?",
            (review_id,),
        ).fetchone()
        return row


def list_reviews(limit: int = 20) -> list[tuple]:
    with sqlite3.connect(DB_PATH) as conn:
        return list(conn.execute(
            "SELECT id, user_id, username, rating, text, created_at, admin_reply FROM reviews ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ))


def delete_review(review_id: int) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("DELETE FROM reviews WHERE id = ?", (review_id,))
        return cur.rowcount > 0


def get_user_review(user_id: int) -> tuple | None:
    """Возвращает (id, rating, text, created_at, edited_at) или None."""
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute(
            "SELECT id, rating, text, created_at, edited_at FROM reviews WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
            (user_id,),
        ).fetchone()


def update_review(review_id: int, rating: int, text: str, edited_at: float) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE reviews SET rating = ?, text = ?, edited_at = ? WHERE id = ?",
            (rating, text, edited_at, review_id),
        )


def add_ticket(user_id: int, username: str | None, ttype: str, offender: str | None, text: str, media_count: int = 0) -> int:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "INSERT INTO tickets (user_id, username, type, offender, text, media_count) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, username, ttype, offender, text, media_count),
        )
        return cur.lastrowid


def set_ticket_status(user_id: int, status: str, reply: str | None = None) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE tickets SET status = ?, "
            "admin_reply = COALESCE(?, admin_reply), "
            "admin_replied_at = CASE WHEN ? IS NOT NULL THEN datetime('now') ELSE admin_replied_at END "
            "WHERE id = (SELECT id FROM tickets WHERE user_id = ? AND status = 'open' ORDER BY created_at DESC LIMIT 1)",
            (status, reply, reply, user_id),
        )


def list_tickets(limit: int = 20) -> list[tuple]:
    with sqlite3.connect(DB_PATH) as conn:
        return list(conn.execute(
            "SELECT id, user_id, username, type, offender, text, media_count, status, created_at, admin_reply "
            "FROM tickets ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ))
