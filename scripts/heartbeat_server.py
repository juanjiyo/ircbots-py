import json
import time
import logging
import subprocess
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from datetime import datetime, timezone

# Configuración de rutas y logs
BASE_DIR = Path("/home/irc/ircbots")
SCRIPTS_DIR = BASE_DIR / "scripts"
HEARTBEAT_DIR = SCRIPTS_DIR / "heartbeats"
COMMANDS_DIR = SCRIPTS_DIR / "commands"
LOG_DIR = BASE_DIR / "logs"
STATE_FILE = SCRIPTS_DIR / "health_state.json"
DASHBOARD_FILE = BASE_DIR / "DASHBOARD_C2.md"

# Telegram Config
TELEGRAM_TOKEN = "TELEGRAM_TOKEN_C2"      
TELEGRAM_NOTIFY_IDS = ["-1003808302723"] # Solo Grupo

LOG_DIR.mkdir(exist_ok=True, parents=True)
HEARTBEAT_DIR.mkdir(exist_ok=True, parents=True)
COMMANDS_DIR.mkdir(exist_ok=True, parents=True)

logging.basicConfig(
    filename=LOG_DIR / "heartbeat_diagnostic.log",
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

PORT = 4471

# SEGURIDAD: Tokens de Acceso
BOT_TOKEN   = "antigravity_token_2026_c2"       # Para que los bots reporten
ADMIN_TOKEN = "antigravity_admin_master_2026"   # Para que Gemini/MiMo den órdenes

# --- Estado Global Persistente ---
class HealthSentinel:
    def __init__(self):
        self.state = self._load()

    def _load(self):
        if STATE_FILE.exists():
            try: return json.loads(STATE_FILE.read_text())
            except: pass
        return {"bots": {}, "incidents": []}

    def save(self):
        STATE_FILE.write_text(json.dumps(self.state, indent=4))
        self._update_dashboard()

    def notify(self, message):
        """Envía notificación a Telegram a todos los IDs configurados."""
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        for chat_id in TELEGRAM_NOTIFY_IDS:
            try:
                requests.post(url, json={
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "HTML"
                }, timeout=10)
            except Exception as e:
                logging.error(f"Error enviando Telegram a {chat_id}: {e}")

    def register_heartbeat(self, bot_name, ip, diagnostic=None):
        logging.info(f"[SENTINEL] Latido recibido de {bot_name} desde {ip}")
        now = datetime.now(timezone.utc).timestamp()
        was_offline = False

        if bot_name in self.state["bots"]:
            last_ts = self.state["bots"][bot_name].get("timestamp", 0)
            if (now - last_ts) > 300: # Si llevaba más de 5 min fuera
                was_offline = True

        self.state["bots"][bot_name] = {
            "timestamp": now,
            "time_str": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "ip": ip,
            "diagnostic": diagnostic,
            "status": "ONLINE"
        }

        if was_offline:
            self.notify(f"[CENTINELA] {bot_name} ha vuelto a la vida. Sistema re-conectado.")

        self.save()

    def check_health(self):
        """Revisa si hay bots caídos y notifica."""
        now = time.time()
        for bot_name, data in self.state["bots"].items():
            last_ts = data.get("timestamp", 0)
            diff = now - last_ts

            # Si lleva más de 90s sin latir y no estaba ya marcado como OFFLINE
            if diff > 90:
                if data.get("status") != "OFFLINE":
                    data["status"] = "OFFLINE"
                    self.notify(f"[CENTINELA] {bot_name} ha dejado de latir ({int(diff)}s). Posible caida.")
                    self.save()

    def register_incident(self, bot_name, error_msg):
        incident = {
            "ts": time.time(),
            "time_str": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "bot": bot_name,
            "error": error_msg
        }
        self.state["incidents"].insert(0, incident)
        self.state["incidents"] = self.state["incidents"][:20] # Mantener solo los últimos 20
        if bot_name in self.state["bots"]:
            self.state["bots"][bot_name]["total_restarts"] += 1
        logging.warning(f"[SENTINEL] Incidente detectado en {bot_name}: {error_msg}")
        self.save()

    def _update_dashboard(self):
        """Genera el reporte Markdown profesional."""
        now_utc = datetime.now(timezone.utc)
        now_ts = now_utc.timestamp()
        lines = [
            "# CEREBRO C2 - DASHBOARD DE ESTADO",
            f"Ultima actualizacion: `{now_utc.strftime('%Y-%m-%d %H:%M:%S')} UTC`",
            "",
            "## Estado de los Agentes",
            "| Bot | Estado | Ultimo Latido | IP | Incidentes |",
            "| :--- | :--- | :--- | :--- | :--- |"
        ]

        for name, data in self.state["bots"].items():
            last_ts = data.get("timestamp", 0)
            diff = now_ts - last_ts
            status = "ONLINE" if diff < 120 else f"OFFLINE ({int(diff)}s)"
            restarts = data.get("total_restarts", 0)
            lines.append(f"| {name} | {status} | {data.get('time_str')} | {data.get('ip')} | {restarts} |")

        lines.append("")
        lines.append("## 📔 Registro de Suicidios (Incidencias)")
        lines.append("| Fecha/Hora | Bot | Descripción del Error |")
        lines.append("| :--- | :--- | :--- |")

        for inc in self.state["incidents"]:
            lines.append(f"| {inc['time_str']} | **{inc['bot']}** | `{inc['error']}` |")

        lines.append("\n---\n*Cerebro Sentinel v4.0 - Autonomía Total*")
        DASHBOARD_FILE.write_text("\n".join(lines))

class HeartbeatHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        client_ip = self.client_address[0]
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try: payload = json.loads(post_data.decode('utf-8'))
        except: payload = {}

        # --- FLUJO A: BOTS (Heartbeat / Shutdown) ---
        if self.path.startswith("/heartbeat/") or self.path.startswith("/shutdown/"):
            auth = self.headers.get('X-Heartbeat-Token')
            if auth != BOT_TOKEN:
                self._respond(403, {"error": "Forbidden"})
                return

            bot_name = self.path.split("/")[-1].strip()
            if not bot_name:
                self._respond(400, {"error": "Missing bot name"})
                return

            if self.path.startswith("/shutdown/"):
                logging.info(f"[SENTINEL] Shutdown recibido de {bot_name}")
                if bot_name in sentinel.state["bots"]:
                    sentinel.state["bots"][bot_name]["status"] = "OFFLINE (Manual)"
                    sentinel.notify(f"🛑 [CENTINELA] {bot_name} se ha apagado de forma controlada.")
                    sentinel.save()
                self._respond(200, {"status": "ok", "msg": "Shutdown registered"})
                return

            # Heartbeat normal
            sentinel.register_heartbeat(
                bot_name, client_ip,
                payload.get("diagnostic"),

            )

            # Buscar comandos pendientes
            cmd_file = COMMANDS_DIR / f"{bot_name}.cmd"
            response = {"status": "ok"}
            if cmd_file.exists():
                cmd_text = cmd_file.read_text(encoding="utf-8").strip()
                if cmd_text:
                    response["cmd"] = cmd_text
                    logging.info(f"[C2] Enviando comando a {bot_name}: {cmd_text}")
                    #log_command(bot_name, cmd_text)
                    cmd_file.unlink()

            self._respond(200, response)
            return

        # --- FLUJO B: AGENTES (Admin API) ---
        if self.path.startswith("/admin/"):
            auth = self.headers.get('X-Admin-Token')
            if auth != ADMIN_TOKEN:
                self._respond(403, {"error": "Forbidden"})
                return

            if self.path == "/admin/execute":
                target = payload.get("target")
                cmd    = payload.get("cmd")
                if target == "vps":
                    try:
                        result = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, timeout=30)
                        self._respond(200, {"ok": True, "output": result.decode('utf-8')})
                    except Exception as e:
                        self._respond(500, {"ok": False, "error": str(e)})
                elif target == "bot":
                    bot_name = payload.get("bot")
                    (COMMANDS_DIR / f"{bot_name}.cmd").write_text(cmd, encoding="utf-8")
                    #log_command(bot_name, cmd)
                    self._respond(200, {"ok": True, "msg": f"Encolado para {bot_name}"})

            elif self.path == "/admin/health":
                self._respond(200, sentinel.state)

            elif self.path == "/admin/history":
                history = _load_json(HISTORY_FILE, [])
                self._respond(200, {"history": history})

            elif self.path == "/admin/outputs":
                outputs = _load_json(OUTPUT_FILE, [])
                bot_filter = payload.get("bot")
                if bot_filter:
                    outputs = [o for o in outputs if o.get("bot") == bot_filter]
                limit = payload.get("limit", 20)
                self._respond(200, {"outputs": outputs[:limit]})

            return

        self._respond(404, {"error": "Not Found"})

    def do_GET(self):
        self._respond(200, {"status": "alive", "server": "Heartbeat Sentinel v4.0"})

    def _respond(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def log_message(self, format, *args): pass

# Instancia global única
sentinel = HealthSentinel()

def main():
    logging.info("Iniciando Heartbeat Sentinel v4.0")

    # Iniciar monitor de salud en segundo plano con alta frecuencia (15s)
    def monitor_loop():
        while True:
            try:
                sentinel.check_health()
            except Exception as e:
                logging.error(f"Error en monitor_loop: {e}")
            time.sleep(15)

    threading.Thread(target=monitor_loop, daemon=True).start()

    # Arrancar Servidor
    server = HTTPServer(('0.0.0.0', PORT), HeartbeatHandler)
    server.serve_forever()

if __name__ == "__main__":
    main()