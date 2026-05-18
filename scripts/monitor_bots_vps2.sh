#!/bin/bash
# ============================================================
# monitor_bots.sh — Monitorización y auto-reinicio de bots
# VPS: vps2 (217.160.136.43) — Debian 13
# Bots: telegram_bot.py, gemini.py, futbot.py, eggdrop, heimdall
# ============================================================

set -uo pipefail

TELEGRAM_TOKEN="TELEGRAM_TOKEN_C2"
TELEGRAM_CHAT_ID="-1003808302723"
HOME_DIR="/home/irc"
LOG_FILE="$HOME_DIR/logs/monitor.log"
LOCK_DIR="$HOME_DIR/.monitor_lock"
RESTART_COOLDOWN=60

BOTS=(
    "Telegram|telegrambot|python3 telegram_bot.py|python3 telegram_bot.py"
    "Gemini|gemini|python3 gemini.py|python3 gemini.py"
    "Futbol|futbot|python3 futbot.py|python3 futbot.py"
    "Eggdrop|eggdrop|./eggdrop eggdrop.conf|eggdrop"
    "Heimdall|heimdall|./heimdall eggdrop.conf|heimdall"
)

log() {
    echo "$(date '+%d/%m/%Y %H:%M:%S') — $1" >> "$LOG_FILE"
}

send_telegram() {
    for cid in "-1003808302723"; do
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
            -d "chat_id=${cid}" \
            -d "text=$1" \
            -d "parse_mode=HTML" \
            --max-time 10 >/dev/null 2>&1 || true
    done
}

is_running() { pgrep -f "$1" >/dev/null 2>&1; }

# Verifica si el proceso tiene conexión TCP al puerto 6667
is_connected_irc() {
    local pattern="$1"
    local pid
    pid=$(pgrep -f "$pattern" | head -1)
    [ -z "$pid" ] && return 1
    # ss muestra IPs, no hostnames. Buscar por puerto 6667 y PID.
    ss -tnp 2>/dev/null | grep -q ":6667.*pid=${pid}" && return 0
    return 1
}

can_restart() {
    local lock="${LOCK_DIR}/${1}.lock"
    if [ -f "$lock" ]; then
        local diff=$(( $(date +%s) - $(cat "$lock") ))
        [ "$diff" -ge "$RESTART_COOLDOWN" ] && return 0
        return 1
    fi
    return 0
}

mark_restart() { mkdir -p "$LOCK_DIR"; date +%s > "${LOCK_DIR}/${1}.lock"; }

restart_bot() {
    local name="$1" dir="$2" cmd="$3" pattern="$4"
    log "[REINICIO] Intentando reiniciar ${name}..."
    send_telegram "🔄 <b>Reiniciando ${name}</b>..."
    screen -ls | grep -q "$name" && screen -S "$name" -X quit 2>/dev/null || true
    sleep 2
    local pid
    pid=$(pgrep -f "$pattern" | head -1)
    [ -n "$pid" ] && kill -9 "$pid" 2>/dev/null || true
    sleep 1
    screen -wipe 2>/dev/null || true
    cd "$HOME_DIR/${dir}" || exit 1
    screen -dmS "$name" $cmd
    sleep 3
    if is_running "$pattern" && is_connected_irc "$pattern"; then
        log "[OK] ${name} reiniciado y conectado a IRC"
        send_telegram "✅ <b>${name} reiniciado</b> y conectado a IRC."
        mark_restart "$name"
    elif is_running "$pattern"; then
        log "[WARN] ${name} arrancó pero SIN conexión IRC (posible G-LINE)"
        send_telegram "⚠️ <b>${name} arrancó pero SIN conexión IRC.</b> Posible G-LINE o ban."
        mark_restart "$name"
    else
        log "[ERROR] ${name} NO arrancó"
        send_telegram "❌ <b>ERROR:</b> ${name} no arrancó. Revisar."
    fi
}

find "$LOCK_DIR" -name "*.lock" -mmin +60 -delete 2>/dev/null || true
mkdir -p "$(dirname "$LOG_FILE")" "$LOCK_DIR"

for bot_entry in "${BOTS[@]}"; do
    IFS='|' read -r name dir cmd pattern <<< "$bot_entry"

    if is_running "$pattern"; then
        if is_connected_irc "$pattern"; then
            log "[OK] ${name} activo y conectado a IRC (PID: $(pgrep -f "$pattern" | head -1))"
        else
            log "[ALERTA] ${name} proceso vivo pero SIN conexión IRC (posible G-LINE)"
            send_telegram "🚨 <b>ALERTA: ${name} sin conexión IRC!</b> Posible G-LINE o ban."
            if can_restart "$name"; then
                restart_bot "$name" "$dir" "$cmd" "$pattern"
            else
                log "[SALTADO] ${name} — cooldown activo"
                send_telegram "⏳ ${name} en cooldown."
            fi
        fi
    else
        log "[ALERTA] ${name} NO está corriendo"
        send_telegram "🚨 <b>ALERTA: ${name} se ha caído!</b>"
        if can_restart "$name"; then
            restart_bot "$name" "$dir" "$cmd" "$pattern"
        else
            log "[SALTADO] ${name} — cooldown activo"
            send_telegram "⏳ ${name} en cooldown."
        fi
    fi
done
log "—— Fin de comprobación ——"
