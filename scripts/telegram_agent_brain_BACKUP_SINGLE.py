import requests
import time
import json
import os
import sys
from pathlib import Path

# --- CONFIGURACIÓN ---
TOKEN = "TELEGRAM_TOKEN"
CHAT_ID = "-1003348942954"

# Claves
NVIDIA_KEY = "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"
OR_KEY = "OPENROUTER_API_KEY"

# Jerarquía NVIDIA NIM (Primaria)
NIM_MODELS = [
    {"id": "meta/llama-3.3-70b-instruct", "label": "NIM Llama 3.3"},
    {"id": "qwen/qwen3.5-397b-a17b", "label": "NIM Qwen 3.5 (Max)"}
]

# Jerarquía OpenRouter FREE (Secundaria - Switch)
OR_MODELS = [
    {"id": "meta-llama/llama-3.3-70b-instruct:free", "label": "OR Llama 3.3 Free"},
    {"id": "google/gemma-3-27b-it:free", "label": "OR Gemma 3 Free"},
    {"id": "openrouter/auto", "label": "OR Auto (Fallback Final)"}
]

BASE_DIR = Path(r"C:\Users\WinterOS\Documents\ircbots")
CONFIG_PATH = BASE_DIR / "config.json"
OFFSET_FILE = BASE_DIR / "brain_offset.json"
MUTE_FILE = BASE_DIR / "brain_mute.json"
REMINDERS_FILE = BASE_DIR / "brain_reminders.json"

# --- GESTIÓN DE ESTADO ---
class BrainState:
    def __init__(self):
        self.is_muted = False
        self.reminders = []
        self._load()

    def _load(self):
        if MUTE_FILE.exists():
            try: self.is_muted = json.loads(MUTE_FILE.read_text())["muted"]
            except: pass
        if REMINDERS_FILE.exists():
            try: self.reminders = json.loads(REMINDERS_FILE.read_text())
            except: pass

    def save(self):
        MUTE_FILE.write_text(json.dumps({"muted": self.is_muted}))
        REMINDERS_FILE.write_text(json.dumps(self.reminders))

    def add_reminder(self, user, minutes, text):
        target_time = time.time() + (minutes * 60)
        self.reminders.append({
            "user": user,
            "time": target_time,
            "text": text
        })
        self.save()

    def check_reminders(self):
        now = time.time()
        due = [r for r in self.reminders if r["time"] <= now]
        self.reminders = [r for r in self.reminders if r["time"] > now]
        if due: self.save()
        return due

state = BrainState()

# Estado del Switch Interno
class ProviderSwitch:
    def __init__(self):
        self.provider = "NVIDIA"  # Empezamos con el mejor
        self.last_check = 0
        self.cooldown = 300 # 5 minutos para re-intentar NVIDIA tras fallo

    def fail_nvidia(self):
        print("🔴 [SWITCH] NVIDIA NIM saturado/caído. Conmutando a OpenRouter...")
        self.provider = "OPENROUTER"
        self.last_check = time.time()

    def check_recovery(self):
        if self.provider == "OPENROUTER" and (time.time() - self.last_check > self.cooldown):
            print("🟢 [SWITCH] Probando recuperación de NVIDIA NIM...")
            self.provider = "NVIDIA"

switch = ProviderSwitch()

LOG_FILE = BASE_DIR / "brain.log"

def log(msg):
    t = time.strftime('%H:%M:%S')
    full_msg = f"[{t}] {msg}"
    print(full_msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(full_msg + "\n")
    sys.stdout.flush()

def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    try: requests.post(url, json=payload, timeout=10)
    except: pass

def get_ia_response(user_text, context_info):
    switch.check_recovery()

    # --- NIVEL 1: NVIDIA NIM ---
    if switch.provider == "NVIDIA":
        for entry in NIM_MODELS:
            try:
                url = "https://integrate.api.nvidia.com/v1/chat/completions"
                headers = {"Authorization": f"Bearer {NVIDIA_KEY}", "Content-Type": "application/json"}
                payload = {
                    "model": entry["id"],
                    "messages": [
                        {"role": "system", "content": f"Eres el Cerebro Central. Contexto: {context_info}"},
                        {"role": "user", "content": user_text}
                    ],
                    "max_tokens": 1000, "temperature": 0.2
                }
                resp = requests.post(url, headers=headers, json=payload, timeout=25)
                if resp.status_code == 200:
                    return resp.json()["choices"][0]["message"]["content"], entry["label"]
                elif resp.status_code in [429, 502, 503, 504]:
                    log(f"⚠️ NVIDIA {entry['label']} falló ({resp.status_code}).")
                    continue
            except: continue
        
        # Si llegamos aquí y el proveedor era NVIDIA, es que todos sus modelos fallaron
        switch.fail_nvidia()

    # --- NIVEL 2: OPENROUTER ---
    for entry in OR_MODELS:
        try:
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {"Authorization": f"Bearer {OR_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": entry["id"],
                "messages": [{"role": "user", "content": f"Contexto: {context_info}\n\nOrden: {user_text}"}],
                "max_tokens": 800
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=20)
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"], entry["label"]
        except: continue

    return "❌ Error total: Ecosistema de IA incomunicado.", "Error"

def main():
    last_update_id = 0
    if OFFSET_FILE.exists():
        try: last_update_id = json.loads(OFFSET_FILE.read_text())["offset"]
        except: pass

    log("🧠 Cerebro Central con Switch Inteligente activo...")
    send_to_telegram("⚡ <b>[SISTEMA]</b> Cerebro Central re-calibrado y operativo. Listo para procesar órdenes con precisión quirúrgica.")
    with open(CONFIG_PATH, 'r') as f: nodes_info = f.read()

    while True:
        try:
            # 1. Verificar recordatorios
            due = state.check_reminders()
            for r in due:
                send_to_telegram(f"⏰ <b>RECORDATORIO</b>\nHola @{r['user']}, me pediste que te recordara: <i>{r['text']}</i>")

            # 2. Obtener actualizaciones
            url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
            resp = requests.get(url, params={"offset": last_update_id + 1, "timeout": 30}, timeout=35)
            if resp.status_code == 200:
                data = resp.json()
                for update in data.get("result", []):
                    last_update_id = update["update_id"]
                    OFFSET_FILE.write_text(json.dumps({"offset": last_update_id}))
                    if "message" in update and "text" in update["message"]:
                        msg = update["message"]
                        text = msg["text"].strip()
                        user = msg.get("from", {}).get("username", "usuario")
                        
                        if str(msg["chat"]["id"]) == CHAT_ID:
                            log(f"📩 Telegram (@{user}): {text}")

                            # --- COMANDOS INTERNOS ---
                            lower_text = text.lower()
                            
                            if lower_text in ["!silencio", "!mute", "cállate", "shutup"]:
                                state.is_muted = True
                                state.save()
                                send_to_telegram("🔇 <b>Silenciado</b>. No responderé hasta que me despiertes con <code>!habla</code>.")
                                continue
                            
                            if lower_text in ["!habla", "!unmute", "despierta"]:
                                state.is_muted = False
                                state.save()
                                send_to_telegram("🔊 <b>Reactivado</b>. ¿En qué puedo ayudarte?")
                                continue

                            if text.startswith("!recordar"):
                                # Formato: !recordar 10m comprar pan
                                import re
                                match = re.match(r"!recordar\s+(\d+)([smhd]?)\s+(.+)", text, re.IGNORECASE)
                                if match:
                                    qty = int(match.group(1))
                                    unit = match.group(2).lower() or "m"
                                    rem_text = match.group(3)
                                    
                                    # Convertir a minutos
                                    mult = {"s": 1/60, "m": 1, "h": 60, "d": 1440}
                                    mins = qty * mult.get(unit, 1)
                                    
                                    state.add_reminder(user, mins, rem_text)
                                    send_to_telegram(f"✅ <b>OK</b> @{user}, te lo recordaré en {qty}{unit}.")
                                else:
                                    send_to_telegram("❌ Formato: <code>!recordar [tiempo][s|m|h|d] [mensaje]</code>\nEjemplo: <code>!recordar 15m sacar la pizza</code>")
                                continue

                            # --- RESPUESTA IA (Si no está silenciado) ---
                            if not state.is_muted:
                                response_text, label = get_ia_response(text, nodes_info)
                                send_to_telegram(f"🧠 <b>[{label}]</b>\n{response_text}")
            
            time.sleep(1)
        except Exception as e:
            log(f"❌ Error en bucle: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
