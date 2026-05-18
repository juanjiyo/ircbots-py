import requests
import time
import json
import os
import sys
import site
sys.path.append(site.USER_SITE)
import threading
from pathlib import Path
from ia_central import hub as ai_hub

# --- CONFIGURACIÓN ---

# Hemisferio Derecho (Asistente Personal)
TOKEN_RIGHT = "TELEGRAM_TOKEN"
CHAT_ID_RIGHT = "-1003348942954"

# Hemisferio Izquierdo (Programación / Técnico)
TOKEN_LEFT = "TELEGRAM_TOKEN_C2" 
CHAT_ID_LEFT = "-1003808302723"

# Rutas en el VPS Panel
BASE_DIR = Path("/home/irc/ircbots")
SCRIPTS_DIR = BASE_DIR / "scripts"
STATE_FILE = SCRIPTS_DIR / "health_state.json"  # Generado por heartbeat_server.py
BRAIN_STATE_FILE = BASE_DIR / "brain_shared_state.json"
LOG_FILE = BASE_DIR / "logs/brain.log"
CONFIG_PATH = BASE_DIR / "AGENTS_COOP/GLOBAL_AI_HUB.json"

# --- ESTADO GLOBAL ---

class BrainState:
    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        self.data = self._load()

    def _load(self):
        if self.path.exists():
            try: return json.loads(self.path.read_text())
            except: pass
        return {"muted": {"left": False, "right": False}, "reminders": [], "alerts": []}

    def save(self):
        self.path.write_text(json.dumps(self.data))

    def is_muted(self, hemisphere):
        return self.data["muted"].get(hemisphere, False)

    def set_mute(self, hemisphere, value):
        with self.lock:
            self.data["muted"][hemisphere] = value
        self.save()

    def add_reminder(self, user, minutes, text):
        with self.lock:
            self.data["reminders"].append({
                "user": user,
                "text": text,
                "time": time.time() + (minutes * 60)
            })
        self.save()

    def check_reminders(self):
        now = time.time()
        with self.lock:
            due = [r for r in self.data["reminders"] if r["time"] <= now]
            self.data["reminders"] = [r for r in self.data["reminders"] if r["time"] > now]
        if due: self.save()
        return due

    def add_alert(self, msg):
        """Añade una alerta para que el Hemisferio Derecho la notifique."""
        with self.lock:
            self.data["alerts"].append({"msg": msg, "time": time.time()})
        self.save()

    def get_alerts(self):
        with self.lock:
            alerts = self.data["alerts"]
            self.data["alerts"] = []
        if alerts: self.save()
        return alerts

state = BrainState(BRAIN_STATE_FILE)

# --- UTILIDADES DE MONITOREO (C2 NATIVE) ---

def obtener_estado_bots(detailed=False):
    if not detailed:
        res = "🤖 <b>ESTADO DE LOS BOTS (C2)</b>\n"
    else:
        res = "🛠️ <b>INFORME TÉCNICO DE SISTEMAS (C2 Native)</b>\n"

    try:
        if not STATE_FILE.exists():
            return "⚠️ Error: No se encuentra el archivo de estado C2."
            
        state_data = json.loads(STATE_FILE.read_text())
        
        res += "🛰️ <b>Agentes en PC B:</b>\n"
        if detailed: res += "<pre>"

        for name, data in state_data.get("bots", {}).items():
            status = data.get("status", "UNKNOWN")
            ts_str = data.get("time_str", "N/A")
            icon = "🟢" if status == "ONLINE" else "🔴"
            if detailed:
                res += f"{name:<10} | {status:<8} | {ts_str}\n"
            else:
                res += f"  {icon} {name} ({status})\n"

        if detailed: res += "</pre>"
    except Exception as e:
        res += f"  ⚠️ Error C2 State: {str(e)[:30]}\n"

    return res

# --- IA GATEWAY (vía Central Hub) ---

def get_ia_response(user_text, context_info, hemisphere):
    if hemisphere == "right":
        sys_prompt = "Eres el Hemisferio Derecho del Cerebro de Juanjo. Eres creativo, empático y servicial. Responde de forma amable y concisa."
    else:
        sys_prompt = """Eres el Hemisferio Izquierdo del Cerebro de Juanjo. Eres un Ingeniero de Software Senior. Técnico y directo.
IMPORTANTE: Si te piden una solución técnica, DEBES generar un ticket de trabajo al final de tu respuesta con este formato:
```ticket
FILE: nombre.md
TÍTULO: Resumen
ACCIÓN: Instrucciones
CÓDIGO:
[código]
```"""

    prompt_final = f"Contexto del sistema: {context_info}\n\nMensaje del usuario: {user_text}"

    response_text, provider_label = ai_hub.call_ai(
        prompt=prompt_final,
        system_prompt=sys_prompt,
        category="chat",
        max_tokens=1000,
        timeout=30
    )

    if response_text:
        return response_text, provider_label

    return "Lo siento, el trío de IAs está saturado. Reintenta en unos instantes.", "FALLBACK"

# --- WORKER DE HEMISFERIO ---

def log(msg):
    t = time.strftime('%d/%m/%Y %H:%M:%S')
    full_msg = f"[{t}] {msg}"
    print(full_msg)
    LOG_FILE.parent.mkdir(exist_ok=True, parents=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(full_msg + "\n")
    sys.stdout.flush()

def send_to_telegram(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try: requests.post(url, json=payload, timeout=10)
    except Exception as e:
        log(f"Error enviando a Telegram: {e}")

def hemisphere_worker(token, chat_id, hemisphere, offset_file):
    last_update_id = 0
    if offset_file.exists():
        try: last_update_id = json.loads(offset_file.read_text())["offset"]
        except: pass

    h_name = "DERECHO" if hemisphere == "right" else "IZQUIERDO"
    log(f"🧠 Hemisferio {h_name} iniciado...")

    # Informe de inicio
    if hemisphere == "left":
        status_report = obtener_estado_bots(detailed=True)
        send_to_telegram(token, chat_id, status_report)

    def get_nodes_info():
        try: return CONFIG_PATH.read_text(encoding='utf-8')
        except: return "No hay info de nodos disponible."

    while True:
        try:
            if hemisphere == "right":
                due = state.check_reminders()
                for r in due:
                    send_to_telegram(token, chat_id, f"⏰ <b>RECORDATORIO</b>\nHola @{r['user']}, me pediste que te recordara: <i>{r['text']}</i>")

                alerts = state.get_alerts()
                for a in alerts:
                    send_to_telegram(token, chat_id, f"⚠️ <b>ALERTA DEL INGENIERO</b>\n{a['msg']}")

            url = f"https://api.telegram.org/bot{token}/getUpdates"
            resp = requests.get(url, params={"offset": last_update_id + 1, "timeout": 20}, timeout=25)
            if resp.status_code == 200:
                data = resp.json()
                for update in data.get("result", []):
                    last_update_id = update["update_id"]
                    offset_file.write_text(json.dumps({"offset": last_update_id}))

                    if "message" in update and "text" in update["message"]:
                        msg = update["message"]
                        text = msg["text"].strip()
                        user = msg.get("from", {}).get("username", "usuario")
                        cid = str(msg["chat"]["id"])

                        if cid == chat_id:
                            log(f"📩 [{h_name}] @{user}: {text}")

                            lower_text = text.lower()

                            if lower_text in ["!silencio", "!mute", "cállate"]:
                                state.set_mute(hemisphere, True)
                                send_to_telegram(token, chat_id, "🔇 <b>Silenciado</b> localmente.")
                                continue

                            if lower_text in ["!habla", "!unmute", "despierta"]:
                                state.set_mute(hemisphere, False)
                                send_to_telegram(token, chat_id, "🔊 <b>Reactivado</b>. ¿En qué puedo ayudarte?")
                                continue

                            if lower_text == "!estado_bots":
                                is_detailed = (hemisphere == "left")
                                status_msg = obtener_estado_bots(detailed=is_detailed)
                                send_to_telegram(token, chat_id, status_msg)
                                continue

                            if not state.is_muted(hemisphere):
                                response_text, label = get_ia_response(text, get_nodes_info(), hemisphere)
                                send_to_telegram(token, chat_id, f"🧠 <b>[{label}]</b>\n{response_text}")

            time.sleep(1)
        except Exception as e:
            log(f"❌ Error en worker {h_name}: {e}")
            time.sleep(5)

# --- PUNTO DE ENTRADA ---

def main():
    log("🚀 Iniciando Arquitectura de Cerebro Dual (C2 Native)...")

    off_left = BASE_DIR / "scripts/brain_offset_left.json"
    off_right = BASE_DIR / "scripts/brain_offset_right.json"

    t_left = threading.Thread(target=hemisphere_worker, args=(TOKEN_LEFT, CHAT_ID_LEFT, "left", off_left), daemon=True)
    t_right = threading.Thread(target=hemisphere_worker, args=(TOKEN_RIGHT, CHAT_ID_RIGHT, "right", off_right), daemon=True)

    t_left.start()
    t_right.start()

    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        log("🛑 Apagando Cerebro...")

if __name__ == "__main__":
    main()
