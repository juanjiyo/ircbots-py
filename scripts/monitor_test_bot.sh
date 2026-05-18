#!/bin/bash
# Monitor en tiempo real para bot de test
LOG_FILE="$HOME/logs/test_bot_$(date +%d%m%Y_%H%M%S).log"

log() {
    local msg="$(date '+%d/%m/%Y %H:%M:%S') — $1"
    echo "$msg" | tee -a "$LOG_FILE"
    send_telegram "$msg"
}

send_telegram() {
    curl -s -X POST "https://api.telegram.org/botTELEGRAM_TOKEN_C2/sendMessage" \
        -d "chat_id=-1003808302723" \
        -d "text=$1" \
        -d "parse_mode=HTML" \
        -d "disable_web_page_preview=true" \
        --max-time 10 >/dev/null 2>&1 || true
}

log "MONITOR ACTIVO — Bot de Test"
log "Inicio: $(date)"
log "Servidor: irc.chatzona.org:6667"
log "Bot: BeBeSaUrIo"
log "Canal: #Limbo"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

send_telegram "Monitor iniciado para bot de test (BeBeSaUrIo)
Observando ciclo completo de conexión..."

# Verificar estado previo
log "[PRE-CHECK] Procesos Python activos:"
ps aux | grep python | grep -v grep | tee -a "$LOG_FILE"

log "[PRE-CHECK] Conexiones IRC activas:"
ss -tnp 2>/dev/null | grep :6667 | tee -a "$LOG_FILE" || log "  → Sin conexiones IRC previas"

log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "Esperando lanzamiento del bot..."

# Esperar a que el bot arranque
BOT_PID=""
for i in $(seq 1 30); do
    BOT_PID=$(pgrep -f 'test_irc.py' | head -1)
    if [ -n "$BOT_PID" ]; then
        log "Bot detectado — PID: $BOT_PID (tardó ${i}s)"
        send_telegram "Bot detectado — PID: $BOT_PID"
        break
    fi
    sleep 1
done

if [ -z "$BOT_PID" ]; then
    log "ERROR: Bot no arrancó en 30s"
    send_telegram "ERROR: Bot de test no arrancó en 30 segundos"
    exit 1
fi

# Monitor de conexión
log "[MONITOR] Observando conexión IRC..."
CONNECTED=false
for i in $(seq 1 15); do
    if ss -tnp 2>/dev/null | grep ":6667.*pid=${BOT_PID}" >/dev/null 2>&1; then
        log "Conexion IRC establecida (${i}s tras deteccion)"
        send_telegram "Conexion IRC establecida (puerto 6667)"
        CONNECTED=true
        break
    fi
    sleep 1
done

if [ "$CONNECTED" = false ]; then
    log "No se detecto conexion TCP al IRC"
    send_telegram "No se detecto conexion IRC"
fi

# Esperar a que el bot termine o timeout
log "[MONITOR] Esperando fin de sesion (max 60s)..."
for i in $(seq 1 60); do
    if ! kill -0 $BOT_PID 2>/dev/null; then
        log "Bot termino — sesion completada"
        send_telegram "Bot finalizo — sesion completada"
        break
    fi
    sleep 1
done

# Estado final
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "[POST-CHECK] Estado final:"
log "Procesos test_irc: $(ps aux | grep test_irc | grep -v grep | wc -l)"
ss -tnp 2>/dev/null | grep :6667 | tee -a "$LOG_FILE" || log "  → Sin conexiones IRC"

log "[POST-CHECK] Ultimas lineas del log:"
tail -20 "$LOG_FILE" | tee -a "$LOG_FILE"

send_telegram "Monitor finalizado
Log: $LOG_FILE"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "Monitor finalizado: $(date)"
