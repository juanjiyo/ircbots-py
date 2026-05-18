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

BASE_DIR = Path(__file__).parent.parent
STATE_FILE = BASE_DIR / "brain_shared_state.json"
LOG_FILE = BASE_DIR / "brain.log"
CONFIG_PATH = BASE_DIR / "config.json"

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

state = BrainState(STATE_FILE)

# --- UTILIDADES DE MONITOREO ---

def obtener_estado_bots(detailed=False):
    if not detailed:
        res = "🤖 <b>ESTADO DE LOS BOTS</b>\n"
    else:
        res = "🛠️ <b>INFORME TÉCNICO DE SISTEMAS</b>\n"
    
    import paramiko
    
    # 1. PC B (Linux Mint)
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect("192.168.100.37", port=2222, username="juanjo", password="IRCPASSWORD", timeout=5)
        
        bots_pcb = {"iND0MiTa": "falkian.py", "Milenium": "iabot.py"}
        res += "🏠 <b>PC B (Linux Mint):</b>\n"
        if detailed: res += "<pre>"
        
        for name, pat in bots_pcb.items():
            _, stdout, _ = ssh.exec_command(f"ps -eo pcpu,pmem,etime,args | grep -F '{pat}' | grep -v grep")
            out = stdout.read().decode().strip()
            if out:
                parts = out.split()
                cpu, mem, uptime = parts[0], parts[1], parts[2]
                if detailed:
                    res += f"{name:<10} | {cpu:>4}% | {mem:>4}% | {uptime}\n"
                else:
                    res += f"  🟢 {name}\n"
            else:
                res += f"  🔴 {name}: OFFLINE\n"
        
        if detailed: res += "</pre>"
        ssh.close()
    except Exception as e:
        res += f"  ⚠️ Error PC B: {str(e)[:30]}\n"

    # 2. VPS 2 (Remoto)
    try:
        res += "\n☁️ <b>VPS 2 (Remoto):</b>\n"
        if detailed: res += "<pre>"
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect("217.160.136.43", port=22, username="irc", key_filename=str(BASE_DIR / "scripts/wsl_key"), timeout=5)

        bots_vps = {
            "KaBot": "./eggdrop",
            "Heimdall": "./heimdall",
            "Futbot": "futbot.py",
            "Gemini": "gemini.py"
        }

        for name, pat in bots_vps.items():
            _, stdout, _ = ssh.exec_command(f"ps -eo pcpu,pmem,etime,args | grep -F '{pat}' | grep -v grep")
            out = stdout.read().decode().strip()
            if out:
                parts = out.split()
                cpu, mem, uptime = parts[0], parts[1], parts[2]
                if detailed:
                    res += f"{name:<10} | {cpu:>4}% | {mem:>4}% | {uptime}\n"
                else:
                    res += f"  🟢 {name}\n"
            else:
                res += f"  🔴 {name}: OFFLINE\n"

        if detailed: res += "</pre>"
        ssh.close()
    except Exception as e:
        res += f"  ⚠️ Error VPS 2: {str(e)[:30]}\n"

    if detailed:
        res += f"\n🛰️ <b>Hilos</b>: 3 Activos"
    return res

# --- IA GATEWAY (vía Central Hub) ---

def get_ia_response(user_text, context_info, hemisphere):
    # Prompt especializado por Hemisferio
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
    
    # Delegar al Hub Centralizado
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
    # SIEMPRE Día antes que Año: DD/MM/YYYY
    t = time.strftime('%d/%m/%Y %H:%M:%S')
    full_msg = f"[{t}] {msg}"
    print(full_msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(full_msg + "\n")
    sys.stdout.flush()

def send_to_telegram(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try: requests.post(url, json=payload, timeout=10)
    except: pass

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

    # Contexto para la IA
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

                            if hemisphere == "right" and text.startswith("!recordar"):
                                import re
                                match = re.match(r"!recordar\s+(\d+)([smhd]?)\s+(.+)", text, re.IGNORECASE)
                                if match:
                                    qty = int(match.group(1))
                                    unit = match.group(2).lower() or "m"
                                    rem_text = match.group(3)
                                    mult = {"s": 1/60, "m": 1, "h": 60, "d": 1440}
                                    mins = qty * mult.get(unit, 1)
                                    state.add_reminder(user, mins, rem_text)
                                    send_to_telegram(token, chat_id, f"✅ <b>OK</b> @{user}, te lo recordaré en {qty}{unit}.")
                                    continue

                            if hemisphere == "left" and text.startswith("!avisa "):
                                alert_msg = text[7:].strip()
                                state.add_alert(f"Mensaje de @{user}: {alert_msg}")
                                send_to_telegram(token, chat_id, "🚀 <b>Mensaje enviado</b> al Hemisferio Derecho.")
                                continue

                            if lower_text == "!estado_bots":
                                is_detailed = (hemisphere == "left")
                                status_msg = obtener_estado_bots(detailed=is_detailed)
                                send_to_telegram(token, chat_id, status_msg)
                                continue

                            if not state.is_muted(hemisphere):
                                response_text, label = get_ia_response(text, get_nodes_info(), hemisphere)
                                
                                if hemisphere == "left" and "```ticket" in response_text:
                                    import re
                                    ticket_match = re.search(r"```ticket\nFILE:\s*([^\n]+)\n(.*?)\n```", response_text, re.DOTALL | re.IGNORECASE)
                                    if ticket_match:
                                        filename = ticket_match.group(1).strip().replace(" ", "_").lower()
                                        if not filename.endswith(".md"): filename += ".md"
                                        ticket_content = ticket_match.group(2).strip()
                                        
                                        try:
                                            ticket_dir = BASE_DIR / "tickets"
                                            ticket_dir.mkdir(exist_ok=True)
                                            ticket_path = ticket_dir / filename
                                            ticket_path.write_text(ticket_content, encoding='utf-8')
                                            response_text = re.sub(r"```ticket\n.*?\n```", f"\n\n<i>🎫 Tarea documentada y guardada como <b>{filename}</b>. Lista para que el Agente Local la ejecute.</i>", response_text, flags=re.DOTALL | re.IGNORECASE)
                                        except Exception as e:
                                            log(f"Error guardando ticket: {e}")

                                send_to_telegram(token, chat_id, f"🧠 <b>[{label}]</b>\n{response_text}")
            
            time.sleep(1)
        except Exception as e:
            log(f"❌ Error en worker {h_name}: {e}")
            time.sleep(5)

# --- SISTEMA CENTINELA (WATCHDOG) ---

def sentinel_worker():
    """Hilo encargado de vigilar la salud de los bots y reiniciarlos si caen."""
    log("🕵️ Hilo Centinela unificado activado. Vigilancia en tiempo real (10s).")
    
    restart_commands = {
        "iND0MiTa": {"node": "pcb", "cmd": "cd ~/ircbots/bots/indomita && nohup python3 falkian.py > falkian.log 2>&1 &"},
        "Milenium": {"node": "pcb", "cmd": "cd ~/ircbots/bots/milenium && nohup python3 iabot.py > iabot.log 2>&1 &"},
        "KaBot":    {"node": "vps2", "cmd": "cd ~/eggdrop && ./eggdrop eggdrop.conf"},
        "Heimdall": {"node": "vps2", "cmd": "cd ~/heimdall && ./heimdall eggdrop.conf"},
        "Futbot":   {"node": "vps2", "cmd": "cd ~/futbot && screen -dmS Futbol python3 futbot.py"},
        "Gemini":   {"node": "vps2", "cmd": "cd ~/gemini && screen -dmS Gemini python3 gemini.py"}
    }
    
    max_restarts = 3
    restart_counts = {bot: 0 for bot in restart_commands}
    
    while True:
        try:
            import paramiko
            # 1. Chequeo PC B
            try:
                ssh_pcb = paramiko.SSHClient()
                ssh_pcb.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh_pcb.connect("192.168.100.37", port=2222, username="juanjo", password="IRCPASSWORD", timeout=5)
                
                for bot in ["iND0MiTa", "Milenium"]:
                    pat = restart_commands[bot]["cmd"].split("python3 ")[1].split()[0]
                    _, stdout, _ = ssh_pcb.exec_command(f"ps aux | grep '{pat}' | grep -v grep")
                    if not stdout.read().decode().strip():
                        if restart_counts[bot] < max_restarts:
                            restart_counts[bot] += 1
                            log(f"⚠️ Centinela: {bot} CAÍDO en PC B. Reinicio #{restart_counts[bot]}")
                            ssh_pcb.exec_command(restart_commands[bot]["cmd"])
                            send_to_telegram(TOKEN_LEFT, CHAT_ID_LEFT, f"🚨 <b>[CENTINELA]</b> {bot} caído en PC B. Reintentando ({restart_counts[bot]}/{max_restarts})")
                        else:
                            log(f"❌ Centinela: {bot} alcanzó límite de reinicios en PC B.")
                            send_to_telegram(TOKEN_LEFT, CHAT_ID_LEFT, f"💀 <b>[ERROR CRÍTICO]</b> {bot} no arranca tras {max_restarts} intentos.")
                    else:
                        restart_counts[bot] = 0
                ssh_pcb.close()
            except: pass

            time.sleep(60)
        except Exception as e:
            log(f"❌ Error en Centinela: {e}")
            time.sleep(60)

# --- PUNTO DE ENTRADA ---

def main():
    log("🚀 Iniciando Arquitectura de Cerebro Dual...")
    
    # Rutas de offsets
    off_left = BASE_DIR / "brain_offset_left.json"
    off_right = BASE_DIR / "brain_offset_right.json"

    # Lanzar hilos
    t_left = threading.Thread(target=hemisphere_worker, args=(TOKEN_LEFT, CHAT_ID_LEFT, "left", off_left), daemon=True)
    t_right = threading.Thread(target=hemisphere_worker, args=(TOKEN_RIGHT, CHAT_ID_RIGHT, "right", off_right), daemon=True)
    t_sentinel = threading.Thread(target=sentinel_worker, daemon=True)

    t_left.start()
    t_right.start()
    t_sentinel.start()

    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        log("🛑 Apagando Cerebro...")

if __name__ == "__main__":
    main()
