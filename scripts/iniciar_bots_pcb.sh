#!/bin/bash
# ============================================================
#  iniciar_bots.sh — Arranque con SCREEN (Antigravity v4.0)
# ============================================================

BOT_ROOT="$HOME/ircbots/bots"
SCRIPTS_DIR="$HOME/ircbots/scripts"

log() { echo "[$(date '+%H:%M:%S')] $1"; }

# 1. Limpiar todo
log "Limpiando procesos y sesiones previas..."
pkill -9 -f python3
screen -wipe 2>/dev/null || true
sleep 2

# 2. Arrancar MiLeNiUm
log "Iniciando MiLeNiUm (screen)..."
screen -dmS milenium bash -c "cd $BOT_ROOT/milenium && python3 -u iabot.py >> /tmp/milenium.log 2>&1"

# 3. Arrancar iND0MiTa
log "Iniciando iND0MiTa (screen)..."
screen -dmS indomita bash -c "cd $BOT_ROOT/indomita && python3 -u falkian.py >> /tmp/falkian.log 2>&1"

# 4. Arrancar Pulsor Central (El que mantiene todo vivo)
log "Iniciando Pulsor Central (screen)..."
screen -dmS pulsor bash -c "python3 -u $SCRIPTS_DIR/node_heartbeat.py >> /tmp/pulsor.log 2>&1"

sleep 2
log "=== ESTADO FINAL ==="
screen -ls
