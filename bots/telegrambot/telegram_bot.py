import time
import irc.client
import threading
import re
import fnmatch
from jaraco.stream import buffer
import requests
import os
import json
import sys
import datetime
import configparser
from collections import defaultdict

# ==========================================
# CARGAR CONFIGURACIÓN EXTERNA
# ==========================================
config = configparser.ConfigParser()
config.read('telegram.conf')

# Configuración de Telegram
TELEGRAM_TOKEN = config.get('telegram', 'token')
TELEGRAM_CHAT_ID = config.getint('telegram', 'chat_id')

# Configuración de IRC
IRC_SERVER = config.get('irc', 'server')
IRC_PORT = config.getint('irc', 'port')
IRC_NICKNAME = config.get('irc', 'nickname')
IRC_IDENT = config.get('irc', 'ident')
IRC_REALNAME = config.get('irc', 'realname')
IRC_PASSWORD = config.get('irc', 'password')
IRC_CHANNELS = [channel.strip() for channel in config.get('irc', 'channels').split(',')]

# Base de datos
DB_FILE = config.get('database', 'file')

# Configuración de OpenRouter (IA)
OPENROUTER_KEY = config.get('openrouter', 'api_key', fallback="")
OPENROUTER_MODEL = config.get('openrouter', 'model', fallback="openai/gpt-oss-120b:free")

# Configuración de servidores
servers = [
    {
        "server": IRC_SERVER,
        "port": IRC_PORT,
        "nickname": IRC_NICKNAME,
        "ident": IRC_IDENT,
        "realname": IRC_REALNAME,
        "channels": IRC_CHANNELS
    }
]

# ==========================================
# VARIABLES GLOBALES
# ==========================================
start_time = datetime.datetime.now()
bridge_enabled = True

root_masks = []
ignore_masks = []
bad_words = []
blocked_domains = []

MASK_REGEX = r"^[^!]+![^@]+@\S+$"

server_data = {}
for server_config in servers:
    server_name = server_config["server"]
    server_data[server_name] = {'client': None}

# ==========================================
# PERSISTENCIA (DATABASE.JSON)
# ==========================================
def load_db():
    global root_masks, ignore_masks, bad_words, blocked_domains
    empty_structure = {"root_masks": [], "ignore_masks": [], "bad_words": [], "blocked_domains": []}
    if not os.path.exists(DB_FILE): save_db(empty_structure)
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            root_masks = data.get("root_masks", [])
            ignore_masks = data.get("ignore_masks", [])
            bad_words = data.get("bad_words", [])
            blocked_domains = data.get("blocked_domains", [])
    except: pass

def save_db(data=None):
    if data is None:
        data = {"root_masks": root_masks, "ignore_masks": ignore_masks, "bad_words": bad_words, "blocked_domains": blocked_domains}
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except: pass

# ==========================================
# LÓGICA DE CENSURA (VISUAL)
# ==========================================
def detect_blocked_content(text):
    """Retorna el texto de reemplazo si encuentra algo malo, o None si está limpio."""
    
    # 1. Links - DESHABILITADO (los links se muestran normalmente)
    # url_pattern = r"(https?://\S+|www\.\S+|\b\S+\.(?:com|net|org|io|gg|ly|tv|info|biz|xyz|me|edu|gov|mil|co|es|uk|fr|de|jp|cn)\b)"
    # urls = re.findall(url_pattern, text, re.IGNORECASE)
    # for url in urls:
    #     for domain in blocked_domains:
    #         if domain.lower() in url.lower(): return "[LINK BLOQUEADO]"
    
    # 2. Badwords (Con comodines *)
    text_lower = text.lower()
    for word in bad_words:
        word = word.lower()
        if '*' in word:
            regex_pattern = re.escape(word).replace(r'\*', r'.*')
            if re.search(regex_pattern, text_lower): return "[PALABRA BLOQUEADA]"
        else:
            if re.search(r'\b' + re.escape(word) + r'\b', text_lower): return "[PALABRA BLOQUEADA]"
    return None

# ==========================================
# UTILIDADES
# ==========================================
def strip_mirc_colors(text):
    return re.sub(r"(\x03\d{1,2}(,\d{1,2})?)|[\x02\x1F\x16\x0F]", "", text)

def is_root(mask):
    mask = mask.lower()
    return any(fnmatch.fnmatch(mask, root_mask.lower()) for root_mask in root_masks)

def is_ignored(mask):
    mask = mask.lower()
    return any(fnmatch.fnmatch(mask, ignore_mask.lower()) for ignore_mask in ignore_masks)

def format_user_name(user_dict):
    first_name = user_dict.get("first_name", "Usuario")
    username = user_dict.get("username", "")
    if username: return username.replace("@", "")
    return first_name

def get_uptime():
    delta = datetime.datetime.now() - start_time
    return str(delta).split('.')[0]

def is_telegram_admin(user_id):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getChatMember"
        params = {"chat_id": TELEGRAM_CHAT_ID, "user_id": user_id}
        resp = requests.get(url, params=params, timeout=5)
        if resp.status_code == 200:
            status = resp.json().get("result", {}).get("status", "")
            return status in ["creator", "administrator"]
    except Exception as e:
        print(f"Error Admin Check: {e}")
    return False

# ==========================================
# LÓGICA TELEGRAM (POLLING CON /KB)
# ==========================================
def send_to_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        requests.post(url, data=data, timeout=10)
    except: pass

def call_ia(prompt):
    if not OPENROUTER_KEY:
        return "⚠️ Error: API Key de OpenRouter no configurada."
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [{"role": "user", "content": prompt}]
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        else:
            return f"❌ Error IA ({response.status_code}): {response.text}"
    except Exception as e:
        return f"❌ Error de conexión con IA: {e}"

def telegram_polling():
    last_update_id = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
            params = {"offset": last_update_id + 1, "timeout": 20, "limit": 10}
            response = requests.get(url, params=params, timeout=25)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("ok") and data.get("result"):
                    for update in data["result"]:
                        last_update_id = update["update_id"]
                        if not bridge_enabled: continue
                        
                        if "message" in update:
                            message = update["message"]
                            if message.get("chat", {}).get("id") != TELEGRAM_CHAT_ID: continue
                            if message.get("from", {}).get("is_bot"): continue
                            
                            from_user = message.get("from", {})
                            sender_name = format_user_name(from_user)
                            msg_text = message.get("text", "")

                            # --- COMANDO /KB (KICKBAN) ---
                            if msg_text.lower().startswith("/kb "):
                                if is_telegram_admin(from_user.get("id")):
                                    parts = msg_text.split(" ", 2)
                                    if len(parts) >= 2:
                                        target_nick = parts[1]
                                        reason = parts[2] if len(parts) > 2 else "Expulsado desde Telegram"
                                        for s_conf in servers:
                                            client = server_data[s_conf["server"]]['client']
                                            if client and client.connected:
                                                for chan in s_conf["channels"]:
                                                    try:
                                                        client.mode(chan, f"+b {target_nick}!*@*")
                                                        client.kick(chan, target_nick, reason)
                                                    except: pass
                                        send_to_telegram(f"⛔ {target_nick} ha sido baneado por {sender_name}.")
                                    else:
                                        send_to_telegram("⚠️ Uso: /kb <Nick> [Razón]")
                                continue

                            # --- COMANDO /IA (INTELIGENCIA ARTIFICIAL) ---
                            if msg_text.lower().startswith("/ia "):
                                prompt = msg_text[4:].strip()
                                if prompt:
                                    respuesta = call_ia(prompt)
                                    send_to_telegram(f"🤖 {respuesta}")
                                else:
                                    send_to_telegram("⚠️ Uso: /ia <pregunta>")
                                continue

                            # Procesamiento normal
                            final_text = ""
                            if "text" in message: final_text = message["text"]
                            elif "photo" in message: final_text = "[Foto]"
                            elif "sticker" in message: final_text = "[Sticker]"
                            elif "video" in message: final_text = "[Video]"
                            elif "voice" in message: final_text = "[Audio]"
                            elif "document" in message: final_text = "[Archivo]"
                            else: continue
                            
                            reply_prefix = ""
                            if "reply_to_message" in message:
                                r_user = message["reply_to_message"].get("from", {})
                                r_name = format_user_name(r_user)
                                reply_prefix = f"(Resp. a {r_name}) "
                            
                            blocked_reason = detect_blocked_content(final_text)
                            if blocked_reason: final_text = blocked_reason
                            
                            formatted_msg = f"<{sender_name}> {reply_prefix}{final_text}"
                            send_to_irc_all(formatted_msg)

                        elif "my_chat_member" in update:
                            cm = update["my_chat_member"]
                            u_name = format_user_name(cm.get("from", {}))
                            status = cm.get("new_chat_member", {}).get("status", "")
                            evt_msg = ""
                            if status == "administrator": evt_msg = f"* Bot es Admin gracias a {u_name}"
                            elif status == "member": evt_msg = f"* Bot degradado por {u_name}"
                            elif status == "kicked": evt_msg = f"* Bot expulsado por {u_name}"
                            elif status == "left": evt_msg = f"* Bot salió del grupo"
                            if evt_msg: send_to_irc_all(f"[Telegram] {evt_msg}")

            elif response.status_code == 409: time.sleep(30)
            else: time.sleep(5)
        except: time.sleep(5)

def send_to_irc_all(message):
    if not bridge_enabled: return
    for s_conf in servers:
        client = server_data[s_conf["server"]]['client']
        if client and client.connected:
            for chan in s_conf["channels"]:
                try: client.privmsg(chan, message)
                except: pass

def send_irc_event_to_telegram(message):
    if not bridge_enabled: return
    send_to_telegram(message)

# ==========================================
# EVENTOS IRC (RECEPCIÓN)
# ==========================================
def on_message(client, event):
    try:
        if event.source.nick == client.nickname: return
        user_mask = f"{event.source.nick}!{event.source.user}@{event.source.host}"
        if is_ignored(user_mask): return

        clean_msg = strip_mirc_colors(event.arguments[0])
        send_irc_event_to_telegram(f"<{event.source.nick}> {clean_msg}")
    except Exception as e: print(f"Error on_message: {e}")

def on_action(client, event):
    if event.source.nick == client.nickname: return
    user_mask = f"{event.source.nick}!{event.source.user}@{event.source.host}"
    if is_ignored(user_mask): return
    clean_act = strip_mirc_colors(event.arguments[0])
    send_irc_event_to_telegram(f"* {event.source.nick} {clean_act}")

def on_raw_message(client, event):
    try:
        raw = event.arguments[0] if event.arguments else ""
        if " NOTICE " in raw and " :" in raw:
            parts = raw.split(" NOTICE ", 1)
            source = parts[0].lstrip(":")
            remaining = parts[1]
            target, msg = remaining.split(" :", 1)
            if target.startswith("#") and "!" in source:
                nick = source.split("!")[0]
                if nick == client.nickname: return
                if is_ignored(source): return
                send_irc_event_to_telegram(f"-{nick}- {strip_mirc_colors(msg)}")
    except: pass

def on_join(client, event):
    if event.source.nick == client.nickname: return
    mask = f"{event.source.nick}!{event.source.user}@{event.source.host}"
    if is_ignored(mask): return
    send_irc_event_to_telegram(f"--> {event.source.nick} entró al canal")

def on_part(client, event):
    if event.source.nick == client.nickname: return
    mask = f"{event.source.nick}!{event.source.user}@{event.source.host}"
    if is_ignored(mask): return
    reason = f" ({event.arguments[0]})" if event.arguments else ""
    send_irc_event_to_telegram(f"<-- {event.source.nick} salió {reason}")

def on_quit(client, event):
    if event.source.nick == client.nickname: return
    mask = f"{event.source.nick}!{event.source.user}@{event.source.host}"
    if is_ignored(mask): return
    reason = f" ({event.arguments[0]})" if event.arguments else ""
    send_irc_event_to_telegram(f"<-- {event.source.nick} desconectó {reason}")

def on_nick(client, event):
    if event.source.nick == client.nickname: return
    mask = f"{event.source.nick}!{event.source.user}@{event.source.host}"
    if is_ignored(mask): return
    send_irc_event_to_telegram(f"* {event.source.nick} es ahora {event.target}")

def on_mode(client, event):
    setter = event.source.nick
    target = event.target
    if not target.startswith("#"): return
    modes = " ".join(event.arguments)
    send_irc_event_to_telegram(f"* {setter} puso modo: {modes}")

def on_topic(client, event):
    setter = event.source.nick
    new_topic = event.arguments[0] if event.arguments else "borró el topic"
    send_irc_event_to_telegram(f"* {setter} cambió topic: {new_topic}")

def on_kick(client, event):
    kicker = event.source.nick
    kicked = event.arguments[0]
    reason = event.arguments[1] if len(event.arguments) > 1 else ""
    send_irc_event_to_telegram(f"‼️ {kicked} expulsado por {kicker} ({reason})")
    if kicked.lower() == client.nickname.lower():
        time.sleep(10)
        client.join(event.target)

def on_invite(client, event):
    inviter = event.source.nick
    channel = event.arguments[0]
    send_irc_event_to_telegram(f"* {inviter} invitó al bot a {channel}")

# ==========================================
# COMANDOS PRIVADOS
# ==========================================
def on_privmsg(client, event):
    global bridge_enabled, root_masks, ignore_masks, bad_words, blocked_domains
    
    sender = event.source.nick
    user_mask = f"{event.source.nick}!{event.source.user}@{event.source.host}"
    msg = strip_mirc_colors(event.arguments[0].strip())
    
    if is_ignored(user_mask): return
    if not is_root(user_mask): return

    parts = msg.split()
    if not parts: return
    cmd = parts[0].lower()

    try:
        if cmd == "help":
            help_messages = [
                "\x02--- [ 🤖 COMANDOS DISPONIBLES ] ---\x0F",
                "",
                "\x021. CENSURA DE PALABRAS (bw)\x0F",
                "   Uso: \x02bw add/del <palabra>\x0F",
                "   Ej (Exacta):  bw add tonto   (Solo borra 'tonto')",
                "   Ej (Comodín): bw add *mier* (Borra 'mierda', 'comier', etc)",
                "",
                "\x022. BLOQUEO DE DOMINIOS (domain)\x0F",
                "   Uso: \x02domain add/del <web>\x0F",
                "   Ej (Smart):   domain add xyz   (Bloquea todo .xyz)",
                "   Ej (Exacto):  domain add bit.ly",
                "",
                "\x023. GESTIÓN DE USUARIOS (root/ignore)\x0F",
                "   Uso: \x02root add <nick!ident@host>\x0F",
                "   Ej:  root add Pepe!*@*",
                "",
                "\x024. CONTROL DE BOTS (notify/bot)\x0F",
                "   Uso: \x02notify add/del/list <nick>\x0F",
                "   Ej:  /notify add JuanJo_Jaen",
                "   Uso: \x02bot <NickBot> <comando>\x0F",
                "   Ej:  /bot iND0MiTa !notify list",
                "",
                "\x025. SISTEMA\x0F",
                "   \x02tlg on/off\x0F  :: Activar/Desactivar puente",
                "   \x02status\x0F      :: Ver Uptime y DB",
                "   \x02restart\x0F     :: Reiniciar bot",
                "   \x02listusers\x0F   :: Listar roots"
            ]
            for line in help_messages: client.privmsg(sender, line)
            return

        elif cmd == "status":
            uptime = get_uptime()
            client.privmsg(sender, f"Uptime: {uptime} | DB: {DB_FILE}")
        
        elif cmd == "restart":
            client.privmsg(sender, "🔄 Reiniciando sistema...")
            os.execv(sys.executable, ['python3'] + sys.argv)

        elif cmd == "tlg" and len(parts) > 1:
            if parts[1] == "on":
                bridge_enabled = True
                client.privmsg(sender, "Puente ACTIVADO")
            else:
                bridge_enabled = False
                client.privmsg(sender, "Puente DESACTIVADO")

        elif cmd == "msg" and len(parts) > 2:
            client.privmsg(parts[1], " ".join(parts[2:]))

        elif cmd == "raw" and len(parts) > 1:
            client.send_raw(" ".join(parts[1:]))
            client.privmsg(sender, "Comando Raw enviado.")

        elif cmd == "root" and len(parts) > 2:
            sub = parts[1]
            val = parts[2]
            if sub == "add":
                if val in root_masks: client.privmsg(sender, f"⚠️ Error: {val} YA es root.")
                else:
                    root_masks.append(val)
                    save_db()
                    client.privmsg(sender, f"✅ Root añadido: {val}")
            elif sub == "del":
                if val not in root_masks: client.privmsg(sender, f"⚠️ Error: {val} NO es root.")
                else:
                    root_masks.remove(val)
                    save_db()
                    client.privmsg(sender, f"🗑️ Root eliminado: {val}")

        elif cmd == "ignore" and len(parts) > 2:
            sub = parts[1]
            val = parts[2]
            if sub == "add":
                if val in ignore_masks: client.privmsg(sender, f"⚠️ Error: {val} YA está ignorado.")
                else:
                    ignore_masks.append(val)
                    save_db()
                    client.privmsg(sender, f"✅ Ignorado añadido: {val}")
            elif sub == "del":
                if val not in ignore_masks: client.privmsg(sender, f"⚠️ Error: {val} NO estaba ignorado.")
                else:
                    ignore_masks.remove(val)
                    save_db()
                    client.privmsg(sender, f"🗑️ Ignorado eliminado: {val}")

        elif cmd == "bw" and len(parts) > 2:
            sub = parts[1]
            val = " ".join(parts[2:]).lower()
            if sub == "add":
                if val in bad_words: client.privmsg(sender, f"⚠️ Error: '{val}' YA está en badwords.")
                else:
                    bad_words.append(val)
                    save_db()
                    client.privmsg(sender, f"✅ Palabra censurada: {val}")
            elif sub == "del":
                if val not in bad_words: client.privmsg(sender, f"⚠️ Error: '{val}' NO estaba en badwords.")
                else:
                    bad_words.remove(val)
                    save_db()
                    client.privmsg(sender, f"🗑️ Palabra permitida: {val}")

        elif cmd == "domain" and len(parts) > 2:
            sub = parts[1]
            val = parts[2].lower()
            if "." not in val: val = "." + val
            if sub == "add":
                if val in blocked_domains: client.privmsg(sender, f"⚠️ Error: '{val}' YA está bloqueado.")
                else:
                    blocked_domains.append(val)
                    save_db()
                    client.privmsg(sender, f"✅ Bloqueado: {val}")
            elif sub == "del":
                if val not in blocked_domains: client.privmsg(sender, f"⚠️ Error: '{val}' NO estaba bloqueado.")
                else:
                    blocked_domains.remove(val)
                    save_db()
                    client.privmsg(sender, f"🗑️ Desbloqueado: {val}")

        # === COMANDOS PARA CONTROLAR iND0MiTa (NOTIFY) ===
        elif cmd == "notify" and len(parts) > 1:
            sub = parts[1]
            if sub == "add" and len(parts) > 2:
                nick = parts[2]
                client.privmsg("iND0MiTa", f"PRIVMSG {IRC_CHANNELS[0]} :!notify add {nick}")
                client.privmsg(sender, f"✅ Solicitando a iND0MiTa añadir {nick} a notify...")
            elif sub == "del" and len(parts) > 2:
                nick = parts[2]
                client.privmsg("iND0MiTa", f"PRIVMSG {IRC_CHANNELS[0]} :!notify del {nick}")
                client.privmsg(sender, f"🗑️ Solicitando a iND0MiTa eliminar {nick} de notify...")
            elif sub == "list":
                client.privmsg("iND0MiTa", f"PRIVMSG {IRC_CHANNELS[0]} :!notify list")
                client.privmsg(sender, f"📋 Solicitando lista de notify a iND0MiTa...")
            else:
                client.privmsg(sender, "Uso: /notify add|del|list <nick>")

        # === ENVIAR COMANDO A CUALQUIER BOT ===
        elif cmd == "bot" and len(parts) > 2:
            bot_nick = parts[1]
            comando = " ".join(parts[2:])
            client.privmsg(bot_nick, f"PRIVMSG {IRC_CHANNELS[0]} :{comando}")
            client.privmsg(sender, f"✅ Comando enviado a {bot_nick}: {comando}")

        elif cmd == "listusers": client.privmsg(sender, f"Roots: {', '.join(root_masks)}")
        elif cmd == "listignore": client.privmsg(sender, f"Ignorados: {', '.join(ignore_masks)}")
        elif cmd == "listdomains": client.privmsg(sender, f"Hay {len(blocked_domains)} dominios bloqueados.")
            
    except Exception as e:
        client.privmsg(sender, f"Error ejecutando comando: {e}")

# ==========================================
# CONEXIÓN
# ==========================================
def on_welcome(client, event):
    def join_channels():
        time.sleep(2)
        for channel in client.config['channels']: 
            client.join(channel)
    threading.Thread(target=join_channels, daemon=True).start()

def conectar(config, reactor=None):
    if reactor is None: reactor = irc.client.Reactor()
    try:
        # Autenticación IRC-Hispano con NICK:PASSWORD
        nick_with_password = f"{config['nickname']}:{IRC_PASSWORD}" if IRC_PASSWORD else config["nickname"]
        c = reactor.server().connect(config["server"], config["port"], nick_with_password, ircname=config["realname"], username=config["ident"])
        c.config = config
        server_data[config['server']]['client'] = c
        c.add_global_handler("welcome", on_welcome)
        c.add_global_handler("disconnect", lambda c, e: (time.sleep(10), conectar(config)))
        c.add_global_handler("pubmsg", on_message)
        c.add_global_handler("action", on_action)
        c.add_global_handler("all_raw_messages", on_raw_message)
        c.add_global_handler("join", on_join)
        c.add_global_handler("part", on_part)
        c.add_global_handler("quit", on_quit)
        c.add_global_handler("nick", on_nick)
        c.add_global_handler("mode", on_mode)
        c.add_global_handler("topic", on_topic)
        c.add_global_handler("kick", on_kick)
        c.add_global_handler("invite", on_invite)
        c.add_global_handler("privmsg", on_privmsg)
        threading.Thread(target=reactor.process_forever, daemon=True).start()
        print(f"Conectado a {config['server']}")
    except Exception as e:
        print(f"Error conexión: {e}")
        time.sleep(10)
        conectar(config)

def main():
    load_db()
    irc.client.ServerConnection.buffer_class = buffer.LenientDecodingLineBuffer
    for s_conf in servers: 
        threading.Thread(target=conectar, args=(s_conf,), daemon=True).start()
    time.sleep(1)
    telegram_thread = threading.Thread(target=telegram_polling, daemon=True)
    telegram_thread.start()
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt: print("Cerrando...")

if __name__ == "__main__":
    main()