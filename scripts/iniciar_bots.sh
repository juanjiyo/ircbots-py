#!/bin/bash

# Script de arranque para bots IRC con nohup
# Los bots corren en background con logs en archivos

BOT_IABOT="$HOME/iabot"
BOT_MODBOT="$HOME/modbot"
PID_IABOT="$BOT_IABOT/iabot.pid"
PID_MODBOT="$BOT_MODBOT/falkian.pid"

log() {
    echo "[$(date '+%H:%M:%S')] $1"
}

# Matar bots anteriores si existen
if [ -f "$PID_IABOT" ]; then
    kill $(cat "$PID_IABOT") 2>/dev/null
    log "MiLeNiUm anterior detenido"
fi
if [ -f "$PID_MODBOT" ]; then
    kill $(cat "$PID_MODBOT") 2>/dev/null
    log "iND0MiTa anterior detenido"
fi

sleep 1

# Limpiar sesiones de screen muertas
screen -wipe 2>/dev/null

# Arrancar MiLeNiUm (iabot)
log "Iniciando MiLeNiUm desde $BOT_IABOT..."
cd "$BOT_IABOT" || { log "ERROR: No se pudo acceder a $BOT_IABOT"; exit 1; }
nohup python3 iabot.py > iabot.log 2>&1 &
echo $! > "$PID_IABOT"
sleep 2

if pgrep -f "iabot.py" > /dev/null; then
    log "[MiLeNiUm] INICIADO ✓ (PID: $(cat $PID_IABOT))"
else
    log "[MiLeNiUm] ERROR al iniciar ✗"
    exit 1
fi

# Arrancar iND0MiTa (modbot)
log "Iniciando iND0MiTa desde $BOT_MODBOT..."
cd "$BOT_MODBOT" || { log "ERROR: No se pudo acceder a $BOT_MODBOT"; exit 1; }
nohup python3 falkian.py > falkian.log 2>&1 &
echo $! > "$PID_MODBOT"
sleep 2

if pgrep -f "falkian.py" > /dev/null; then
    log "[iND0MiTa] INICIADO ✓ (PID: $(cat $PID_MODBOT))"
else
    log "[iND0MiTa] ERROR al iniciar ✗"
    exit 1
fi


# Arrancar monitor de bots (watchdog con auto-reinicio)
MONITOR_SCRIPT="/home/juanjo/ircbots/scripts/monitor_bots_wsl.sh"
MONITOR_PID_FILE="$HOME/monitor_bots.pid"

if [ -f "$MONITOR_PID_FILE" ]; then
    kill $(cat "$MONITOR_PID_FILE") 2>/dev/null
    log "Monitor anterior detenido"
    rm -f "$MONITOR_PID_FILE"
fi

sleep 1
log "Iniciando monitor de bots..."
nohup bash "$MONITOR_SCRIPT" > /home/irc/logs/monitor_bots.log 2>&1 &
echo $! > "$MONITOR_PID_FILE"
sleep 2

if pgrep -f "monitor_bots_wsl.sh" > /dev/null; then
    log "[Monitor Bots] INICIADO ✓ (PID: $(cat $MONITOR_PID_FILE))"
else
    log "[Monitor Bots] ERROR al iniciar ✗"
fi

log ""
log "=== Bots IRC + Monitor iniciados correctamente ==="
log "MiLeNiUm:           tail -f $BOT_IABOT/iabot.log"
log "iND0MiTa:           tail -f $BOT_MODBOT/falkian.log"
log "Monitor Bots:      tail -f /home/irc/logs/monitor_bots.log"
log "Para detener: $0 stop"