"""
CLoNeS — Bot de gestión de excepciones de clones para UnrealIRCd.

Comandos (por privado):
  add <IP> <N>      — Excepción temporal (N clones, expira en temp_days)
  perm <IP> <N>     — Excepción permanente (N clones)
  del <IP>           — Eliminar excepción
  ipinfo <IP>        — Información de una IP
  list               — Listar todas las excepciones
  help / ayuda       — Mostrar ayuda

Servicios usados: OPeR (EXCEPTION ADD/DEL), NiCK (identificación)
"""

import configparser
import json
import logging
import os
import re
import sys
import threading
import time
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from pathlib import Path

import irc.client
from jaraco.stream import buffer

# ── Config ────────────────────────────────────────────────────────────────

CONFIG_FILE = Path(__file__).with_suffix(".conf")
CONFIG = configparser.ConfigParser()

if not CONFIG_FILE.exists():
    print(f"Error: {CONFIG_FILE} no encontrado.")
    sys.exit(1)

CONFIG.read(CONFIG_FILE)

SERVER = CONFIG.get("irc", "server")
PORT = CONFIG.getint("irc", "port")
SSL = CONFIG.getboolean("irc", "ssl", fallback=False)
NICK = CONFIG.get("irc", "nickname")
IDENT = CONFIG.get("irc", "ident")
REALNAME = CONFIG.get("irc", "realname")
NICKSERV_PASS = CONFIG.get("irc", "nickserv_pass", fallback="")
OPER_USER = CONFIG.get("irc", "oper_user", fallback="")
OPER_PASS = CONFIG.get("irc", "oper_pass", fallback="")

DB_FILE = CONFIG.get("settings", "db_file", fallback="clones_db.json")
CLONES_CONF = CONFIG.get("settings", "clones_conf", fallback="")
TEMP_DAYS = CONFIG.getint("settings", "temp_days", fallback=2)
REHASH_ENABLED = CONFIG.getboolean("settings", "rehash", fallback=True)
RECONNECT_DELAY = CONFIG.getint("settings", "reconnect_delay", fallback=10)

ADMINS = [a.strip().lower() for a in CONFIG.get("admins", "nicks", fallback="").split(",") if a.strip()]

# ── Logging ───────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger("CLoNeS")


# ── Lock para DB thread-safe ──────────────────────────────────────────────

_db_lock = threading.Lock()


# ── Bot ────────────────────────────────────────────────────────────────────

class ClonesBot:
    """Bot que gestiona excepciones de clones vía OPeR y archivo de UnrealIRCd."""

    def __init__(self):
        self.reactor: irc.client.Reactor | None = None
        self.conn: irc.client.ServerConnection | None = None
        self.running = True
        self._reconnecting = False

    # ── Conexión IRC ──────────────────────────────────────────────────────

    def conectar(self) -> None:
        irc.client.ServerConnection.buffer_class = buffer.LenientDecodingLineBuffer
        self.reactor = irc.client.Reactor()

        try:
            if SSL:
                from irc.connection import Factory as IRCFactory
                factory = IRCFactory(wrapper=ssl.wrap_socket)
                self.conn = self.reactor.server().connect(
                    SERVER, PORT, NICK,
                    ircname=REALNAME, username=IDENT,
                    connect_factory=factory,
                )
            else:
                self.conn = self.reactor.server().connect(
                    SERVER, PORT, NICK,
                    ircname=REALNAME, username=IDENT,
                )
        except irc.client.ServerConnectionError as e:
            log.error("Error de conexión: %s", e)
            raise

        self.conn.add_global_handler("welcome", self._on_welcome)
        self.conn.add_global_handler("privmsg", self._on_privmsg)
        self.conn.add_global_handler("disconnect", self._on_disconnect)
        self.conn.add_global_handler("error", self._on_error)
        self.conn.add_global_handler("pubmsg", self._on_pubmsg)
        self.conn.add_global_handler("notice", self._on_notice)

        log.info("Conectando a %s:%s (SSL=%s)...", SERVER, PORT, SSL)

    def run(self) -> None:
        while self.running:
            try:
                self.conectar()
                # Hilo de limpieza periódica
                t = threading.Thread(target=self._cleanup_loop, daemon=True)
                t.start()
                self.reactor.process_forever(60)
            except Exception as e:
                log.error("Error en el reactor: %s", e)
            if self.running:
                log.info("Reconectando en %ds...", RECONNECT_DELAY)
                time.sleep(RECONNECT_DELAY)

    def detener(self) -> None:
        self.running = False
        if self.conn:
            with suppress(Exception):
                self.conn.quit("Bot detenido")
        if self.reactor:
            self.reactor.stop()

    # ── Eventos IRC ───────────────────────────────────────────────────────

    def _on_welcome(self, _conn: irc.client.ServerConnection, _event: irc.client.Event) -> None:
        log.info("Conectado como %s", NICK)
        # Identificación con NickServ
        if NICKSERV_PASS:
            self._privmsg("NiCK", f"IDENTIFY {NICKSERV_PASS}")
            time.sleep(2)
        # OPER
        if OPER_USER and OPER_PASS:
            self.conn.send_raw(f"OPER {OPER_USER} {OPER_PASS}")
            time.sleep(1)
        self.conn.send_raw(f"MODE {NICK} +B")

    def _on_disconnect(self, _conn: irc.client.ServerConnection, _event: irc.client.Event) -> None:
        log.warning("Desconectado")
        if self.running and not self._reconnecting:
            self._reconnecting = True
            threading.Thread(target=self._reconnect_loop, daemon=True).start()

    def _on_error(self, _conn: irc.client.ServerConnection, event: irc.client.Event) -> None:
        msg = event.arguments[0] if event.arguments else "sin detalle"
        log.error("Error del servidor: %s", msg)

    def _on_pubmsg(self, _conn: irc.client.ServerConnection, event: irc.client.Event) -> None:
        """También acepta comandos en canal para admins."""
        nick = irc.client.NickMask(event.source).nick
        msg = event.arguments[0].strip()
        target = event.target
        if target.startswith("#") and nick.lower() in ADMINS:
            self._handle_cmd(nick, msg)

    def _on_privmsg(self, _conn: irc.client.ServerConnection, event: irc.client.Event) -> None:
        nick = irc.client.NickMask(event.source).nick
        msg = event.arguments[0].strip()
        self._handle_cmd(nick, msg)

    def _on_notice(self, _conn: irc.client.ServerConnection, event: irc.client.Event) -> None:
        """Capturar respuestas de OPeR, WHOIS, etc."""
        pass  # Por ahora no se procesan

    # ── Reconexión ────────────────────────────────────────────────────────

    def _reconnect_loop(self) -> None:
        time.sleep(RECONNECT_DELAY)
        self._reconnecting = False
        if self.running:
            log.info("Reconectando...")
            self.reactor.stop()

    # ── Primitivas de envío ───────────────────────────────────────────────

    def _privmsg(self, target: str, msg: str) -> None:
        if self.conn:
            self.conn.privmsg(target, msg)

    def _notice(self, target: str, msg: str) -> None:
        if self.conn:
            self.conn.notice(target, msg)

    # ── BD de clones (thread-safe) ────────────────────────────────────────

    def _db_path(self) -> Path:
        p = Path(DB_FILE)
        return p if p.is_absolute() else Path(__file__).parent / p

    def _db_load(self) -> dict:
        with _db_lock:
            path = self._db_path()
            if path.exists():
                with open(path, "r") as f:
                    return json.load(f)
            return {}

    def _db_save(self, db: dict) -> None:
        with _db_lock:
            path = self._db_path()
            path.write_text(json.dumps(db, indent=2, ensure_ascii=False))

    # ── Archivo de configuración de UnrealIRCd ────────────────────────────

    def _write_allow(self, ip: str, clones: int) -> bool:
        if not CLONES_CONF:
            return False
        try:
            line = f"allow {{ mask {ip}; class clients; maxperip {clones}; }};\n"
            with open(CLONES_CONF, "a") as f:
                f.write(line)
            return True
        except (FileNotFoundError, PermissionError) as e:
            log.warning("No se pudo escribir en %s: %s", CLONES_CONF, e)
            return False

    def _remove_allow(self, ip: str) -> bool:
        if not CLONES_CONF or not os.path.exists(CLONES_CONF):
            return False
        try:
            with open(CLONES_CONF, "r") as f:
                lines = f.readlines()
            with open(CLONES_CONF, "w") as f:
                for line in lines:
                    if f"mask {ip};" not in line:
                        f.write(line)
            return True
        except (FileNotFoundError, PermissionError) as e:
            log.warning("No se pudo modificar %s: %s", CLONES_CONF, e)
            return False

    # ── Comandos OPeR ─────────────────────────────────────────────────────

    def _oper_cmd(self, cmd: str) -> None:
        self._privmsg("OPeR", cmd)

    # ── Lógica de negocio ─────────────────────────────────────────────────

    @staticmethod
    def _validar_ip(ip: str) -> bool:
        return bool(re.match(r"^[\w\.\-\:]+$", ip))

    def _add_entry(self, ip: str, clones: int, tipo: str, autor: str) -> str:
        db = self._db_load()
        if ip in db:
            return f"Ya existe una entrada para {ip}."

        ok = self._write_allow(ip, clones)
        if CLONES_CONF and not ok:
            return f"No se pudo escribir en {CLONES_CONF}."

        # Comando EXCEPTION ADD: EXCEPTION ADD <expiración> <mask> <límite> <razón>
        self._oper_cmd(f"EXCEPTION ADD +0 {ip} {clones} {autor} ({tipo})")

        db[ip] = {
            "ip": ip,
            "clones": clones,
            "type": tipo,
            "author": autor,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._db_save(db)

        if REHASH_ENABLED and ok:
            self.conn.send_raw("REHASH")

        log.info("Añadida %s: %s (%d clones) por %s", tipo.upper(), ip, clones, autor)
        return f"Entrada {tipo.upper()} añadida para {ip} ({clones} clones)."

    def _del_entry(self, ip: str) -> str:
        db = self._db_load()
        if ip not in db:
            return f"No existe entrada para {ip}."

        self._remove_allow(ip)
        self._oper_cmd(f"EXCEPTION DEL +0 {ip}")

        del db[ip]
        self._db_save(db)

        if REHASH_ENABLED:
            self.conn.send_raw("REHASH")

        log.info("Eliminada entrada para %s", ip)
        return f"Entrada eliminada para {ip}."

    def _ip_info(self, ip: str) -> str:
        db = self._db_load()
        e = db.get(ip)
        if not e:
            return "IP no encontrada."
        return (
            f"IP: {e['ip']} | Clones: {e['clones']} | "
            f"Tipo: {e['type'].upper()} | Autor: {e['author']} | "
            f"Fecha: {e['timestamp']}"
        )

    def _list_all(self) -> str:
        db = self._db_load()
        if not db:
            return "No hay entradas."
        return " | ".join(
            f"{ip}: {e['clones']} clones ({e['type'].upper()})"
            for ip, e in db.items()
        )

    def _cleanup_expired(self) -> None:
        db = self._db_load()
        now = datetime.now(timezone.utc)
        changed = False

        for ip in list(db):
            e = db[ip]
            if e["type"] != "temp":
                continue
            try:
                t0 = datetime.strptime(e["timestamp"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            if now <= t0 + timedelta(days=TEMP_DAYS):
                continue

            self._remove_allow(ip)
            self._oper_cmd(f"EXCEPTION DEL +0 {ip}")
            del db[ip]
            changed = True
            log.info("Entrada temporal expirada: %s", ip)

        if changed:
            self._db_save(db)
            if REHASH_ENABLED:
                self.conn.send_raw("REHASH")

    # ── Dispatch de comandos ──────────────────────────────────────────────

    def _handle_cmd(self, nick: str, msg: str) -> None:
        args = msg.strip().split()
        if not args:
            return

        cmd = args[0].lower()
        nick_lower = nick.lower()

        # Solo admins pueden usar comandos
        if nick_lower not in ADMINS:
            self._notice(nick, "No tienes permiso para usar este bot.")
            return

        if cmd in ("help", "ayuda"):
            self._notice(nick, "Comandos disponibles:")
            self._notice(nick, "  add <IP> <N>      — Excepción temporal (N clones, expira en días)")
            self._notice(nick, "  perm <IP> <N>     — Excepción permanente (N clones)")
            self._notice(nick, "  del <IP>           — Eliminar excepción")
            self._notice(nick, "  ipinfo <IP>        — Información de una IP")
            self._notice(nick, "  list               — Listar todas")
            self._notice(nick, "  help / ayuda       — Esta ayuda")

        elif cmd in ("add", "perm") and len(args) == 3:
            ip = args[1]
            clones = args[2]

            if not self._validar_ip(ip):
                self._notice(nick, "IP no válida.")
                return
            if not clones.isdigit() or int(clones) < 1:
                self._notice(nick, "Número de clones no válido.")
                return

            tipo = "perm" if cmd == "perm" else "temp"
            self._notice(nick, self._add_entry(ip, int(clones), tipo, nick))

        elif cmd == "del" and len(args) == 2:
            self._notice(nick, self._del_entry(args[1]))

        elif cmd == "ipinfo" and len(args) == 2:
            self._notice(nick, self._ip_info(args[1]))

        elif cmd == "list":
            self._notice(nick, self._list_all())

        else:
            self._notice(nick, "Comando no reconocido. Usa: help / ayuda")

    # ── Loop de limpieza ──────────────────────────────────────────────────

    def _cleanup_loop(self) -> None:
        while self.running:
            time.sleep(3600)
            if self.running and self.conn and self.conn.is_connected():
                self._cleanup_expired()


# ── Entrypoint ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    bot = ClonesBot()
    try:
        bot.run()
    except KeyboardInterrupt:
        log.info("Deteniendo CLoNeS...")
        bot.detener()
        log.info("Detenido.")
