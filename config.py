import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
ADMIN_ID: int = int(os.getenv("ADMIN_ID", "0"))
RCON_HOST: str = os.getenv("RCON_HOST", "127.0.0.1")
RCON_PORT: int = int(os.getenv("RCON_PORT", "25575"))
RCON_PASS: str = os.getenv("RCON_PASS", "")
# WARP proxy: пусто = не использовать, иначе socks5://127.0.0.1:40000
PROXY_URL: str = os.getenv("PROXY_URL", "")
MC_LOG_PATH: str = os.getenv("MC_LOG_PATH", "/home/danya/minecraft/logs/latest.log")
BACKUP_ROOT: str = os.getenv("BACKUP_ROOT", "/home/danya/minecraft/minecraft_backups")
REVIEWS_GROUP_ID: int = int(os.getenv("REVIEWS_GROUP_ID", "0"))
CHATIK_TOPIC_ID: int = int(os.getenv("CHATIK_TOPIC_ID", "0"))

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан в .env файле")
if not ADMIN_ID:
    raise ValueError("ADMIN_ID не задан в .env файле")
