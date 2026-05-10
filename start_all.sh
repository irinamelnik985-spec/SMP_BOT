#!/bin/bash

# ===================== НАСТРОЙКИ =====================
SERVER_DIR="/home/danya/minecraft"
BACKUP_ROOT="/home/danya/minecraft/minecraft_backups"
JAR_NAME="server.jar"
RAM_MIN="4G"
RAM_MAX="4G"
RCON_PORT=25575
RCON_PASS="werty3108"
LOG_FILE="$SERVER_DIR/server_errors.log"
BOT_DIR="$SERVER_DIR/whitelist-bot"
# =====================================================

# убиваем старые зомби-процессы бэкапа
pkill -f "minecraft_backups" 2>/dev/null
echo "старые процессы бэкапа убиты (если были)"

# включаем Transparent Huge Pages для производительности
echo "madvise" | sudo tee /sys/kernel/mm/transparent_hugepage/enabled > /dev/null 2>&1

# снижаем агрессивность свопа
echo '2323' | sudo -S sysctl -q vm.swappiness=10

# уменьшаем I/O спайки при записи чанков
echo '2323' | sudo -S sysctl -q vm.dirty_ratio=10
echo '2323' | sudo -S sysctl -q vm.dirty_background_ratio=5

# фиксируем частоту CPU на максимуме
for cpu in /sys/devices/system/cpu/cpu*/cpufreq/; do
    echo 2100000 | sudo tee "${cpu}scaling_max_freq" > /dev/null 2>&1
    echo 2100000 | sudo tee "${cpu}scaling_min_freq" > /dev/null 2>&1
done
echo "CPU частота зафиксирована на 2100 МГц"

# лимит открытых файлов
ulimit -n 65535

# ротация лога ошибок (оставляем последние 50 МБ)
if [ -f "$LOG_FILE" ] && [ "$(stat -c%s "$LOG_FILE" 2>/dev/null || echo 0)" -gt $((50 * 1024 * 1024)) ]; then
    mv "$LOG_FILE" "${LOG_FILE}.old"
    echo "лог ротирован"
fi

# создаём временный конфиг для rconclt
RCON_CONFIG=$(mktemp)
cat > "$RCON_CONFIG" << EOF
[minecraft]
host = 127.0.0.1
port = $RCON_PORT
passwd = $RCON_PASS
EOF

rcon() {
    rconclt -c "$RCON_CONFIG" minecraft "$@" 2>/dev/null
}

echo "пробиваем порты..."
upnpc -e "sshd"      -a 192.168.0.102 22    22    tcp
upnpc -u http://192.168.1.1:1900/gatedesc.xml -e "sshd"      -a 192.168.1.76  22    22    tcp
upnpc -e "minet"     -a 192.168.0.102 25565 25565 tcp
upnpc -u http://192.168.1.1:1900/gatedesc.xml -e "minet"     -a 192.168.1.76  25565 25565 tcp
upnpc -e "pl3xmap"   -a 192.168.0.102 8080  8080  tcp
upnpc -u http://192.168.1.1:1900/gatedesc.xml -e "pl3xmap"   -a 192.168.1.76  8080  8080  tcp
upnpc -e "voicechat" -a 192.168.0.102 24454 24454 udp
upnpc -u http://192.168.1.1:1900/gatedesc.xml -e "voicechat" -a 192.168.1.76  24454 24454 udp

# бэкап-система
mkdir -p "$BACKUP_ROOT"
(
while true; do
    TIMESTAMP=$(date +'%Y-%m-%d_%H-%M')
    BACKUP_FILE="$BACKUP_ROOT/$TIMESTAMP.tar.gz"

    # останавливаем запись перед бэкапом
    rcon save-off
    rcon save-all
    sleep 5

    tar -czf "$BACKUP_FILE" \
        -C "$SERVER_DIR" world world_nether world_the_end

    # включаем запись обратно
    rcon save-on

    # удаляем старые бэкапы, оставляем 25
    ls -t "$BACKUP_ROOT"/*.tar.gz 2>/dev/null | tail -n +26 | xargs -I {} rm -f "{}"

    echo "[$TIMESTAMP] бэкап сохранён: $BACKUP_FILE"
    sleep 1200
done
) &

BACKUP_PID=$!
echo "бэкап запущен, PID: $BACKUP_PID"

echo "запускаем tor..."
sudo systemctl start tor
sleep 2

source /home/danya/minecraft/venv/bin/activate

echo "перезапускаем телеграм-бот через systemd..."
echo '2323' | sudo -S systemctl restart whitelist-bot.service
echo "бот запущен"

echo "запускаем сервер..."
cd "$SERVER_DIR"

# автоперезапуск при краше
while true; do
    java -Xms$RAM_MIN -Xmx$RAM_MAX \
      -XX:+UseG1GC \
      -XX:+ParallelRefProcEnabled \
      -XX:MaxGCPauseMillis=200 \
      -XX:+UnlockExperimentalVMOptions \
      -XX:+DisableExplicitGC \
      -XX:+AlwaysPreTouch \
      -XX:G1NewSizePercent=30 \
      -XX:G1MaxNewSizePercent=40 \
      -XX:G1HeapRegionSize=8M \
      -XX:G1ReservePercent=20 \
      -XX:G1HeapWastePercent=5 \
      -XX:G1MixedGCCountTarget=4 \
      -XX:InitiatingHeapOccupancyPercent=15 \
      -XX:G1MixedGCLiveThresholdPercent=90 \
      -XX:G1RSetUpdatingPauseTimePercent=5 \
      -XX:SurvivorRatio=32 \
      -XX:+PerfDisableSharedMem \
      -XX:MaxTenuringThreshold=1 \
      -Dusing.aikars.flags=https://mcflags.emc.gs \
      -Daikars.new.flags=true \
      -jar "$JAR_NAME" nogui 2>> "$LOG_FILE"

    EXIT_CODE=$?

    if [ $EXIT_CODE -eq 0 ]; then
        echo "сервер остановлен штатно."
        break
    fi

    echo "сервер упал (код $EXIT_CODE)! перезапуск через 5 сек..."
    sleep 5
done

# завершение
kill $BACKUP_PID
rm -f "$RCON_CONFIG"
echo "всё остановлено."
