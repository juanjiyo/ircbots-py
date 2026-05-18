#!/bin/bash
# Script de arranque para bots IRC
# Uso: ./start_bots_wsl.sh

BOT_ROOT="/mnt/c/Users/JuanJo-Server/Documents/ircbots/bots"
LOG_DIR="$BOT_ROOT/logs"

# Crear directorio de logs
mkdir -p "$LOG_DIR"

echo "=== Iniciando Bots IRC ==="
echo "Fecha: $(date '+%d/%m/%Y %H:%M:%S')"
echo ""

# Función para iniciar bot en background
start_bot() {
    local nombre=$1
    local carpeta=$2
    local archivo=$3
    
    echo "[$nombre] Iniciando..."
    cd "$BOT_ROOT/$carpeta" || exit 1
    
    # Iniciar en background con screen
    screen -dmS "$nombre" python3 "$archivo"
    
    if [ $? -eq 0 ]; then
        echo "[$nombre] INICIADO ✓"
    else
        echo "[$nombre] ERROR al iniciar ✗"
    fi
}

# Iniciar bots
start_bot "MiLeNiUm" "milenium" "iabot.py"
start_bot "iND0MiTa" "indomita" "falkian.py"

echo ""
echo "=== Estado de sesiones Screen ==="
screen -ls

echo ""
echo "Para ver logs en tiempo real:"
echo "  screen -r MiLeNiUm  # Ver MiLeNiUm"
echo "  screen -r iND0MiTa  # Ver iND0MiTa"
echo ""
echo "Para detener un bot: screen -r <nombre> && Ctrl+C"
