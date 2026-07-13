import asyncio
import logging
import os
import re
import socket
import subprocess
import time

import psutil
from aiogram import Bot

from config import ADMIN_ID, RCON_HOST, RCON_PASS, RCON_PORT
from rcon import rcon as rcon_cmd

logger = logging.getLogger(__name__)

_server_was_up: bool | None = None  # None = состояние ещё не определено
CHECK_INTERVAL = 30  # секунд

ALERT_CFG = {
    "cpu_temp": {"fire": 90.0, "reset": 83.0, "label": "🌡 CPU перегрев", "unit": "°C"},
    "cpu_load": {"fire": 90.0, "reset": 70.0, "label": "🖥 CPU загружен",  "unit": "%"},
    "ram":      {"fire": 90.0, "reset": 80.0, "label": "💾 RAM забита",   "unit": "%"},
    "disk":     {"fire": 90.0, "reset": 85.0, "label": "💿 Диск забит",   "unit": "%"},
}
CPU_LOAD_STREAK = 3
_alert_fired: dict[str, bool] = {k: False for k in ALERT_CFG}
_cpu_streak = 0


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


def _get_cpu_temp() -> float | None:
    try:
        temps = psutil.sensors_temperatures()
    except Exception:
        return None
    for entry in temps.get("coretemp", []):
        if entry.label and "Package" in entry.label:
            return float(entry.current)
    vals = [e.current for entries in temps.values() for e in entries if e.current]
    return max(vals) if vals else None


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




async def _check_alerts(bot: Bot) -> None:
    global _cpu_streak

    samples = {
        "cpu_temp": _get_cpu_temp(),
        "cpu_load": psutil.cpu_percent(interval=None),
        "ram":      psutil.virtual_memory().percent,
        "disk":     psutil.disk_usage("/").percent,
    }

    cpu_val = samples["cpu_load"]
    if cpu_val is not None and cpu_val >= ALERT_CFG["cpu_load"]["fire"]:
        _cpu_streak += 1
    else:
        _cpu_streak = 0

    for key, val in samples.items():
        if val is None:
            continue
        cfg = ALERT_CFG[key]
        fired = _alert_fired[key]

        if not fired:
            trigger = _cpu_streak >= CPU_LOAD_STREAK if key == "cpu_load" else val >= cfg["fire"]
            if trigger:
                _alert_fired[key] = True
                await bot.send_message(
                    ADMIN_ID,
                    f"⚠️ <b>{cfg['label']}</b>\n"
                    f"Текущее: <b>{val:.1f}{cfg['unit']}</b> (порог {cfg['fire']:.0f}{cfg['unit']})",
                    parse_mode="HTML",
                )
                logger.warning("Алерт: %s = %.1f", key, val)
        else:
            if val < cfg["reset"]:
                _alert_fired[key] = False
                await bot.send_message(
                    ADMIN_ID,
                    f"✅ <b>{cfg['label']} — норма</b>\n"
                    f"Текущее: <b>{val:.1f}{cfg['unit']}</b>",
                    parse_mode="HTML",
                )
                logger.info("Алерт снят: %s = %.1f", key, val)


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
                reason = await asyncio.get_event_loop().run_in_executor(None, _detect_crash_reason)
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

            await _check_alerts(bot)

        except Exception:
            logger.exception("Ошибка в цикле мониторинга")

        await asyncio.sleep(CHECK_INTERVAL)
