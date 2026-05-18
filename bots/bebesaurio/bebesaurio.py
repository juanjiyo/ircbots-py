import irc.client
import json
import time
import threading
import urllib.request
from datetime import datetime
from pathlib import Path
from jaraco.stream import buffer

# --- CONFIGURACIÓN ---
SERVER   = "irc.chatzona.org"
PORT     = 6667
NICK     = "BeBeSaUrIo"
PASSWORD = "IRCPASSWORD"
REPORT_CHAN = "#Limbo"
WATCH_CHANS = ["#España", "#ChatZona", "#Amistad", "#mexico", "#chateagratis.net", "#Canalchat", "#latinos"] 

# La base de datos ahora está en la misma carpeta que el script
DB_FILE = Path(__file__).parent / "ident_history.json"

class IdentWatcher(irc.client.SimpleIRCClient):
    def __init__(self):
        super().__init__()
        self.db = {} 
        self.online_now = {} 
        self.geo_cache = {} 
        self.msg_queue = [] # Cola de mensajes para evitar flood
        self.last_msg_ts = 0
        self.load_db()
        # Hilo para procesar la cola de mensajes
        threading.Thread(target=self.queue_worker, daemon=True).start()

    def load_db(self):
        if DB_FILE.exists():
            try:
                self.db = json.loads(DB_FILE.read_text(encoding="utf-8"))
            except: self.db = {}

    def save_db(self):
        try:
            DB_FILE.parent.mkdir(parents=True, exist_ok=True)
            DB_FILE.write_text(json.dumps(self.db, indent=2, ensure_ascii=False), encoding="utf-8")
        except: pass

    def queue_worker(self):
        """Envía mensajes de la cola respetando un tiempo mínimo entre ellos."""
        while True:
            if self.msg_queue:
                ahora = time.time()
                if ahora - self.last_msg_ts > 2.0: # 1 mensaje cada 2 segundos máximo
                    msg = self.msg_queue.pop(0)
                    try:
                        self.connection.privmsg(REPORT_CHAN, msg)
                        self.last_msg_ts = ahora
                    except: pass
            time.sleep(0.5)

    def enqueue(self, msg):
        """Añade un mensaje a la cola."""
        if len(self.msg_queue) < 50: # Límite de seguridad para no acumular basura
            self.msg_queue.append(msg)

    def get_country(self, host):
        if host in self.geo_cache: return self.geo_cache[host]
        try:
            url = f"http://ip-api.com/json/{host}?fields=countryCode"
            with urllib.request.urlopen(url, timeout=2) as response:
                data = json.loads(response.read().decode())
                code = data.get("countryCode", "??")
                self.geo_cache[host] = code
                return code
        except: return "??"

    def on_welcome(self, connection, event):
        print(f"[*] BeBeSaUrIo conectado y listo.")
        connection.privmsg("NiCK", f"IDENTIFY {PASSWORD}")
        threading.Timer(5.0, self.join_channels, args=[connection]).start()

    def join_channels(self, connection):
        connection.join(REPORT_CHAN)
        for chan in WATCH_CHANS:
            connection.join(chan)
            connection.who(chan)

    def on_whoreply(self, connection, event):
        ident, nick, host = event.arguments[1], event.arguments[4], event.arguments[2]
        if nick.lower() == NICK.lower(): return
        if ident not in self.online_now: self.online_now[ident] = set()
        self.online_now[ident].add(nick)
        if ident not in self.db:
            self.db[ident] = [{"nick": nick, "host": host, "last": "INIT"}]
        else:
            if not any(e["nick"].lower() == nick.lower() and e["host"].lower() == host.lower() for e in self.db[ident]):
                self.db[ident].append({"nick": nick, "host": host, "last": "INIT"})

    def on_join(self, connection, event):
        nick    = event.source.nick
        ident   = event.source.user
        host    = event.source.host
        ahora   = datetime.now().strftime("%H:%M")
        if nick.lower() == NICK.lower(): return

        # 1. Registro y Presencia
        if ident not in self.online_now: self.online_now[ident] = set()
        
        # Alerta Duplicado Activo (Solo si no es un Ident masivo)
        if len(self.online_now[ident]) >= 1 and nick not in self.online_now[ident]:
            if len(self.online_now[ident]) < 5: # Si hay más de 5, ignoramos (pasarela pública)
                otros = ", ".join(self.online_now[ident])
                self.enqueue(f"\x0304[DUPLICADO-ACTIVO]\x03 Ident: \x02{ident}\x02 en uso por: \x0312{nick}\x03 y \x0312{otros}\x03")
        
        self.online_now[ident].add(nick)

        # 2. Análisis de Historial
        if ident not in self.db:
            self.db[ident] = [{"nick": nick, "host": host, "last": ahora}]
            return
        
        entries = self.db[ident]
        
        # Si ya conocemos esta combinación exacta, fuera.
        if any(e["nick"].lower() == nick.lower() and e["host"].lower() == host.lower() for e in entries):
            return

        # Solo avisamos si es un SHARED-ID real (IP y Nick nuevos para este Ident)
        # Ignoramos si el Ident ya tiene demasiadas entradas (pasarela pública)
        if len(entries) < 8:
            match_host = any(e["host"].lower() == host.lower() for e in entries)
            match_nick = any(e["nick"].lower() == nick.lower() for e in entries)
            
            if not match_host and not match_nick:
                pais = self.get_country(host)
                self.enqueue(f"\x0304[SHARED-ID]\x03 [\x02{pais}\x02] Ident: \x02{ident}\x02 | Conflicto: \x0312{nick}\x03 (\x0314{host}\x03)")

        entries.append({"nick": nick, "host": host, "last": ahora})
        self.save_db()

    def _remove_online(self, nick):
        for i in list(self.online_now.keys()):
            self.online_now[i].discard(nick)

    def on_part(self, connection, event): self._remove_online(event.source.nick)
    def on_quit(self, connection, event): self._remove_online(event.source.nick)
    def on_kick(self, connection, event): self._remove_online(event.arguments[0])
    def on_nick(self, connection, event):
        old, new = event.source.nick, event.target
        for i in self.online_now:
            if old in self.online_now[i]:
                self.online_now[i].discard(old)
                self.online_now[i].add(new)

    def on_disconnect(self, connection, event):
        time.sleep(15)
        self.conectar()

    def conectar(self):
        irc.client.ServerConnection.buffer_class = buffer.LenientDecodingLineBuffer
        self.connect(SERVER, PORT, NICK)

if __name__ == "__main__":
    watcher = IdentWatcher()
    watcher.conectar()
    watcher.reactor.process_forever()
