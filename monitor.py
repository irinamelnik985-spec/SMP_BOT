import asyncio
import logging
import os
import re
import socket
import subprocess
import time

import psutil
from aiogram import Bot

from config import ADMIN_ID, MC_LOG_PATH, RCON_HOST, RCON_PASS, RCON_PORT
from rcon import rcon as rcon_cmd

logger = logging.getLogger(__name__)

_server_was_up: bool | None = None  # None = состояние ещё не определено
CHECK_INTERVAL = 30  # секунд


async def _rcon_ping() -> bool:
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(RCON_HOST, RCON_PORT), timeout=3
        )
        writer.close()
        await writer.wait_closed()
        return True
    except Exception:
        return False


def _check_internet() -> bool:
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        return True
    except OSError:
        return False


def _detect_crash_reason() -> str:
    reasons = []

    # Недавняя перезагрузка системы — возможен сбой питания
    uptime_sec = time.time() - psutil.boot_time()
    if uptime_sec < 600:
        minutes = int(uptime_sec // 60)
        reasons.append(f"🔌 Система перезагрузилась {minutes} мин. назад — возможен сбой питания")

    # OOM killer убил java-процесс
    try:
        result = subprocess.run(
            ["dmesg", "--ctime"],
            capture_output=True, text=True, timeout=5,
        )
        lines = result.stdout.lower().splitlines()
        for line in reversed(lines[-300:]):
            if "out of memory" in line or ("killed process" in line and "java" in line):
                reasons.append("💾 OOM: сервер убит из-за нехватки оперативной памяти")
                break
    except Exception:
        pass

    # Интернет
    if not _check_internet():
        reasons.append("🌐 Нет подключения к интернету")

    if not reasons:
        reasons.append("❓ Причина неизвестна — возможен краш или ручная остановка")

    return "\n".join(f"  • {r}" for r in reasons)


def _get_cpu_freq() -> str:
    try:
        freqs = []
        for path in sorted(
            f"/sys/devices/system/cpu/cpu{i}/cpufreq/scaling_cur_freq"
            for i in range(os.cpu_count() or 1)
        ):
            try:
                with open(path) as f:
                    freqs.append(int(f.read().strip()))
            except OSError:
                pass
        if freqs:
            avg_mhz = sum(freqs) / len(freqs) / 1000
            return f"{avg_mhz:.0f} МГц"
    except Exception:
        pass
    try:
        with open("/proc/cpuinfo") as f:
            vals = re.findall(r"cpu MHz\s*:\s*([\d.]+)", f.read())
        if vals:
            avg = sum(float(v) for v in vals) / len(vals)
            return f"{avg:.0f} МГц"
    except Exception:
        pass
    return "—"


def _parse_tps(raw: str) -> str:
    clean = re.sub(r"§.", "", raw)
    after_colon = re.search(r":\s*(.+)$", clean.strip())
    if not after_colon:
        return "—"
    vals = re.sub(r"(\d),(\d)", r"\1.\2", after_colon.group(1))
    m = re.search(r"\*?([\d.]+)\s*,\s*\*?([\d.]+)\s*,\s*\*?([\d.]+)", vals)
    if not m:
        return "—"
    tps1 = float(m.group(1))
    icon = "✅" if tps1 >= 19 else ("⚠️" if tps1 >= 15 else "❌")
    return f"{icon} {tps1:.1f} <i>(5м: {m.group(2)}, 15м: {m.group(3)})</i>"


def _system_status_sync(mc_up: bool = False, tps_str: str = "—") -> str:
    cpu = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    cpu_freq = _get_cpu_freq()

    uptime_sec = int(time.time() - psutil.boot_time())
    days, rem = divmod(uptime_sec, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    uptime_str = f"{days}д " if days else ""
    uptime_str += f"{hours}ч {minutes}м"

    mem_used = mem.used / 1024 ** 3
    mem_total = mem.total / 1024 ** 3
    disk_used = disk.used / 1024 ** 3
    disk_total = disk.total / 1024 ** 3

    internet = "✅" if _check_internet() else "❌"
    mc = "✅ Работает" if mc_up else "❌ Недоступен"

    def bar(pct: float) -> str:
        filled = int(pct / 10)
        return "█" * filled + "░" * (10 - filled)

    return (
        f"📊 <b>Статус системы</b>\n\n"
        f"🖥 CPU:   <code>{bar(cpu)}</code> {cpu:.1f}%\n"
        f"       <i>{cpu_freq}</i>\n"
        f"💾 RAM:   <code>{bar(mem.percent)}</code> {mem.percent:.1f}%\n"
        f"       <i>{mem_used:.1f} / {mem_total:.1f} GB</i>\n"
        f"💿 Диск:  <code>{bar(disk.percent)}</code> {disk.percent:.1f}%\n"
        f"       <i>{disk_used:.1f} / {disk_total:.1f} GB</i>\n\n"
        f"⏱ Аптайм:    <b>{uptime_str}</b>\n"
        f"🌐 Интернет:  {internet}\n"
        f"⛏ Майнкрафт: <b>{mc}</b>\n"
        f"⚡ TPS:       {tps_str}"
    )


async def get_system_status() -> str:
    mc_up = await _rcon_ping()
    tps_str = "—"
    if mc_up:
        try:
            raw = await rcon_cmd(RCON_HOST, RCON_PASS, "tps", RCON_PORT)
            tps_str = _parse_tps(raw)
        except Exception:
            pass
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _system_status_sync, mc_up, tps_str)


async def log_watcher_loop(bot: Bot) -> None:
    pos = 0

    while not os.path.exists(MC_LOG_PATH):
        await asyncio.sleep(5)

    with open(MC_LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
        f.seek(0, 2)
        pos = f.tell()

    while True:
        try:
            size = os.path.getsize(MC_LOG_PATH)
            if size < pos:
                pos = 0

            with open(MC_LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
                f.seek(pos)
                lines = f.readlines()
                pos = f.tell()

            for line in lines:
                m = re.search(r"\[Server thread/INFO\]: (\w+)\[/[^\]]+\] logged in", line)
                if m:
                    await bot.send_message(ADMIN_ID, f"👋 <b>{m.group(1)}</b> зашёл на сервер", parse_mode="HTML")
                    continue
                m = re.search(r"\[Server thread/INFO\]: (\w+) lost connection:", line)
                if m:
                    await bot.send_message(ADMIN_ID, f"🚪 <b>{m.group(1)}</b> вышел с сервера", parse_mode="HTML")

        except FileNotFoundError:
            pos = 0
        except Exception:
            logger.exception("Ошибка в log_watcher_loop")

        await asyncio.sleep(2)


async def monitoring_loop(bot: Bot) -> None:
    global _server_was_up

    # Даём серверу время запуститься перед первой проверкой
    await asyncio.sleep(15)

    while True:
        try:
            is_up = await _rcon_ping()

            if _server_was_up is None:
                _server_was_up = is_up
                logger.info("Мониторинг запущен, сервер: %s", "UP" if is_up else "DOWN")

            elif _server_was_up and not is_up:
                _server_was_up = False
                logger.warning("Сервер упал — определяем причину")
                reason = await loop.run_in_executor(None, _detect_crash_reason)
                await bot.send_message(
                    ADMIN_ID,
                    f"🚨 <b>Сервер упал!</b>\n\n<b>Возможные причины:</b>\n{reason}",
                    parse_mode="HTML",
                )

            elif not _server_was_up and is_up:
                _server_was_up = True
                logger.info("Сервер восстановился")
                await bot.send_message(
                    ADMIN_ID,
                    "✅ <b>Сервер снова онлайн!</b>",
                    parse_mode="HTML",
                )

        except Exception:
            logger.exception("Ошибка в цикле мониторинга")

        await asyncio.sleep(CHECK_INTERVAL)
