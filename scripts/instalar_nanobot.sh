#!/usr/bin/env bash
# =============================================================
#  instalar_nanobot.sh — Instalador de nanobot para Ubuntu/Debian
#  Uso: bash instalar_nanobot.sh
#  Probado en: Ubuntu 24.04 / Debian 13 / Linux Mint
# =============================================================

set -e  # Si algo falla, el script se detiene

# Forzar IPv4 para evitar errores de red en servidores con IPv6 mal configurado
APT_OPTS="-o Acquire::ForceIPv4=true"

# ── Colores para los mensajes ─────────────────────────────────
VERDE="\033[1;32m"
AMARILLO="\033[1;33m"
ROJO="\033[1;31m"
CYAN="\033[1;36m"
NC="\033[0m"  # Sin color

info()    { echo -e "${CYAN}[INFO]${NC} $1"; }
ok()      { echo -e "${VERDE}[OK]${NC} $1"; }
aviso()   { echo -e "${AMARILLO}[AVISO]${NC} $1"; }
error()   { echo -e "${ROJO}[ERROR]${NC} $1"; exit 1; }

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════╗"
echo "║       Instalador de nanobot (HKUDS)          ║"
echo "║    Agente AI personal ultraligero en Python  ║"
echo "╚══════════════════════════════════════════════╝"
echo -e "${NC}"

# ── 1. Comprobar que no se ejecuta como root ───────────────────
if [ "$EUID" -eq 0 ]; then
    aviso "Ejecutando como root. Se recomienda usarlo con un usuario normal."
fi

# Limpiar restos de instalaciones fallidas previas para evitar errores de firma en el primer update
sudo rm -f /etc/apt/sources.list.d/deadsnakes.list
sudo rm -f /usr/share/keyrings/deadsnakes.gpg

# ── 2. Detectar distro y actualizar paquetes ──────────────────
info "Actualizando lista de paquetes..."
sudo apt-get $APT_OPTS update -qq

# ── 3. Instalar dependencias base del sistema ─────────────────
info "Instalando dependencias base y certificados..."
sudo apt-get $APT_OPTS install -y -qq \
    git \
    screen \
    curl \
    ca-certificates \
    gnupg

# ── 4. Detectar distro: Ubuntu o Debian ──────────────────────
DISTRO_ID=$(grep "^ID=" /etc/os-release | cut -d= -f2 | tr -d '"')
DISTRO_VER=$(grep "^VERSION_ID=" /etc/os-release | cut -d= -f2 | tr -d '"')

# CODENAME: lsb_release primero, luego /etc/os-release, luego fallback por VERSION_ID
CODENAME=""
if command -v lsb_release &>/dev/null; then
    CODENAME=$(lsb_release -cs 2>/dev/null)
fi
if [ -z "$CODENAME" ]; then
    CODENAME=$(grep "^VERSION_CODENAME=" /etc/os-release | cut -d= -f2 | tr -d '"')
fi
if [ -z "$CODENAME" ]; then
    case "$DISTRO_VER" in
        "24.04") CODENAME="noble"  ;;
        "22.04") CODENAME="jammy"  ;;
        "20.04") CODENAME="focal"  ;;
        "18.04") CODENAME="bionic" ;;
        *) echo "[ERROR] No se pudo determinar el codename para Ubuntu ${DISTRO_VER}"; exit 1 ;;
    esac
    echo "[AVISO] lsb_release no disponible. Codename deducido: ${CODENAME}"
fi

info "Distro detectada: ${DISTRO_ID} ${DISTRO_VER} (${CODENAME})"

TARGET_PYTHON="3.13"
PYTHON_BIN="python3.13"

info "Preparando instalación de Python 3.13 (sin afectar al sistema)..."

# ── 6. Añadir repo de Python 3.13 según distro ───────────────
if [ "$DISTRO_ID" = "ubuntu" ]; then
    info "Ubuntu ($CODENAME) detectado → añadiendo deadsnakes manualmente..."
    sudo apt-get install -y -qq gnupg curl

    # Importar clave GPG de deadsnakes
    sudo mkdir -p /usr/share/keyrings
    
    info "Descargando clave GPG de deadsnakes (con reintentos)..."
    # Intentamos descargar la clave usando el puerto 80, que suele estar más abierto
    # Añadimos --max-time y reintentos para mayor robustez
    DOWNLOAD_SUCCESS=false
    KEY_URL="http://keyserver.ubuntu.com/pks/lookup?op=get&search=0xF23C5A6CF475977595C89F51BA6932366A755776"
    ALT_KEY_URL="https://keyserver.ubuntu.com/pks/lookup?op=get&search=0xF23C5A6CF475977595C89F51BA6932366A755776"

    for i in {1..3}; do
        info "Intento $i: Descargando desde servidor principal..."
        if curl -4 -fsSL --connect-timeout 15 --max-time 30 "$KEY_URL" | sudo gpg --dearmor --yes -o /usr/share/keyrings/deadsnakes.gpg; then
            DOWNLOAD_SUCCESS=true
            break
        fi
        aviso "Fallo en intento $i. Reintentando en 5 segundos..."
        sleep 5
    done

    if [ "$DOWNLOAD_SUCCESS" = false ]; then
        info "Intentando vía servidor alternativo (HTTPS)..."
        if curl -4 -fsSL --connect-timeout 15 --max-time 30 "$ALT_KEY_URL" | sudo gpg --dearmor --yes -o /usr/share/keyrings/deadsnakes.gpg; then
            DOWNLOAD_SUCCESS=true
        fi
    fi

    if [ "$DOWNLOAD_SUCCESS" = false ]; then
        aviso "Fallo en descarga directa. Intentando vía apt-key (hkp/80) como último recurso..."
        sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys BA6932366A755776 || error "No se pudo obtener la clave GPG por ningún método."
    fi

    # Usar ppa.launchpadcontent.net para evitar errores de coincidencia de nombre en certificado
    echo "deb [signed-by=/usr/share/keyrings/deadsnakes.gpg] http://ppa.launchpadcontent.net/deadsnakes/ppa/ubuntu ${CODENAME} main" \
        | sudo tee /etc/apt/sources.list.d/deadsnakes.list > /dev/null

    # Forzar actualización de certificados y reintentar update
    sudo update-ca-certificates
    sudo apt-get $APT_OPTS update -qq

elif [ "$DISTRO_ID" = "debian" ]; then
    info "Debian detectado → usando repositorios oficiales..."
    # En Debian 13 (trixie) Python 3.13 está en los repos oficiales.
    # En Debian 12 (bookworm) usamos backports.
    if [ "$DISTRO_VER" = "13" ]; then
        info "Debian 13 (trixie): Python 3.13 disponible en repos oficiales."
        sudo apt-get update -qq
    else
        info "Debian ${DISTRO_VER}: activando backports para Python 3.13..."
        CODENAME=$(grep "^VERSION_CODENAME=" /etc/os-release | cut -d= -f2 | tr -d '"')
        echo "deb http://deb.debian.org/debian ${CODENAME}-backports main" \
            | sudo tee /etc/apt/sources.list.d/backports.list > /dev/null
        sudo apt-get update -qq
    fi
else
    aviso "Distro '$DISTRO_ID' no reconocida. Intentando instalación directa..."
    sudo apt-get update -qq
fi

# ── 7. Instalar Python 3.13 limpio ───────────────────────────
info "Instalando Python ${TARGET_PYTHON}..."
sudo apt-get $APT_OPTS install -y -qq \
    python3.13 \
    python3.13-venv \
    python3.13-dev

# Instalar pip via get-pip.py (más fiable que el paquete del sistema)
info "Instalando pip para Python ${TARGET_PYTHON}..."
curl -4 -sSL https://bootstrap.pypa.io/get-pip.py | sudo python3.13

# Establecer python3.13 como python3 por defecto en el sistema
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.13 1
set +e
sudo update-alternatives --set python3 /usr/bin/python3.13 2>/dev/null
set -e

INSTALLED_VERSION=$($PYTHON_BIN --version 2>&1)
ok "Python instalado: $INSTALLED_VERSION"

# ── 5. Crear entorno virtual ──────────────────────────────────
INSTALL_DIR="$HOME/nanobot"
VENV_DIR="$INSTALL_DIR/.venv"

info "Creando directorio de instalación en: $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"

info "Creando entorno virtual Python en: $VENV_DIR"
$PYTHON_BIN -m venv "$VENV_DIR"

# Activar el entorno virtual
source "$VENV_DIR/bin/activate"
ok "Entorno virtual activado"

# ── 6. Instalar nanobot desde PyPI ────────────────────────────
info "Instalando nanobot-ai desde PyPI..."
pip install --quiet --upgrade pip
pip install --quiet nanobot-ai
ok "nanobot instalado correctamente"

# Verificar instalación
NANOBOT_VERSION=$(nanobot --version 2>/dev/null || echo "desconocida")
ok "Versión instalada: $NANOBOT_VERSION"

# ── 7. Crear config básica ────────────────────────────────────
CONFIG_DIR="$HOME/.nanobot"
CONFIG_FILE="$CONFIG_DIR/config.json"

mkdir -p "$CONFIG_DIR"

if [ -f "$CONFIG_FILE" ]; then
    aviso "Ya existe config en $CONFIG_FILE — no se sobreescribe."
    aviso "Haz una copia antes de modificarla manualmente si es necesario."
else
    info "Creando configuración base en: $CONFIG_FILE"
    cat > "$CONFIG_FILE" << 'CONFIGEOF'
{
  "providers": {
    "openrouter": {
      "apiKey": "PON_AQUI_TU_CLAVE_OPENROUTER"
    }
  },
  "agents": {
    "defaults": {
      "provider": "openrouter",
      "model": "google/gemini-2.0-flash-exp:free"
    }
  },
  "channels": {
    "telegram": {
      "enabled": true,
      "token": "PON_AQUI_TU_TOKEN_BOT_TELEGRAM",
      "allowFrom": []
    }
  }
}
CONFIGEOF
    ok "Config creada. Edítala con tu API key y token de Telegram antes de arrancar."
fi

# ── 8. Crear script de arranque ───────────────────────────────
LAUNCHER="$INSTALL_DIR/start_nanobot.sh"

info "Creando script de arranque en: $LAUNCHER"
cat > "$LAUNCHER" << LAUNCHEOF
#!/usr/bin/env bash
# Arranca nanobot dentro de un screen llamado 'nanobot'
# Uso: bash ~/nanobot/start_nanobot.sh

source "$VENV_DIR/bin/activate"

if screen -list | grep -q "nanobot"; then
    echo "nanobot ya está corriendo. Usa: screen -r nanobot"
else
    screen -dmS nanobot bash -c "source $VENV_DIR/bin/activate && nanobot gateway; exec bash"
    echo "nanobot arrancado en screen. Conéctate con: screen -r nanobot"
fi
LAUNCHEOF

chmod +x "$LAUNCHER"
dos2unix "$LAUNCHER"
ok "Script de arranque creado: $LAUNCHER"

# ── 9. Crear script de actualización ─────────────────────────
UPDATER="$INSTALL_DIR/update_nanobot.sh"

cat > "$UPDATER" << UPDATEEOF
#!/usr/bin/env bash
# Actualiza nanobot a la última versión estable
source "$VENV_DIR/bin/activate"
echo "Actualizando nanobot..."
pip install --quiet --upgrade nanobot-ai
echo "Versión instalada: \$(nanobot --version 2>/dev/null || echo 'desconocida')"
UPDATEEOF

chmod +x "$UPDATER"
ok "Script de actualización creado: $UPDATER"

# ── 10. Resumen final ─────────────────────────────────────────
echo ""
echo -e "${VERDE}╔══════════════════════════════════════════════╗${NC}"
echo -e "${VERDE}║         Instalación completada 🎉            ║${NC}"
echo -e "${VERDE}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${CYAN}Pasos siguientes:${NC}"
echo ""
echo -e "  1. Edita la configuración:"
echo -e "     ${AMARILLO}nano ~/.nanobot/config.json${NC}"
echo -e "     → Pon tu API key de OpenRouter"
echo -e "     → Pon el token de tu bot de Telegram"
echo ""
echo -e "  2. Arranca nanobot:"
echo -e "     ${AMARILLO}bash ~/nanobot/start_nanobot.sh${NC}"
echo ""
echo -e "  3. Ver logs en tiempo real:"
echo -e "     ${AMARILLO}screen -r nanobot${NC}"
echo -e "     (Sal con Ctrl+A, D sin matar el proceso)"
echo ""
echo -e "  4. Actualizar en el futuro:"
echo -e "     ${AMARILLO}bash ~/nanobot/update_nanobot.sh${NC}"
echo ""