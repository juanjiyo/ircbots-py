#!/bin/bash
# Monitor continuo con auto-reinicio para bots IRC
# Uso: ./monitor_bots_wsl.sh

BOT_ROOT="/mnt/c/Users/WinterOS/Documents/ircbots/bots"
CHECK_INTERVAL=10
MAX_RESTARTS=3
declare -A RESTART_COUNT
declare -A LAST_RESTART

TELEGRAM_TOKEN="TELEGRAM_TOKEN_C2"
CHAT_ID="-1003808302723"

log() {
    echo "[$(date '+%H:%M:%S')] $1"
}

send_telegram() {
    for cid in "-1003808302723"; do
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
            -d "chat_id=${cid}" \
            -d "text=$1" \
            -d "parse_mode=HTML" \
            -d "disable_web_page_preview=true" \
            --max-time 10 >/dev/null 2>&1 || true
    done
}

check_bot() {
    local nombre=$1
    local archivo=$2
    local carpeta=$3

    if ! pgrep -f "python3.*$archivo" > /dev/null; then
        log "[$nombre] DETECTADO CAÍDO - Reiniciando..."
        send_telegram "🚨 <b>[$nombre] Bot CAÍDO</b>
📁 $archivo ($carpeta)
⚠️ Intentando reinicio automático..."

        # Evitar bucle de reinicios
        if [ "${RESTART_COUNT[$nombre]:-0}" -ge $MAX_RESTARTS ]; then
            log "[$nombre] Máximo de reinicios alcanzado. No se reiniciará más."
            send_telegram "❌ <b>[$nombre] Máximo de reinicios alcanzado</b>
El bot no se reiniciará automáticamente.
Reinicios previos: ${RESTART_COUNT[$nombre]}"
            return 1
        fi

        cd "$BOT_ROOT/$carpeta" || return 1
        nohup python3 "$archivo" > /home/irc/logs/${nombre,,}.log 2>&1 &

        if [ $? -eq 0 ]; then
            local new_pid=$(pgrep -f "python3.*$archivo")
            log "[$nombre] REINICIADO ✓ (PID: $new_pid)"
            RESTART_COUNT[$nombre]=$((${RESTART_COUNT[$nombre]:-0} + 1))
            LAST_RESTART[$nombre]=$(date '+%H:%M:%S')
            send_telegram "✅ <b>[$nombre] Bot REINICIADO</b>
🆕 PID: $new_pid
🔄 Reinicios totales: ${RESTART_COUNT[$nombre]}"
        else
            log "[$nombre] ERROR al reiniciar ✗"
            send_telegram "❌ <b>[$nombre] Error al reiniciar</b>
No se pudo iniciar el bot automáticamente."
        fi
    fi
}

log "=== Monitor de Bots IRC ==="
log "Check interval: ${CHECK_INTERVAL}s"
log "Presiona Ctrl+C para detener"
echo ""

while true; do
    check_bot "MiLeNiUm" "iabot.py" "milenium"
    check_bot "iND0MiTa" "falkian.py" "indomita"

    # Verificar cada 10s
    sleep $CHECK_INTERVAL
done
