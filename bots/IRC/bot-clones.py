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
import ssl
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
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                from irc.connection import Factory as IRCFactory
                factory = IRCFactory(wrapper=ctx.wrap_socket)
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

    # ── Nickmap (asignación nick → IP) ─────────────────────────────────────

    def _nickmap_get(self) -> dict:
        db = self._db_load()
        return db.get("_nickmap", {})

    @staticmethod
    def _parse_duracion(texto: str) -> tuple[datetime | None, str]:
        """Convierte '30d', '6m', '1y', '0' a datetime de expiración.
        Devuelve (datetime, descripción) o (None, 'Permanente')."""
        if texto == "0" or not texto:
            return None, "Permanente"
        match = re.match(r"^(\d+)\s*(d|m|y)$", texto.lower().strip())
        if not match:
            return None, "Permanente"
        cantidad = int(match.group(1))
        unidad = match.group(2)
        ahora = datetime.now(timezone.utc)
        if unidad == "d":
            expira = ahora + timedelta(days=cantidad)
            desc = f"{cantidad} día(s)"
        elif unidad == "m":
            # Aproximación: 30 días por mes
            expira = ahora + timedelta(days=cantidad * 30)
            desc = f"{cantidad} mes(es)"
        elif unidad == "y":
            expira = ahora + timedelta(days=cantidad * 365)
            desc = f"{cantidad} año(s)"
        else:
            return None, "Permanente"
        return expira, desc

    def _add_entry(self, ip: str, clones: int, tipo: str, autor: str, expira: datetime | None = None) -> str:
        db = self._db_load()
        if ip in db:
            return f"\x030,3\x02 CLoNeS \x02\x03\x034Ya existe una entrada para {ip}.\x03"

        ok = self._write_allow(ip, clones)
        if CLONES_CONF and not ok:
            return f"\x030,3\x02 CLoNeS \x02\x03\x034No se pudo escribir en {CLONES_CONF}.\x03"

        # Calcular expiración para OPeR: +0 = permanente, +N = N segundos
        if expira:
            segundos = int((expira - datetime.now(timezone.utc)).total_seconds())
            oper_expiracion = f"+{segundos}"
        else:
            oper_expiracion = "+0"
        self._oper_cmd(f"EXCEPTION ADD {oper_expiracion} {ip} {clones} {autor} ({tipo})")

        ahora = datetime.now(timezone.utc)
        db[ip] = {
            "ip": ip,
            "clones": clones,
            "type": tipo,
            "author": autor,
            "created_at": ahora.strftime("%Y-%m-%d %H:%M:%S"),
            "expires_at": expira.strftime("%Y-%m-%d %H:%M:%S") if expira else None,
        }
        # Asignar automáticamente la IP al autor
        nickmap = db.get("_nickmap", {})
        for n, i in list(nickmap.items()):
            if i == ip:
                del nickmap[n]
        nickmap[autor.lower()] = ip
        db["_nickmap"] = nickmap
        self._db_save(db)

        if REHASH_ENABLED and ok:
            self.conn.send_raw("REHASH")

        log.info("Añadida %s: %s (%d clones) por %s", tipo.upper(), ip, clones, autor)
        return f"\x030,3\x02 CLoNeS \x02\x03 \x0310Entrada {tipo.upper()} añadida para {ip} ({clones} clones).\x03"

    def _del_entry(self, ip: str) -> str:
        db = self._db_load()
        if ip not in db:
            return f"\x030,3\x02 CLoNeS \x02\x03\x034No existe entrada para {ip}.\x03"

        self._remove_allow(ip)
        self._oper_cmd(f"EXCEPTION DEL +0 {ip}")

        del db[ip]
        self._db_save(db)

        if REHASH_ENABLED:
            self.conn.send_raw("REHASH")

        log.info("Eliminada entrada para %s", ip)
        return f"\x030,3\x02 CLoNeS \x02\x03 \x0310Entrada eliminada para {ip}.\x03"

    def _c(self, msg: str, color: str = "") -> str:
        """Envuelve un mensaje con colores IRC estilo ChatHispano."""
        prefix = f"\x030,3\x02 CLoNeS \x02\x03" if not color else color
        return f"{prefix}{msg}"

    @staticmethod
    def _formatear_fecha(fecha_str: str | None) -> str:
        """Convierte '2026-10-14 06:15:10' a '14/10/2026 06:15:10'."""
        if not fecha_str:
            return "Permanente"
        try:
            dt = datetime.strptime(fecha_str, "%Y-%m-%d %H:%M:%S")
            return dt.strftime("%d/%m/%Y %H:%M:%S")
        except ValueError:
            return fecha_str

    def _ip_info(self, ip: str) -> str:
        db = self._db_load()
        e = db.get(ip)
        if not e:
            return "\x030,3\x02 CLoNeS \x02\x03\x034IP no encontrada.\x03"
        expire = self._formatear_fecha(e.get("expires_at"))
        lines = [
            f"\x030,3\x02 CLoNeS \x02\x03 Información de la iline:",
            f"\x030,3\x02 CLoNeS \x02\x03 \x0312IP:\x03 {e['ip']}",
            f"\x030,3\x02 CLoNeS \x02\x03 \x0312Clones:\x03 {e['clones']}",
            f"\x030,3\x02 CLoNeS \x02\x03 \x0312Estado:\x03 Active",
            f"\x030,3\x02 CLoNeS \x02\x03 \x0312Expiración:\x03 {expire}",
            f"\x030,3\x02 CLoNeS \x02\x03 Fin de la información.",
        ]
        return "\n".join(lines)

    def _list_all(self) -> str:
        db = self._db_load()
        if not db:
            return "\x030,3\x02 CLoNeS \x02\x03 No hay entradas."
        lines = [f"\x030,3\x02 CLoNeS \x02\x03 \x0312Lista de ilines activas:\x03"]
        for ip, e in db.items():
            lines.append(
                f"\x030,3\x02 CLoNeS \x02\x03 {ip} → {e['clones']} clones ({e['type'].upper()})"
            )
        return "\n".join(lines)

    def _notify_user(self, nick: str, msg: str) -> None:
        """Envía una notificación IRC a un usuario."""
        try:
            self._notice(nick, msg)
        except Exception:
            pass

    def _cleanup_expired(self) -> None:
        db = self._db_load()
        now = datetime.now(timezone.utc)
        changed = False

        for ip in list(db):
            if ip.startswith("_"):
                continue
            e = db[ip]
            expires_at = e.get("expires_at")
            if not expires_at:
                continue  # Permanente, no expira
            try:
                t0 = datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            # Dejar 1 día de rigor antes de eliminar
            if now <= t0 + timedelta(days=1):
                continue

            self._remove_allow(ip)
            self._oper_cmd(f"EXCEPTION DEL +0 {ip}")

            # Notificar al autor
            autor = e.get("author", "")
            if autor:
                fecha_legible = self._formatear_fecha(expires_at)
                self._notify_user(
                    autor,
                    f"\x030,3\x02 CLoNeS \x02\x03\x034Tu iline para {ip} expiró el {fecha_legible} y ha sido eliminada.\x03"
                )

            del db[ip]
            changed = True
            log.info("Entrada expirada y eliminada: %s (autor: %s)", ip, autor)

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
            return

        if cmd in ("help", "ayuda"):
            self._notice(nick, "\x030,3\x02 CLoNeS \x02\x03\x07Clones\x03 - \x07SitioChat")
            self._notice(nick, "\x030,3\x02 CLoNeS \x02\x03\x03Clones\x03 es un bot que administra las ilines de usuarios o corporativas.")
            self._notice(nick, "\x030,3\x02 CLoNeS \x02\x03\x02Ordenes disponibles\x02:")
            self._notice(nick, "\x030,3\x02 CLoNeS \x02\x03 \x0312INFO\x03 Muestra la información de la iline")

            self._notice(nick, "\x030,3\x02 CLoNeS \x02\x03 \x0312ADD <IP> <N> <tiempo>\x03 Añade iline temporal (ej: 30d, 6m, 1y)")
            self._notice(nick, "\x030,3\x02 CLoNeS \x02\x03 \x0312PERM <IP> <N>\x03 Añade iline permanente")
            self._notice(nick, "\x030,3\x02 CLoNeS \x02\x03 \x0312DEL <IP>\x03 Elimina una iline")
            self._notice(nick, "\x030,3\x02 CLoNeS \x02\x03 \x0312LIST\x03 Lista todas las ilines")
            self._notice(nick, "\x030,3\x02 CLoNeS \x02\x03\x02FIN de la AYUDA de \x03Clones")

        elif cmd == "add" and len(args) == 4:
            ip = args[1]
            clones = args[2]
            duracion = args[3]
            if not self._validar_ip(ip):
                self._notice(nick, "\x030,3\x02 CLoNeS \x02\x03\x034IP no válida.\x03")
                return
            if not clones.isdigit() or int(clones) < 1:
                self._notice(nick, "\x030,3\x02 CLoNeS \x02\x03\x034Número de clones no válido.\x03")
                return
            expira, desc = self._parse_duracion(duracion)
            if not expira:
                self._notice(nick, "\x030,3\x02 CLoNeS \x02\x03\x034Formato de tiempo no válido. Usa: 30d, 6m, 1y\x03")
                return
            self._notice(nick, self._add_entry(ip, int(clones), "temp", nick, expira))

        elif cmd == "perm" and len(args) == 3:
            ip = args[1]
            clones = args[2]

            if not self._validar_ip(ip):
                self._notice(nick, "\x030,3\x02 CLoNeS \x02\x03\x034IP no válida.\x03")
                return
            if not clones.isdigit() or int(clones) < 1:
                self._notice(nick, "\x030,3\x02 CLoNeS \x02\x03\x034Número de clones no válido.\x03")
                return

            self._notice(nick, self._add_entry(ip, int(clones), "perm", nick))

        elif cmd == "del" and len(args) == 2:
            self._notice(nick, self._del_entry(args[1]))

        elif cmd == "info":
            nickmap = self._nickmap_get()
            ip = nickmap.get(nick_lower)
            if ip:
                self._notice(nick, self._ip_info(ip))
            else:
                self._notice(nick, "\x030,3\x02 CLoNeS \x02\x03\x034No tienes una IP asignada.\x03")

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
