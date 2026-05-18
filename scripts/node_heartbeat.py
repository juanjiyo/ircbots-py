import time
import requests
import os
import sys
from datetime import datetime, timezone

# Configuración del Centinela
SENTINEL_URL = "http://93.93.116.244:4471/heartbeat/"
HEARTBEAT_TOKEN = "antigravity_token_2026_c2"

# Configuración de Bots en PC B
BOT_ROOT = os.path.expanduser("~/ircbots/bots")
BOTS = {
    "MiLeNiUm": {
        "script": "iabot.py",
        "dir": os.path.join(BOT_ROOT, "milenium"),
        "screen": "milenium"
    },
    "iND0MiTa": {
        "script": "falkian.py",
        "dir": os.path.join(BOT_ROOT, "indomita"),
        "screen": "indomita"
    }
}

def check_process(script_name):
    """Chequea si el proceso está corriendo en memoria."""
    # Usamos pgrep para mayor precisión
    return os.system(f"pgrep -f {script_name} > /dev/null") == 0

def start_bot(name, config):
    """Arranca un bot en una sesión de screen dedicada."""
    print(f"[{datetime.now(timezone.utc)}] 🚀 Arrancando {name} en screen '{config['screen']}'...", flush=True)
    cmd = f"cd {config['dir']} && screen -dmS {config['screen']} python3 -u {config['script']}"
    os.system(cmd)

def execute_c2_command(bot_name, cmd):
    """Ejecuta un comando recibido desde el C2."""
    print(f"[{datetime.now(timezone.utc)}] 🛰️ C2 Command para {bot_name}: {cmd}", flush=True)
    # Ejecutamos el comando directamente. Si es un reinicio, el comando ya debería venir con screen si es complejo.
    os.system(cmd)

def sync_pulse():
    print(f"[{datetime.now(timezone.utc)}] Pulsor Sentinel v4.0 (Screen Native) Iniciado", flush=True)
    while True:
        for bot_name, config in BOTS.items():
            is_running = check_process(config['script'])
            
            # 1. Auto-Recuperación si está caído
            if not is_running:
                print(f"[{datetime.now(timezone.utc)}] ⚠️ {bot_name} detectado como CAÍDO.", flush=True)
                start_bot(bot_name, config)
                time.sleep(2) # Esperar a que arranque
                is_running = check_process(config['script'])

            status = "ALIVE" if is_running else "DEAD"
            
            # 2. Enviar Latido y Consultar C2
            url = f"{SENTINEL_URL}{bot_name}"
            payload = {"status": status}
            headers = {"X-Heartbeat-Token": HEARTBEAT_TOKEN}
            
            try:
                r = requests.post(url, json=payload, headers=headers, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    # 3. Procesar comandos C2
                    if "cmd" in data:
                        execute_c2_command(bot_name, data["cmd"])
                else:
                    print(f"[{datetime.now(timezone.utc)}] {bot_name} Sentinel Error: HTTP {r.status_code}", flush=True)
            except Exception as e:
                print(f"[{datetime.now(timezone.utc)}] {bot_name} Connection Error: {e}", flush=True)
        
        time.sleep(15)

if __name__ == "__main__":
    sync_pulse()
