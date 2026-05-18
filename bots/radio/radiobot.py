import sys
import io
import time
import logging
import os
import re
import threading
import requests
import irc.client
import irc.connection
import json
import configparser
from datetime import datetime
from typing import Dict, List, Optional, Any
from jaraco.stream import buffer

# Forzar codificación UTF-8 para evitar errores con emojis en Windows
if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except:
        pass

# ============================ CONFIGURACIÓN ============================

class RadioBot:
    def __init__(self, config_file: str):
        self.config = configparser.ConfigParser()
        self.config.read(config_file, encoding='utf-8')
        
        # IRC
        self.server = self.config.get('irc', 'server')
        self.port = self.config.getint('irc', 'port')
        self.nickname = self.config.get('irc', 'nickname')
        self.password = self.config.get('irc', 'password', fallback=None)
        self.ident = self.config.get('irc', 'ident', fallback='RadioBot')
        self.realname = self.config.get('irc', 'realname', fallback='RadioBot')
        self.channels = [c.strip() for c in self.config.get('irc', 'channels').split(',')]
        
        # Radio
        self.radio_ip = self.config.get('radio', 'ip')
        self.radio_port = self.config.get('radio', 'port')
        self.radio_name = self.config.get('radio', 'name')
        self.radio_web = self.config.get('radio', 'web')
        self.radio_player = self.config.get('radio', 'player')
        self.announce_interval = self.config.getint('radio', 'announce_interval', fallback=2700)
        
        # Permisos
        self.roots = [r.strip() for r in self.config.get('admins', 'roots').split(',')]
        
        # Estado
        self.emision = "AutoDJ"
        self.peticiones_abiertas = False
        self.current_song = "Cargando..."
        self.listeners = 0
        self.peak_listeners = 0
        self.max_listeners = 100
        self.online = False
        
        # Persistencia
        self.data_dir = os.path.join(os.path.dirname(config_file), "data")
        self.djs = self.load_data("djs.json")
        self.admins = self.load_data("admins.json")
        self.fans = self.load_data("fans.json")
        self.peticiones = self.load_data("peticiones.json")
        self.parrilla = self.load_data("parrilla.json")
        
        # IRC Client
        self.reactor = irc.client.Reactor()
        self.connection = None
        
        # Registrar handlers una sola vez en el reactor
        self.reactor.add_global_handler("welcome", self.on_welcome)
        self.reactor.add_global_handler("disconnect", self.on_disconnect)
        self.reactor.add_global_handler("privmsg", self.on_privmsg)
        self.reactor.add_global_handler("pubmsg", self.on_pubmsg)
        
        # Logging
        log_path = os.path.join(os.path.dirname(config_file), "radiobot.log")
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_path, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger("RadioBot")

    def load_data(self, filename: str) -> Any:
        path = os.path.join(self.data_dir, filename)
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return [] if "json" in filename else {}
        return [] if "json" in filename else {}

    def save_data(self, filename: str, data: Any):
        path = os.path.join(self.data_dir, filename)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    # ---------------------------- LÓGICA RADIO ----------------------------

    def update_metadata(self):
        """Consulta el archivo /7.html del servidor Shoutcast."""
        url = f"http://{self.radio_ip}:{self.radio_port}/7.html"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        try:
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                # El formato es: listeners,connected,peak,max,unique,bitrate,song_title
                content = response.text.replace('<html><body>', '').replace('</body></html>', '').strip()
                parts = content.split(',')
                if len(parts) >= 7:
                    self.online = parts[1] == "1"
                    self.listeners = int(parts[0])
                    self.peak_listeners = int(parts[2])
                    self.max_listeners = int(parts[3])
                    new_song = ",".join(parts[6:]) # Por si el titulo tiene comas
                    
                    if new_song != self.current_song and self.online:
                        self.current_song = new_song
                        self.on_song_change()
                else:
                    self.online = False
            else:
                self.online = False
        except Exception as e:
            # self.logger.error(f"Error consultando radio: {e}")
            self.online = False

    def on_song_change(self):
        self.logger.info(f"Nueva canción: {self.current_song}")
        if self.connection and self.connection.is_connected():
            msg = f"\x0301,04[ \x0315{self.radio_name} \x0301,04]\x03 \x02\x0301Sonando:\x03\x02 \x0304{self.current_song}\x03"
            for channel in self.channels:
                self.connection.privmsg(channel, msg)

    def radio_worker(self):
        """Hilo secundario para checkear la radio periódicamente."""
        while True:
            self.update_metadata()
            time.sleep(15)

    def announce_worker(self):
        """Hilo secundario para anuncios periódicos."""
        while True:
            time.sleep(self.announce_interval)
            if self.connection and self.connection.is_connected():
                msg = f"\x0301,04[ \x0315{self.radio_name} \x0301,04]\x03 \x0301Emite:\x03 \x0302{self.emision}\x03 \x0301Escúchanos en:\x03 \x0312{self.radio_web}\x03"
                for channel in self.channels:
                    self.connection.privmsg(channel, msg)

    # ---------------------------- LÓGICA IRC ----------------------------

    def on_welcome(self, connection, event):
        self.logger.info(f"✅ Bienvenido al servidor {self.server}")
        # Unirse a canales
        for channel in self.channels:
            connection.join(channel)
            self.logger.info(f"Uniéndose a {channel}...")

    def on_privmsg(self, connection, event):
        self.handle_command(connection, event, is_private=True)

    def on_pubmsg(self, connection, event):
        self.handle_command(connection, event, is_private=False)

    def handle_command(self, connection, event, is_private: bool):
        nick = event.source.nick
        target = event.target if not is_private else nick
        message = event.arguments[0].strip()
        
        if not message.startswith('!'):
            return

        cmd_parts = message[1:].split(' ', 1)
        cmd = cmd_parts[0].lower()
        args = cmd_parts[1] if len(cmd_parts) > 1 else ""

        # Comandos Públicos
        if cmd == "np" or cmd == "sonando" or cmd == "cancion":
            if not self.online:
                connection.privmsg(target, f"\x0304[ERROR]\x03 La radio está actualmente \x02OFFLINE\x02.")
            else:
                connection.privmsg(target, f"\x0301,04[ \x0315{self.radio_name} \x0301,04]\x03 \x02\x0301Sonando:\x03\x02 \x0304{self.current_song}\x03")

        elif cmd == "dj":
            connection.privmsg(target, f"\x0301,04[ \x0315{self.radio_name} \x0301,04]\x03 \x0301En cabina:\x03 \x0302{self.emision}\x03 \x0301Web:\x03 \x0312{self.radio_web}\x03")

        elif cmd == "radio" or cmd == "web":
            connection.privmsg(target, f"\x0301,04[ \x0315{self.radio_name} \x0301,04]\x03 \x0301Web oficial:\x03 \x0312{self.radio_web}\x03 \x0301Reproductor:\x03 \x0312{self.radio_player}\x03")

        elif cmd == "oyentes" or cmd == "listeners":
            if not self.online:
                connection.privmsg(target, f"\x0304[ERROR]\x03 La radio está offline.")
            else:
                connection.privmsg(target, f"\x0301,04[ \x0315{self.radio_name} \x0301,04]\x03 \x0301Oyentes:\x03 \x0304{self.listeners}/{self.max_listeners}\x03 \x0301Pico:\x03 \x0304{self.peak_listeners}\x03")

        elif cmd == "peticion":
            if not self.peticiones_abiertas:
                connection.privmsg(target, f"\x0304[AVISO]\x03 Las peticiones están cerradas en este momento.")
            elif not args:
                connection.privmsg(target, f"\x0301Sintaxis:\x03 !peticion <artista - canción> [dedicatoria]")
            else:
                # Cooldown de 5 min (simplificado)
                self.peticiones.append({"nick": nick, "canal": event.target if not is_private else "Privado", "peticion": args, "time": time.time()})
                self.save_data("peticiones.json", self.peticiones)
                connection.privmsg(target, f"\x0303[OK]\x03 {nick}, tu petición ha sido enviada al DJ. ¡Gracias por sintonizar!")
                # Notificar al DJ si no es AutoDJ
                if self.emision != "AutoDJ":
                    connection.privmsg(self.emision, f"\x0312[PETICIÓN]\x03 {nick} pide: {args}")

        # Comandos de DJ / Admin
        elif cmd == "emitir":
            if self.is_dj(nick) or self.is_admin(nick):
                self.emision = nick
                connection.privmsg(target, f"\x0303[EMISIÓN]\x03 \x02{nick}\x02 entra en cabina. ¡A disfrutar!")
            else:
                connection.privmsg(target, f"\x0304[Error]\x03 No tienes permisos de DJ.")

        elif cmd == "autodj":
            if self.is_dj(nick) or self.is_admin(nick):
                self.emision = "AutoDJ"
                self.peticiones_abiertas = False
                connection.privmsg(target, f"\x0303[EMISIÓN]\x03 Volviendo al modo \x02AutoDJ\x02.")
            else:
                connection.privmsg(target, f"\x0304[Error]\x03 No tienes permisos.")

        elif cmd == "peticiones":
            if self.is_dj(nick) or self.is_admin(nick):
                if args.lower() == "on":
                    self.peticiones_abiertas = True
                    connection.privmsg(target, f"\x0303[INFO]\x03 Las peticiones se han \x02ABIERTO\x02.")
                elif args.lower() == "off":
                    self.peticiones_abiertas = False
                    connection.privmsg(target, f"\x0303[INFO]\x03 Las peticiones se han \x02CERRADO\x02.")
                else:
                    connection.privmsg(target, f"Uso: !peticiones <on/off>")

        elif cmd == "lista":
            if self.is_dj(nick) or self.is_admin(nick):
                if not self.peticiones:
                    connection.privmsg(nick, "No hay peticiones pendientes.")
                else:
                    connection.privmsg(nick, "\x0304--- Peticiones Pendientes ---")
                    for p in self.peticiones[-10:]: # Ultimas 10
                        connection.privmsg(nick, f"\x0312{p['nick']}\x03 ({p['canal']}): {p['peticion']}")
            else:
                connection.privmsg(target, "Acceso denegado.")

        elif cmd == "help":
            help_msg = "!np, !dj, !radio, !oyentes, !peticion. "
            if self.is_dj(nick) or self.is_admin(nick):
                help_msg += "DJs: !emitir, !autodj, !peticiones <on/off>, !lista. "
            if self.is_admin(nick):
                help_msg += "Admins: !add.dj, !del.dj, !add.fan, !del.fan, !add.admin, !del.admin."
            connection.privmsg(nick, f"\x0301Comandos de {self.radio_name}:\x03 {help_msg}")

        # Comandos de gestión de base de datos (Admin only)
        elif cmd == "add.dj" and self.is_admin(nick):
            if args and args not in self.djs:
                self.djs.append(args)
                self.save_data("djs.json", self.djs)
                connection.privmsg(target, f"\x0303[OK]\x03 {args} ahora es DJ.")
        
        elif cmd == "del.dj" and self.is_admin(nick):
            if args in self.djs:
                self.djs.remove(args)
                self.save_data("djs.json", self.djs)
                connection.privmsg(target, f"\x0303[OK]\x03 {args} ya no es DJ.")

        elif cmd == "add.admin" and self.is_root(nick):
            if args and args not in self.admins:
                self.admins.append(args)
                self.save_data("admins.json", self.admins)
                connection.privmsg(target, f"\x0303[OK]\x03 {args} ahora es Administrador.")

        elif cmd == "del.admin" and self.is_root(nick):
            if args in self.admins:
                self.admins.remove(args)
                self.save_data("admins.json", self.admins)
                connection.privmsg(target, f"\x0303[OK]\x03 {args} ya no es Administrador.")

        elif cmd == "add.fan" and self.is_admin(nick):
            if args and args not in self.fans:
                self.fans.append(args)
                self.save_data("fans.json", self.fans)
                connection.privmsg(target, f"\x0303[OK]\x03 {args} ahora es Fan.")

        elif cmd == "del.fan" and self.is_admin(nick):
            if args in self.fans:
                self.fans.remove(args)
                self.save_data("fans.json", self.fans)
                connection.privmsg(target, f"\x0303[OK]\x03 {args} ya no es Fan.")

        # Comandos de Parrilla
        elif cmd == "parrilla":
            connection.privmsg(nick, "\x0304--- Parrilla de DJs ---")
            for h in range(24):
                dj = self.parrilla.get(str(h), "Libre")
                connection.privmsg(nick, f"\x0312{h:02d}:00\x03 - {dj}")

        elif cmd == "hora.add":
            if args.isdigit() and 0 <= int(args) <= 23:
                hour = str(int(args))
                if self.parrilla.get(hour, "Libre") == "Libre":
                    self.parrilla[hour] = nick
                    self.save_data("parrilla.json", self.parrilla)
                    connection.privmsg(target, f"\x0303[OK]\x03 {nick}, te hemos asignado las {hour}:00.")
                else:
                    connection.privmsg(target, f"\x0304[Error]\x03 Las {hour}:00 ya están ocupadas por {self.parrilla[hour]}.")
            else:
                connection.privmsg(target, "Uso: !hora.add <0-23>")

        elif cmd == "hora.del":
            if args.isdigit() and 0 <= int(args) <= 23:
                hour = str(int(args))
                current_dj = self.parrilla.get(hour, "Libre")
                if current_dj == "Libre":
                    connection.privmsg(target, "Esa hora ya está libre.")
                elif current_dj == nick or self.is_admin(nick):
                    self.parrilla[hour] = "Libre"
                    self.save_data("parrilla.json", self.parrilla)
                    connection.privmsg(target, f"\x0303[OK]\x03 La hora {hour}:00 ahora está libre.")
                else:
                    connection.privmsg(target, "Solo el DJ asignado o un admin pueden liberar esta hora.")
            else:
                connection.privmsg(target, "Uso: !hora.del <0-23>")

        elif cmd == "global" and self.is_admin(nick):
            if args:
                broadcast = f"\x0301,04[ \x0315MENSAJE GLOBAL \x0301,04]\x03 \x0304{args}\x03"
                for channel in self.channels:
                    connection.privmsg(channel, broadcast)
                connection.privmsg(target, "\x0303[OK]\x03 Mensaje global enviado.")
            else:
                connection.privmsg(target, "Uso: !global <mensaje>")

    # ---------------------------- HELPERS ----------------------------

    def is_root(self, nick: str) -> bool:
        return nick in self.roots

    def is_admin(self, nick: str) -> bool:
        return self.is_root(nick) or nick in self.admins

    def is_dj(self, nick: str) -> bool:
        return nick in self.djs or self.is_admin(nick)

    def on_disconnect(self, connection, event):
        error_msg = str(event.arguments[0]).lower() if event.arguments else ""
        wait_time = 30
        
        if "g-lined" in error_msg or "banned" in error_msg or "estás baneado" in error_msg:
            self.logger.error(f"BAN DETECTADO: {error_msg}")
            self.logger.error("Esperando 30 minutos antes de reintentar...")
            wait_time = 1800
        else:
            self.logger.info(f"Desconectado ({error_msg}). Intentando reconectar en {wait_time} segundos...")
            
        time.sleep(wait_time)
        self.start()

    def start(self):
        # Iniciar hilos si no están corriendo
        if not hasattr(self, 'workers_started'):
            threading.Thread(target=self.radio_worker, daemon=True).start()
            threading.Thread(target=self.announce_worker, daemon=True).start()
            self.workers_started = True
        
        # Configurar buffer para evitar errores de decodificación
        irc.client.ServerConnection.buffer_class = buffer.LenientDecodingLineBuffer

        # Conectar IRC
        try:
            # Formato ChatHispano exitoso: NICK:PASS como nickname
            nick_ident = f"{self.nickname}:{self.password}" if self.password else self.nickname
            self.logger.info(f"Conectando a {self.server}:{self.port} con nick {nick_ident}...")
            
            factory = irc.connection.Factory()
            # Soporte SSL para puerto 6697
            if self.port == 6697:
                import ssl
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                factory = irc.connection.Factory(wrapper=ssl_context.wrap_socket)
                self.logger.info("Usando conexión SSL segura")

            self.connection = self.reactor.server().connect(
                self.server, self.port, nick_ident,
                username=self.ident,
                ircname=self.realname,
                connect_factory=factory
            )
            
            self.logger.info("Iniciando reactor IRC (process_forever)...")
            self.reactor.process_forever()
        except Exception as e:
            self.logger.error(f"Error en el reactor IRC: {e}")
            time.sleep(30)
            self.start()

if __name__ == "__main__":
    conf_path = os.path.join(os.path.dirname(__file__), "radiobot.conf")
    bot = RadioBot(conf_path)
    bot.start()
