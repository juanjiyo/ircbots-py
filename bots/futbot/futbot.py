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
import ssl
from jaraco.stream import buffer
from bs4 import BeautifulSoup
from datetime import datetime
import unicodedata
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Set

# Forzar codificación UTF-8 para evitar errores con emojis en Windows
if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except:
        pass

# ============================ CONFIGURACIÓN ============================
class Config:
    IRC_SERVER = "ssl.chathispano.com"
    IRC_PORT = 6697
    IRC_NICK = "MaLeFiCo"
    IRC_PASS = "IRCPASSWORD"
    IRC_USER = "Futbol"
    IRC_REALNAME = "2«MaLe4FiCo2» * Bot de retransmisión de partidos de fútbol"    
    CANAL_FUTBOL = "#mis_vips"
    CANAL_DEBUG = "#Limbo"  # Canal para enviar mensajes de debug
    DEBUG_TO_CHANNEL = False  # Si es True, envía debug al canal; si es False, solo a logs    
    FUNDADORES = ["JuanJo_Jaen", "JuanJo_Jaen2", "JuanJo_Jaen-OFF"]  # Fundadores permanentes (no se pueden eliminar)
    # Configuración de reconexión
    RECONNECT_DELAY = 30
    MAX_RECONNECT_ATTEMPTS = 0    
    # Rate limiting y anti-flood
    MESSAGE_DELAY = 0.3  # Delay base entre mensajes
    FLOOD_PROTECTION = True
    FLOOD_BURST = 5  # Mensajes permitidos en ráfaga
    FLOOD_DELAY = 2  # Segundos de pausa después de ráfaga    
    # Configuración de scraping
    SCRAPER_ENABLED = True
    SCRAPER_INTERVAL = 30  # segundos entre búsquedas de partidos (reducido para evitar eventos perdidos)
    MATCH_CHECK_INTERVAL = 30  # segundos entre revisiones de cada partido
    SCRAPER_URL = "https://www.resultados-futbol.com"
    SCRAPER_LIVESCORE_URLS = [
        "https://www.resultados-futbol.com/livescore/pais/espana",
        "https://www.resultados-futbol.com/livescore/pais/European_competition",
    ]
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"    
    # Filtro de ligas permitidas
    LIGAS_PERMITIDAS = [
        "primera división",
        "segunda división",
        "copa del rey",
        "supercopa",
        "eurocopa",
        "champions league",
        "europa league", 
        "nations league",
        "mundial",
    ]
    
    # Ligas internacionales que requieren validación de equipo español
    LIGAS_INTERNACIONALES = [
        "champions league", 
        "europa league", 
        "conference league",
        "eurocopa",
        "mundial",
        "nations league"
    ]
    
    # Renombrar ligas para mostrar
    LIGAS_RENAME = {
        "primera división": "LaLiga EA Sports",
        "segunda división": "LaLiga Hypermotion",
        "champions league": "Champions League",
        "europa league": "Europa League",
    }
    
    # Colores por liga (código IRC) - COLORES ÚNICOS
    # EVITAR: 02, 03, 04, 08, 12, 14 (usados en eventos)
    # DISPONIBLES: 05, 06, 07, 09, 10, 11, 13, 15
    # 05=burdeos, 06=morado, 07=naranja, 09=verde lima, 10=cyan, 11=cyan claro, 13=rosa, 15=gris claro
    LIGAS_COLORES = {
        "laliga ea sports": "05",      # Burdeos
        "laliga hypermotion": "07",    # Naranja  
        "copa del rey": "06",          # Morado
        "supercopa": "13",             # Rosa
        "eurocopa": "09",              # Verde lima
        "champions league": "11",      # Cyan claro
        "europa league": "15",         # Gris claro
        "conference league": "10",     # Cyan
        "nations league": "01",        # Negro (visible en fondos claros)
        "mundial": "12",               # Azul royal
    }

# Eventos importantes que se narran en canales externos + #mis_vips
# #mis_vips recibe TODO (incluyendo eventos NO en esta lista)
# Basado en la estructura real de resultados-futbol.com
EVENTOS_IMPORTANTES = [
    'accion1.png',   # GOL
    'accion2.png',   # Gol de penalti
    'accion43.png',  # Gol de penalti (Primera División)
    'accion5.png',   # Tarjeta amarilla
    'accion4.png',   # Doble amarilla / tarjeta roja
    'accion3.png',   # Tarjeta roja directa
    'accion6.png',   # Tarjeta roja
    'accion14.png',  # Gol anulado (por fuera de juego u otra razón)
    'accion15.png',  # Penalti fallado (el tirador falla)
    'accion16.png',  # Penalti parado (el portero lo detiene)
    'accion20.png',  # VAR / Lesión (se distingue por texto)
    'accion22.png',  # Asistencia
    'accion18.png',  # Salida de jugador (cambio)
    'accion19.png',  # Entrada de jugador (cambio)
    'accion23.png',  # Gol en tanda de penaltis
    'accion24.png',  # Fallo en tanda de penaltis
    'accion28.png',  # Penalti cometido (falta que causa penalti)
    'accion29.png',  # Silbato de descanso / fin de parte
    'accion34.png',  # Penalti (señalado por el árbitro)
    'accion36.png',  # No penalti (VAR descarta / revisión)
]

# ============================ LOGGING ============================
# Configuramos el logging para que no pete con los emojis en Windows
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

# ============================ UTILIDADES ============================
def strip_mirc_colors(text):
    """Elimina códigos de color y formato mIRC de un texto"""
    return re.sub(r"(\x03\d{1,2}(,\d{1,2})?)|[\x02\x1F\x16\x0F]", "", text)

# ============================ BASE DE DATOS (SQLite embebido) ============================
import sqlite3
from contextlib import contextmanager

_DB_FILE = "malefico.db"
_db_lock = threading.Lock()


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_FILE, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _exec(sql: str, params: tuple = ()) -> bool:
    with _db_lock:
        try:
            conn = _get_conn()
            conn.execute(sql, params)
            conn.commit()
            conn.close()
            return True
        except Exception as exc:
            logging.error("DB error [%s] → %s", sql[:60], exc)
            return False


def _fetch_one(sql: str, params: tuple = ()):
    with _db_lock:
        try:
            conn = _get_conn()
            row = conn.execute(sql, params).fetchone()
            conn.close()
            return row
        except Exception as exc:
            logging.error("DB fetch_one [%s] → %s", sql[:60], exc)
            return None


def _fetch_all(sql: str, params: tuple = ()):
    with _db_lock:
        try:
            conn = _get_conn()
            rows = conn.execute(sql, params).fetchall()
            conn.close()
            return rows
        except Exception as exc:
            logging.error("DB fetch_all [%s] → %s", sql[:60], exc)
            return []


def _init_db() -> None:
    """Crea las tablas si no existen."""
    ddl = [
        """CREATE TABLE IF NOT EXISTS ef_canales (
            canal     TEXT PRIMARY KEY,
            founder   TEXT NOT NULL DEFAULT \'\',
            narracion INTEGER NOT NULL DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS ef_staff (
            nick  TEXT PRIMARY KEY,
            nivel INTEGER NOT NULL DEFAULT 101
        )""",
        """CREATE TABLE IF NOT EXISTS ef_partidos (
            id               TEXT PRIMARY KEY,
            equipo_local     TEXT NOT NULL DEFAULT \'\',
            equipo_visitante TEXT NOT NULL DEFAULT \'\',
            estado           TEXT NOT NULL DEFAULT \'\',
            ultima_jugada    TEXT NOT NULL DEFAULT \'\',
            ultimo_check     TEXT NOT NULL DEFAULT \'\',
            fecha_inicio     TEXT NOT NULL DEFAULT \'\',
            anunciado        INTEGER NOT NULL DEFAULT 0,
            liga             TEXT NOT NULL DEFAULT \'\'
        )""",
        """CREATE TABLE IF NOT EXISTS ef_eventos (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            partido_id TEXT NOT NULL,
            minuto     TEXT NOT NULL DEFAULT \'\',
            icono      TEXT NOT NULL DEFAULT \'\',
            texto      TEXT NOT NULL DEFAULT \'\',
            marcador   TEXT NOT NULL DEFAULT \'\'
        )""",
        """CREATE TABLE IF NOT EXISTS ef_partidos_filtro (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            equipo_local     TEXT NOT NULL DEFAULT \'\',
            equipo_visitante TEXT NOT NULL DEFAULT \'\',
            agregado_por     TEXT NOT NULL DEFAULT \'system\',
            liga             TEXT NOT NULL DEFAULT \'\'
        )""",
        """CREATE TABLE IF NOT EXISTS ef_usuarios (
            nick                   TEXT PRIMARY KEY,
            fecha_registro         TEXT NOT NULL DEFAULT \'\',
            puntos                 INTEGER NOT NULL DEFAULT 0,
            forbid                 INTEGER NOT NULL DEFAULT 0,
            motivo_forbid          TEXT NOT NULL DEFAULT \'\',
            agregado_por_forbid    TEXT NOT NULL DEFAULT \'\'
        )""",
        """CREATE TABLE IF NOT EXISTS ef_porras (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            partido_id       TEXT NOT NULL DEFAULT \'\',
            equipo_local     TEXT NOT NULL DEFAULT \'\',
            equipo_visitante TEXT NOT NULL DEFAULT \'\',
            premio           TEXT NOT NULL DEFAULT \'\',
            creado_por       TEXT NOT NULL DEFAULT \'\',
            estado           TEXT NOT NULL DEFAULT \'ABIERTA\'
        )""",
        """CREATE TABLE IF NOT EXISTS ef_apuestas (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            porra_id        INTEGER NOT NULL,
            nick            TEXT NOT NULL,
            goles_local     INTEGER NOT NULL DEFAULT 0,
            goles_visitante INTEGER NOT NULL DEFAULT 0,
            UNIQUE (porra_id, nick)
        )""",
    ]
    with _db_lock:
        try:
            conn = _get_conn()
            for stmt in ddl:
                conn.execute(stmt)
            conn.commit()
            conn.close()
            logging.info("✅ Base de datos inicializada: %s", _DB_FILE)
        except Exception as exc:
            logging.critical("❌ Error inicializando BD: %s", exc)
            raise


class BotDB:
    def __init__(self, db_file=None):
        _init_db()

    # -------- Canales --------
    def add_canal(self, canal: str, founder: str) -> bool:
        return _exec(
            "INSERT INTO ef_canales (canal, founder, narracion) VALUES (?,?,1) "
            "ON CONFLICT(canal) DO UPDATE SET founder=excluded.founder",
            (canal.lower(), founder),
        )

    def del_canal(self, canal: str) -> bool:
        return _exec("DELETE FROM ef_canales WHERE canal=?", (canal.lower(),))

    def list_canales(self):
        rows = _fetch_all("SELECT canal, founder, narracion FROM ef_canales ORDER BY canal")
        return [(r["canal"], r["founder"], r["narracion"]) for r in rows]

    def set_narracion(self, canal: str, estado) -> bool:
        return _exec(
            "UPDATE ef_canales SET narracion=? WHERE canal=?",
            (1 if estado else 0, canal.lower()),
        )

    def get_canales_narracion_activa(self):
        rows = _fetch_all("SELECT canal FROM ef_canales WHERE narracion=1")
        return [r["canal"] for r in rows]

    # -------- Staff --------
    def add_root(self, nick: str) -> bool:
        return _exec(
            "INSERT INTO ef_staff (nick, nivel) VALUES (?,102) "
            "ON CONFLICT(nick) DO UPDATE SET nivel=102", (nick,)
        )

    def del_root(self, nick: str) -> bool:
        return _exec("DELETE FROM ef_staff WHERE nick=?", (nick,))

    def list_root(self):
        rows = _fetch_all("SELECT nick FROM ef_staff WHERE nivel>=102 ORDER BY nick")
        return [r["nick"] for r in rows]

    @staticmethod
    def is_fundador(nick: str) -> bool:
        return nick.lower() in [f.lower() for f in Config.FUNDADORES]

    def is_root(self, nick: str) -> bool:
        row = _fetch_one("SELECT nivel FROM ef_staff WHERE nick=?", (nick,))
        return row["nivel"] >= 102 if row else False

    def add_admin(self, nick: str) -> bool:
        return _exec(
            "INSERT INTO ef_staff (nick, nivel) VALUES (?,101) "
            "ON CONFLICT(nick) DO UPDATE SET nivel=101", (nick,)
        )

    def del_admin(self, nick: str) -> bool:
        if self.is_fundador(nick) or self.is_root(nick):
            return False
        return _exec("DELETE FROM ef_staff WHERE nick=?", (nick,))

    def list_admins(self):
        rows = _fetch_all("SELECT nick FROM ef_staff WHERE nivel=101 ORDER BY nick")
        return [r["nick"] for r in rows]

    # -------- Partidos --------
    def add_partido(self, partido_id: str, local: str, visitante: str, estado: str, liga: str = "") -> bool:
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return _exec(
            """INSERT INTO ef_partidos
                   (id, equipo_local, equipo_visitante, estado,
                    ultima_jugada, ultimo_check, fecha_inicio, anunciado, liga)
               VALUES (?,?,?,?,\'\',?,?,0,?)
               ON CONFLICT(id) DO UPDATE SET
                   estado=excluded.estado,
                   ultimo_check=excluded.ultimo_check,
                   liga=CASE WHEN excluded.liga!=\'\'  THEN excluded.liga ELSE liga END""",
            (partido_id, local, visitante, estado, ahora, ahora, liga),
        )

    def get_partido(self, partido_id: str):
        row = _fetch_one("SELECT * FROM ef_partidos WHERE id=?", (partido_id,))
        if not row:
            return None
        return (row["id"], row["equipo_local"], row["equipo_visitante"], row["estado"],
                row["ultima_jugada"], row["ultimo_check"], row["fecha_inicio"],
                row["anunciado"], row["liga"])

    def update_partido(self, partido_id: str, ultima_jugada: str) -> bool:
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return _exec(
            "UPDATE ef_partidos SET ultima_jugada=?, ultimo_check=? WHERE id=?",
            (ultima_jugada, ahora, partido_id),
        )

    def add_evento(self, partido_id: str, minuto: str, icono: str, texto: str, marcador: str) -> bool:
        return _exec(
            "INSERT INTO ef_eventos (partido_id, minuto, icono, texto, marcador) VALUES (?,?,?,?,?)",
            (partido_id, minuto, icono, texto, marcador),
        )

    def limpiar_partidos_antiguos(self, dias: int = 1) -> bool:
        return _exec(
            "DELETE FROM ef_partidos WHERE julianday(\'now\')-julianday(ultimo_check)>?", (dias,)
        )

    def marcar_partido_anunciado(self, partido_id: str) -> bool:
        return _exec("UPDATE ef_partidos SET anunciado=1 WHERE id=?", (partido_id,))

    # -------- Filtro de partidos --------
    def add_partido_filtro(self, equipo_local: str, equipo_visitante: str,
                           agregado_por: str = "system", liga=None) -> bool:
        return _exec(
            "INSERT INTO ef_partidos_filtro (equipo_local, equipo_visitante, agregado_por, liga) "
            "VALUES (?,?,?,?)",
            (equipo_local.lower(), equipo_visitante.lower(), agregado_por, liga or ""),
        )

    def del_partido_filtro(self, equipo_local: str, equipo_visitante: str) -> bool:
        return _exec(
            "DELETE FROM ef_partidos_filtro WHERE equipo_local=? AND equipo_visitante=?",
            (equipo_local.lower(), equipo_visitante.lower()),
        )

    def del_partido_filtro_por_id(self, partido_id: int) -> bool:
        return _exec("DELETE FROM ef_partidos_filtro WHERE id=?", (partido_id,))

    def list_partidos_filtro(self):
        rows = _fetch_all(
            "SELECT id, equipo_local, equipo_visitante, agregado_por, liga "
            "FROM ef_partidos_filtro ORDER BY id"
        )
        return [(r["id"], r["equipo_local"], r["equipo_visitante"], r["agregado_por"], r["liga"]) for r in rows]

    def clear_partidos_filtro(self) -> bool:
        return _exec("DELETE FROM ef_partidos_filtro")

    def partido_en_filtro(self, equipo_local: str, equipo_visitante: str):
        partidos = self.list_partidos_filtro()
        if not partidos:
            return -1
        el_l = equipo_local.lower()
        ev_l = equipo_visitante.lower()
        for fid, fl, fv, _, _ in partidos:
            if ((fl in el_l or el_l in fl) and (fv in ev_l or ev_l in fv)) or \
               ((fl in ev_l or ev_l in fl) and (fv in el_l or el_l in fv)):
                return fid
        return None

    # -------- Usuarios --------
    def usuario_registrado(self, nick: str) -> bool:
        row = _fetch_one("SELECT nick FROM ef_usuarios WHERE nick=?", (nick,))
        return row is not None

    def usuario_forbid(self, nick: str) -> bool:
        row = _fetch_one("SELECT forbid FROM ef_usuarios WHERE nick=?", (nick,))
        return bool(row["forbid"]) if row else False

    def registrar_usuario(self, nick: str) -> bool:
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return _exec(
            "INSERT INTO ef_usuarios (nick, fecha_registro, puntos, forbid) "
            "VALUES (?,?,0,0) ON CONFLICT(nick) DO NOTHING",
            (nick, ahora),
        )

    def baja_usuario(self, nick: str) -> bool:
        return _exec("DELETE FROM ef_usuarios WHERE nick=?", (nick,))

    def get_usuario(self, nick: str):
        row = _fetch_one("SELECT * FROM ef_usuarios WHERE nick=?", (nick,))
        if not row:
            return None
        return {
            "nick": row["nick"], "fecha_registro": row["fecha_registro"],
            "puntos": row["puntos"], "forbid": row["forbid"],
            "motivo_forbid": row["motivo_forbid"],
            "agregado_por_forbid": row["agregado_por_forbid"],
        }

    def add_puntos_usuario(self, nick: str, puntos: int) -> bool:
        return _exec("UPDATE ef_usuarios SET puntos=puntos+? WHERE nick=?", (puntos, nick))

    def forbid_usuario(self, nick: str, motivo: str, agregado_por: str) -> bool:
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return _exec(
            """INSERT INTO ef_usuarios (nick, fecha_registro, puntos, forbid, motivo_forbid, agregado_por_forbid)
               VALUES (?,?,0,1,?,?)
               ON CONFLICT(nick) DO UPDATE SET
                   forbid=1, motivo_forbid=excluded.motivo_forbid,
                   agregado_por_forbid=excluded.agregado_por_forbid""",
            (nick, ahora, motivo, agregado_por),
        )

    def unforbid_usuario(self, nick: str) -> bool:
        return _exec(
            "UPDATE ef_usuarios SET forbid=0, motivo_forbid=\'\', agregado_por_forbid=\'\'  WHERE nick=?",
            (nick,),
        )

    # -------- Porras --------
    def crear_porra(self, partido_id: str, equipo_local: str, equipo_visitante: str,
                    premio: str, creado_por: str) -> bool:
        _exec("UPDATE ef_porras SET estado=\'CERRADA\' WHERE estado=\'ABIERTA\'")
        return _exec(
            "INSERT INTO ef_porras (partido_id, equipo_local, equipo_visitante, premio, creado_por, estado) "
            "VALUES (?,?,?,?,?,\'ABIERTA\')",
            (partido_id, equipo_local, equipo_visitante, premio, creado_por),
        )

    def get_porra_activa(self):
        row = _fetch_one(
            "SELECT id, partido_id, equipo_local, equipo_visitante, premio, estado "
            "FROM ef_porras WHERE estado IN (\'ABIERTA\',\'CERRADA\') ORDER BY id DESC LIMIT 1"
        )
        if not row:
            return None
        return (row["id"], row["partido_id"], row["equipo_local"],
                row["equipo_visitante"], row["premio"], row["estado"])

    def abrir_porra(self) -> bool:
        row = _fetch_one("SELECT id FROM ef_porras ORDER BY id DESC LIMIT 1")
        return _exec("UPDATE ef_porras SET estado=\'ABIERTA\' WHERE id=?", (row["id"],)) if row else False

    def cerrar_porra(self) -> bool:
        return _exec("UPDATE ef_porras SET estado=\'CERRADA\' WHERE estado=\'ABIERTA\'")

    def finalizar_porra(self, porra_id: int) -> bool:
        return _exec("UPDATE ef_porras SET estado=\'FINALIZADA\' WHERE id=?", (porra_id,))

    def eliminar_porra(self, porra_id: int) -> bool:
        _exec("DELETE FROM ef_apuestas WHERE porra_id=?", (porra_id,))
        return _exec("DELETE FROM ef_porras WHERE id=?", (porra_id,))

    def crear_apuesta(self, porra_id: int, nick: str, goles_local: int, goles_visitante: int) -> bool:
        return _exec(
            "INSERT INTO ef_apuestas (porra_id, nick, goles_local, goles_visitante) "
            "VALUES (?,?,?,?) ON CONFLICT(porra_id, nick) DO NOTHING",
            (porra_id, nick, goles_local, goles_visitante),
        )

    def get_apuesta(self, porra_id: int, nick: str):
        row = _fetch_one(
            "SELECT id, porra_id, nick, goles_local, goles_visitante "
            "FROM ef_apuestas WHERE porra_id=? AND nick=?", (porra_id, nick)
        )
        return (row["id"], row["porra_id"], row["nick"],
                row["goles_local"], row["goles_visitante"]) if row else None

    def get_apuestas_porra(self, porra_id: int):
        rows = _fetch_all(
            "SELECT id, porra_id, nick, goles_local, goles_visitante "
            "FROM ef_apuestas WHERE porra_id=? ORDER BY id", (porra_id,)
        )
        return [(r["id"], r["porra_id"], r["nick"], r["goles_local"], r["goles_visitante"]) for r in rows]

    def eliminar_apuesta(self, porra_id: int, nick: str) -> bool:
        return _exec("DELETE FROM ef_apuestas WHERE porra_id=? AND nick=?", (porra_id, nick))

    def get_ganadores_porra(self, porra_id: int, goles_local: int, goles_visitante: int):
        rows = _fetch_all(
            "SELECT nick FROM ef_apuestas WHERE porra_id=? AND goles_local=? AND goles_visitante=?",
            (porra_id, goles_local, goles_visitante),
        )
        return [r["nick"] for r in rows]

    def close(self):
        pass

# ============================ SCRAPER DE PARTIDOS ============================

# ============================ CONTEXTO DE PARTIDO ============================

@dataclass
class PartidoContexto:
    """Snapshot inmutable del estado de un partido en un instante dado.

    Se construye una vez por ciclo de scraping a partir del HTML parseado y se
    pasa entre métodos sin modificarse.  Separa la fase de *extracción* (HTTP +
    BeautifulSoup) de la fase de *decisión* (detectar eventos nuevos) y de la
    fase de *formateo* (construir mensajes IRC).
    """
    partido_id:   str
    equipo_local: str
    equipo_visitante: str
    liga:         str
    color_liga:   str
    marcador:     str          # "2 - 1"
    estado:       str          # 'vivo' | 'finalizado' | 'proximo'
    parte:        str          # '1ª' | 'Descanso' | '2ª' | ...
    minuto_status: int         # minuto extraído del jor-status
    eventos:      List[dict]   # lista completa de eventos parseados (índice 0 = más reciente)
    alineaciones: Dict[str, str]  # {apellido/nombre: equipo}
    soup:         Any          # BeautifulSoup — solo para métodos que necesiten re-parsear


# ============================ FORMATEADOR DE EVENTOS IRC ============================

class EventFormatter:
    """Convierte un evento parseado en un mensaje IRC formateado.

    Todos los métodos son estáticos — no tienen estado propio.  Cada método
    corresponde a un tipo de evento y recibe exactamente los datos que necesita,
    sin acceder a self ni a variables globales.

    Convención de retorno:
        str   → mensaje listo para enviar
        None  → evento silenciado (sin mensaje)
    """

    # ── Colores IRC usados en los mensajes ───────────────────────────────────
    # \x02 = negrita  \x03NN = color  \x03 solo = reset color  \x0F = reset todo
    _V  = "\x02"   # bold on/off
    _R  = "\x03"   # color reset
    _G  = "\x0303" # verde
    _RJ = "\x0304" # rojo
    _AZ = "\x0312" # azul
    _CY = "\x0310" # cyan
    _GR = "\x0314" # gris

    # ── Helpers de formato ────────────────────────────────────────────────────

    @staticmethod
    def _parte_str(minuto: str, parte_estado: str = '') -> str:
        """Devuelve ' - 2ª Parte' etc. a partir del minuto o el estado de parte."""
        if parte_estado in ('1ª', 'Descanso'):
            parte = '1ª'
        elif parte_estado == '2ª':
            parte = '2ª'
        elif parte_estado == '1ª PRO':
            parte = '1ª PRO'
        elif parte_estado == '2ª PRO':
            parte = '2ª PRO'
        else:
            try:
                m = int(re.sub(r'[^\d]', '', minuto.split('+')[0]))
            except Exception:
                m = 0
            if m <= 45:
                parte = '1ª'
            elif m <= 90:
                parte = '2ª'
            elif m <= 105:
                parte = '1ª PRO'
            else:
                parte = '2ª PRO'
        return f" - \x0312{parte} Parte"

    @staticmethod
    def _marcador_str(local: str, gl: str, gv: str, visitante: str) -> str:
        return (
            f"\x02\x0312{local}\x03\x02 "
            f"\x0304{gl}\x03-\x0304{gv}\x03 "
            f"\x02\x0312{visitante}\x03\x02"
        )

    @staticmethod
    def _liga_str(liga: str, color: str) -> str:
        return f"\x03{color}«{liga}»\x03" if liga else ""

    # ── Eventos de gol ────────────────────────────────────────────────────────

    @staticmethod
    def gol(liga: str, color: str, equipo: str, jugador: str,
            minuto: str, parte: str,
            local: str, gl: str, gv: str, visitante: str) -> str:
        lf  = EventFormatter._liga_str(liga, color)
        pf  = EventFormatter._parte_str(minuto, parte)
        mf  = EventFormatter._marcador_str(local, gl, gv, visitante)
        if equipo and jugador:
            return (f"{lf} \x033¡¡¡\x034GOO\x032OO\x034L\x033!!!\x03 "
                    f"\x032del\x03 \x02\x034{equipo}\x03\x02 \x033»\x03 "
                    f"\x032Marcó:\x03 \x02\x0312{jugador}\x03\x02 "
                    f"\x032(Min:\x0312 {minuto}{pf}\x032)\x03 \x033»\x03 {mf}")
        if equipo:
            return (f"{lf} \x033¡¡¡\x034GOO\x032OO\x034L\x033!!!\x03 "
                    f"\x032del\x03 \x02\x034{equipo}\x03\x02 "
                    f"\x032(Min:\x0312 {minuto}{pf}\x032)\x03 \x033»\x03 {mf}")
        return (f"{lf} \x033¡¡¡\x034GOO\x032OO\x034L\x033!!!\x03 "
                f"\x032(Min:\x0312 {minuto}{pf}\x032)\x03 \x033»\x03 {mf}")

    @staticmethod
    def gol_penalti(liga: str, color: str, equipo: str, jugador: str,
                    minuto: str, parte: str,
                    local: str, gl: str, gv: str, visitante: str) -> str:
        lf = EventFormatter._liga_str(liga, color)
        pf = EventFormatter._parte_str(minuto, parte)
        mf = EventFormatter._marcador_str(local, gl, gv, visitante)
        if equipo and jugador:
            return (f"{lf} \x033¡¡¡\x034P\x032ENALT\x034I\x033!!!\x03 "
                    f"\x032del\x03 \x02\x034{equipo}\x03\x02 \x033»\x03 "
                    f"\x032Marcó:\x03 \x02\x0312{jugador}\x03\x02 "
                    f"\x032(Min:\x0312 {minuto}{pf}\x032)\x03 \x033»\x03 {mf}")
        if equipo:
            return (f"{lf} \x033¡¡¡\x034P\x032ENALT\x034I\x033!!!\x03 "
                    f"\x032del\x03 \x02\x034{equipo}\x03\x02 "
                    f"\x032(Min:\x0312 {minuto}{pf}\x032)\x03 \x033»\x03 {mf}")
        return (f"{lf} \x033¡¡¡\x034P\x032ENALT\x034I\x033!!!\x03 "
                f"\x032(Min:\x0312 {minuto}{pf}\x032)\x03 \x033»\x03 {mf}")

    @staticmethod
    def autogol(liga: str, color: str, equipo: str, jugador: str,
                minuto: str, parte: str,
                local: str, gl: str, gv: str, visitante: str) -> str:
        lf = EventFormatter._liga_str(liga, color)
        pf = EventFormatter._parte_str(minuto, parte)
        mf = EventFormatter._marcador_str(local, gl, gv, visitante)
        if jugador and equipo:
            return (f"{lf} \x033¡¡¡\x034AUTOGOL\x033!!!\x03 "
                    f"\x032en propia puerta de\x03 \x02\x0312{jugador}\x03\x02 "
                    f"\x032del\x03 \x02\x034{equipo}\x03\x02 "
                    f"\x032(Min:\x0312 {minuto}{pf}\x032)\x03 \x033»\x03 {mf}")
        if jugador:
            return (f"{lf} \x033¡¡¡\x034AUTOGOL\x033!!!\x03 "
                    f"\x032en propia puerta de\x03 \x02\x0312{jugador}\x03\x02 "
                    f"\x032(Min:\x0312 {minuto}{pf}\x032)\x03 \x033»\x03 {mf}")
        return (f"{lf} \x033¡¡¡\x034AUTOGOL\x033!!!\x03 "
                f"\x032(Min:\x0312 {minuto}{pf}\x032)\x03 \x033»\x03 {mf}")

    # ── Tarjetas ──────────────────────────────────────────────────────────────

    @staticmethod
    def tarjeta_amarilla(liga: str, color: str, jugador: str, equipo: str,
                         minuto: str, parte: str) -> str:
        lf = EventFormatter._liga_str(liga, color)
        pf = EventFormatter._parte_str(minuto, parte)
        if jugador and equipo:
            return (f"{lf} \x034T\x032arjeta \x038A\x032marilla\x03 "
                    f"\x038,8|_\x03 \x032para\x03 \x02\x0312{jugador}\x03\x02 "
                    f"\x032del\x03 \x02\x034{equipo}\x03\x02 "
                    f"\x032(Min:\x0312 {minuto}{pf}\x032)\x03")
        if jugador:
            return (f"{lf} \x034T\x032arjeta \x038A\x032marilla\x03 "
                    f"\x038,8|_\x03 \x032para\x03 \x02\x0312{jugador}\x03\x02 "
                    f"\x032(Min:\x0312 {minuto}{pf}\x032)\x03")
        return f"{lf} \x034T\x032arjeta \x038A\x032marilla\x03 \x032(Min:\x0312 {minuto}{pf}\x032)\x03"

    @staticmethod
    def tarjeta_roja(liga: str, color: str, jugador: str, equipo: str,
                     minuto: str, parte: str, doble: bool = False) -> str:
        lf = EventFormatter._liga_str(liga, color)
        pf = EventFormatter._parte_str(minuto, parte)
        exp = " \x033»\x03 \x02\x034¡EXPULSADO!\x03\x02"
        if doble:
            header = "\x033⚠️\x03 \x03042ª AMARILLA = ROJA\x03 \x033⚠️\x03"
        else:
            header = "\x034T\x032arjeta \x034R\x032oja\x03 \x034,4|_\x03"
        if jugador and equipo:
            return (f"{lf} {header} \x032para\x03 \x02\x0312{jugador}\x03\x02 "
                    f"\x032del\x03 \x02\x034{equipo}\x03\x02 "
                    f"\x032(Min:\x0312 {minuto}{pf}\x032)\x03{exp}")
        if jugador:
            return (f"{lf} {header} \x032para\x03 \x02\x0312{jugador}\x03\x02 "
                    f"\x032(Min:\x0312 {minuto}{pf}\x032)\x03{exp}")
        return f"{lf} {header} \x032(Min:\x0312 {minuto}{pf}\x032)\x03{exp}"

    # ── Cambio ────────────────────────────────────────────────────────────────

    @staticmethod
    def cambio(liga: str, color: str, equipo: str,
               sale: str, entra: str, minuto: str, parte: str) -> Optional[str]:
        lf = EventFormatter._liga_str(liga, color)
        pf = EventFormatter._parte_str(minuto, parte)
        pf_fmt = f"'{pf}" if pf else "'"
        if sale and entra:
            base = (f"\x033»\x03 \x034Sale:\x03 \x02\x0312{sale}\x03\x02 "
                    f"\x033»\x03 \x032Entra:\x03 \x02\x0312{entra}\x03\x02 "
                    f"\x032(Min:\x0312 {minuto}{pf_fmt}\x032)\x03")
        elif entra:
            base = (f"\x033»\x03 \x032Entra:\x03 \x02\x0312{entra}\x03\x02 "
                    f"\x032(Min:\x0312 {minuto}{pf_fmt}\x032)\x03")
        elif sale:
            base = (f"\x033»\x03 \x034Sale:\x03 \x02\x0312{sale}\x03\x02 "
                    f"\x032(Min:\x0312 {minuto}{pf_fmt}\x032)\x03")
        else:
            return None
        header = "\x033¡¡¡\x034C\x032ambi\x032o\x033!!!\x03"
        if equipo:
            # Evitar "del el Levante" -> "del Levante"
            equipo_limpio = re.sub(r'^(?:el|la|los|las)\s+', '', equipo, flags=re.IGNORECASE)
            return f"{lf} {header} \x032del:\x03 \x02\x034{equipo_limpio}\x03\x02 {base}"
        return f"{lf} {header} {base}"

    # ── Penaltis ──────────────────────────────────────────────────────────────

    @staticmethod
    def penalti_senalado(liga: str, color: str, equipo: str, jugador: str,
                         minuto: str, parte: str,
                         local: str, gl: str, gv: str, visitante: str) -> str:
        lf = EventFormatter._liga_str(liga, color)
        pf = EventFormatter._parte_str(minuto, parte)
        mf = EventFormatter._marcador_str(local, gl, gv, visitante)
        if jugador and equipo:
            return (f"{lf} \x034⚠️\x03 \x032¡PENALTI para\x03 "
                    f"\x02\x034{equipo}\x03\x02 \x033»\x03 "
                    f"\x032Cometido sobre\x03 \x02\x0312{jugador}\x03\x02 "
                    f"\x032(Min:\x0312 {minuto}{pf}\x032)\x03 \x033»\x03 {mf}")
        if equipo:
            return (f"{lf} \x034⚠️\x03 \x032¡PENALTI para\x03 "
                    f"\x02\x034{equipo}\x03\x02 "
                    f"\x032(Min:\x0312 {minuto}{pf}\x032)\x03 \x033»\x03 {mf}")
        return (f"{lf} \x034⚠️\x03 \x032¡PENALTI!\x03 "
                f"\x032(Min:\x0312 {minuto}{pf}\x032)\x03 \x033»\x03 {mf}")

    @staticmethod
    def penalti_fallado(liga: str, color: str, jugador: str, equipo: str,
                        minuto: str, parte: str) -> str:
        lf = EventFormatter._liga_str(liga, color)
        pf = EventFormatter._parte_str(minuto, parte)
        if jugador and equipo:
            return (f"{lf} \x034❌\x03 \x032¡¡PENALTI FALLADO!!\x03 "
                    f"\x032por\x03 \x02\x0312{jugador}\x03\x02 "
                    f"\x032del\x03 \x02\x034{equipo}\x03\x02 "
                    f"\x032(Min:\x0312 {minuto}{pf}\x032)\x03")
        if jugador:
            return (f"{lf} \x034❌\x03 \x032¡¡PENALTI FALLADO!!\x03 "
                    f"\x032por\x03 \x02\x0312{jugador}\x03\x02 "
                    f"\x032(Min:\x0312 {minuto}{pf}\x032)\x03")
        return (f"{lf} \x034❌\x03 \x032¡¡PENALTI FALLADO!!\x03 "
                f"\x032(Min:\x0312 {minuto}{pf}\x032)\x03")

    @staticmethod
    def penalti_parado(liga: str, color: str, jugador: str, equipo: str,
                       minuto: str, parte: str) -> str:
        lf = EventFormatter._liga_str(liga, color)
        pf = EventFormatter._parte_str(minuto, parte)
        if jugador and equipo:
            return (f"{lf} \x034🧤\x03 \x032¡¡PENALTI PARADO!!\x03 "
                    f"\x032por\x03 \x02\x0312{jugador}\x03\x02 "
                    f"\x032del\x03 \x02\x034{equipo}\x03\x02 "
                    f"\x032(Min:\x0312 {minuto}{pf}\x032)\x03")
        if jugador:
            return (f"{lf} \x034🧤\x03 \x032¡¡PENALTI PARADO!!\x03 "
                    f"\x032por\x03 \x02\x0312{jugador}\x03\x02 "
                    f"\x032(Min:\x0312 {minuto}{pf}\x032)\x03")
        return (f"{lf} \x034🧤\x03 \x032¡¡PENALTI PARADO!!\x03 "
                f"\x032(Min:\x0312 {minuto}{pf}\x032)\x03")

    # ── Tanda de penaltis ─────────────────────────────────────────────────────

    @staticmethod
    def tanda_inicio(liga: str, color: str,
                     local: str, gl: str, gv: str, visitante: str) -> str:
        lf = EventFormatter._liga_str(liga, color)
        mf = EventFormatter._marcador_str(local, gl, gv, visitante)
        return f"{lf} \x033»\x03 \x034🎯 ¡¡TANDA DE PENALTIS!!\x03 \x033«\x03 {mf}"

    @staticmethod
    def tanda_gol(liga: str, color: str, jugador: str, equipo: str,
                  local: str, tl: int, tv: int, visitante: str) -> str:
        lf  = EventFormatter._liga_str(liga, color)
        mt  = f"(\x0303{tl}\x03-\x0303{tv}\x03)"
        if jugador and equipo:
            return (f"{lf} \x033✅\x03 \x032Gol en tanda:\x03 "
                    f"\x02\x0312{jugador}\x03\x02 \x032del\x03 \x02\x034{equipo}\x03\x02 "
                    f"\x033»\x03 \x02\x0312{local}\x03\x02 {mt} \x02\x0312{visitante}\x03\x02")
        if jugador:
            return (f"{lf} \x033✅\x03 \x032Gol en tanda:\x03 "
                    f"\x02\x0312{jugador}\x03\x02 "
                    f"\x033»\x03 \x02\x0312{local}\x03\x02 {mt} \x02\x0312{visitante}\x03\x02")
        return (f"{lf} \x033✅\x03 \x032Gol en tanda\x03 "
                f"\x033»\x03 \x02\x0312{local}\x03\x02 {mt} \x02\x0312{visitante}\x03\x02")

    @staticmethod
    def tanda_fallo(liga: str, color: str, jugador: str, equipo: str,
                    local: str, tl: int, tv: int, visitante: str) -> str:
        lf  = EventFormatter._liga_str(liga, color)
        mt  = f"(\x0303{tl}\x03-\x0303{tv}\x03)"
        if jugador and equipo:
            return (f"{lf} \x034❌\x03 \x032Fallo en tanda:\x03 "
                    f"\x02\x0312{jugador}\x03\x02 \x032del\x03 \x02\x034{equipo}\x03\x02 "
                    f"\x033»\x03 \x02\x0312{local}\x03\x02 {mt} \x02\x0312{visitante}\x03\x02")
        if jugador:
            return (f"{lf} \x034❌\x03 \x032Fallo en tanda:\x03 "
                    f"\x02\x0312{jugador}\x03\x02 "
                    f"\x033»\x03 \x02\x0312{local}\x03\x02 {mt} \x02\x0312{visitante}\x03\x02")
        return (f"{lf} \x034❌\x03 \x032Fallo en tanda\x03 "
                f"\x033»\x03 \x02\x0312{local}\x03\x02 {mt} \x02\x0312{visitante}\x03\x02")

    # ── VAR / Gol anulado / Descanso ──────────────────────────────────────────

    @staticmethod
    def gol_anulado(liga: str, color: str, equipo: str, jugador: str,
                    motivo: str, minuto: str, parte: str,
                    local: str, gl: str, gv: str, visitante: str) -> str:
        lf = EventFormatter._liga_str(liga, color)
        pf = EventFormatter._parte_str(minuto, parte)
        mf = EventFormatter._marcador_str(local, gl, gv, visitante)
        header = "\x033»\x03 \x034⚑ GOL ANULADO\x03"
        if equipo and jugador and motivo:
            return (f"{lf} {header} \x032a\x03 \x02\x034{equipo}\x03\x02 "
                    f"\x033»\x03 \x032{motivo} de\x03 \x02\x0312{jugador}\x03\x02 "
                    f"\x032(Min:\x0312 {minuto}{pf}\x032)\x03 \x033»\x03 {mf}")
        if equipo and jugador:
            return (f"{lf} {header} \x032a\x03 \x02\x034{equipo}\x03\x02 "
                    f"\x033»\x03 \x032Gol anulado a\x03 \x02\x0312{jugador}\x03\x02 "
                    f"\x032(Min:\x0312 {minuto}{pf}\x032)\x03 \x033»\x03 {mf}")
        if equipo:
            return (f"{lf} {header} \x032a\x03 \x02\x034{equipo}\x03\x02 "
                    f"\x032(Min:\x0312 {minuto}{pf}\x032)\x03 \x033»\x03 {mf}")
        return f"{lf} {header} \x032(Min:\x0312 {minuto}{pf}\x032)\x03 \x033»\x03 {mf}"

    @staticmethod
    def var_revision(liga: str, color: str, minuto: str, parte: str,
                     local: str, gl: str, gv: str, visitante: str) -> str:
        lf = EventFormatter._liga_str(liga, color)
        pf = EventFormatter._parte_str(minuto, parte)
        mf = EventFormatter._marcador_str(local, gl, gv, visitante)
        return (f"{lf} \x033»\x03 \x034V\x032A\x034R\x03 \x033«\x03 "
                f"\x032Revisión en curso\x03 "
                f"\x032(Min:\x0312 {minuto}{pf}\x032)\x03 \x033»\x03 {mf}")

    @staticmethod
    def descanso(liga: str, color: str,
                 local: str, gl: str, gv: str, visitante: str) -> str:
        lf = EventFormatter._liga_str(liga, color)
        mf = EventFormatter._marcador_str(local, gl, gv, visitante)
        return (f"{lf} \x033»\x03 \x0304D\x0302escanso\x03 \x033«\x03 {mf}")

    @staticmethod
    def inicio_2a_parte(liga: str, color: str,
                        local: str, gl: str, gv: str, visitante: str) -> str:
        lf = EventFormatter._liga_str(liga, color)
        mf = EventFormatter._marcador_str(local, gl, gv, visitante)
        return (f"{lf} \x033»\x03 \x0304E\x0302mpieza la 2ª \x0304P\x0302arte\x03 \x033«\x03 {mf}")

    @staticmethod
    def inicio_partido(liga: str, color: str, local: str, visitante: str) -> str:
        return (f"\x03{color}«{liga}»\x0F "
                f"⚽ \x02¡Comienza el partido!\x02 "
                f"\x0312{local}\x0F vs \x0304{visitante}\x0F")

    @staticmethod
    def fin_partido(liga: str, color: str,
                    local: str, gl: str, gv: str, visitante: str) -> str:
        lf = EventFormatter._liga_str(liga, color)
        mf = EventFormatter._marcador_str(local, gl, gv, visitante)
        return f"{lf} \x033»\x03 \x02Final del Partido\x03\x02 \x033«\x03 {mf}"

    @staticmethod
    def asistencia(liga: str, color: str, jugador: str, equipo: str,
                   minuto: str, parte: str) -> str:
        lf = EventFormatter._liga_str(liga, color)
        pf = EventFormatter._parte_str(minuto, parte)
        if jugador and equipo:
            return (f"{lf} \x033»\x03 \x032Asistencia de\x03 "
                    f"\x02\x0312{jugador}\x03\x02 \x032del\x03 "
                    f"\x02\x034{equipo}\x03\x02 "
                    f"\x032(Min:\x0312 {minuto}{pf}\x032)\x03")
        if jugador:
            return (f"{lf} \x033»\x03 \x032Asistencia de\x03 "
                    f"\x02\x0312{jugador}\x03\x02 "
                    f"\x032(Min:\x0312 {minuto}{pf}\x032)\x03")
        return f"{lf} \x033»\x03 \x032Asistencia\x03 \x032(Min:\x0312 {minuto}{pf}\x032)\x03"

    @staticmethod
    def lesion(liga: str, color: str, texto: str, minuto: str,
               local: str, gl: str, gv: str, visitante: str) -> str:
        lf = EventFormatter._liga_str(liga, color)
        mf = EventFormatter._marcador_str(local, gl, gv, visitante)
        return (f"{lf} \x034🚑\x03 {minuto}' \x033»\x03 "
                f"{texto} \x033»\x03 {mf}")

    @staticmethod
    def generico(liga: str, color: str, emoji: str, texto: str, minuto: str,
                 local: str, gl: str, gv: str, visitante: str) -> str:
        """Formato de último recurso para eventos sin handler específico."""
        lf = EventFormatter._liga_str(liga, color)
        mf = EventFormatter._marcador_str(local, gl, gv, visitante)
        return f"{lf} {emoji} {minuto}' \x033»\x03 {texto} \x033»\x03 {mf}"


class FootballScraper:
    def __init__(self, db: BotDB, bot_callback):
        self.db = db
        self.bot_callback = bot_callback
        self.running = False
        self.pre_reload_hashes = {}        # {partido_id: hash} — silencio inteligente post-reload
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': Config.USER_AGENT})
        # Connection pooling: reutilizar conexiones TCP
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        _retry = Retry(total=2, backoff_factor=0.5, status_forcelist=[500, 502, 503])
        _adapter = HTTPAdapter(pool_connections=2, pool_maxsize=10, max_retries=_retry)
        self.session.mount('https://', _adapter)
        self.session.mount('http://', _adapter)
        self.partidos_activos = {}         # {partido_id: dict de estado}
        self._cambios_pendientes = {}      # {partido_id: {equipo_minuto: jugador_sale}}

        # ── Estructuras nuevas (refactor) ─────────────────────────────────────
        # Set de hashes ya anunciados por partido.  Reemplaza el catch-up por
        # índice (num_eventos) que fallaba cuando la web reordenaba eventos.
        self._hashes_vistos: Dict[str, Set[str]] = {}   # {partido_id: {hash, ...}}

        # Un lock por partido para que los threads concurrentes no se pisen al
        # leer/escribir partidos_activos y _hashes_vistos.
        self._partido_locks: Dict[str, threading.Lock] = {}

        # Sesión separada por thread (thread-safe)
        self._session_lock = threading.Lock()
    

    def _evento_hash(self, minuto, jugador, icono, tipo_evento='evento'):
        """
        Genera un hash único para identificar un evento y evitar duplicados.
        
        Args:
            minuto: Minuto del evento (ej: "64", "90+2")
            jugador: Nombre del jugador
            icono: Nombre del archivo de icono
            tipo_evento: Tipo (gol, tarjeta, cambio, etc.)
        
        Returns:
            Hash único del evento (ej: "64:ramazani:accion1:gol")
        """
        try:
            # Normalizar jugador: quitar acentos, minúsculas, espacios
            jugador_norm = unicodedata.normalize('NFKD', str(jugador))
            jugador_norm = jugador_norm.encode('ASCII', 'ignore').decode('ASCII')
            jugador_norm = jugador_norm.lower().strip().replace(' ', '').replace('.', '')
            
            # Normalizar minuto: quitar espacios
            minuto_norm = str(minuto).strip().replace(' ', '')
            
            # Extraer nombre del icono (sin .png)
            icono_norm = str(icono).replace('.png', '').lower()
            
            # Crear hash
            return f"{minuto_norm}:{jugador_norm}:{icono_norm}:{tipo_evento}"
        except Exception as e:
            logging.error(f"Error generando hash: {e}")
            return f"{minuto}:{jugador}:{tipo_evento}"
    
    def _debug(self, mensaje, importante=False):
        """Envía un mensaje de debug al canal y/o log"""
        if importante:
            logging.info(mensaje)
        else:
            logging.debug(mensaje)
        if Config.DEBUG_TO_CHANNEL and importante:
            self.bot_callback('message', Config.CANAL_DEBUG, f"[DEBUG] {mensaje}")
    
    def start(self):
        """Inicia el scraper en un thread separado"""
        self.running = True
        self.thread = threading.Thread(target=self._run_scraper, daemon=True)
        self.thread.start()
    
    def stop(self):
        """Detiene el scraper"""
        self.running = False
        logging.info("🛑 Scraper de partidos detenido")
        self._debug("🛑 Scraper de partidos detenido")
    
    def _liga_permitida(self, nombre_liga):
        """Verifica si una liga está en la lista de permitidas.
        
        NOTA: 'primera división' y 'segunda división' sin sufijo de país = España.
        Si la web trae 'Primera División Bolivia' (u otro país), se rechaza.
        """
        nombre_lower = nombre_liga.lower()
        
        # Excluir explícitamente ligas femeninas, juveniles y divisiones de honor
        excluidas = ['femenina', 'femenino', 'juvenil', 'u19', 'u21', 'división de honor', 'honor grupo']
        for excluida in excluidas:
            if excluida in nombre_lower:
                return False
        
        # Excluir champions/europa/conference de otras confederaciones (no UEFA)
        confederaciones_excluidas = ['afc', 'concacaf', 'caf', 'conmebol', 'ofc']
        for conf in confederaciones_excluidas:
            if conf in nombre_lower:
                return False
        
        # Excluir "Primera/Segunda División" de otros países
        paises_excluidos = [
            'bolivia', 'paraguay', 'argentina', 'colombia', 'chile', 'peru',
            'uruguay', 'venezuela', 'ecuador', 'costa rica', 'mexico', 'méxico',
            'honduras', 'guatemala', 'panamá', 'panama', 'brasil', 'portugal',
            'grecia', 'turquia', 'turquía', 'rumania', 'serbia', 'croacia',
            'bulgaria', 'hungria', 'hungría', 'eslovaquia', 'eslovenia',
            'australia', 'japón', 'japon', 'corea', 'china', 'india',
            'arabia', 'emiratos', 'qatar', 'iran', 'irán', 'israel',
            'sudáfrica', 'sudafrica', 'nigeria', 'egipto', 'marruecos',
            'argelia', 'tunez', 'túnez',
        ]
        if 'división' in nombre_lower or 'division' in nombre_lower:
            for pais in paises_excluidos:
                if pais in nombre_lower:
                    return False
        
        # Finalmente verificar si está en las permitidas
        for liga in Config.LIGAS_PERMITIDAS:
            liga_clean = liga.replace('ó', 'o').replace('í', 'i').replace('á', 'a')
            n_clean = nombre_lower.replace('ó', 'o').replace('í', 'i').replace('á', 'a')
            
            if liga == nombre_lower or liga_clean == n_clean:
                return True
            # Para ligas tipo "Champions League" permitimos coincidencia parcial si es exacto el término
            if liga in ['champions league', 'europa league', 'conference league'] and liga in nombre_lower:
                return True
            
        return False

    def _es_equipo_esp(self, nombre):
        """Verifica si un equipo es español (o la selección) para filtrar competiciones internacionales"""
        if not nombre: return False
        n = nombre.lower()
        # Lista de palabras clave para identificar equipos españoles
        espanoles = [
            "españa", "espana", "madrid", "barcelona", "atlético", "atletico", "sevilla", 
            "betis", "villarreal", "sociedad", "athletic", "osasuna", "girona", 
            "valencia", "getafe", "rayo vallecano", "las palmas", "alavés", "alaves",
            "mallorca", "granada", "celta", "cádiz", "cadiz", "almería", "almeria",
            "espanyol", "zaragoza", "levante", "eibar", "elche", "leganés", "leganes",
            "valladolid", "sporting gijon", "sporting de gijon", "oviedo", "racing",
            "tenerife", "burgos", "ferrol", "mirandés", "mirandes", "cartagena",
            "huesca", "alcorcón", "alcorcon", "albacete", "málaga", "malaga", "deportivo",
            "ponferradina", "ibiza", "lugo", "badajoz", "córdoba", "cordoba", "recreativo",
            "castellón", "castellon", "hércules", "hercules", "murcia"
        ]
        
        # Caso especial para "Sporting" (evitar Sporting Braga, Sporting Portugal)
        if "sporting" in n:
            if any(x in n for x in ["braga", "lisboa", "portugal", "sporting cp"]):
                return False
            return True
            
        return any(e in n for e in espanoles)
    
    def _obtener_nombre_liga(self, nombre_liga):
        """Obtiene el nombre a mostrar de la liga (con posible rename)"""
        nombre_lower = nombre_liga.lower()
        # Primero intentar coincidencia exacta para evitar que "Primera División Bolivia" 
        # se convierta en "LaLiga EA Sports"
        for original, nuevo in Config.LIGAS_RENAME.items():
            if original == nombre_lower:
                return nuevo
        
        # Luego coincidencia parcial
        for original, nuevo in Config.LIGAS_RENAME.items():
            if original in nombre_lower:
                return nuevo
        # Limpiar nombre por defecto
        return nombre_liga.replace('»', '').strip()
    
    def _obtener_color_liga(self, nombre_liga):
        """Obtiene el código de color IRC para la liga"""
        nombre_lower = nombre_liga.lower()
        for liga, color in Config.LIGAS_COLORES.items():
            if liga in nombre_lower:
                return color
        return "14"  # Gris por defecto
    
    def buscar_partido_en_web(self, equipo_local, equipo_visitante):
        """Busca un partido en la web y devuelve su liga si lo encuentra"""
        try:
            eq_local_low = equipo_local.lower()
            eq_visitante_low = equipo_visitante.lower()
            
            for url in Config.SCRAPER_LIVESCORE_URLS:
                try:
                    response = self.session.get(url, timeout=10)
                    # No forzar UTF-8, dejar que requests/BeautifulSoup detecten la codificación real
                    # de resultados-futbol.com (suele ser ISO-8859-1 o similar)
                    soup = BeautifulSoup(response.content, 'lxml', from_encoding=response.apparent_encoding)
                    
                    # Buscar ligas con la misma estructura que _buscar_partidos
                    for liga_div in soup.find_all('div', class_='liga'):
                        titulo_liga = liga_div.find('h2', class_='title')
                        if not titulo_liga:
                            continue
                        nombre_liga = titulo_liga.get_text(strip=True).replace('»', '').strip()
                        
                        tabla = liga_div.find('table', class_='tablemarcador')
                        if not tabla:
                            continue
                        
                        for fila in tabla.find_all('tr'):
                            team_home = fila.find('td', class_='team-home')
                            team_away = fila.find('td', class_='team-away')
                            if not team_home or not team_away:
                                continue
                            
                            local = team_home.get_text(strip=True).lower()
                            visitante = team_away.get_text(strip=True).lower()
                            
                            # Comparar equipos (coincidencia parcial, ambos órdenes)
                            if (eq_local_low in local or local in eq_local_low) and \
                               (eq_visitante_low in visitante or visitante in eq_visitante_low):
                                return self._obtener_nombre_liga(nombre_liga)
                            if (eq_visitante_low in local or local in eq_visitante_low) and \
                               (eq_local_low in visitante or visitante in eq_local_low):
                                return self._obtener_nombre_liga(nombre_liga)
                except Exception as e:
                    logging.error(f"Error buscando partido en {url}: {e}")
                    continue
            
            return None
            
        except Exception as e:
            logging.error(f"Error buscando partido en web: {e}")
            return None
    
    def _run_scraper(self):
        """Loop principal del scraper.

        Arquitectura refactorizada (v2):
        ─────────────────────────────────────────────────────────────────
        ANTES  (secuencial):
            para cada partido → _revisar_partido() → sleep(2) → siguiente
            Latencia máxima con N partidos: 30s + 2×N  (=40s con 5 partidos)

        AHORA  (paralelo):
            Lanza un thread daemon por partido activo, todos corren a la vez.
            Latencia máxima: max(tiempo_HTTP_por_partido) ≈ 10-15 s
            El sleep(SCRAPER_INTERVAL) marca la cadencia del ciclo de búsqueda,
            no la de revisión individual.
        ─────────────────────────────────────────────────────────────────
        """
        while self.running:
            try:
                _soups = self._buscar_partidos() or {}
                self._anunciar_partidos_proximos(_soups)

                partidos_ids = list(self.partidos_activos.keys())
                if partidos_ids:
                    # Crear un lock por partido si aún no existe
                    for pid in partidos_ids:
                        if pid not in self._partido_locks:
                            self._partido_locks[pid] = threading.Lock()
                        if pid not in self._hashes_vistos:
                            self._hashes_vistos[pid] = set()

                    # Lanzar threads en paralelo
                    threads = [
                        threading.Thread(
                            target=self._revisar_partido_safe,
                            args=(pid,),
                            daemon=True,
                            name=f"scraper-{pid[:20]}"
                        )
                        for pid in partidos_ids
                    ]
                    for t in threads:
                        t.start()
                    # Esperar a que terminen (timeout generoso para no bloquear el ciclo)
                    for t in threads:
                        t.join(timeout=20)

                    # Limpiar locks de partidos que ya no están activos
                    ids_inactivos = set(self._partido_locks) - set(self.partidos_activos)
                    for pid in ids_inactivos:
                        self._partido_locks.pop(pid, None)
                        self._hashes_vistos.pop(pid, None)
                        self._cambios_pendientes.pop(pid, None)

                    self._debug(f"🔄 Revisados {len(partidos_ids)} partidos (paralelo)")

                self.db.limpiar_partidos_antiguos()
                self._debug(f"⏳ Esperando {Config.SCRAPER_INTERVAL}s para próxima búsqueda...")
                time.sleep(Config.SCRAPER_INTERVAL)

            except Exception as e:
                logging.error(f"Error en scraper: {e}", exc_info=True)
                time.sleep(30)

    def _revisar_partido_safe(self, partido_id: str) -> None:
        """Wrapper con manejo de excepciones para llamar desde thread."""
        try:
            self._revisar_partido(partido_id)
        except Exception as e:
            logging.error(f"Error revisando {partido_id}: {e}", exc_info=True)
    
    def _anunciar_partidos_proximos(self, livescore_soups=None):
        """Busca partidos que comienzan en 15-20 min y anuncia con alineación.
        
        Flujo:
        - Primera detección (15-20 min antes): envía «Liga» ⏰ En ~X min: A vs B
          + alineación si ya está disponible. Si no hay alineación, marca
          'alineacion_anunciada': False para reintentar en el siguiente ciclo.
        - Ciclos siguientes: si 'previo_anunciado' pero 'alineacion_anunciada' es False,
          reintenta obtener la alineación y la envía en cuanto esté disponible.
          Deja de reintentar cuando el partido ya ha comenzado (parte != 'Próximo').
        """
        try:
            ahora = datetime.now()

            # ── PASO 1: Reintentar alineaciones pendientes ──────────────────────
            for partido_id, info in list(self.partidos_activos.items()):
                if not info.get('previo_anunciado', False):
                    continue
                if info.get('alineacion_anunciada', True):
                    continue
                # Si el partido ya empezó, ya no tiene sentido enviar alineación
                if info.get('parte', 'Próximo') not in ('Próximo', ''):
                    info['alineacion_anunciada'] = True
                    continue

                local     = info.get('local', '')
                visitante = info.get('visitante', '')
                nombre_liga = info.get('liga', '')
                color_liga  = info.get('color', '14')

                alineacion_local, alineacion_visitante = self._obtener_alineacion_previa(
                    partido_id, local, visitante
                )
                if not alineacion_local and not alineacion_visitante:
                    logging.info(f"⏳ Alineación aún no disponible, reintentando: {local} vs {visitante}")
                    continue  # volvemos a intentarlo en el próximo ciclo

                liga_fmt = f"\x03{color_liga}«{nombre_liga}»\x03"
                ali_l = '\x0312' + ' · '.join(alineacion_local)  + '\x03' if alineacion_local  else '\x0314Sin datos\x03'
                ali_v = '\x0304' + ' · '.join(alineacion_visitante) + '\x03' if alineacion_visitante else '\x0314Sin datos\x03'
                linea2 = f"{liga_fmt} \x0312{local}\x03: {ali_l}"
                linea3 = f"{liga_fmt} \x0304{visitante}\x03: {ali_v}"

                canales = self.db.get_canales_narracion_activa()
                for canal in canales:
                    for msg in [linea2, linea3]:
                        self.bot_callback('message', canal, msg)
                        time.sleep(0.3)

                info['alineacion_anunciada'] = True
                logging.info(f"📋 Alineación (reintento OK): {local} vs {visitante} [{nombre_liga}]")

            # ── PASO 2: Detectar nuevos partidos en ventana 15-20 min ────────────
            if livescore_soups is None:
                livescore_soups = {}
            for url in Config.SCRAPER_LIVESCORE_URLS:
                try:
                    if url in livescore_soups:
                        soup = livescore_soups[url]
                    else:
                        response = self.session.get(url, timeout=10)
                        soup = BeautifulSoup(response.content, 'lxml', from_encoding=response.apparent_encoding)
                except Exception as e:
                    logging.error(f"Error descargando {url}: {e}")
                    continue

                for liga_div in soup.find_all('div', class_=re.compile(r'liga|competition|league', re.I)):
                    titulo_liga = liga_div.find(['h2', 'h3', 'div'], class_=re.compile(r'title|nombre|liga', re.I))
                    nombre_liga_raw = titulo_liga.get_text(strip=True) if titulo_liga else ''
                    if not self._liga_permitida(nombre_liga_raw):
                        continue
                    nombre_liga = self._obtener_nombre_liga(nombre_liga_raw)
                    color_liga  = self._obtener_color_liga(nombre_liga)

                    tabla = liga_div.find('table', class_='tablemarcador')
                    if not tabla:
                        continue

                    for fila in tabla.find_all('tr'):
                        # Los partidos "Próximo" llevan clase nonplayingnow; los en vivo
                        # tienen span.playing activo (sin nonplayingnow). Excluimos publicidad
                        # y partidos ya en curso.
                        clases_fila = ' '.join(fila.get('class', []))
                        if 'advertising-row' in clases_fila:
                            continue
                        playing_span = fila.find('span', class_='playing')
                        if playing_span and 'nonplayingnow' not in ' '.join(playing_span.get('class', [])):
                            continue  # en vivo, no es próximo

                        # Extraer hora (timer_td o chk_hour)
                        hora_str = None
                        timer_td = fila.find('td', class_='timer')
                        if timer_td:
                            hora_str = timer_td.get_text(strip=True)
                        if not hora_str:
                            chk = fila.find('div', class_='chk_hour')
                            if chk:
                                hora_str = chk.get_text(strip=True)
                        if not hora_str:
                            continue

                        m = re.search(r'(\d{1,2}):(\d{2})', hora_str)
                        if not m:
                            continue
                        hora_partido = ahora.replace(
                            hour=int(m.group(1)), minute=int(m.group(2)),
                            second=0, microsecond=0
                        )
                        minutos_para_inicio = (hora_partido - ahora).total_seconds() / 60

                        # Ventana: entre 15 y 20 minutos antes del inicio
                        if not (15 <= minutos_para_inicio <= 20):
                            continue

                        # Partido ID
                        enlace = fila.find('a', href=re.compile(r'/partido/'))
                        if not enlace:
                            continue
                        href     = enlace.get('href', '')
                        match_id = re.search(r'/partido/(.+?)(?:/\d+)?$', href)
                        if not match_id:
                            continue
                        partido_id = match_id.group(1).replace('/', '_')

                        # Ya anunciado: no repetir linea1
                        if self.partidos_activos.get(partido_id, {}).get('previo_anunciado', False):
                            continue

                        # Equipos
                        team_home = fila.find('td', class_='team-home')
                        team_away = fila.find('td', class_='team-away')
                        if not team_home or not team_away:
                            continue
                        local     = team_home.get_text(strip=True)
                        visitante = team_away.get_text(strip=True)

                        # Filtro de participación española en ligas internacionales
                        if nombre_liga.lower() in [l.lower() for l in Config.LIGAS_INTERNACIONALES]:
                            if not self._es_equipo_esp(local) and not self._es_equipo_esp(visitante):
                                continue

                        # Registrar en partidos_activos
                        if partido_id not in self.partidos_activos:
                            self.partidos_activos[partido_id] = {
                                'parte': 'Próximo', 'liga': nombre_liga, 'color': color_liga,
                                'local': local, 'visitante': visitante, 'anunciado': False,
                                'marcador': '0 - 0', 'descanso_anunciado': False,
                                'inicio_2a_anunciado': False,
                            }
                        self.partidos_activos[partido_id]['previo_anunciado'] = True

                        # Intentar obtener alineación
                        alineacion_local, alineacion_visitante = self._obtener_alineacion_previa(
                            partido_id, local, visitante
                        )
                        tiene_alineacion = bool(alineacion_local or alineacion_visitante)
                        self.partidos_activos[partido_id]['alineacion_anunciada'] = tiene_alineacion

                        # Construir y enviar mensajes
                        liga_fmt = f"\x03{color_liga}«{nombre_liga}»\x03"
                        mins     = int(minutos_para_inicio)
                        linea1   = (
                            f"{liga_fmt} \x033»\x03 \x02⏰ En ~{mins} min:\x02 "
                            f"\x0312{local}\x0F vs \x0304{visitante}\x0F "
                            f"\x033«\x03 \x0314{hora_partido.strftime('%H:%M')}\x03"
                        )
                        mensajes = [linea1]
                        if tiene_alineacion:
                            ali_l = '\x0312' + ' · '.join(alineacion_local)     + '\x03' if alineacion_local     else '\x0314Sin datos\x03'
                            ali_v = '\x0304' + ' · '.join(alineacion_visitante) + '\x03' if alineacion_visitante else '\x0314Sin datos\x03'
                            mensajes.append(f"{liga_fmt} \x0312{local}\x03: {ali_l}")
                            mensajes.append(f"{liga_fmt} \x0304{visitante}\x03: {ali_v}")
                        else:
                            logging.info(f"⏳ Sin alineación aún, se reintentará: {local} vs {visitante}")

                        canales = self.db.get_canales_narracion_activa()
                        for canal in canales:
                            for msg in mensajes:
                                self.bot_callback('message', canal, msg)
                                time.sleep(0.3)

                        logging.info(f"📣 Anuncio previo: {local} vs {visitante} en {mins} min [{nombre_liga}] (alineación: {'✅' if tiene_alineacion else '⏳'})")

        except Exception as e:
            logging.error(f"Error en _anunciar_partidos_proximos: {e}", exc_info=True)

    def _obtener_alineacion_previa(self, partido_id, equipo_local, equipo_visitante):
        """Raspa la página /alineacion del partido y devuelve dos listas de jugadores titulares."""
        alineacion_local = []
        alineacion_visitante = []
        try:
            url = f"{Config.SCRAPER_URL}/partido/{partido_id.replace('_', '/')}/alineacion"
            response = self.session.get(url, timeout=10)
            if response.status_code != 200:
                return alineacion_local, alineacion_visitante
            soup = BeautifulSoup(response.content, 'lxml', from_encoding=response.apparent_encoding)

            # La página de alineación tiene dos bloques: equipo1 y equipo2
            # Cada uno con una lista de jugadores titulares en elementos con clase "jugador" o similar
            for lado, lista in [('equipo1', alineacion_local), ('equipo2', alineacion_visitante)]:
                bloque = soup.find('div', class_=re.compile(lado, re.I))
                if not bloque:
                    continue
                # Titulares: elementos con clase "tit" o dentro de tabla de titular
                for jugador_tag in bloque.find_all(
                    ['span', 'div', 'td', 'li'],
                    class_=re.compile(r'tit|titular|player-name|jugador', re.I)
                ):
                    nombre = jugador_tag.get_text(strip=True)
                    if nombre and len(nombre) > 1 and nombre not in lista:
                        lista.append(nombre)
                # Fallback: enlaces /jugador/
                if not lista:
                    for a in bloque.find_all('a', href=re.compile(r'/jugador/')):
                        nombre = a.get_text(strip=True)
                        if nombre and len(nombre) > 1 and nombre not in lista:
                            lista.append(nombre)

            logging.info(f"📋 Alineación previa: {equipo_local}({len(alineacion_local)}) vs {equipo_visitante}({len(alineacion_visitante)})")
        except Exception as e:
            logging.error(f"Error obteniendo alineación previa {partido_id}: {e}")
        return alineacion_local, alineacion_visitante
    
    def _buscar_partidos(self):
        """Busca partidos en juego o finalizados en todas las URLs configuradas"""
        partidos_encontrados = 0
        partidos_en_vivo = 0
        livescore_soups = {}  # {url: soup} para reutilizar en _anunciar_partidos_proximos
        
        for url in Config.SCRAPER_LIVESCORE_URLS:
            try:
                response = self.session.get(url, timeout=10)
                
                if response.status_code != 200:
                    logging.warning(f"Error HTTP {response.status_code} al buscar partidos en {url}")
                    continue
                
                # Usar apparent_encoding para detectar correctamente acentos de la web
                soup = BeautifulSoup(response.content, 'lxml', from_encoding=response.apparent_encoding)
                livescore_soups[url] = soup  # guardar para reutilizar
                
                # Buscar ligas (div con class="liga")
                ligas_divs = soup.find_all('div', class_='liga')
                logging.info(f"🔍 Encontradas {len(ligas_divs)} ligas en {url.split('/')[-1]}")
                
                for liga_div in ligas_divs:
                    try:
                        # Extraer nombre de la liga
                        titulo_liga = liga_div.find('h2', class_='title')
                        if not titulo_liga:
                            continue
                    
                        nombre_liga_original = titulo_liga.get_text(strip=True).replace('»', '').strip()
                    
                        # Filtrar solo ligas permitidas
                        if not self._liga_permitida(nombre_liga_original):
                            logging.debug(f"⏭️ Liga ignorada: {nombre_liga_original}")
                            continue
                    
                        logging.info(f"✅ Liga permitida: {nombre_liga_original}")
                    
                        # Obtener nombre a mostrar y color
                        nombre_liga = self._obtener_nombre_liga(nombre_liga_original)
                        color_liga = self._obtener_color_liga(nombre_liga)
                    
                        # Buscar filas de partidos dentro de esta liga
                        tabla = liga_div.find('table', class_='tablemarcador')
                        if not tabla:
                            continue
                    
                        filas_partidos = tabla.find_all('tr')
                    
                        for fila in filas_partidos:
                            try:
                                # Saltar filas de publicidad
                                if 'advertising-row' in ' '.join(fila.get('class', [])):
                                    continue
                            
                                # Buscar enlace al partido
                                enlace = fila.find('a', href=re.compile(r'/partido/'))
                                if not enlace:
                                    continue
                            
                                href = enlace.get('href', '')
                                match = re.search(r'/partido/(.+?)(?:/\d+)?$', href)
                                if not match:
                                    continue
                            
                                partido_id = match.group(1).replace('/', '_')
                                partidos_encontrados += 1
                            
                                # Determinar si está en vivo y extraer minuto/parte
                                en_vivo = False
                                minuto_actual = ""
                                parte_actual = ""
                                clases_fila = ' '.join(fila.get('class', []))
                            
                                # Buscar span con clase "playing" (muestra minuto o "Des")
                                playing_span = fila.find('span', class_='playing')
                                timer_td = fila.find('td', class_='timer')
                            
                                if playing_span and 'nonplayingnow' not in clases_fila:
                                    en_vivo = True
                                    minuto_texto = playing_span.get_text(strip=True)
                                
                                    if minuto_texto == 'Des':
                                        minuto_actual = "Des"
                                        parte_actual = "Descanso"
                                    else:
                                        # Extraer número del minuto (ej: "36'" -> 36, "90+3'" -> 93)
                                        match_min = re.match(r"(\d+)(?:\+(\d+))?'?", minuto_texto)
                                        if match_min:
                                            minuto = int(match_min.group(1))
                                            adicional = int(match_min.group(2)) if match_min.group(2) else 0
                                            minuto_total = minuto + adicional
                                            minuto_actual = minuto_texto
                                        
                                            # Determinar parte según minuto
                                            # NOTA: "90+3'" (adicional) = tiempo añadido → sigue en 2ª
                                            #        "93'" (sin adicional, base>90) = prórroga → 1ª PRO
                                            #        "45+2'" = tiempo añadido → sigue en 1ª
                                            if minuto <= 45:
                                                parte_actual = "1ª"
                                            elif minuto <= 90:
                                                # base ≤ 90: ya sea "85'" o "90+3'", es 2ª parte
                                                parte_actual = "2ª"
                                            elif minuto <= 105:
                                                parte_actual = "1ª PRO"
                                            else:
                                                parte_actual = "2ª PRO"
                            
                                # También revisar td score con clase "playing"
                                if not en_vivo and 'nonplayingnow' not in clases_fila:
                                    score_td = fila.find('td', class_='score')
                                    if score_td and 'playing' in ' '.join(score_td.get('class', [])):
                                        en_vivo = True
                            
                                # Verificar si es finalizado
                                finalizado = False
                                if timer_td:
                                    timer_text = timer_td.get_text(strip=True)
                                    if 'Finalizado' in timer_text:
                                        finalizado = True
                                        en_vivo = False
                                        parte_actual = "Final"
                            
                                # Agregar partido
                                if partido_id not in self.partidos_activos:
                                    if en_vivo:
                                        if parte_actual:
                                            estado_txt = f"EN VIVO ({minuto_actual} - {parte_actual})"
                                        else:
                                            estado_txt = "EN VIVO"
                                    elif finalizado:
                                        estado_txt = "Finalizado"
                                    else:
                                        estado_txt = "Próximo"
                                
                                    # Extraer nombres de equipos
                                    team_home = fila.find('td', class_='team-home')
                                    team_away = fila.find('td', class_='team-away')
                                
                                    if team_home and team_away:
                                        local = team_home.get_text(strip=True)
                                        visitante = team_away.get_text(strip=True)
                                    else:
                                        texto_enlace = enlace.get_text(strip=True)
                                        equipos = texto_enlace.split(' vs ') if ' vs ' in texto_enlace else [texto_enlace, '']
                                        local = equipos[0] if len(equipos) > 0 else "Local"
                                        visitante = equipos[1] if len(equipos) > 1 else "Visitante"
                                    
                                    # Filtro de participación española en ligas internacionales
                                    if nombre_liga.lower() in [l.lower() for l in Config.LIGAS_INTERNACIONALES]:
                                        if not self._es_equipo_esp(local) and not self._es_equipo_esp(visitante):
                                            continue
                                
                                    # Guardar estado inicial: {parte, liga, color, local, visitante, anunciado}
                                    # FIX: Si el partido ya lleva tiempo en juego (reload del bot),
                                    # marcarlo como anunciado para NO re-anunciar el inicio
                                    ya_en_curso = False
                                    if en_vivo:
                                        try:
                                            min_num = int(re.sub(r'[^\d]', '', (minuto_actual or '0').split('+')[0]) or '0')
                                        except:
                                            min_num = 0
                                        # Si lleva más de 10 minutos, o está en Descanso/2ª parte, ya empezó hace rato
                                        if min_num > 10 or parte_actual in ['Descanso', '2ª', '1ª PRO', '2ª PRO']:
                                            ya_en_curso = True
                                            logging.info(f"🔄 Partido ya en curso (min {minuto_actual}, {parte_actual}), no re-anunciar: {local} vs {visitante}")
                                
                                    self.partidos_activos[partido_id] = {
                                        'parte': parte_actual,
                                        'liga': nombre_liga,
                                        'color': color_liga,
                                        'local': local,
                                        'visitante': visitante,
                                        'anunciado': ya_en_curso,  # True si ya estaba en juego (reload)
                                        'marcador': '0 - 0',
                                        'descanso_anunciado': parte_actual in ['Descanso', '2ª', '1ª PRO', '2ª PRO'] if ya_en_curso else False,
                                        'inicio_2a_anunciado': parte_actual in ['2ª', '1ª PRO', '2ª PRO'] if ya_en_curso else False,
                                    }
                                
                                    # Guardar en BD con liga
                                    self.db.add_partido(partido_id, local, visitante, estado_txt, nombre_liga)
                                
                                    # Log del partido
                                    logging.info(f"⚽ Nuevo partido [{nombre_liga}]: {local} vs {visitante} [{estado_txt}]")
                                    if en_vivo:
                                        partidos_en_vivo += 1
                            
                                # Si el partido ya existe, verificar cambio de parte
                                elif en_vivo and parte_actual and partido_id in self.partidos_activos:
                                    estado_anterior = self.partidos_activos[partido_id]
                                    if estado_anterior and isinstance(estado_anterior, dict):
                                        parte_anterior = estado_anterior.get('parte', '')
                                    
                                        # Extraer marcador actual
                                        score_td = fila.find('td', class_='score')
                                        marcador = "0 - 0"
                                        if score_td:
                                            # Primero intentar con marker_box directo (tabla de partidos)
                                            marker_div = score_td.find('div', class_='marker_box')
                                            if marker_div:
                                                marcador = marker_div.get_text(strip=True)
                                            else:
                                                # Alternativa: buscar spans con marker_box (formato resultado)
                                                spans = score_td.find_all('span', class_='marker_box')
                                                if len(spans) >= 2:
                                                    gol_local = spans[0].get_text(strip=True)
                                                    gol_visitante = spans[1].get_text(strip=True)
                                                    marcador = f"{gol_local} - {gol_visitante}"
                                                else:
                                                    # Último intento: texto directo
                                                    marcador_txt = score_td.get_text(strip=True)
                                                    if marcador_txt and '-' in marcador_txt:
                                                        marcador = marcador_txt
                                    
                                        logging.debug(f"🎯 Marcador extraído: '{marcador}' para {local} vs {visitante}")
                                    
                                        # FIX Bug 32: Guardar marcador PRE-CICLO antes de que el livescore lo actualice.
                                        # Esto permite que el detector de race condition compare contra el marcador
                                        # que teníamos ANTES de este ciclo de scraping, no contra el ya actualizado.
                                        marcador_anterior = self.partidos_activos[partido_id].get('marcador', '0 - 0')
                                        if marcador != marcador_anterior:
                                            self.partidos_activos[partido_id]['marcador_pre_ciclo'] = marcador_anterior
                                            logging.info(f"📊 Marcador cambió en livescore: '{marcador_anterior}' → '{marcador}'")
                                        
                                        # Actualizar marcador almacenado
                                        self.partidos_activos[partido_id]['marcador'] = marcador
                                    
                                        liga = estado_anterior.get('liga', 'Liga')
                                        color = estado_anterior.get('color', '14')
                                        local = estado_anterior.get('local', 'Local')
                                        visitante = estado_anterior.get('visitante', 'Visitante')
                                    
                                        # VERIFICAR FILTRO DE PARTIDOS antes de narrar cambios de parte
                                        filtro_id = self.db.partido_en_filtro(local, visitante)
                                        debe_narrar = filtro_id is not None

                                        # Helper: parsear marcador a goles local/visitante
                                        def _gl_gv(marc):
                                            sp = marc.split(' - ')
                                            return (sp[0].strip() if sp else '0',
                                                    sp[1].strip() if len(sp) > 1 else '0')

                                        # Detectar cambio a descanso
                                        if parte_anterior == '1ª' and parte_actual == 'Descanso':
                                            if not estado_anterior.get('descanso_anunciado', False):
                                                minuto_desc = 0
                                                try:
                                                    minuto_desc = int(re.sub(r'[^\d]', '', minuto_actual or '0') or '0')
                                                except Exception:
                                                    pass
                                                if minuto_desc >= 42 or minuto_actual == 'Des':
                                                    if debe_narrar:
                                                        gl, gv = _gl_gv(marcador)
                                                        msg_desc = EventFormatter.descanso(liga, color, local, gl, gv, visitante)
                                                        self.partidos_activos[partido_id]['descanso_pendiente'] = msg_desc
                                                        logging.info(f"⏸️ Descanso PENDIENTE: {local} {marcador} {visitante}")
                                                    else:
                                                        self.partidos_activos[partido_id]['descanso_anunciado'] = True
                                                else:
                                                    logging.warning(f"⚠️ Descanso prematuro ignorado (min {minuto_desc}): {local} vs {visitante}")

                                        # Detectar inicio de partido
                                        elif parte_anterior in ['', 'Próximo', None] and parte_actual == '1ª':
                                            minuto_num = 0
                                            try:
                                                minuto_num = int(re.sub(r'[^\d]', '', minuto_actual or '0') or '0')
                                            except Exception:
                                                pass
                                            if minuto_num <= 5:
                                                logging.info(f"🏁 Inicio detectado (min {minuto_num}): {local} vs {visitante}")
                                            else:
                                                self.partidos_activos[partido_id]['anunciado'] = True
                                                self.db.marcar_partido_anunciado(partido_id)
                                                logging.debug(f"⏭️ Partido ya en juego (min {minuto_num}), marcado anunciado: {local} vs {visitante}")

                                        # Detectar inicio 2ª parte
                                        elif (parte_anterior in ['1ª', 'Descanso', '', None]) and parte_actual == '2ª':
                                            if not estado_anterior.get('inicio_2a_anunciado', False):
                                                if not estado_anterior.get('descanso_anunciado', False):
                                                    self.partidos_activos[partido_id]['descanso_anunciado'] = True
                                                    logging.info(f"⏸️ Descanso implícito: {local} vs {visitante}")
                                                minuto_2a = 0
                                                try:
                                                    minuto_2a = int(re.sub(r'[^\d]', '', minuto_actual or '0') or '0')
                                                except Exception:
                                                    pass
                                                if minuto_2a >= 46:
                                                    if debe_narrar:
                                                        gl, gv = _gl_gv(marcador)
                                                        msg_2a = EventFormatter.inicio_2a_parte(liga, color, local, gl, gv, visitante)
                                                        self._encolar_narracion(partido_id, msg_2a, es_importante=True)
                                                    self.partidos_activos[partido_id]['inicio_2a_anunciado'] = True
                                                    logging.info(f"▶️ Inicio 2ª parte: {local} {marcador} {visitante}")
                                                else:
                                                    logging.warning(f"⚠️ 2ª parte prematura ignorada (min {minuto_2a}): {local} vs {visitante}")

                                        # Detectar inicio prórroga
                                        elif parte_anterior == '2ª' and parte_actual == '1ª PRO':
                                            if debe_narrar:
                                                gl, gv = _gl_gv(marcador)
                                                lf = EventFormatter._liga_str(liga, color)
                                                mf = EventFormatter._marcador_str(local, gl, gv, visitante)
                                                msg_pro = f"{lf} \x033»\x03 \x0304E\x0302mpieza la \x0304P\x0302rorroga\x03 \x033«\x03 {mf}"
                                                self._encolar_narracion(partido_id, msg_pro, es_importante=True)
                                            logging.info(f"▶️ Inicio prórroga: {local} {marcador} {visitante}")

                                        # Detectar descanso prórroga
                                        elif parte_anterior == '1ª PRO' and parte_actual == 'Descanso':
                                            if not estado_anterior.get('descanso_prorroga_anunciado', False):
                                                if debe_narrar:
                                                    gl, gv = _gl_gv(marcador)
                                                    lf = EventFormatter._liga_str(liga, color)
                                                    mf = EventFormatter._marcador_str(local, gl, gv, visitante)
                                                    msg_dp = f"{lf} \x033»\x03 \x0304D\x0302escanso de la \x0304P\x0302rorroga\x03 \x033«\x03 {mf}"
                                                    self._encolar_narracion(partido_id, msg_dp, es_importante=True)
                                                self.partidos_activos[partido_id]['descanso_prorroga_anunciado'] = True
                                                logging.info(f"⏸️ Descanso prórroga: {local} {marcador} {visitante}")
                                            parte_actual = 'Des PRO'

                                        # Detectar inicio 2ª prórroga
                                        elif parte_anterior in ['Descanso', 'Des PRO'] and parte_actual == '2ª PRO':
                                            if debe_narrar:
                                                gl, gv = _gl_gv(marcador)
                                                lf = EventFormatter._liga_str(liga, color)
                                                mf = EventFormatter._marcador_str(local, gl, gv, visitante)
                                                msg_2pro = f"{lf} \x033»\x03 \x0304E\x0302mpieza la 2ª parte de la \x0304P\x0302rorroga\x03 \x033«\x03 {mf}"
                                                self._encolar_narracion(partido_id, msg_2pro, es_importante=True)
                                            logging.info(f"▶️ Inicio 2ª prórroga: {local} {marcador} {visitante}")

                                        # Detectar final del partido
                                        elif parte_anterior in ['2ª', '2ª PRO'] and parte_actual == 'Final':
                                            if debe_narrar:
                                                gl, gv = _gl_gv(marcador)
                                                msg_fin = EventFormatter.fin_partido(liga, color, local, gl, gv, visitante)
                                                self._encolar_narracion(partido_id, msg_fin, es_importante=True)
                                            logging.info(f"🏁 Final: {local} {marcador} {visitante}")
                                    
                                        # Actualizar parte actual (con prevención de regresión)
                                        # Orden válido: '' → 1ª → Descanso → 2ª → 1ª PRO → Des PRO → 2ª PRO → Final
                                        ORDEN_ESTADOS = {'': 0, 'Próximo': 0, '1ª': 1, 'Descanso': 2, '2ª': 3, '1ª PRO': 4, 'Des PRO': 5, '2ª PRO': 6, 'Penaltis': 7, 'Final': 8}
                                        orden_anterior = ORDEN_ESTADOS.get(parte_anterior, 0)
                                        orden_nuevo = ORDEN_ESTADOS.get(parte_actual, 0)
                                    
                                        if orden_nuevo >= orden_anterior:
                                            self.partidos_activos[partido_id]['parte'] = parte_actual
                                        else:
                                            logging.warning(f"⚠️ Regresión de estado ignorada: {parte_anterior} → {parte_actual} para {local} vs {visitante}")
                            
                            except Exception as e:
                                logging.debug(f"Error procesando fila de partido: {e}")
                                continue
                
                    except Exception as e:
                        logging.debug(f"Error procesando liga: {e}")
                        continue
            
                # Mostrar resumen parcial por URL
                if partidos_en_vivo > 0:
                    logging.info(f"📊 {partidos_en_vivo} partidos en vivo de {partidos_encontrados} totales ({url.split(chr(47))[-1]})")
            
            except Exception as e:
                logging.error(f"Error buscando partidos en {url}: {e}")
        return livescore_soups
    
    def _revisar_partido(self, partido_id):
        """Revisa un partido específico para detectar nuevos eventos"""
        try:
            # Construir URL del partido - añadir /directo para obtener la crónica en vivo
            url_partido = f"{Config.SCRAPER_URL}/partido/{partido_id.replace('_', '/')}/directo"
            logging.info(f"🔍 _revisar_partido: {partido_id} -> {url_partido}")
            
            response = self.session.get(url_partido, timeout=10)
            if response.status_code != 200:
                logging.debug(f"Error HTTP {response.status_code} al revisar {partido_id}")
                return
            
            soup = BeautifulSoup(response.content, 'lxml', from_encoding=response.apparent_encoding)
            
            # Extraer nombres de equipos - múltiples métodos
            equipo_local = None
            equipo_visitante = None
            liga = ""
            
            # MÉTODO 1: JSON-LD (más confiable)
            json_ld = soup.find('script', type='application/ld+json')
            if json_ld:
                try:
                    data = json.loads(json_ld.string)
                    if 'homeTeam' in data and 'name' in data['homeTeam']:
                        equipo_local = data['homeTeam']['name']
                    if 'awayTeam' in data and 'name' in data['awayTeam']:
                        equipo_visitante = data['awayTeam']['name']
                except:
                    pass
            
            # MÉTODO 2: H2 dentro de .team.equipo1 y .team.equipo2
            if not equipo_local or not equipo_visitante:
                team1 = soup.find('div', class_='team equipo1')
                team2 = soup.find('div', class_='team equipo2')
                if team1:
                    h2 = team1.find('h2')
                    if h2:
                        equipo_local = h2.get_text(strip=True)
                if team2:
                    h2 = team2.find('h2')
                    if h2:
                        equipo_visitante = h2.get_text(strip=True)
            
            # MÉTODO 3: H1 en breadcrumbs (formato "Equipo1 - Equipo2")
            if not equipo_local or not equipo_visitante:
                h1 = soup.find('h1')
                if h1:
                    texto_h1 = h1.get_text(strip=True)
                    if ' - ' in texto_h1:
                        partes = texto_h1.split(' - ', 1)
                        equipo_local = partes[0].strip()
                        equipo_visitante = partes[1].strip()
            
            # MÉTODO 4: Fallback desde partido_id
            if not equipo_local or not equipo_visitante:
                partes = partido_id.split('_')
                if len(partes) >= 2:
                    equipo_local = partes[0].replace('-', ' ').title()
                    equipo_visitante = partes[1].replace('-', ' ').title()
                else:
                    equipo_local = "Local"
                    equipo_visitante = "Visitante"
            
            # Extraer liga desde breadcrumbs
            crumbs = soup.find('ul', id='crumbs')
            if crumbs:
                links = crumbs.find_all('a')
                if len(links) >= 2:
                    liga = links[1].get_text(strip=True)
            
            # Si no hay liga en crumbs, intentar desde título
            if not liga:
                title_tag = soup.find('title')
                if title_tag:
                    titulo = title_tag.text.strip()
                    liga_match = re.search(r'[\|\-–]\s*(.+?)(?:\s*\d{4})?$', titulo)
                    if liga_match:
                        liga = liga_match.group(1).strip()
            
            # Renombrar liga si aplica
            liga_original = liga
            liga = self._obtener_nombre_liga(liga) if liga else ""
            
            # Filtro de participación española en ligas internacionales (capa de seguridad extra)
            if liga and liga.lower() in [l.lower() for l in Config.LIGAS_INTERNACIONALES]:
                if not self._es_equipo_esp(equipo_local) and not self._es_equipo_esp(equipo_visitante):
                    logging.info(f"⏭️ Ignorando partido internacional sin equipos españoles: {equipo_local} vs {equipo_visitante} [{liga}]")
                    # Eliminar de activos para no seguir revisándolo
                    if partido_id in self.partidos_activos:
                        del self.partidos_activos[partido_id]
                    return
            
            # Obtener color de la liga
            color_liga = self._obtener_color_liga(liga) if liga else "14"
            
            # Extraer marcador
            marcador = self._extraer_marcador(soup)
            logging.debug(f"🎯 Marcador extraído: {marcador}")
            
            # VERIFICAR ESTADO DEL PARTIDO
            partido_en_vivo = False
            partido_finalizado = False
            partido_proximo = False
            
            estado_span = soup.find('span', class_='jor-status')
            if estado_span:
                clases = estado_span.get('class', [])
                estado_texto = estado_span.get_text(strip=True).upper()
                
                # Clasificar estado
                if 'jor-live' in clases or any(x in estado_texto for x in ['DIRECTO', 'LIVE', 'EN VIVO', 'JUGANDO']):
                    partido_en_vivo = True
                elif 'jor-finished' in clases or any(x in estado_texto for x in ['FINALIZADO', 'FINAL', 'FIN', 'TERMINADO']):
                    partido_finalizado = True
                else:
                    # Si no es live ni finished, es próximo
                    partido_proximo = True
            else:
                # Sin span de estado, asumir próximo
                partido_proximo = True
            
            # PARTIDO PRÓXIMO: mantener en activos pero no procesar eventos
            if partido_proximo:
                logging.debug(f"⏳ Partido próximo: {equipo_local} vs {equipo_visitante}")
                return
            
            # PARTIDO FINALIZADO: anunciar fin si lo estábamos siguiendo
            if partido_finalizado:
                partido_bd = self.db.get_partido(partido_id)
                ultima_jugada_bd = partido_bd[4] if partido_bd else None
                
                # Solo anunciar si teníamos eventos previos (estábamos siguiendo el partido)
                if ultima_jugada_bd and ultima_jugada_bd != "PARTIDO_FINALIZADO" and ultima_jugada_bd != "":
                    # VERIFICAR FILTRO DE PARTIDOS
                    filtro_id = self.db.partido_en_filtro(equipo_local, equipo_visitante)
                    if filtro_id is not None:
                        marcador_split = marcador.split(' - ')
                        gl_fin = marcador_split[0].strip() if marcador_split else '0'
                        gv_fin = marcador_split[1].strip() if len(marcador_split) > 1 else '0'
                        color_fin = self._obtener_color_liga(liga) if liga else "14"
                        liga_fin  = liga or ""

                        mensaje_fin = EventFormatter.fin_partido(liga_fin, color_fin,
                                                                  equipo_local, gl_fin, gv_fin, equipo_visitante)
                        canales = self.db.get_canales_narracion_activa()
                        for canal in canales:
                            self.bot_callback('message', canal, mensaje_fin)
                            time.sleep(0.3)

                        self._debug(f"🏁 Fin anunciado: {equipo_local} {gl_fin}-{gv_fin} {equipo_visitante}", importante=True)

                        if filtro_id and filtro_id > 0:
                            self.db.del_partido_filtro_por_id(filtro_id)

                    self.db.update_partido(partido_id, "PARTIDO_FINALIZADO")
                
                # Eliminar de partidos activos (ya terminó)
                if partido_id in self.partidos_activos:
                    del self.partidos_activos[partido_id]
                return
            
            # PARTIDO EN VIVO: Anunciar inicio si es la primera vez
            info_partido = self.partidos_activos.get(partido_id, {})
            if not info_partido.get('anunciado', False):
                if partido_id in self.partidos_activos:
                    self.partidos_activos[partido_id]['anunciado'] = True
                self.db.marcar_partido_anunciado(partido_id)

                color_inicio = info_partido.get('color', '01')
                nombre_inicio = info_partido.get('liga', liga)
                mensaje = EventFormatter.inicio_partido(nombre_inicio, color_inicio, equipo_local, equipo_visitante)

                canales = self.db.get_canales_narracion_activa()
                for canal in canales:
                    self.bot_callback('message', canal, mensaje)
                    time.sleep(0.3)

                logging.info(f"📢 Anunciado inicio: {equipo_local} vs {equipo_visitante} [{nombre_inicio}]")
            
            # PARTIDO EN VIVO: Detectar descanso/inicio 2ª desde jor-status
            # Algunas ligas (Segunda) no incluyen evento de crónica para el descanso,
            # y _buscar_partidos() puede no detectar el cambio si la tabla de jornada
            # no usa span.playing con "Des". Detectamos aquí como fallback.
            if estado_span and partido_id in self.partidos_activos:
                estado_upper = estado_span.get_text(strip=True).upper()
                info_p = self.partidos_activos[partido_id]
                
                # FIX: Obtener el último evento procesado para verificar si ya pasamos el minuto 45
                # antes de anunciar el descanso. Esto evita anunciar descanso ANTES de eventos
                # del final de la 1ª parte que aún no se han procesado.
                partido_bd_temp = self.db.get_partido(partido_id)
                ultima_jugada_bd_temp = partido_bd_temp[4] if partido_bd_temp else None
                
                def _marc_split(marc):
                    sp = marc.split(' - ')
                    return sp[0].strip() if sp else '0', sp[1].strip() if len(sp) > 1 else '0'

                if 'DESCANSO' in estado_upper and not info_p.get('descanso_anunciado', False):
                    if ultima_jugada_bd_temp and ultima_jugada_bd_temp != "":
                        filtro_id = self.db.partido_en_filtro(equipo_local, equipo_visitante)
                        if filtro_id is not None:
                            _c = info_p.get('color', '01')
                            _l = info_p.get('liga', liga)
                            gl, gv = _marc_split(marcador)
                            self._encolar_narracion(partido_id,
                                EventFormatter.descanso(_l, _c, equipo_local, gl, gv, equipo_visitante),
                                es_importante=True)
                        self.partidos_activos[partido_id]['descanso_anunciado'] = True
                        self.partidos_activos[partido_id]['parte'] = 'Descanso'
                        logging.info(f"⏸️ Descanso detectado desde jor-status: {equipo_local} {marcador} {equipo_visitante}")
                    else:
                        logging.info(f"⏸️ Descanso detectado pero esperando eventos de fin de 1ª parte")

                elif any(x in estado_upper for x in ['2ª PARTE', 'SEGUNDA PARTE']):
                    if not info_p.get('inicio_2a_anunciado', False):
                        if not info_p.get('descanso_anunciado', False):
                            self.partidos_activos[partido_id]['descanso_anunciado'] = True
                            logging.info(f"⏸️ Descanso implícito (ya en 2ª): {equipo_local} vs {equipo_visitante}")
                        filtro_id = self.db.partido_en_filtro(equipo_local, equipo_visitante)
                        if filtro_id is not None:
                            _c = info_p.get('color', color_liga)
                            _l = info_p.get('liga', liga)
                            gl, gv = _marc_split(marcador)
                            self._encolar_narracion(partido_id,
                                EventFormatter.inicio_2a_parte(_l, _c, equipo_local, gl, gv, equipo_visitante),
                                es_importante=True)
                        self.partidos_activos[partido_id]['inicio_2a_anunciado'] = True
                        self.partidos_activos[partido_id]['parte'] = '2ª'
                        logging.info(f"▶️ 2ª parte detectada desde jor-status: {equipo_local} vs {equipo_visitante}")

                elif 'DIRECTO' in estado_upper:
                    match_min_status = re.search(r"(\d+)'", estado_upper)
                    if match_min_status:
                        min_status = int(match_min_status.group(1))
                        if min_status > 45 and not info_p.get('descanso_anunciado', False):
                            filtro_id = self.db.partido_en_filtro(equipo_local, equipo_visitante)
                            if filtro_id is not None:
                                _c = info_p.get('color', '01')
                                _l = info_p.get('liga', liga)
                                gl, gv = _marc_split(marcador)
                                self._encolar_narracion(partido_id,
                                    EventFormatter.descanso(_l, _c, equipo_local, gl, gv, equipo_visitante),
                                    es_importante=True)
                            self.partidos_activos[partido_id]['descanso_anunciado'] = True
                            self.partidos_activos[partido_id]['inicio_2a_anunciado'] = True
                            self.partidos_activos[partido_id]['parte'] = '2ª'
                            logging.info(f"⏸️ Descanso retroactivo (min {min_status}>45): {equipo_local} {marcador} {equipo_visitante}")
                        elif min_status > 45 and info_p.get('descanso_anunciado', False) and not info_p.get('inicio_2a_anunciado', False):
                            filtro_id = self.db.partido_en_filtro(equipo_local, equipo_visitante)
                            if filtro_id is not None:
                                _c = info_p.get('color', color_liga)
                                _l = info_p.get('liga', liga)
                                gl, gv = _marc_split(marcador)
                                self._encolar_narracion(partido_id,
                                    EventFormatter.inicio_2a_parte(_l, _c, equipo_local, gl, gv, equipo_visitante),
                                    es_importante=True)
                            self.partidos_activos[partido_id]['inicio_2a_anunciado'] = True
                            self.partidos_activos[partido_id]['parte'] = '2ª'
                            logging.info(f"▶️ Inicio 2ª parte (min {min_status}): {equipo_local} {marcador} {equipo_visitante}")
            
            # PARTIDO EN VIVO: procesar eventos normalmente
            
            # Extraer alineaciones (para deducir equipos de jugadores)
            alineaciones = self._extraer_alineaciones(soup, equipo_local, equipo_visitante)
            
            # Extraer última jugada/evento
            eventos = self._extraer_eventos(soup)
            
            if not eventos:
                logging.debug(f"📭 {partido_id}: No se encontraron eventos")
                return
            
            self._debug(f"📋 {partido_id}: {len(eventos)} eventos | Marcador: {marcador}")
            
            # Liga formato (necesario para catch-up y para mensajes de eventos)
            info_partido_liga = self.partidos_activos.get(partido_id, {})
            liga_fmt_color = info_partido_liga.get('color', color_liga)
            liga_fmt_nombre = info_partido_liga.get('liga', liga)
            liga_formato = f"\x03{liga_fmt_color}«{liga_fmt_nombre}»\x03" if liga_fmt_nombre else ""
            
            # ═══════════════════════════════════════════════════════════════
            # MULTI-EVENT: Catch-up por hashes (v2 — reemplaza catch-up por índice)
            # ───────────────────────────────────────────────────────────────
            # ANTES: se usaba num_eventos_prev vs num_eventos_actual para
            #        determinar qué eventos procesar con eventos[1:N].
            #        Fallo: si la web reordenaba eventos entre scrapes, los
            #        índices eran incorrectos y se perdían o duplicaban eventos.
            #
            # AHORA: cada evento tiene un hash estable (minuto + jugador + icono).
            #        Se mantiene un set _hashes_vistos[partido_id] con todos los
            #        hashes ya anunciados.  El catch-up itera TODO el array de
            #        eventos (cronológico) y procesa solo los que no están en el set.
            #        Después el procesador principal hace lo mismo para eventos[0].
            #        Resultado: cero duplicados, cero eventos perdidos por reorden.
            # ═══════════════════════════════════════════════════════════════
            marcador_split_tmp = marcador.split(' - ')
            goles_local_tmp  = marcador_split_tmp[0].strip() if marcador_split_tmp else '?'
            goles_visitante_tmp = marcador_split_tmp[1].strip() if len(marcador_split_tmp) > 1 else '?'

            # Inicializar set si es la primera vez que vemos este partido
            if partido_id not in self._hashes_vistos:
                self._hashes_vistos[partido_id] = set()
            hashes_vistos = self._hashes_vistos[partido_id]

            # Calcular hashes de todos los eventos actuales
            def _hash_evento_catchup(ev: dict) -> str:
                key = ev.get('jugador') or ev.get('texto', '')[:50]
                return self._evento_hash(
                    ev.get('minuto', ''), key,
                    ev.get('icono', 'none.png'), 'evento'
                )

            # Eventos en orden cronológico (la web los devuelve invertidos)
            eventos_cronologicos = list(reversed(eventos))

            # Eventos realmente nuevos = los que NO están en hashes_vistos
            # Excluimos eventos[0] (el más reciente) porque lo procesa el bloque principal
            ultimo_hash = _hash_evento_catchup(eventos[0]) if eventos else ''
            eventos_perdidos = [
                ev for ev in eventos_cronologicos
                if _hash_evento_catchup(ev) not in hashes_vistos
                   and _hash_evento_catchup(ev) != ultimo_hash
            ]

            if eventos_perdidos:
                logging.info(f"📬 {partido_id}: {len(eventos_perdidos)} evento(s) pendiente(s) de catch-up")

            for ev_perdido in eventos_perdidos:
                ev_icono   = ev_perdido.get('icono', '')
                ev_texto   = ev_perdido.get('texto', '')
                ev_minuto  = ev_perdido.get('minuto', '')
                ev_jugador = ev_perdido.get('jugador', '')
                ev_equipo  = ev_perdido.get('equipo_nombre', '') or ev_perdido.get('equipo', '')

                # Traducir 'local'/'visitante' al nombre real
                if ev_equipo == 'local':
                    ev_equipo = equipo_local
                elif ev_equipo == 'visitante':
                    ev_equipo = equipo_visitante

                # Marcar como visto ANTES de procesar (evitar re-anuncio si falla)
                hashes_vistos.add(_hash_evento_catchup(ev_perdido))

                # Solo procesar eventos importantes
                es_importante = any(ic in ev_icono for ic in EVENTOS_IMPORTANTES)
                es_gol_texto = bool(re.search(
                    r'^[¡!]?\s*(?:go+l(?:azo|ito)?|autogol)\b'
                    r'|^[¡!]?\s*(?:¡+go+l(?:azo|ito)?[!\s])'
                    r'|\bautogol\b|\bpropia puerta\b|\bpropia meta\b',
                    ev_texto.lower().strip()
                )) if ev_texto else False
                if es_gol_texto and ev_texto and 'tanda' in ev_texto.lower():
                    es_gol_texto = False
                es_tarjeta_texto = any(
                    x in ev_texto.lower()
                    for x in ['roja', 'expulsado', 'expulsión']
                ) if ev_texto else False

                if not es_importante and not es_gol_texto and not es_tarjeta_texto:
                    continue

                # Extraer jugador del texto (aplica todos los patrones, igual que el path principal)
                if not ev_jugador and 'accion5.png' in ev_icono:
                    ev_jugador = self._extraer_jugador_tarjeta(ev_texto)

                # Extraer equipo del formato "Acción - Jugador (Equipo)" si aún falta
                if not ev_equipo:
                    m = re.search(r'^[^-]+-\s*([^(]+)\s*\(([^)]+)\)', ev_texto)
                    if m:
                        ev_jugador = ev_jugador or m.group(1).strip()
                        ev_equipo  = ev_equipo  or m.group(2).strip()

                # Deducir equipo desde alineaciones si falta
                if ev_jugador and not ev_equipo:
                    for p in reversed(ev_jugador.split()):
                        if p in alineaciones:
                            ev_equipo = alineaciones[p]
                            break

                # Normalizar nombre de equipo
                if ev_equipo:
                    for eq in [equipo_local, equipo_visitante]:
                        if eq and (ev_equipo.lower() in eq.lower() or eq.lower() in ev_equipo.lower()):
                            ev_equipo = eq
                            break

                # Determinar parte
                try:
                    min_num = int(re.search(r'\d+', ev_minuto).group()) if ev_minuto else 0
                except Exception:
                    min_num = 0
                if min_num <= 45:
                    ev_parte = "1ª"
                elif min_num <= 90:
                    ev_parte = "2ª"
                elif min_num <= 105:
                    ev_parte = "1ª PRO"
                elif min_num <= 120:
                    ev_parte = "2ª PRO"
                else:
                    ev_parte = "Penaltis"

                # Marcador en el momento del evento
                ev_marcador_gol = ev_perdido.get('marcador_gol', '')
                if ev_marcador_gol:
                    ev_sp = ev_marcador_gol.split(' - ')
                    ev_gl = ev_sp[0].strip() if ev_sp else goles_local_tmp
                    ev_gv = ev_sp[1].strip() if len(ev_sp) > 1 else goles_visitante_tmp
                else:
                    ev_gl, ev_gv = goles_local_tmp, goles_visitante_tmp

                msg = None
                liga_cu  = info_partido_liga.get('liga', liga)
                color_cu = info_partido_liga.get('color', color_liga)

                # ── Formatear con EventFormatter ────────────────────────────
                es_gol_icono_cu = any(g in ev_icono for g in ('accion1.png', 'accion2.png', 'accion43.png'))

                if es_gol_icono_cu or es_gol_texto:
                    # Guard: icono de gol pero sin MHR y texto narrativo → saltar
                    if es_gol_icono_cu and not es_gol_texto:
                        if not ev_perdido.get('marcador_gol'):
                            _anuncia = bool(re.search(
                                r'^[¡!]?\s*(?:go+l(?:azo|ito)?|autogol)\b'
                                r'|^[¡!]?\s*¡+go+l(?:azo|ito)?[!\s]'
                                r'|\bautogol\b|\bpropia puerta\b',
                                ev_texto.lower().strip()
                            ))
                            if not _anuncia:
                                continue
                    es_auto = any(x in ev_texto.lower() for x in
                                  ['autogol', 'propia puerta', 'propia meta', 'en propia'])
                    if es_auto:
                        msg = EventFormatter.autogol(
                            liga_cu, color_cu, ev_equipo, ev_jugador,
                            ev_minuto, ev_parte, equipo_local, ev_gl, ev_gv, equipo_visitante)
                    elif 'accion2.png' in ev_icono:
                        msg = EventFormatter.gol_penalti(
                            liga_cu, color_cu, ev_equipo, ev_jugador,
                            ev_minuto, ev_parte, equipo_local, ev_gl, ev_gv, equipo_visitante)
                    else:
                        msg = EventFormatter.gol(
                            liga_cu, color_cu, ev_equipo, ev_jugador,
                            ev_minuto, ev_parte, equipo_local, ev_gl, ev_gv, equipo_visitante)

                elif 'accion5.png' in ev_icono:
                    msg = EventFormatter.tarjeta_amarilla(
                        liga_cu, color_cu, ev_jugador, ev_equipo, ev_minuto, ev_parte)

                elif any(x in ev_icono for x in ('accion3.png', 'accion4.png', 'accion6.png')) or es_tarjeta_texto:
                    doble = any(x in ev_texto.lower() for x in
                                ['2a amarilla', 'doble amarilla', 'segunda amarilla', '2ª amarilla'])
                    msg = EventFormatter.tarjeta_roja(
                        liga_cu, color_cu, ev_jugador, ev_equipo,
                        ev_minuto, ev_parte, doble)

                elif 'accion15.png' in ev_icono:
                    msg = EventFormatter.penalti_fallado(
                        liga_cu, color_cu, ev_jugador, ev_equipo, ev_minuto, ev_parte)

                elif 'accion16.png' in ev_icono:
                    msg = EventFormatter.penalti_parado(
                        liga_cu, color_cu, ev_jugador, ev_equipo, ev_minuto, ev_parte)

                elif 'accion23.png' in ev_icono or 'accion24.png' in ev_icono:
                    # GUARD: accion23/24 también se usan para alineaciones y kickoff.
                    # Solo procesar como tanda si el texto lo confirma, el partido ya
                    # estaba en tanda, o el minuto es > 90 (prórroga/penaltis).
                    _texto_lower_cu = (ev_texto or '').lower()
                    _info_cu = self.partidos_activos.get(partido_id, {})
                    try:
                        _min_num_cu = int(re.sub(r'[^\d]', '', (ev_minuto or '').split('+')[0]) or '0')
                    except:
                        _min_num_cu = 0
                    _es_contexto_tanda_cu = (
                        any(x in _texto_lower_cu for x in [
                            'tanda', 'penalti', 'penalty', 'lanza', 'dispara desde los once',
                            'falla desde el punto', 'transforma desde el punto',
                            'gol en la tanda', 'fallo en la tanda'
                        ])
                        or _info_cu.get('tanda_penaltis_activa', False)
                        or _min_num_cu > 120
                    )
                    if not _es_contexto_tanda_cu:
                        logging.debug(f"⏭️ accion{'23' if 'accion23' in ev_icono else '24'} ignorado en catch-up (no es tanda): min={ev_minuto} texto={_texto_lower_cu[:60]}")
                        if msg:
                            canales = self.db.get_canales_narracion_activa()
                            for canal in canales:
                                self.bot_callback('message', canal, msg)
                            logging.info(f"📬 Catch-up anunciado: [{ev_minuto}] {ev_icono} {ev_jugador}")
                        continue

                    _es_gol_tanda_cu = 'accion23.png' in ev_icono
                    if not _info_cu.get('tanda_penaltis_activa', False):
                        with self._partido_locks.get(partido_id, threading.Lock()):
                            self.partidos_activos[partido_id]['tanda_penaltis_activa'] = True
                            self.partidos_activos[partido_id]['tanda_local']    = 0
                            self.partidos_activos[partido_id]['tanda_visitante'] = 0
                            self.partidos_activos[partido_id]['parte']           = 'Penaltis'
                        msg_tanda = EventFormatter.tanda_inicio(
                            liga_cu, color_cu, equipo_local, ev_gl, ev_gv, equipo_visitante)
                        for canal in self.db.get_canales_narracion_activa():
                            self.bot_callback('message', canal, msg_tanda)
                        logging.info(f"🎯 TANDA DE PENALTIS (catch-up): {equipo_local} vs {equipo_visitante}")
                    _es_local_cu = self._equipo_es_local(ev_equipo, equipo_local, equipo_visitante)
                    with self._partido_locks.get(partido_id, threading.Lock()):
                        if _es_gol_tanda_cu and _es_local_cu:
                            self.partidos_activos[partido_id]['tanda_local'] = \
                                self.partidos_activos[partido_id].get('tanda_local', 0) + 1
                        elif _es_gol_tanda_cu:
                            self.partidos_activos[partido_id]['tanda_visitante'] = \
                                self.partidos_activos[partido_id].get('tanda_visitante', 0) + 1
                        _tl = self.partidos_activos[partido_id].get('tanda_local', 0)
                        _tv = self.partidos_activos[partido_id].get('tanda_visitante', 0)
                    if _es_gol_tanda_cu:
                        msg = EventFormatter.tanda_gol(
                            liga_cu, color_cu, ev_jugador, ev_equipo,
                            equipo_local, _tl, _tv, equipo_visitante)
                    else:
                        msg = EventFormatter.tanda_fallo(
                            liga_cu, color_cu, ev_jugador, ev_equipo,
                            equipo_local, _tl, _tv, equipo_visitante)

                if msg:
                    canales = self.db.get_canales_narracion_activa()
                    for canal in canales:
                        self.bot_callback('message', canal, msg)
                    logging.info(f"📬 Catch-up anunciado: [{ev_minuto}] {ev_icono} {ev_jugador}")

            # ── Marcar todos los hashes actuales como vistos ─────────────────
            # (incluso los que no se procesaron porque no eran importantes)
            for ev in eventos:
                hashes_vistos.add(_hash_evento_catchup(ev))
            
            # ═══════════════════════════════════════════════════════
            # Procesar el evento más reciente (eventos[0] = el más nuevo)
            # ═══════════════════════════════════════════════════════
            ultimo_evento = eventos[0]
            minuto = ultimo_evento.get('minuto', '')
            icono = ultimo_evento.get('icono', '')
            texto = ultimo_evento.get('texto', '')
            jugador = ultimo_evento.get('jugador', '')
            minuto = ultimo_evento.get('minuto', '')
            icono = ultimo_evento.get('icono', '')
            texto = ultimo_evento.get('texto', '')
            jugador = ultimo_evento.get('jugador', '')
            
            # Si tenemos jugador pero no equipo_nombre, buscar en alineaciones
            if jugador and not ultimo_evento.get('equipo_nombre') and not ultimo_evento.get('equipo'):
                # Buscar por apellido (última palabra)
                palabras = jugador.split()
                equipo_encontrado = None
                
                # Intento 1: apellido exacto
                if palabras:
                    apellido = palabras[-1]
                    if apellido in alineaciones:
                        equipo_encontrado = alineaciones[apellido]
                    # Intento 2: nombre completo
                    elif jugador in alineaciones:
                        equipo_encontrado = alineaciones[jugador]
                    # Intento 3: búsqueda parcial (por si el nombre está truncado o abreviado)
                    else:
                        for nombre_al, equipo_al in alineaciones.items():
                            if len(apellido) >= 3 and (apellido.lower() in nombre_al.lower() or nombre_al.lower() in apellido.lower()):
                                equipo_encontrado = equipo_al
                                logging.info(f"✅ Equipo deducido por coincidencia parcial: '{jugador}' ~ '{nombre_al}' → {equipo_al}")
                                break
                
                if equipo_encontrado:
                    ultimo_evento['equipo_nombre'] = equipo_encontrado
                    logging.info(f"✅ Equipo deducido de alineación: {jugador} → {equipo_encontrado}")
            
            logging.debug(f"  ⏱️  Último evento: [{minuto}] {texto[:50]}... (icono: {icono})")
            
            # Verificar si es un evento nuevo
            partido_bd = self.db.get_partido(partido_id)
            ultima_jugada_bd = partido_bd[4] if partido_bd else None
            
            # Generar hash del evento para deduplicación robusta
            # CRÍTICO: Usar jugador (estable) en vez de texto (variable entre scrapes).
            # El texto narrativo de la web cambia entre ciclos de scraping (se añaden
            # detalles, se reformatea), lo que generaba hashes diferentes para el MISMO
            # evento → duplicados.  El nombre del jugador y el minuto son estables.
            _hash_key = jugador if jugador else texto[:50]
            evento_hash = self._evento_hash(minuto, _hash_key, icono, 'evento')
            
            # FIX Bug 34: Hash secundario sin minuto para detectar correcciones de minuto
            # La web a veces corrige el minuto de un evento (ej: 34' → 31') entre scrapes.
            # Si el jugador+icono es el mismo, es el MISMO evento con minuto corregido.
            _hash_sin_minuto = f"{_hash_key}:{icono}".lower().strip()
            _ultimo_hash_sin_min = self.partidos_activos.get(partido_id, {}).get('_ultimo_hash_sin_minuto', '')
            if evento_hash != ultima_jugada_bd and _hash_sin_minuto == _ultimo_hash_sin_min:
                # Mismo jugador+icono pero minuto diferente → corrección de minuto
                logging.info(f"⏭️ Bug34-Guard: Minuto corregido detectado ({partido_id}): {_ultimo_hash_sin_min} → min cambió, ignorando duplicado")
                # Actualizar hash en BD con el nuevo minuto para mantener sincronía
                self.db.update_partido(partido_id, evento_hash)
                if partido_id in self.partidos_activos:
                    self.partidos_activos[partido_id]['_ultimo_hash_sin_minuto'] = _hash_sin_minuto
                return  # Salir de _revisar_partido sin anunciar (es duplicado con min corregido)
            # Guardar hash sin minuto para próxima comparación
            if partido_id in self.partidos_activos:
                self.partidos_activos[partido_id]['_ultimo_hash_sin_minuto'] = _hash_sin_minuto
            
            if evento_hash != ultima_jugada_bd:
                # Nuevo evento detectado (basado en hash, no en texto)
                self._debug(f"🆕 {partido_id}: NUEVO EVENTO!")
                self._debug(f"  [{minuto}] {texto[:80]}")

                # ── Silencio inteligente post-reload ──────────────────────────
                # Tras un reload, evitamos re-anunciar el último evento que ya
                # se envió antes del reload.  Como el scraper solo procesa
                # eventos[0] (el más reciente), hay dos escenarios:
                #
                #  A) evento_hash == pre_reload_hash
                #     → El último evento de la página es el mismo de antes
                #       del reload. Ya se anunció. Sincronizado, no anunciar.
                #
                #  B) evento_hash != pre_reload_hash
                #     → Hay un evento NUEVO que ocurrió durante/después del
                #       reload. Romper silencio y anunciarlo normalmente.
                #
                if partido_id in self.pre_reload_hashes:
                    pre_hash = self.pre_reload_hashes[partido_id]
                    del self.pre_reload_hashes[partido_id]  # Siempre limpiar
                    
                    if evento_hash == pre_hash:
                        # Caso A: mismo evento, ya anunciado antes del reload
                        self.db.update_partido(partido_id, evento_hash)
                        self.db.add_evento(partido_id, minuto, icono, texto, marcador)
                        logging.info(f"🔔 Silencio OK para {partido_id} — mismo evento, sincronizado ({minuto})")
                        self._debug(f"🔔 Silencio OK: {partido_id} sincronizado en [{minuto}]", importante=True)
                        return
                    else:
                        # Caso B: evento NUEVO durante reload — anunciar normalmente
                        logging.info(f"🔔 Silencio roto para {partido_id} — evento nuevo post-reload ({minuto}): {texto[:50]}")
                        self._debug(f"🔔 Silencio roto: {partido_id} evento nuevo [{minuto}]", importante=True)
                        # NO return → cae al flujo normal de anuncio
                # ─────────────────────────────────────────────────────────────

                self.db.update_partido(partido_id, evento_hash)
                self.db.add_evento(partido_id, minuto, icono, texto, marcador)
                
                # VERIFICAR FILTRO DE PARTIDOS (desde BD)
                filtro_id = self.db.partido_en_filtro(equipo_local, equipo_visitante)
                if filtro_id is None:  # No está en el filtro
                    self._debug(f"⏭️  Partido filtrado: {equipo_local} vs {equipo_visitante}")
                    return
                
                # Determinar si narrar en todos los canales o solo en canal de fútbol
                # Función auxiliar para detectar tarjetas rojas desde el texto (definir aquí temprano)
                def _es_tarjeta_roja_temp(texto):
                    """Detecta si un texto describe una tarjeta roja/expulsión"""
                    texto_lower = texto.lower()
                    patrones_roja = [
                        'roja directa', 'tarjeta roja', 'expulsado', 'expulsión',
                        'se va a la calle', 'mostró la roja', 'le muestra la roja',
                        'vio la roja', 've la roja', 'roja para', 't. roja',
                    ]
                    return any(patron in texto_lower for patron in patrones_roja)
                
                es_evento_importante = any(icono_importante in icono for icono_importante in EVENTOS_IMPORTANTES) or _es_tarjeta_roja_temp(texto)
                
                # Extraer marcador separado
                # Usar marcador del evento (de match-header-resume) si está disponible, sino usar el general
                marcador_evento = ultimo_evento.get('marcador_gol', '')
                logging.info(f"🎯 [DEBUG] marcador_evento='{marcador_evento}', marcador_general='{marcador}'")
                if marcador_evento:
                    marcador = marcador_evento
                    logging.info(f"✅ Usando marcador del evento: '{marcador}'")
                else:
                    logging.info(f"⚠️ No hay marcador en evento, usando marcador general: '{marcador}'")
                marcador_split = marcador.split(' - ')
                goles_local = marcador_split[0].strip() if len(marcador_split) > 0 else '?'
                goles_visitante = marcador_split[1].strip() if len(marcador_split) > 1 else '?'
                
                # FIX: Race condition - si es gol y el marcador no ha cambiado, inferir +1
                # GUARD: Verificar que el texto NO sea un cambio/sustitución disfrazado con icono de gol
                # (la web a veces reutiliza accion43.png para cambios)
                _texto_es_cambio = texto and any(x in texto.lower() for x in [
                    'cambio', 'se retira', 'sustitu', 'reemplaz', 'da paso a',
                    'entra por', 'entra en', 'deja su sitio', 'cede su puesto',
                    'se marcha', 'abandona', 'ovacionado', 'sale del campo',
                    'sale de', 'entra al campo', 'último cambio'
                ]) and not (re.search(r'go+l', texto, re.IGNORECASE) or any(x in texto.lower() for x in ['marca', 'tanto', 'autogol', 'propia puerta']))
                es_gol_icono = any(g in icono for g in ['accion1.png', 'accion2.png', 'accion43.png']) and not _texto_es_cambio and not (texto and 'tanda' in texto.lower())
                # FIX Bug 27: Guard contra goles fantasma por iconos transitorios de la web.
                # La web a veces asigna temporalmente accion1.png a posts narrativos durante
                # el scraping en vivo, y luego lo corrige a none.png. Para evitar falsos positivos:
                #   - Si el MHR tiene el gol para este minuto (marcador_gol existe) → confiable
                #   - Si NO hay entrada MHR, el texto DEBE anunciar el gol explícitamente
                #     (empezar con "¡Gol/Goool" etc.), no basta con mencionar "gol" en narrativa
                if es_gol_icono and texto:
                    _tiene_mhr = bool(ultimo_evento.get('marcador_gol', ''))
                    if not _tiene_mhr:
                        # Sin MHR → verificar con regex estricto (texto ANUNCIA el gol)
                        _texto_anuncia_gol = bool(re.search(
                            r'^[¡!]?\s*(?:go+l(?:azo|ito)?|autogol)\b'
                            r'|^[¡!]?\s*(?:¡+go+l(?:azo|ito)?[!\s])'
                            r'|\bautogol\b|\bpropia puerta\b|\bpropia meta\b',
                            texto.lower().strip()
                        ))
                        if not _texto_anuncia_gol:
                            logging.warning(f"⚠️ Bug27-Guard: Icono gol ({icono}) sin MHR y texto no anuncia gol: {texto[:80]}")
                            es_gol_icono = False
                # Regex mejorado: \b para límites de palabra, evita "contragolpe", "goleada", etc.
                # _texto_es_gol: detecta gol POR TEXTO cuando el icono no es accion1.
                # Requisitos:
                #   1. El texto ANUNCIA el gol (empieza con "¡Gol/Goool" o "Gol de" / "Golazo de")
                #      NO sirve que "gol" aparezca en medio de una narración (ej: "autor de un gol en...")
                #   2. Además, el marcador debe haber cambiado respecto al almacenado
                #      (si la página aún no actualizó el marcador, dejamos que lo trate es_gol_icono)
                _texto_es_gol_patron = bool(re.search(
                    r'^[¡!]?\s*(?:go+l(?:azo|ito)?|autogol)\b'          # Empieza con ¡Gol/Golazo/Goool/Autogol
                    r'|^[¡!]?\s*(?:¡+go+l(?:azo|ito)?[!\s])'            # ¡¡¡Goool!!!
                    r'|\bautogol\b|\bpropia puerta\b|\bpropia meta\b',   # autogol / propia siempre
                    texto.lower().strip()
                )) if texto else False
                # Verificar que el marcador realmente cambió (anti-falso-positivo)
                _marcador_actual = marcador or self.partidos_activos.get(partido_id, {}).get('marcador', '0 - 0')
                _marcador_previo = self.partidos_activos.get(partido_id, {}).get('marcador', '0 - 0')
                _marcador_cambio = _marcador_actual != _marcador_previo
                _texto_es_gol = (_texto_es_gol_patron and not _texto_es_cambio
                                 and 'anulad' not in texto.lower()
                                 and 'tanda' not in texto.lower()
                                 and _marcador_cambio)
                if _texto_es_cambio and any(g in icono for g in ['accion1.png', 'accion2.png', 'accion43.png']):
                    logging.warning(f"⚠️ Icono de gol ({icono}) pero texto es cambio: {texto[:80]}")
                if es_gol_icono and not marcador_evento:
                    # Obtener marcador previo almacenado
                    marcador_previo = self.partidos_activos.get(partido_id, {}).get('marcador', '0 - 0')
                    if marcador == marcador_previo:
                        # La página NO ha actualizado el marcador - inferir
                        equipo_goleador = ultimo_evento.get('equipo', '')
                        if not equipo_goleador:
                            equipo_nombre_ev = ultimo_evento.get('equipo_nombre', '')
                            if equipo_nombre_ev:
                                if equipo_nombre_ev.lower() in equipo_local.lower() or equipo_local.lower() in equipo_nombre_ev.lower():
                                    equipo_goleador = 'local'
                                elif equipo_nombre_ev.lower() in equipo_visitante.lower() or equipo_visitante.lower() in equipo_nombre_ev.lower():
                                    equipo_goleador = 'visitante'
                        
                        # FIX: Si aún no sabemos el equipo, buscar en el texto narrativo
                        if not equipo_goleador and texto:
                            texto_lower_gol = texto.lower()
                            # Buscar mención directa del equipo ("gol del Getafe", "del Real Madrid")
                            if equipo_local.lower() in texto_lower_gol:
                                equipo_goleador = 'local'
                                logging.info(f"✅ Equipo goleador deducido del texto: {equipo_local} (local)")
                            elif equipo_visitante.lower() in texto_lower_gol:
                                equipo_goleador = 'visitante'
                                logging.info(f"✅ Equipo goleador deducido del texto: {equipo_visitante} (visitante)")
                            else:
                                # Buscar por nombre parcial (ej: "del Athletic" en "Athletic Club")
                                for palabra in equipo_local.split():
                                    if len(palabra) > 3 and palabra.lower() in texto_lower_gol:
                                        equipo_goleador = 'local'
                                        logging.info(f"✅ Equipo goleador deducido (parcial): {equipo_local} (local)")
                                        break
                                if not equipo_goleador:
                                    for palabra in equipo_visitante.split():
                                        if len(palabra) > 3 and palabra.lower() in texto_lower_gol:
                                            equipo_goleador = 'visitante'
                                            logging.info(f"✅ Equipo goleador deducido (parcial): {equipo_visitante} (visitante)")
                                            break
                        
                        # FIX: Si aún no sabemos, buscar en alineaciones por nombre del goleador
                        if not equipo_goleador and jugador and alineaciones:
                            palabras_jug = jugador.split()
                            for p in palabras_jug:
                                if p in alineaciones:
                                    eq_jug = alineaciones[p]
                                    if eq_jug == equipo_local or (equipo_local.lower() in eq_jug.lower()):
                                        equipo_goleador = 'local'
                                    elif eq_jug == equipo_visitante or (equipo_visitante.lower() in eq_jug.lower()):
                                        equipo_goleador = 'visitante'
                                    if equipo_goleador:
                                        logging.info(f"✅ Equipo goleador deducido de alineaciones: {jugador} → {eq_jug}")
                                        break
                        
                        try:
                            gl_int = int(goles_local) if goles_local.isdigit() else 0
                            gv_int = int(goles_visitante) if goles_visitante.isdigit() else 0
                            # FIX Bug 26: Validar que el incremento sea exactamente +1 gol total
                            # Si el marcador ya fue incrementado en un scrape anterior (hash inestable
                            # por cambio de jugador entre scrapes: ej "BENFICA" → "Rafa Silva"),
                            # el marcador almacenado ya tendrá el gol. No incrementar de nuevo.
                            _prev_split = marcador_previo.split(' - ')
                            _prev_gl = int(_prev_split[0].strip()) if len(_prev_split) > 0 and _prev_split[0].strip().isdigit() else 0
                            _prev_gv = int(_prev_split[1].strip()) if len(_prev_split) > 1 and _prev_split[1].strip().isdigit() else 0
                            _total_antes = _prev_gl + _prev_gv
                            
                            if equipo_goleador == 'local':
                                gl_int += 1
                            elif equipo_goleador == 'visitante':
                                gv_int += 1
                            else:
                                # No sabemos quién marcó, incrementar un genérico
                                logging.warning(f"⚠️ Gol sin equipo para race condition - no se puede inferir marcador")
                            
                            _total_despues = gl_int + gv_int
                            if _total_despues != _total_antes + 1:
                                logging.warning(f"⚠️ Bug26-Guard: Incremento anómalo ({_total_antes} → {_total_despues}), revirtiendo a marcador actual {goles_local}-{goles_visitante}")
                                # Revertir: usar marcador de página sin modificar
                                gl_int = int(goles_local) if goles_local.isdigit() else 0
                                gv_int = int(goles_visitante) if goles_visitante.isdigit() else 0
                            
                            goles_local = str(gl_int)
                            goles_visitante = str(gv_int)
                            marcador = f"{goles_local} - {goles_visitante}"
                            logging.info(f"🔧 Race condition: marcador inferido {marcador} (previo: {marcador_previo})")
                        except Exception as e:
                            logging.warning(f"⚠️ Error infiriendo marcador: {e}")
                
                # Actualizar marcador almacenado
                if partido_id in self.partidos_activos and marcador:
                    self.partidos_activos[partido_id]['marcador'] = marcador

                logging.info(f"🎯 [DEBUG] FINAL - goles_local='{goles_local}', goles_visitante='{goles_visitante}'")

                # ── Dedup de goles ─────────────────────────────────────────────────────
                # Cada gol se identifica por (minuto, marcador_resultado).
                # Si ya fue anunciado en un ciclo anterior, saltarlo completamente
                # para evitar el doble anuncio y el marcador erróneo por race condition.
                if es_gol_icono or _texto_es_gol:
                    _gol_key = (minuto, f"{goles_local}-{goles_visitante}")
                    _goles_anunciados = self.partidos_activos.get(partido_id, {}).get('goles_anunciados', set())
                    if _gol_key in _goles_anunciados:
                        logging.info(f"⏭️ Gol ya anunciado, ignorando: {_gol_key}")
                        es_gol_icono = False
                        _texto_es_gol = False
                    else:
                        # Registrar para no anunciarlo de nuevo
                        if partido_id in self.partidos_activos:
                            if 'goles_anunciados' not in self.partidos_activos[partido_id]:
                                self.partidos_activos[partido_id]['goles_anunciados'] = set()
                            self.partidos_activos[partido_id]['goles_anunciados'].add(_gol_key)
                
                # Determinar tipo de evento para color
                color_evento = "03"  # Verde por defecto
                emoji_evento = "⚽"
                
                if ('accion1.png' in icono or 'accion2.png' in icono or 'accion43.png' in icono) and not _texto_es_cambio:  # Gol (normal o penalti)
                    color_evento = "03"  # Verde
                    emoji_evento = "⚽"
                elif _texto_es_cambio and ('accion18.png' in icono or 'accion19.png' in icono or 'accion43.png' in icono or any(g in icono for g in ['accion1.png', 'accion2.png'])):  # Cambio con icono incorrecto
                    color_evento = "10"  # Cyan (cambio)
                    emoji_evento = "🔄"
                elif 'accion5.png' in icono:  # Tarjeta amarilla
                    color_evento = "08"  # Amarillo (solo para tarjetas)
                    emoji_evento = "📒"
                elif 'accion4.png' in icono or 'accion6.png' in icono or 'accion3.png' in icono:  # Tarjeta roja / doble amarilla
                    color_evento = "04"  # Rojo
                    emoji_evento = "📕"
                elif 'accion14.png' in icono:  # Gol anulado
                    color_evento = "06"  # Magenta/Morado
                    emoji_evento = "⚑"
                elif 'accion34.png' in icono:  # Penalti
                    color_evento = "04"  # Rojo
                    emoji_evento = "⚽"
                elif 'accion15.png' in icono:  # Penalti fallado
                    color_evento = "04"  # Rojo
                    emoji_evento = "❌"
                elif 'accion16.png' in icono:  # Penalti parado
                    color_evento = "04"  # Rojo
                    emoji_evento = "🧤"
                elif 'accion28.png' in icono:  # Penalti cometido (solo si texto lo confirma)
                    _txt28 = texto.lower() if texto else ''
                    if any(x in _txt28 for x in ['penalti', 'penalty', 'penal ']):
                        color_evento = "04"  # Rojo
                        emoji_evento = "⚠️"
                    else:
                        color_evento = "14"  # Gris (evento genérico: saque, reanudación)
                        emoji_evento = "▶️"
                elif 'accion23.png' in icono:  # Gol en tanda de penaltis
                    color_evento = "03"  # Verde
                    emoji_evento = "✅"
                elif 'accion24.png' in icono:  # Fallo en tanda de penaltis
                    color_evento = "04"  # Rojo
                    emoji_evento = "❌"
                elif 'accion36.png' in icono:  # No penalti (VAR descarta)
                    color_evento = "06"  # Magenta
                    emoji_evento = "🚫"
                elif 'accion18.png' in icono or 'accion19.png' in icono:  # Cambio
                    color_evento = "10"  # Cyan
                    emoji_evento = "🔄"
                elif 'accion20.png' in icono:  # VAR / lesión / demora
                    # Distinguir por texto: lesión → ambulancia, VAR → TV
                    _ev_texto_l = texto.lower() if texto else ''
                    if any(x in _ev_texto_l for x in ['lesión', 'lesion', 'lesionado', 'no puede continuar', 'pide el cambio', 'se retira lesionado', 'en camilla', 'asistencia médica']):
                        color_evento = "04"  # Rojo
                        emoji_evento = "🚑"
                    else:
                        color_evento = "06"  # Magenta
                        emoji_evento = "ℹ️"
                
                # Formatear mensaje con colores IRC estilo mIRC
                # Colores: 02=azul, 03=verde, 04=rojo, 08=amarillo, 12=azul claro, 14=gris
                # \x02 = negrita
                
                # liga_formato ya definida arriba (línea ~1843) con datos de partidos_activos
                
                # Función auxiliar para detectar tarjetas rojas desde el texto
                def _es_tarjeta_roja(texto):
                    """Detecta si un texto describe una tarjeta roja/expulsión"""
                    texto_lower = texto.lower()
                    
                    # Patrones que indican tarjeta roja
                    patrones_roja = [
                        'roja directa',
                        'tarjeta roja',
                        'expulsado',
                        'expulsión',
                        'se va a la calle',
                        'mostró la roja',
                        'le muestra la roja',
                        'vio la roja',
                        've la roja',
                        'roja para',
                        't. roja',
                    ]
                    
                    return any(patron in texto_lower for patron in patrones_roja)
                
                # Obtener info del evento
                equipo_jugador = ultimo_evento.get('equipo', '')
                jugador = ultimo_evento.get('jugador', '')
                
                # Si tenemos equipo_nombre (del texto de crónica simplificada), determinar si es local o visitante
                equipo_nombre_evento = ultimo_evento.get('equipo_nombre', '')
                if equipo_nombre_evento and not equipo_jugador:
                    # Comparar con nombres de equipos (case-insensitive, parcial)
                    if equipo_nombre_evento.lower() in equipo_local.lower() or equipo_local.lower() in equipo_nombre_evento.lower():
                        equipo_jugador = 'local'
                    elif equipo_nombre_evento.lower() in equipo_visitante.lower() or equipo_visitante.lower() in equipo_nombre_evento.lower():
                        equipo_jugador = 'visitante'
                
                nombre_equipo = equipo_local if equipo_jugador == 'local' else equipo_visitante if equipo_jugador == 'visitante' else equipo_nombre_evento
                
                # Determinar la parte del partido
                # FUENTE PRIMARIA: estado real almacenado en partidos_activos
                # Evita clasificar goles en tiempo añadido de 1ª parte como "2ª"
                # (ej: gol en el 46' durante el descuento de la primera mitad)
                _parte_estado = self.partidos_activos.get(partido_id, {}).get('parte', '')
                try:
                    minuto_num = int(re.sub(r'[^\d]', '', minuto.split('+')[0]))
                except:
                    minuto_num = 0

                if _parte_estado in ('1ª', 'Descanso'):
                    parte = "1ª"
                elif _parte_estado == '2ª':
                    parte = "2ª"
                elif _parte_estado == '1ª PRO':
                    parte = "1ª PRO"
                elif _parte_estado == '2ª PRO':
                    parte = "2ª PRO"
                else:
                    # Estado desconocido → inferir por minuto (fallback)
                    if minuto_num <= 45:
                        parte = "1ª"
                    elif minuto_num <= 90:
                        parte = "2ª"
                    elif minuto_num <= 105:
                        parte = "1ª PRO"
                    else:
                        parte = "2ª PRO"
                
                # Formatear parte si existe
                parte_formato = f" - \x0312{parte} Parte" if parte else ""
                
                # Formatear según tipo de evento
                if 'accion1.png' in icono and not _texto_es_cambio:  # Gol normal
                    # Verificar que tenemos jugador y equipo, sino es evento mal parseado
                    if not jugador or not nombre_equipo:
                        # Intentar extraer equipo del texto narrativo: "¡Goool del Equipo!"
                        if not nombre_equipo:
                            match_gol_equipo = re.search(r'(?:go+l|golazo)\s+(?:del?|para)\s+(?:el\s+|la\s+)?(.+?)(?:!|\'|\.|\s*$)', texto, re.IGNORECASE)
                            if match_gol_equipo:
                                equipo_texto = match_gol_equipo.group(1).strip().rstrip("!'.")
                                if equipo_texto.lower() in equipo_local.lower() or equipo_local.lower() in equipo_texto.lower():
                                    nombre_equipo = equipo_local
                                    equipo_jugador = 'local'
                                elif equipo_texto.lower() in equipo_visitante.lower() or equipo_visitante.lower() in equipo_texto.lower():
                                    nombre_equipo = equipo_visitante
                                    equipo_jugador = 'visitante'
                                else:
                                    # Búsqueda parcial
                                    for palabra in equipo_texto.split():
                                        if len(palabra) > 3:
                                            if palabra.lower() in equipo_local.lower():
                                                nombre_equipo = equipo_local
                                                equipo_jugador = 'local'
                                                break
                                            elif palabra.lower() in equipo_visitante.lower():
                                                nombre_equipo = equipo_visitante
                                                equipo_jugador = 'visitante'
                                                break
                                    if not nombre_equipo:
                                        nombre_equipo = equipo_texto
                        
                        # FIX: Intentar extraer goleador del texto narrativo
                        if not jugador and texto:
                            # Patrón: "Lo transformó Nombreeeee" / "Lo marcó Nombreee"
                            match_transf = re.search(r'(?:[Tt]ransform|[Mm]arc|[Aa]not)[óoaá]\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:i+|!)*)', texto)
                            if match_transf:
                                # Limpiar letras repetidas del final ("Arambarriiiiii" -> "Arambarri")
                                nombre_raw = match_transf.group(1).rstrip('!')
                                nombre_clean = re.sub(r'(.)\1{2,}', r'\1\1', nombre_raw)  # Reducir 3+ repetidas a 2
                                nombre_clean = re.sub(r'(.)\1+$', r'\1', nombre_clean)  # Quitar repetidas del final
                                if len(nombre_clean) >= 3:
                                    jugador = nombre_clean
                                    logging.info(f"✅ Goleador extraído de narración: '{nombre_raw}' → '{jugador}'")
                            
                            # Patrón: "¡¡Es Nombre Apellido!!" 
                            if not jugador:
                                match_es = re.search(r'¡+\s*[Ee]s\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)*)', texto)
                                if match_es:
                                    jugador = match_es.group(1).strip()
                                    logging.info(f"✅ Goleador extraído de '¡Es...!': '{jugador}'")
                            
                            # Patrón: "Gol de Nombre" (Primera narrativa)
                            if not jugador:
                                match_gol_de = re.search(r'[Gg]o+l(?:azo)?\s+de\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s\-\.]+?)(?:\s+que|\s+tras|\s+para|\s+en|,|\.|\!|\'|$)', texto)
                                if match_gol_de:
                                    jugador = match_gol_de.group(1).strip()
                                    logging.info(f"✅ Goleador extraído de 'gol de': '{jugador}'")
                            
                            # Patrón: "Goool del André Silva" (con artículo antes del nombre)
                            if not jugador:
                                match_gol_del = re.search(r'[Gg]o+l\w*\s+del?\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s\-\.]+?)(?:\.|!|,|\'|$)', texto)
                                if match_gol_del:
                                    _nombre_candidato = match_gol_del.group(1).strip().rstrip("!.'")
                                    # Verificar que NO es nombre de equipo
                                    if _nombre_candidato.lower() not in [equipo_local.lower(), equipo_visitante.lower()]:
                                        # Podría ser "del Athletic" → equipo, o "del André Silva" → jugador
                                        # Si tiene nombre+apellido y no es un equipo, es jugador
                                        if ' ' in _nombre_candidato and not any(eq.lower() in _nombre_candidato.lower() for eq in [equipo_local, equipo_visitante]):
                                            jugador = _nombre_candidato
                                            logging.info(f"✅ Goleador extraído de 'gol del [nombre]': '{jugador}'")
                            
                            # Patrón narrativo: "No falla Nombre" / "No perdona Nombre" / "Marca Nombre"
                            if not jugador:
                                match_narrativo = re.search(
                                    r'(?:[Nn]o\s+(?:falla|perdona|desaprovecha)|[Mm]arca|[Aa]nota|[Ee]mpuja|[Cc]lava|[Rr]emata)\s+'
                                    r'([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)?)',
                                    texto)
                                if match_narrativo:
                                    jugador = match_narrativo.group(1).strip()
                                    logging.info(f"✅ Goleador extraído de patrón narrativo: '{jugador}'")
                            
                            # Buscar equipo del goleador en alineaciones si ahora tenemos nombre
                            if jugador and not nombre_equipo:
                                for p in reversed(jugador.split()):
                                    if p in alineaciones:
                                        eq = alineaciones[p]
                                        if eq.lower() in equipo_local.lower() or equipo_local.lower() in eq.lower():
                                            nombre_equipo = equipo_local
                                            equipo_jugador = 'local'
                                        elif eq.lower() in equipo_visitante.lower() or equipo_visitante.lower() in eq.lower():
                                            nombre_equipo = equipo_visitante
                                            equipo_jugador = 'visitante'
                                        else:
                                            nombre_equipo = eq
                                        break
                        
                        if nombre_equipo and jugador:
                            # Tenemos ambos, usar formato normal
                            mensaje_evento = f"{liga_formato} \x033¡¡¡\x034GOO\x032OO\x034L\x033!!!\x03 \x032del\x03 \x02\x034{nombre_equipo}\x03\x02 \x033»\x03 \x032Marcó:\x03 \x02\x0312{jugador}\x03\x02 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03 \x033»\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03 \x03- \x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                            mensaje_titulo = None
                        elif nombre_equipo and not jugador:
                            # Gol con equipo pero sin goleador
                            logging.warning(f"⚠️ Gol sin goleador identificado: equipo={nombre_equipo}, texto={texto[:50]}")
                            mensaje_evento = f"{liga_formato} \x033¡¡¡\x034GOO\x032OO\x034L\x033!!!\x03 \x032del\x03 \x02\x034{nombre_equipo}\x03\x02 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03 \x033»\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03 \x03- \x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                            mensaje_titulo = None
                        else:
                            logging.warning(f"⚠️ Gol sin datos completos: jugador={jugador}, equipo={nombre_equipo}, texto={texto[:50]}")
                            # Tratarlo como evento genérico
                            mensaje_titulo = None
                            mensaje_evento = f"{liga_formato} \x0314⚽\x03 {minuto}' \x033»\x03 {texto} \x033»\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03-\x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                    else:
                        mensaje_evento = f"{liga_formato} \x033¡¡¡\x034GOO\x032OO\x034L\x033!!!\x03 \x032del\x03 \x02\x034{nombre_equipo}\x03\x02 \x033»\x03 \x032Marcó:\x03 \x02\x0312{jugador}\x03\x02 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03 \x033»\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03 \x03- \x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                        mensaje_titulo = None
                    
                elif ('accion2.png' in icono or 'accion43.png' in icono) and not _texto_es_cambio:  # Gol de penalti
                    # Verificar que tenemos jugador y equipo
                    if not jugador or not nombre_equipo:
                        logging.warning(f"⚠️ Penalti sin datos completos: jugador={jugador}, equipo={nombre_equipo}")
                        mensaje_titulo = None
                        mensaje_evento = f"{liga_formato} \x0314⚽\x03 {minuto}' \x033»\x03 {texto} \x033»\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03-\x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                    else:
                        mensaje_evento = f"{liga_formato} \x033¡¡¡\x034P\x032ENALT\x034I\x033!!!\x03 \x032del\x03 \x02\x034{nombre_equipo}\x03\x02 \x033»\x03 \x032Marcó:\x03 \x02\x0312{jugador}\x03\x02 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03 \x033»\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03 \x03- \x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                        mensaje_titulo = None
                
                elif 'accion14.png' in icono:  # Gol anulado (icono definitivo de la web)
                    # accion14 es el icono específico de gol anulado en resultados-futbol.com
                    # Extraer el equipo al que le anulan y el jugador en fuera de juego (si se menciona)
                    _eq_anulado = nombre_equipo or ''
                    if not _eq_anulado:
                        # Patrón: "anulado a Celta" / "anulado al Real Madrid"
                        _m_eq = re.search(r'anulad[oa]\s+(?:a(?:l)?|para)\s+(?:el\s+|la\s+)?([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s]+?)(?:!|[.,\s]|$)', texto, re.IGNORECASE)
                        if _m_eq:
                            _eq_txt = _m_eq.group(1).strip().rstrip("!., ")
                            for _eq in [equipo_local, equipo_visitante]:
                                if _eq and (_eq_txt.lower() in _eq.lower() or _eq.lower() in _eq_txt.lower()):
                                    _eq_anulado = _eq
                                    break
                            if not _eq_anulado:
                                _eq_anulado = _eq_txt
                    if not _eq_anulado:
                        _eq_anulado = next((eq for eq in [equipo_local, equipo_visitante] if eq and eq.lower() in texto.lower()), '')
                    # Extraer jugador al que le anulan el gol
                    _jug_anulado = jugador or ''
                    if not _jug_anulado:
                        # Solo buscar jugador por patrón "fuera de juego de X" si el texto lo menciona
                        _m_jug = re.search(r'(?:fuera\s+de\s+juego|offside)(?:\s+\w+){0,3}?\s+de\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÀ-ÖØ-öø-ÿ\s\.\-]+?)(?:!|[.,\s]|$)', texto, re.IGNORECASE)
                        if _m_jug:
                            _jug_anulado = _m_jug.group(1).strip().rstrip("!., ")
                    # Detectar si el texto menciona explícitamente fuera de juego
                    _es_fuera_de_juego = bool(re.search(r'fuera\s+de\s+juego|offside', texto, re.IGNORECASE))
                    # Formatear según si hay fuera de juego explícito o no
                    if _eq_anulado and _jug_anulado and _es_fuera_de_juego:
                        mensaje_evento = f"{liga_formato} \x033»\x03 \x034⚑ GOL ANULADO\x03 \x032a\x03 \x02\x034{_eq_anulado}\x03\x02 \x033»\x03 \x032Fuera de juego de\x03 \x02\x0312{_jug_anulado}\x03\x02 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03 \x033»\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03-\x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                    elif _eq_anulado and _jug_anulado:
                        mensaje_evento = f"{liga_formato} \x033»\x03 \x034⚑ GOL ANULADO\x03 \x032a\x03 \x02\x034{_eq_anulado}\x03\x02 \x033»\x03 \x032Gol anulado a\x03 \x02\x0312{_jug_anulado}\x03\x02 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03 \x033»\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03-\x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                    elif _eq_anulado:
                        mensaje_evento = f"{liga_formato} \x033»\x03 \x034⚑ GOL ANULADO\x03 \x032a\x03 \x02\x034{_eq_anulado}\x03\x02 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03 \x033»\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03-\x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                    else:
                        mensaje_evento = f"{liga_formato} \x033»\x03 \x034⚑ GOL ANULADO\x03 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03 \x033»\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03-\x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                    mensaje_titulo = None
                    es_evento_importante = True
                    logging.info(f"⚑ Gol anulado (accion14): equipo={_eq_anulado} jugador={_jug_anulado}")
                    
                elif 'accion5.png' in icono:  # Tarjeta amarilla
                    # Fallback: extraer del texto si no tenemos jugador/equipo
                    if not jugador or not nombre_equipo:
                        # Patrón 1: "T. Amarilla - Jugador (Equipo)" - Segunda División
                        match_texto = re.search(r'^[^-]+-\s*([^(]+)\s*\(([^)]+)\)', texto)
                        if match_texto:
                            if not jugador:
                                jugador = match_texto.group(1).strip()
                            if not nombre_equipo:
                                nombre_equipo = match_texto.group(2).strip()
                        else:
                            # Patrón 2: "Amarilla para Jugador por/que/en la/tras/,..." - Primera División
                            match_tarjeta = re.search(r'[Aa]marilla para ([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s\-\.]{2,50})(?:\s+por|\s+que|\s+del|\s+en\s+|\s+tras|\.|,|$)', texto)
                            if match_tarjeta:
                                if not jugador:
                                    jugador = self._limpiar_nombre_jugador(match_tarjeta.group(1).strip())
                            else:
                                # Patrón 3: Buscar nombre después de "Amarilla" (sin "para")
                                # Ejemplo: "Amarilla de Jugador"
                                match_simple = re.search(r'[Aa]marilla\s+(?:de\s+)?([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s\-\.]{2,50})(?:\s+por|\s+en\s+|\.|,|$)', texto)
                                if match_simple:
                                    if not jugador:
                                        jugador = self._limpiar_nombre_jugador(match_simple.group(1).strip())
                                else:
                                    # Patrón 4: "Se la lleva NOMBRE por..." (Primera División narrativo)
                                    # Ej: "Se la lleva Salinas por un agarrón sobre Pape Gueye"
                                    match_lleva = re.search(r'[Ss]e la lleva\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s\-\.]{2,50})(?:\s+por|\.|\s*,|$)', texto)
                                    if match_lleva:
                                        if not jugador:
                                            jugador = self._limpiar_nombre_jugador(match_lleva.group(1).strip())
                                    else:
                                        # Patrón 5: "Tarjeta [adjetivo] NOMBRE" - narrativo Champions/LaLiga
                                        # Ej: "Tarjeta clara Jonathan Tah, que pisó a Mbappé"
                                        match_tarjeta_adj = re.search(r'[Tt]arjeta\s+\w+\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s\-\.]{2,40})(?:,|\s+por|\s+que|\.)', texto)
                                        if match_tarjeta_adj:
                                            if not jugador:
                                                jugador = self._limpiar_nombre_jugador(match_tarjeta_adj.group(1).strip())
                    
                    # Si aún no tenemos jugador, intentar extraer del texto completo
                    if not jugador:
                        # Último recurso: buscar nombres propios con finditer para saltar falsos positivos
                        _palabras_no_jugador = ['sale', 'entra', 'gol', 'tarjeta', 'amarilla', 'roja', 'segunda',
                                                'ya tenemos', 'se la lleva', 'se la llevan', 'y', 'otra', 'y otra', 'y orta', 'pero', 'tras']
                        for match_nombre in re.finditer(r'([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s\-\.]{2,25})(?:\s+por|\s+que|\s+en\s+|\.|,|\'|$)', texto):
                            posible_jugador = match_nombre.group(1).strip()
                            pj_lower = posible_jugador.lower()
                            # Filtrar si es una palabra prohibida o empieza por una frase narrativa
                            if pj_lower not in _palabras_no_jugador and not any(pj_lower.startswith(p + " ") for p in _palabras_no_jugador):
                                jugador = self._limpiar_nombre_jugador(posible_jugador)
                                break
                    
                    # Mensaje adaptativo: con o sin equipo
                    # FIX: Si tenemos jugador pero no equipo, buscar en alineaciones
                    if jugador and not nombre_equipo:
                        palabras_jug = jugador.split()
                        for p in reversed(palabras_jug):  # Buscar desde apellido
                            if p in alineaciones:
                                eq_encontrado = alineaciones[p]
                                if eq_encontrado.lower() in equipo_local.lower() or equipo_local.lower() in eq_encontrado.lower():
                                    nombre_equipo = equipo_local
                                elif eq_encontrado.lower() in equipo_visitante.lower() or equipo_visitante.lower() in eq_encontrado.lower():
                                    nombre_equipo = equipo_visitante
                                else:
                                    nombre_equipo = eq_encontrado
                                logging.info(f"✅ Equipo tarjeta deducido de alineación: {jugador} → {nombre_equipo}")
                                break
                            # Búsqueda parcial para nombres truncados
                            elif len(p) >= 4:
                                for nom_al, eq_al in alineaciones.items():
                                    if p.lower() in nom_al.lower() or nom_al.lower().startswith(p.lower()):
                                        if eq_al.lower() in equipo_local.lower() or equipo_local.lower() in eq_al.lower():
                                            nombre_equipo = equipo_local
                                        elif eq_al.lower() in equipo_visitante.lower() or equipo_visitante.lower() in eq_al.lower():
                                            nombre_equipo = equipo_visitante
                                        else:
                                            nombre_equipo = eq_al
                                        logging.info(f"✅ Equipo tarjeta deducido (parcial): '{p}' ~ '{nom_al}' → {nombre_equipo}")
                                        break
                                if nombre_equipo:
                                    break
                    
                    if jugador:
                        # Intentar deducir equipo por contexto si aún no lo tenemos
                        if not nombre_equipo:
                            # Fallback A: Extraer equipo directamente del texto narrativo
                            # Patrones: "del Real Betis", "de la Real Sociedad", "del Rayo"
                            for eq in [equipo_local, equipo_visitante]:
                                if eq and eq.lower() in texto.lower():
                                    nombre_equipo = eq
                                    logging.info(f"✅ Equipo tarjeta extraído del texto narrativo: '{eq}' en '{texto[:60]}'")
                                    break
                        
                        if not nombre_equipo:
                            # Fallback B: Buscar patrón "del/de la [Equipo]" con nombres parciales
                            _m_del_equipo = re.search(r'(?:del|de la|de el)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s]+?)(?:\s+por|\s+tras|[.,!]|$)', texto, re.IGNORECASE)
                            if _m_del_equipo:
                                _eq_txt = _m_del_equipo.group(1).strip().rstrip(".,! ")
                                for eq in [equipo_local, equipo_visitante]:
                                    if eq and (_eq_txt.lower() in eq.lower() or eq.lower() in _eq_txt.lower()):
                                        nombre_equipo = eq
                                        logging.info(f"✅ Equipo tarjeta deducido del patrón 'del X': '{_eq_txt}' → {eq}")
                                        break

                        if not nombre_equipo:
                            # Fallback C: usar contexto del partido (alineaciones)
                            # Si sólo hay un jugador con ese apellido en las alineaciones, asumir ese equipo
                            palabras_jug = jugador.split()
                            posibles_equipos = []
                            for p in palabras_jug:
                                if len(p) >= 3:  # Solo palabras significativas
                                    for nom_al, eq_al in alineaciones.items():
                                        if p.lower() in nom_al.lower():
                                            posibles_equipos.append(eq_al)
                            
                            if posibles_equipos:
                                # Si todos los matches apuntan al mismo equipo, usar ese
                                equipos_unicos = list(set(posibles_equipos))
                                if len(equipos_unicos) == 1:
                                    eq_deducido = equipos_unicos[0]
                                    if eq_deducido.lower() in equipo_local.lower():
                                        nombre_equipo = equipo_local
                                    elif eq_deducido.lower() in equipo_visitante.lower():
                                        nombre_equipo = equipo_visitante
                                    else:
                                        nombre_equipo = eq_deducido
                                    logging.info(f"✅ Equipo tarjeta deducido por contexto único: {jugador} → {nombre_equipo}")
                        
                        if nombre_equipo:
                            mensaje_evento = f"{liga_formato} \x034T\x032arjeta \x034A\x032marilla\x03 \x033»\x03 \x02\x0312{jugador}\x03\x02 \x032del\x03 \x02\x034{nombre_equipo}\x03\x02 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03"
                        else:
                            # Sin equipo, mostrar solo jugador
                            mensaje_evento = f"{liga_formato} \x034T\x032arjeta \x034A\x032marilla\x03 \x033»\x03 \x02\x0312{jugador}\x03\x02 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03"
                            logging.warning(f"⚠️ Tarjeta amarilla sin equipo identificado: jugador={jugador}")
                    else:
                        # Sin jugador extraído, mostrar solo el evento genérico
                        logging.warning(f"⚠️ Tarjeta amarilla sin jugador: {texto[:80]}")
                        mensaje_evento = f"{liga_formato} \x034T\x032arjeta \x034A\x032marilla\x03 \x032(Min:\x0312 {minuto}{parte_formato}\x032) \x033»\x03 \x0314{texto}\x03"
                    mensaje_titulo = None
                    
                elif ('accion4.png' in icono or 'accion6.png' in icono or 'accion3.png' in icono or _es_tarjeta_roja(texto)) and not _texto_es_gol:  # Tarjeta roja o doble amarilla (pero no si es gol con icono incorrecto)
                    # Detectar si es doble amarilla (2a amarilla = roja)
                    es_doble_amarilla = any(x in texto.lower() for x in ['2a amarilla', 'doble amarilla', 'segunda amarilla', '2ª amarilla'])
                    
                    # Fallback: extraer del texto si no tenemos jugador/equipo
                    if not jugador or not nombre_equipo:
                        # Patrón 1: "T. Roja - Jugador (Equipo)" o "2a Amarilla/Roja - Jugador (Equipo)"
                        match_texto = re.search(r'^[^-]+-\s*([^(]+)\s*\(([^)]+)\)', texto)
                        if match_texto:
                            if not jugador:
                                jugador = match_texto.group(1).strip()
                            if not nombre_equipo:
                                nombre_equipo = match_texto.group(2).strip()
                        else:
                            # Patrón 2: "Roja para Jugador..." o "Expulsado Jugador" - Primera División
                            match_tarjeta = re.search(r'(?:[Rr]oja para|[Ee]xpulsado|[Ee]xpulsión de) ([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s\-\.]+?)(?:\s+por|\s+que|,|\.)', texto)
                            if match_tarjeta:
                                if not jugador:
                                    jugador = match_tarjeta.group(1).strip()
                    
                    # FIX: Si tenemos jugador pero no equipo, buscar en alineaciones
                    if jugador and jugador.strip() and not nombre_equipo:
                        palabras_jug = jugador.split()
                        for p in reversed(palabras_jug):
                            if p in alineaciones:
                                eq_encontrado = alineaciones[p]
                                if eq_encontrado.lower() in equipo_local.lower() or equipo_local.lower() in eq_encontrado.lower():
                                    nombre_equipo = equipo_local
                                elif eq_encontrado.lower() in equipo_visitante.lower() or equipo_visitante.lower() in eq_encontrado.lower():
                                    nombre_equipo = equipo_visitante
                                else:
                                    nombre_equipo = eq_encontrado
                                logging.info(f"✅ Equipo roja deducido de alineación: {jugador} → {nombre_equipo}")
                                break
                            elif len(p) >= 4:
                                for nom_al, eq_al in alineaciones.items():
                                    if p.lower() in nom_al.lower() or nom_al.lower().startswith(p.lower()):
                                        if eq_al.lower() in equipo_local.lower() or equipo_local.lower() in eq_al.lower():
                                            nombre_equipo = equipo_local
                                        elif eq_al.lower() in equipo_visitante.lower() or equipo_visitante.lower() in eq_al.lower():
                                            nombre_equipo = equipo_visitante
                                        else:
                                            nombre_equipo = eq_al
                                        logging.info(f"✅ Equipo roja deducido (parcial): '{p}' ~ '{nom_al}' → {nombre_equipo}")
                                        break
                                if nombre_equipo:
                                    break
                    
                    # VALIDACIÓN: Si no hay jugador, podría ser un falso positivo de _es_tarjeta_roja
                    # (narración que menciona "roja" sin ser realmente una tarjeta)
                    if not jugador or not jugador.strip():
                        logging.warning(f"⚠️ Tarjeta roja sin jugador - posible falso positivo: '{texto[:80]}'")
                        # Tratar como evento genérico
                        mensaje_titulo = None
                        mensaje_evento = f"{liga_formato} \x0314⚽\x03 {minuto}' \x033»\x03 {texto} \x033»\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03-\x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                    else:
                        # Intentar deducir equipo por contexto si aún no lo tenemos
                        if not nombre_equipo:
                            palabras_jug = jugador.split()
                            posibles_equipos = []
                            for p in palabras_jug:
                                if len(p) >= 3:
                                    for nom_al, eq_al in alineaciones.items():
                                        if p.lower() in nom_al.lower():
                                            posibles_equipos.append(eq_al)
                            
                            if posibles_equipos:
                                equipos_unicos = list(set(posibles_equipos))
                                if len(equipos_unicos) == 1:
                                    eq_deducido = equipos_unicos[0]
                                    if eq_deducido.lower() in equipo_local.lower():
                                        nombre_equipo = equipo_local
                                    elif eq_deducido.lower() in equipo_visitante.lower():
                                        nombre_equipo = equipo_visitante
                                    else:
                                        nombre_equipo = eq_deducido
                                    logging.info(f"✅ Equipo roja deducido por contexto único: {jugador} → {nombre_equipo}")
                        
                        # Formatear mensaje según tipo
                        if es_doble_amarilla:
                            # Formato especial para doble amarilla
                            if nombre_equipo:
                                mensaje_evento = f"{liga_formato} \x033⚠️\x03 \x03042ª AMARILLA = ROJA\x03 \x033⚠️\x03 \x032para\x03 \x02\x0312{jugador}\x03\x02 \x032del\x03 \x02\x034{nombre_equipo}\x03\x02 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03 \x033»\x03 \x02\x034¡EXPULSADO!\x03\x02"
                            else:
                                mensaje_evento = f"{liga_formato} \x033⚠️\x03 \x03042ª AMARILLA = ROJA\x03 \x033⚠️\x03 \x032para\x03 \x02\x0312{jugador}\x03\x02 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03 \x033»\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03-\x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02 \x033»\x03 \x02\x034¡EXPULSADO!\x03\x02"
                                logging.warning(f"⚠️ Tarjeta roja (2ª amarilla) sin equipo: jugador={jugador}")
                        else:
                            # Formato normal para tarjeta roja directa
                            if nombre_equipo:
                                mensaje_evento = f"{liga_formato} \x034T\x032arjeta \x034R\x032oja\x03 \x034,4|_\x03 \x032para\x03 \x02\x0312{jugador}\x03\x02 \x032del\x03 \x02\x034{nombre_equipo}\x03\x02 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03 \x033»\x03 \x02\x034¡EXPULSADO!\x03\x02"
                            else:
                                mensaje_evento = f"{liga_formato} \x034T\x032arjeta \x034R\x032oja\x03 \x034,4|_\x03 \x032para\x03 \x02\x0312{jugador}\x03\x02 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03 \x033»\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03-\x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02 \x033»\x03 \x02\x034¡EXPULSADO!\x03\x02"
                                logging.warning(f"⚠️ Tarjeta roja sin equipo: jugador={jugador}")
                    mensaje_titulo = None
                    
                elif 'accion18.png' in icono or 'accion19.png' in icono:  # Cambio (sale o entra)
                    # VALIDACIÓN ROBUSTA: Verificar que el texto realmente describe una sustitución
                    # Primera División reutiliza iconos para textos narrativos genéricos
                    texto_lower_cambio = texto.lower().strip()
                    
                    # Palabras que indican que NO es una sustitución real
                    _palabras_narrativas = [
                        'fuera', 'directamente', 'lanzamiento', 'remate', 'disparo',
                        'balón', 'balon', 'córner', 'corner', 'falta', 'tiro',
                        'platea', 'grada', 'por su propio pie', 'el rostro',
                        'algo no va bien', 'saque', 'centro', 'pase', 'portería',
                        'cabeza', 'pie izquierdo', 'pie derecho', 'volea',
                        'penalti', 'penalty', 'área', 'area',
                    ]
                    
                    # Helper: Verificar si un texto parece nombre de jugador real
                    def _es_nombre_valido(nombre):
                        if not nombre or len(nombre.strip()) < 2:
                            return False
                        nombre_lower = nombre.lower().strip()
                        palabras_invalidas = [
                            'fuera', 'directamente', 'platea', 'lanzamiento', 'remate',
                            'disparo', 'balón', 'córner', 'falta', 'tiro', 'centro',
                            'el ', 'la ', 'un ', 'una ', 'del ', 'al ', 'por ',
                            'que ', 'su ', 'con ', 'sin ', 'sobre ', 'tras ', 'desde ',
                            'propio', 'rostro', 'algo', 'lejano', 'bien', 'mal',
                            'grada', 'banquillo', 'pie', 'cabeza', 'portería',
                        ]
                        if any(nombre_lower.startswith(p) or f' {p}' in f' {nombre_lower}' for p in palabras_invalidas):
                            return False
                        if not any(c.isupper() for c in nombre):
                            return False
                        if len(nombre.split()) > 5:
                            return False
                        return True
                    
                    es_cambio_real = True
                    
                    # Detectar formato estructurado (Segunda División)
                    tiene_formato_struct = bool(re.search(r'(?:Sale|Entra)[^-]*-\s*[^(]+\s*\([^)]+\)', texto, re.IGNORECASE))
                    tiene_formato_vestuario = bool(re.search(r'(?:Se queda en el vestuario|Sale)\s+[A-ZÁÉÍÓÚÑ].+\s+y\s+entra', texto, re.IGNORECASE))
                    # NUEVO: Detectar formato "Doble/Triple cambio" narrativo
                    tiene_formato_doble = bool(re.search(r'(?:doble|triple)\s+cambio', texto_lower_cambio))
                    tiene_formato_se_van = bool(re.search(r'se va[n]?\s+[A-ZÁÉÍÓÚÑ]|entra[n]?\s+[A-ZÁÉÍÓÚÑ]', texto, re.IGNORECASE))
                    
                    if not tiene_formato_struct and not tiene_formato_vestuario and not tiene_formato_doble and not tiene_formato_se_van:
                        # Sin formato estructurado - verificar si es narrativo
                        if any(falso in texto_lower_cambio for falso in _palabras_narrativas):
                            es_cambio_real = False
                            logging.info(f"⏭️ accion18/19 descartado como narrativo: '{texto[:60]}'")
                        elif not jugador and len(texto.strip()) < 10:
                            es_cambio_real = False
                            logging.info(f"⏭️ accion18/19 descartado (texto muy corto): '{texto[:60]}'")
                        elif jugador and not _es_nombre_valido(jugador):
                            es_cambio_real = False
                            logging.info(f"⏭️ accion18/19 descartado (nombre inválido '{jugador}'): '{texto[:60]}'")
                    
                    if not es_cambio_real:
                        # Tratar como evento genérico de narración
                        mensaje_titulo = None
                        mensaje_evento = f"{liga_formato} \x0314⚽\x03 {minuto}' \x033»\x03 {texto} \x033»\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03-\x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                    else:
                        # Es un cambio real
                        jugador_actual = jugador
                        equipo_actual = nombre_equipo
                        
                        # NUEVO: Procesar cambios dobles/múltiples
                        if tiene_formato_doble or tiene_formato_se_van:
                            # Intentar parsear jugadores del texto narrativo antes de formatear
                            # para producir el mismo formato bonito que el resto de cambios.
                            # Si no se puede parsear, se deja para los patrones N1-N5 del bloque
                            # elif de más abajo, que tienen más variantes.
                            # Aquí solo manejamos el caso en que ya tenemos jugador_actual y equipo_actual.
                            if jugador_actual and equipo_actual:
                                # Evitar "del el Levante"
                                eq_fmt = re.sub(r'^(?:el|la|los|las)\s+', '', equipo_actual, flags=re.IGNORECASE)
                                mensaje_evento = f"{liga_formato} \x033¡¡¡\x034C\x032ambi\x032o\x033!!!\x03 \x032del:\x03 \x02\x034{eq_fmt}\x03\x02 \x033»\x03 \x032Entra:\x03 \x02\x0312{jugador_actual}\x03\x02 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03"
                            else:
                                # Sin datos suficientes en este icono, dejar mensaje_evento=None
                                # para que el bloque elif de cambios narrativos lo procese correctamente
                                mensaje_evento = None
                            mensaje_titulo = None
                            logging.info(f"✅ Cambio múltiple (accion18/19) detectado: jugador={jugador_actual}")
                        elif not jugador_actual or not equipo_actual:
                            # Patrón 1: Segunda "Sale/Entra - Jugador (Equipo)"
                            match_cambio = re.search(r'(?:Sale|Entra)[^-]*-\s*([^(]+)\s*\(([^)]+)\)', texto, re.IGNORECASE)
                            if match_cambio:
                                if not jugador_actual:
                                    jugador_actual = match_cambio.group(1).strip()
                                if not equipo_actual:
                                    equipo_actual = match_cambio.group(2).strip()
                            else:
                                # Patrón 2: "Sale X y entra Y"
                                match_vestuario = re.search(r'(?:Se queda en el vestuario|Sale)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s\-\.]+?)\s+y\s+entra\s+(?:en\s+su\s+lugar\s+)?([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s\-\.]+?)[\.\'"]', texto, re.IGNORECASE)
                                if match_vestuario:
                                    jugador_sale_v = match_vestuario.group(1).strip()
                                    jugador_entra_v = match_vestuario.group(2).strip()
                                    if equipo_actual:
                                        eq_fmt_v = re.sub(r'^(?:el|la|los|las)\s+', '', equipo_actual, flags=re.IGNORECASE)
                                        mensaje_evento = f"{liga_formato} \x033¡¡¡\x034C\x032ambi\x032o\x033!!!\x03 \x032del:\x03 \x02\x034{eq_fmt_v}\x03\x02 \x033»\x03 \x034Sale:\x03 \x02\x0312{jugador_sale_v}\x03\x02 \x033»\x03 \x032Entra:\x03 \x02\x0312{jugador_entra_v}\x03\x02 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03"
                                    else:
                                        mensaje_evento = f"{liga_formato} \x033¡¡¡\x034C\x032ambi\x032o\x033!!!\x03 \x033»\x03 \x034Sale:\x03 \x02\x0312{jugador_sale_v}\x03\x02 \x033»\x03 \x032Entra:\x03 \x02\x0312{jugador_entra_v}\x03\x02 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03"
                                    mensaje_titulo = None
                        
                        # Validación final del nombre extraído
                        if jugador_actual and not _es_nombre_valido(jugador_actual):
                            logging.warning(f"⚠️ Nombre inválido en cambio: '{jugador_actual}', descartando")
                            jugador_actual = ''
                        
                        if 'accion18.png' in icono:  # Sale
                            if jugador_actual:
                                if partido_id not in self._cambios_pendientes:
                                    self._cambios_pendientes[partido_id] = {}
                                clave_cambio = f"{equipo_actual}_{minuto}"
                                self._cambios_pendientes[partido_id][clave_cambio] = jugador_actual
                            mensaje_evento = None
                            mensaje_titulo = None
                        else:  # Entra (accion19)
                            jugador_sale = ""
                            if partido_id in self._cambios_pendientes:
                                clave_cambio = f"{equipo_actual}_{minuto}"
                                if clave_cambio in self._cambios_pendientes[partido_id]:
                                    jugador_sale = self._cambios_pendientes[partido_id].pop(clave_cambio)
                                elif self._cambios_pendientes[partido_id]:
                                    for clave in list(self._cambios_pendientes[partido_id].keys()):
                                        if clave.startswith(f"{equipo_actual}_"):
                                            jugador_sale = self._cambios_pendientes[partido_id].pop(clave)
                                            break
                            
                            # FIX: Si no hay sale pendiente, buscar en TODOS los eventos del mismo minuto
                            if not jugador_sale and eventos:
                                for ev in eventos:
                                    if ev is ultimo_evento:
                                        continue
                                    if 'accion18.png' in ev.get('icono', '') and ev.get('minuto') == minuto:
                                        ev_texto = ev.get('texto', '')
                                        match_sale = re.search(r'^[^-]+-\s*([^(]+)\s*\(([^)]+)\)', ev_texto)
                                        if match_sale:
                                            jugador_sale = match_sale.group(1).strip()
                                            logging.info(f"✅ Sale encontrado en eventos paralelos: {jugador_sale}")
                                            break
                                        elif ev.get('jugador'):
                                            jugador_sale = ev['jugador']
                                            logging.info(f"✅ Sale encontrado (jugador): {jugador_sale}")
                                            break
                            
                            if jugador_sale and jugador_actual:
                                if equipo_actual:
                                    eq_fmt_p = re.sub(r'^(?:el|la|los|las)\s+', '', equipo_actual, flags=re.IGNORECASE)
                                    mensaje_evento = f"{liga_formato} \x033¡¡¡\x034C\x032ambi\x032o\x033!!!\x03 \x032del:\x03 \x02\x034{eq_fmt_p}\x03\x02 \x033»\x03 \x034Sale:\x03 \x02\x0312{jugador_sale}\x03\x02 \x033»\x03 \x032Entra:\x03 \x02\x0312{jugador_actual}\x03\x02 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03"
                                else:
                                    mensaje_evento = f"{liga_formato} \x033¡¡¡\x034C\x032ambi\x032o\x033!!!\x03 \x034Sale:\x03 \x02\x0312{jugador_sale}\x03\x02 \x033»\x03 \x032Entra:\x03 \x02\x0312{jugador_actual}\x03\x02 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03"
                            elif jugador_actual:
                                if equipo_actual:
                                    mensaje_evento = f"{liga_formato} \x033¡¡¡\x034C\x032ambi\x032o\x033!!!\x03 \x032del:\x03 \x02\x034{equipo_actual}\x03\x02 \x033»\x03 \x032Entra:\x03 \x02\x0312{jugador_actual}\x03\x02 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03"
                                else:
                                    mensaje_evento = f"{liga_formato} \x033¡¡¡\x034C\x032ambi\x032o\x033!!!\x03 \x032Entra:\x03 \x02\x0312{jugador_actual}\x03\x02 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03"
                            else:
                                # Sin datos válidos, evento genérico
                                mensaje_titulo = None
                                mensaje_evento = f"{liga_formato} \x0314⚽\x03 {minuto}' \x033»\x03 {texto} \x033»\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03-\x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                            mensaje_titulo = None
                    
                elif 'accion20.png' in icono:  # VAR / tiempo añadido / demora
                    # accion20 se usa para VAR, tiempo de descuento y demoras médicas.
                    # Distinguir por el texto para no anunciar "VAR" cuando no lo es.
                    _texto_l = texto.lower()
                    _es_var_real = bool(re.search(r'\bvar\b', _texto_l)) or any(x in _texto_l for x in ['vídeo', 'video arbitr', 'videoarbitr', 'revisión del', 'revisa el', 'árbitro asistente', 'se está revisando', 'se revisa'])
                    _es_tiempo = any(x in _texto_l for x in ['minuto', 'tiempo de descuento', 'añadirán', 'se añaden', 'tiempo adicional', 'se han perdido'])
                    _es_lesion = any(x in _texto_l for x in ['lesión', 'lesion', 'lesionado', 'lesionada', 'no puede continuar', 'pide el cambio', 'se retira lesionado', 'se retira dolorido', 'se duele', 'en camilla', 'asistencia médica', 'asistencia sanitaria', 'atendido por', 'servicio médico', 'retirado en camilla', 'problemas físicos', 'molestias', 'se resiente'])
                    if _es_var_real:
                        mensaje_evento = f"{liga_formato} \x033»\x03 \x034V\x032A\x034R\x03 \x033«\x03 \x032Revisión en curso\x03 \x032(Min:\x0312 {minuto}\x032)\x03 \x033»\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03-\x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                    elif _es_tiempo:
                        # Tiempo añadido/perdido: anunciar con formato unificado
                        mensaje_evento = f"{liga_formato} \x036⏱\x03 {minuto}' \x033»\x03 {texto} \x033»\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03-\x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                        mensaje_titulo = None
                    elif _es_lesion:
                        # Lesión/atención médica: usar formato con ambulancia
                        mensaje_evento = f"{liga_formato} \x034🚑\x03 {minuto}' \x033»\x03 {texto} \x033»\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03-\x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                        mensaje_titulo = None
                    else:
                        # Otro uso desconocido de accion20: formato genérico unificado
                        mensaje_evento = f"{liga_formato} \x036ℹ️\x03 {minuto}' \x033»\x03 {texto} \x033»\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03-\x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                        mensaje_titulo = None
                    if _es_var_real:
                        mensaje_titulo = None
                
                elif 'accion22.png' in icono:  # Asistencia
                    if jugador and nombre_equipo:
                        mensaje_evento = f"{liga_formato} \x033»\x03 \x032Asistencia de\x03 \x02\x0312{jugador}\x03\x02 \x032del\x03 \x02\x034{nombre_equipo}\x03\x02 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03"
                    elif jugador:
                        mensaje_evento = f"{liga_formato} \x033»\x03 \x032Asistencia de\x03 \x02\x0312{jugador}\x03\x02 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03"
                    else:
                        mensaje_evento = f"{liga_formato} \x033»\x03 \x032Asistencia\x03 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03"
                    mensaje_titulo = None
                
                elif 'accion34.png' in icono:  # Penalti
                    # Extraer jugador/equipo del texto si no los tenemos
                    if not jugador:
                        # Patrón "Penalti - Jugador (Equipo)" (Segunda División)
                        match_guion = re.search(r'^[^-]+-\s*([^(]+)\s*\(([^)]+)\)', texto)
                        if match_guion:
                            jugador = match_guion.group(1).strip()
                            if not nombre_equipo:
                                nombre_equipo = match_guion.group(2).strip()
                        else:
                            # Intentar extraer del texto narrativo (Primera División)
                            match_penalti = re.search(r'[Pp]enalti\s+(?:para\s+(?:el\s+)?)?([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s\-\.]{2,40})(?:[,\.!]|$)', texto)
                            if match_penalti:
                                nombre_equipo = self._limpiar_nombre_jugador(match_penalti.group(1).strip())

                    marcador_fmt = f"\x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03-\x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                    if nombre_equipo:
                        mensaje_evento = f"{liga_formato} \x034⚽\x03 \x032¡¡PENALTI!!\x03 \x032para\x03 \x02\x034{nombre_equipo}\x03\x02 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03 \x033»\x03 {marcador_fmt}"
                    else:
                        mensaje_evento = f"{liga_formato} \x034⚽\x03 \x032¡¡PENALTI!!\x03 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03 \x033»\x03 {marcador_fmt}"
                    mensaje_titulo = None
                    es_evento_importante = True
                    logging.info(f"⚽ Penalti: equipo={nombre_equipo}, min={minuto}")

                elif 'accion15.png' in icono:  # Penalti fallado (el tirador falla)
                    # HTML real: "Penalti fallado - M. Janković (Qarabağ)"
                    marcador_fmt = f"\x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03-\x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                    if jugador and nombre_equipo:
                        mensaje_evento = f"{liga_formato} \x034❌\x03 \x032¡¡PENALTI FALLADO!!\x03 \x032por\x03 \x02\x0312{jugador}\x03\x02 \x032del\x03 \x02\x034{nombre_equipo}\x03\x02 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03 \x033»\x03 {marcador_fmt}"
                    elif jugador:
                        mensaje_evento = f"{liga_formato} \x034❌\x03 \x032¡¡PENALTI FALLADO!!\x03 \x032por\x03 \x02\x0312{jugador}\x03\x02 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03 \x033»\x03 {marcador_fmt}"
                    else:
                        mensaje_evento = f"{liga_formato} \x034❌\x03 \x032¡¡PENALTI FALLADO!!\x03 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03 \x033»\x03 {marcador_fmt}"
                    mensaje_titulo = None
                    es_evento_importante = True
                    logging.info(f"❌ Penalti fallado: jugador={jugador}, equipo={nombre_equipo}, min={minuto}")

                elif 'accion16.png' in icono:  # Penalti parado (el portero lo detiene)
                    # HTML real: "Penalti parado - A. Ramsdale (Newcastle)"
                    marcador_fmt = f"\x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03-\x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                    if jugador and nombre_equipo:
                        mensaje_evento = f"{liga_formato} \x034🧤\x03 \x032¡¡PENALTI PARADO!!\x03 \x032por\x03 \x02\x0312{jugador}\x03\x02 \x032del\x03 \x02\x034{nombre_equipo}\x03\x02 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03 \x033»\x03 {marcador_fmt}"
                    elif jugador:
                        mensaje_evento = f"{liga_formato} \x034🧤\x03 \x032¡¡PENALTI PARADO!!\x03 \x032por\x03 \x02\x0312{jugador}\x03\x02 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03 \x033»\x03 {marcador_fmt}"
                    else:
                        mensaje_evento = f"{liga_formato} \x034🧤\x03 \x032¡¡PENALTI PARADO!!\x03 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03 \x033»\x03 {marcador_fmt}"
                    mensaje_titulo = None
                    es_evento_importante = True
                    logging.info(f"🧤 Penalti parado: jugador={jugador}, equipo={nombre_equipo}, min={minuto}")

                elif 'accion28.png' in icono:  # Penalti cometido (falta que causa penalti)
                    # GUARD: accion28.png NO es exclusivo de penaltis — la web lo usa también
                    # para saques de centro ("¡Ya está en juego!") y reanudaciones tras parones.
                    # Solo anunciar como penalti si el texto realmente lo menciona.
                    _texto28_lower = texto.lower() if texto else ''
                    _es_penalti_real = any(x in _texto28_lower for x in ['penalti', 'penalty', 'penal '])
                    
                    if _es_penalti_real:
                        # HTML real: "Penalti cometido - Dan Burn (Newcastle)"
                        marcador_fmt = f"\x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03-\x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                        if jugador and nombre_equipo:
                            mensaje_evento = f"{liga_formato} \x034⚠️\x03 \x032¡¡PENALTI COMETIDO!!\x03 \x032por\x03 \x02\x0312{jugador}\x03\x02 \x032del\x03 \x02\x034{nombre_equipo}\x03\x02 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03 \x033»\x03 {marcador_fmt}"
                        elif jugador:
                            mensaje_evento = f"{liga_formato} \x034⚠️\x03 \x032¡¡PENALTI COMETIDO!!\x03 \x032por\x03 \x02\x0312{jugador}\x03\x02 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03 \x033»\x03 {marcador_fmt}"
                        else:
                            mensaje_evento = f"{liga_formato} \x034⚠️\x03 \x032¡¡PENALTI COMETIDO!!\x03 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03 \x033»\x03 {marcador_fmt}"
                        mensaje_titulo = None
                        es_evento_importante = True
                        logging.info(f"⚠️ Penalti cometido: jugador={jugador}, equipo={nombre_equipo}, min={minuto}")
                    else:
                        # accion28 sin mención de penalti → saque de centro / reanudación → ignorar
                        logging.info(f"⏭️ accion28 ignorado (no es penalti): {texto[:80]}")
                        mensaje_evento = None
                        mensaje_titulo = None

                # ═══ TANDA DE PENALTIS ═══
                # accion23.png = Gol en tanda de penaltis  (también usado en alineaciones)
                # accion24.png = Fallo en tanda de penaltis (también usado en kickoff)
                # GUARD: solo activar si el texto lo confirma, ya estábamos en tanda,
                # o el minuto supera la prórroga (>120).
                elif 'accion23.png' in icono or 'accion24.png' in icono:
                    _texto_lower_tp = (texto or '').lower()
                    _info_partido = self.partidos_activos.get(partido_id, {})
                    try:
                        _min_num_tp = int(re.sub(r'[^\d]', '', (minuto or '').split('+')[0]) or '0')
                    except:
                        _min_num_tp = 0
                    _es_contexto_tanda = (
                        any(x in _texto_lower_tp for x in [
                            'tanda', 'penalti', 'penalty', 'lanza', 'dispara desde los once',
                            'falla desde el punto', 'transforma desde el punto',
                            'gol en la tanda', 'fallo en la tanda'
                        ])
                        or _info_partido.get('tanda_penaltis_activa', False)
                        or _min_num_tp > 120
                    )
                    if not _es_contexto_tanda:
                        logging.debug(f"⏭️ accion{'23' if 'accion23' in icono else '24'} ignorado (no es tanda): min={minuto} texto={_texto_lower_tp[:60]}")
                        mensaje_evento = None
                        mensaje_titulo = None
                    else:
                        _es_gol_tanda = 'accion23.png' in icono
                        # Inicializar tanda si es el primer evento
                        if not _info_partido.get('tanda_penaltis_activa', False):
                            self.partidos_activos[partido_id]['tanda_penaltis_activa'] = True
                            self.partidos_activos[partido_id]['tanda_local'] = 0
                            self.partidos_activos[partido_id]['tanda_visitante'] = 0
                            self.partidos_activos[partido_id]['parte'] = 'Penaltis'
                            # Anunciar inicio de tanda
                            marcador_fmt = f"\x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03-\x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                            msg_inicio = f"{liga_formato} \x033»\x03 \x034🎯 ¡¡TANDA DE PENALTIS!!\x03 \x033«\x03 {marcador_fmt}"
                            self.bot_callback('message', Config.CANAL_FUTBOL, msg_inicio)
                            canales_ext = [c for c in self.db.get_canales_narracion_activa()
                                           if c.lower() != Config.CANAL_FUTBOL.lower()]
                            for canal in canales_ext:
                                self.bot_callback('message', canal, msg_inicio)
                            logging.info(f"🎯 TANDA DE PENALTIS: {equipo_local} vs {equipo_visitante}")

                        # Actualizar marcador de tanda
                        _es_equipo_local = False
                        if nombre_equipo:
                            _es_equipo_local = self._equipo_es_local(nombre_equipo, equipo_local, equipo_visitante)
                        if _es_gol_tanda and _es_equipo_local:
                            self.partidos_activos[partido_id]['tanda_local'] = _info_partido.get('tanda_local', 0) + 1
                        elif _es_gol_tanda:
                            self.partidos_activos[partido_id]['tanda_visitante'] = _info_partido.get('tanda_visitante', 0) + 1

                        _tl = self.partidos_activos[partido_id].get('tanda_local', 0)
                        _tv = self.partidos_activos[partido_id].get('tanda_visitante', 0)
                        _marcador_tanda = f"(\x0303{_tl}\x03-\x0303{_tv}\x03)"

                        if _es_gol_tanda:
                            if jugador and nombre_equipo:
                                mensaje_evento = f"{liga_formato} \x033✅\x03 \x032Gol en tanda:\x03 \x02\x0312{jugador}\x03\x02 \x032del\x03 \x02\x034{nombre_equipo}\x03\x02 \x033»\x03 \x02\x0312{equipo_local}\x03\x02 {_marcador_tanda} \x02\x0312{equipo_visitante}\x03\x02"
                            elif jugador:
                                mensaje_evento = f"{liga_formato} \x033✅\x03 \x032Gol en tanda:\x03 \x02\x0312{jugador}\x03\x02 \x033»\x03 \x02\x0312{equipo_local}\x03\x02 {_marcador_tanda} \x02\x0312{equipo_visitante}\x03\x02"
                            else:
                                mensaje_evento = f"{liga_formato} \x033✅\x03 \x032Gol en tanda\x03 \x033»\x03 \x02\x0312{equipo_local}\x03\x02 {_marcador_tanda} \x02\x0312{equipo_visitante}\x03\x02"
                        else:
                            if jugador and nombre_equipo:
                                mensaje_evento = f"{liga_formato} \x034❌\x03 \x032Fallo en tanda:\x03 \x02\x0312{jugador}\x03\x02 \x032del\x03 \x02\x034{nombre_equipo}\x03\x02 \x033»\x03 \x02\x0312{equipo_local}\x03\x02 {_marcador_tanda} \x02\x0312{equipo_visitante}\x03\x02"
                            elif jugador:
                                mensaje_evento = f"{liga_formato} \x034❌\x03 \x032Fallo en tanda:\x03 \x02\x0312{jugador}\x03\x02 \x033»\x03 \x02\x0312{equipo_local}\x03\x02 {_marcador_tanda} \x02\x0312{equipo_visitante}\x03\x02"
                            else:
                                mensaje_evento = f"{liga_formato} \x034❌\x03 \x032Fallo en tanda\x03 \x033»\x03 \x02\x0312{equipo_local}\x03\x02 {_marcador_tanda} \x02\x0312{equipo_visitante}\x03\x02"
                        mensaje_titulo = None
                        es_evento_importante = True
                        logging.info(f"🎯 Tanda: {'GOL' if _es_gol_tanda else 'FALLO'} - {jugador} ({nombre_equipo}) → {_tl}-{_tv}")

                # ═══ NO PENALTI (accion36) ═══
                # "No penalti - K. Duah (Ludogorets)" = VAR descarta / árbitro no señala
                elif 'accion36.png' in icono:
                    marcador_fmt = f"\x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03-\x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                    if jugador and nombre_equipo:
                        mensaje_evento = f"{liga_formato} \x036🚫\x03 \x032No es penalti -\x03 \x02\x0312{jugador}\x03\x02 \x032del\x03 \x02\x034{nombre_equipo}\x03\x02 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03 \x033»\x03 {marcador_fmt}"
                    elif jugador:
                        mensaje_evento = f"{liga_formato} \x036🚫\x03 \x032No es penalti -\x03 \x02\x0312{jugador}\x03\x02 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03 \x033»\x03 {marcador_fmt}"
                    else:
                        mensaje_evento = f"{liga_formato} \x036🚫\x03 \x032No es penalti\x03 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03 \x033»\x03 {marcador_fmt}"
                    mensaje_titulo = None
                    es_evento_importante = True
                    logging.info(f"🚫 No penalti: {jugador} ({nombre_equipo}) min={minuto}")

                # Detectar eventos de PRÓRROGA
                elif 'prorroga' in texto.lower() or 'prórroga' in texto.lower() or 'extra time' in texto.lower():
                    texto_lower = texto.lower()
                    if 'inicio' in texto_lower or 'comienza' in texto_lower or 'empieza' in texto_lower:
                        if '2' in texto_lower or 'segunda' in texto_lower:
                            # Empieza 2ª parte de prórroga
                            mensaje_evento = f"{liga_formato} \x033»\x03 \x034E\x032mpieza la 2ª parte de la \x034P\x032rorroga\x03 \x033«\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03 \x03-\x03 \x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                        else:
                            # Empieza prórroga
                            mensaje_evento = f"{liga_formato} \x033»\x03 \x034E\x032mpieza la \x034P\x032rorroga\x03 \x033«\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03 \x03-\x03 \x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                    elif 'descanso' in texto_lower:
                        # Descanso de prórroga
                        mensaje_evento = f"{liga_formato} \x033»\x03 \x034D\x032escanso de la \x034P\x032rorroga\x03 \x033«\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03 \x03-\x03 \x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                    elif 'final' in texto_lower or 'fin' in texto_lower:
                        # Final de prórroga
                        mensaje_evento = f"{liga_formato} \x033»\x03 \x034F\x032inal de la \x034P\x032rorroga\x03 \x033«\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03 \x03-\x03 \x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                    else:
                        # Prórroga genérica
                        mensaje_evento = f"{liga_formato} \x033»\x03 \x034P\x032rorroga\x03 \x033«\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03 \x03-\x03 \x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                    mensaje_titulo = None
                    
                elif 'accion29.png' in icono:  # Silbato de descanso / fin de parte
                    texto_lower_29 = texto.lower()
                    # Helper local para formato final con resultado
                    def _msg_final_resultado():
                        try:
                            gl_n, gv_n = int(goles_local), int(goles_visitante)
                            if gl_n > gv_n:
                                res = f"🏆 \x02\x034¡{equipo_local.upper()} GANA!\x03\x02"
                            elif gv_n > gl_n:
                                res = f"🏆 \x02\x034¡{equipo_visitante.upper()} GANA!\x03\x02"
                            else:
                                res = f"🤝 \x02\x08¡EMPATE!\x03\x02"
                            return (f"{liga_formato} \x033»»\x03 \x034⚽ FINAL\x03 \x033««\x03 "
                                    f"\x02\x0312{equipo_local}\x03\x02 \x034[\x02{goles_local}\x02]\x03 "
                                    f"\x03-\x03 \x034[\x02{goles_visitante}\x02]\x03 "
                                    f"\x02\x0312{equipo_visitante}\x03\x02 \x033»\x03 {res}")
                        except Exception:
                            return EventFormatter.fin_partido(
                                info_partido_liga.get('liga', liga),
                                info_partido_liga.get('color', color_liga),
                                equipo_local, goles_local, goles_visitante, equipo_visitante)

                    if any(x in texto_lower_29 for x in ['primera mitad', 'primer tiempo', 'primera parte', 'al descanso']):
                        info_match = self.partidos_activos.get(partido_id, {})
                        if info_match.get('descanso_anunciado', False):
                            logging.info(f"⏭️ Descanso (accion29) ya anunciado, ignorando")
                            return
                        mensaje_evento = EventFormatter.descanso(
                            info_partido_liga.get('liga', liga),
                            info_partido_liga.get('color', color_liga),
                            equipo_local, goles_local, goles_visitante, equipo_visitante)
                        if partido_id in self.partidos_activos:
                            self.partidos_activos[partido_id]['descanso_anunciado'] = True
                        es_evento_importante = True
                    elif any(x in texto_lower_29 for x in ['segunda parte', 'segunda mitad', 'fin del partido', 'fin del encuentro', 'pita el final']):
                        mensaje_evento = _msg_final_resultado()
                        es_evento_importante = True
                    else:
                        try:
                            min_29 = int(re.sub(r'[^\d]', '', minuto.split('+')[0]) or '0')
                        except Exception:
                            min_29 = 0
                        if min_29 <= 50:
                            info_match = self.partidos_activos.get(partido_id, {})
                            if not info_match.get('descanso_anunciado', False):
                                mensaje_evento = EventFormatter.descanso(
                                    info_partido_liga.get('liga', liga),
                                    info_partido_liga.get('color', color_liga),
                                    equipo_local, goles_local, goles_visitante, equipo_visitante)
                                if partido_id in self.partidos_activos:
                                    self.partidos_activos[partido_id]['descanso_anunciado'] = True
                                es_evento_importante = True
                            else:
                                return
                        else:
                            mensaje_evento = _msg_final_resultado()
                            es_evento_importante = True
                    mensaje_titulo = None
                
                elif ('¡Fin' in texto or 'Fin del' in texto) and not any(x in texto.lower() for x in ['primera mitad', 'primer tiempo', 'primera parte', 'al descanso', 'primera \xbd']):  # Fin del partido (NO descanso)
                    # Determinar ganador o empate
                    try:
                        goles_local_num = int(goles_local)
                        goles_visitante_num = int(goles_visitante)
                        
                        if goles_local_num > goles_visitante_num:
                            # Gana local
                            resultado = f"🏆 \x02\x034¡{equipo_local.upper()} GANA!\x03\x02"
                        elif goles_visitante_num > goles_local_num:
                            # Gana visitante
                            resultado = f"🏆 \x02\x034¡{equipo_visitante.upper()} GANA!\x03\x02"
                        else:
                            # Empate
                            resultado = f"🤝 \x02\x08¡EMPATE!\x03\x02"
                    except:
                        resultado = ""
                    
                    # Mensaje final bonito en una línea
                    if resultado:
                        mensaje_evento = f"{liga_formato} \x033»»\x03 \x034⚽ FINAL\x03 \x033««\x03 \x02\x0312{equipo_local}\x03\x02 \x034[\x02{goles_local}\x02]\x03 \x03-\x03 \x034[\x02{goles_visitante}\x02]\x03 \x02\x0312{equipo_visitante}\x03\x02 \x033»\x03 {resultado}"
                    else:
                        mensaje_evento = f"{liga_formato} \x033»»\x03 \x034⚽ FINAL\x03 \x033««\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03 \x03-\x03 \x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                    mensaje_titulo = None
                    
                elif '¡Descanso' in texto or 'Descanso' in texto or any(x in texto.lower() for x in ['primera mitad', 'primer tiempo']):  # Descanso
                    # Evitar doble anuncio: si ya se anunció desde _buscar_partidos, ignorar
                    info_match = self.partidos_activos.get(partido_id, {})
                    if info_match.get('descanso_anunciado', False):
                        logging.info(f"⏭️ Descanso ya anunciado, ignorando evento de crónica")
                        return
                    mensaje_evento = f"{liga_formato} \x033»\x03 \x034D\x032escanso\x03 \x033«\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03 \x03-\x03 \x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                    mensaje_titulo = None
                
                elif 'Comienza' in texto or 'Empieza' in texto or 'Inicio' in texto:  # Inicio del partido
                    # Evitar doble anuncio: si ya se anunció desde _buscar_partidos, ignorar
                    info_match = self.partidos_activos.get(partido_id, {})
                    if info_match.get('anunciado', False):
                        logging.info(f"⏭️ Inicio ya anunciado, ignorando evento de crónica: {texto[:50]}")
                        return
                    mensaje_evento = f"{liga_formato} \x033»\x03 \x034E\x032mpieza el \x034P\x032artido\x03 \x033«\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03 \x03-\x03 \x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                    mensaje_titulo = None
                
                # Detectar cambios en Primera División (varios formatos de texto)
                elif re.search(r'[Ss]e retira|[Ss]e march|[Ss]e va[ns]?\b|[Ee]ntra .+ por |.+ entra por |cambio en |[Mm]ete .+ a .+ por |salen del campo|dejar sitio|entren al campo|entran en |para dentro', texto, re.IGNORECASE):
                    jugadores_salen = []
                    jugadores_entran = []
                    equipo_cambio = ""
                    
                    # Extraer equipo del texto: "cambio en el Getafe" / "en el Brujas" / "del Levante"
                    # También: "Reacciona el PAOK con un triple cambio"
                    match_equipo = re.search(
                        r'(?:cambio en |marchan en |entran en |en (?:las filas del |el |la )|'
                        r'[Rr]eacciona (?:el |la )?|[Rr]esponde (?:el |la )?)([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s]+?)'
                        r'(?:\.|:|,|\s+con\s|\s+para|\s+y\b)',
                        texto, re.IGNORECASE)
                    if match_equipo:
                        equipo_cambio = match_equipo.group(1).strip()
                    
                    # Patrón 0: "Mete X a Y por Z" o "Mete el técnico a Y por Z"
                    match_mete = re.search(r'[Mm]ete\s+(?:[A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s\-\.]+?\s+)?a\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s\-\.]+?)\s+por\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s\-\.]+?)(?:\.|\s*\'|$)', texto)
                    if match_mete:
                        jugadores_entran.append(match_mete.group(1).strip())
                        jugadores_salen.append(match_mete.group(2).strip())
                        es_evento_importante = True
                    
                    # Patrón N1: "X, Y y Z salen del campo. A, B y C."
                    # Ej: "Matías Moreno, Víctor García y Raghouber salen del campo. Maturro, Etta Eyong y Unai Vencedor."
                    if not jugadores_salen and not jugadores_entran:
                        match_salen_campo = re.search(
                            r'(.+?)\s+salen del campo[.\s]+(.+?)(?:\.|\s*\'|$)', texto, re.IGNORECASE)
                        if match_salen_campo:
                            salen_raw = match_salen_campo.group(1).strip()
                            entran_raw = match_salen_campo.group(2).strip()
                            # Limpiar texto extra del entran ("La entrada del delantero...")
                            entran_raw = re.split(r'\.\s*[A-Z]', entran_raw)[0].strip()
                            jugadores_salen = self._parsear_lista_jugadores(salen_raw)
                            jugadores_entran = self._parsear_lista_jugadores(entran_raw)
                    
                    # Patrón N2: "X y Y se marchan para dejar sitio a A y B"
                    if not jugadores_salen and not jugadores_entran:
                        match_dejar = re.search(
                            r'(.+?)\s+se marchan?\s+(?:.*?para (?:dejar sitio a|que entren?)\s+)(.+?)(?:\.|\s*\'|$)',
                            texto, re.IGNORECASE)
                        if match_dejar:
                            jugadores_salen = self._parsear_lista_jugadores(match_dejar.group(1).strip())
                            jugadores_entran = self._parsear_lista_jugadores(match_dejar.group(2).strip())
                    
                    # Patrón N3: "X y Y entran en el Equipo. Se marchan A y B."
                    if not jugadores_salen and not jugadores_entran:
                        match_entran_se = re.search(
                            r'(.+?)\s+entran?\s+en\s+(?:el\s+)?(?:\w+)[.\s]+[Ss]e marchan?\s+(.+?)(?:\.|\s*\'|$)',
                            texto, re.IGNORECASE)
                        if match_entran_se:
                            jugadores_entran = self._parsear_lista_jugadores(match_entran_se.group(1).strip())
                            jugadores_salen = self._parsear_lista_jugadores(match_entran_se.group(2).strip())
                    
                    # Patrón N4: "X y Y se marchan en el Equipo para que entren al campo A y B"
                    if not jugadores_salen and not jugadores_entran:
                        match_marchan_en = re.search(
                            r'(.+?)\s+se marchan?\s+en\s+(?:el\s+)?\w+\s+para que entren?\s+(?:al campo\s+)?(.+?)(?:\.|\s*\'|$)',
                            texto, re.IGNORECASE)
                        if match_marchan_en:
                            jugadores_salen = self._parsear_lista_jugadores(match_marchan_en.group(1).strip())
                            jugadores_entran = self._parsear_lista_jugadores(match_marchan_en.group(2).strip())
                    
                    # Patrón N5: "Reacciona el PAOK con un triple cambio. Baba, X y Z, para dentro. Se marchan A, B y C."
                    # También cubre: "doble cambio. X e Y, para dentro. Se marcha Z."
                    # Estructura: [texto intro]. [entran], para dentro. Se marchan [salen].
                    if not jugadores_salen and not jugadores_entran:
                        match_para_dentro = re.search(
                            r'(?:doble|triple|cu[aá]druple)?\s*cambio[^.]*\.\s*'
                            r'(.+?),\s*para\s+dentro\.\s*'
                            r'[Ss]e\s+march[aó]n?\s+(.+?)(?:\.|\s*\'|$)',
                            texto, re.IGNORECASE)
                        if match_para_dentro:
                            jugadores_entran = self._parsear_lista_jugadores(match_para_dentro.group(1).strip())
                            jugadores_salen  = self._parsear_lista_jugadores(match_para_dentro.group(2).strip())
                            logging.info(f"✅ Patrón N5 (para dentro/se marchan): entran={jugadores_entran} salen={jugadores_salen}")
                    
                    # Patrón N6: "Se marcha X en el Equipo. [frase intercalada]. Entra Y."
                    # Ej: "Se marcha Román en el Celta. Qué partido se ha marcado. Entra Vecino."
                    # El jugador que sale y el que entra están separados por texto narrativo intermedio.
                    if not jugadores_salen and not jugadores_entran:
                        m_n6_sale = re.search(
                            r'[Ss]e\s+march[aó]\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s\-\.]+?)\s+en\s+(?:el\s+|la\s+)?([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s]+?)\.',
                            texto)
                        m_n6_entra = re.findall(
                            r'[Ee]ntra\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s\-\.]+?)(?:\.|\s*\'|$)',
                            texto)
                        if m_n6_sale and m_n6_entra:
                            jugadores_salen  = [m_n6_sale.group(1).strip()]
                            jugadores_entran = [m_n6_entra[-1].strip()]
                            if not equipo_cambio:
                                equipo_cambio = m_n6_sale.group(2).strip()
                            logging.info(f"✅ Patrón N6 (se marcha...entra separados): sale={jugadores_salen} entra={jugadores_entran}")
                    
                    # Patrón para cambios múltiples: "Se marchan X, Y y Z y entran A, B y C"
                    if not jugadores_salen and not jugadores_entran:
                        match_multiple = re.search(r'[Ss]e (?:marchan|van|retiran) ([^y]+(?:,\s*[^y]+)*)\s+y\s+([^y]+)\s+y\s+entran\s+(.+?)(?:\.|\s*\'|$)', texto)
                        if match_multiple:
                            # Parsear los que salen: "X, Y" + "Z"
                            salen_parte1 = match_multiple.group(1).strip()
                            salen_parte2 = match_multiple.group(2).strip()
                            entran_texto = match_multiple.group(3).strip()
                            
                            # Combinar los que salen
                            for j in salen_parte1.split(','):
                                j = j.strip()
                                if j:
                                    jugadores_salen.append(j)
                            jugadores_salen.append(salen_parte2)
                            
                            # Parsear los que entran: "A, B y C" o "A y B"
                            if ' y ' in entran_texto:
                                partes = entran_texto.rsplit(' y ', 1)
                                for j in partes[0].split(','):
                                    j = j.strip()
                                    if j:
                                        jugadores_entran.append(j)
                                jugadores_entran.append(partes[1].strip().rstrip(".'"))
                            else:
                                jugadores_entran.append(entran_texto.rstrip(".'"))
                        else:
                            # Patrón simple: "Se retira/va X y entra Y"
                            match_retira = re.search(r'[Ss]e (?:retira|marcha|va) ([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s\-\.]+?) y entra (?:en su (?:lugar|puesto) )?(?:(?:el|la) \w+ )?([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s\-\.]+?)(?:\.|\s*\'|$)', texto)
                            if match_retira:
                                jugadores_salen.append(match_retira.group(1).strip())
                                jugadores_entran.append(match_retira.group(2).strip())
                            else:
                                # Patrón: "X se marcha para que entre Y (en el Equipo)"
                                match_marcha_entre = re.search(r'([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s\-\.]+?)\s+se\s+marcha\s+para\s+que\s+entre\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s\-\.]+?)(?:\s+en\s+|\.|\'|$)', texto)
                                if match_marcha_entre:
                                    jugadores_salen.append(match_marcha_entre.group(1).strip())
                                    jugadores_entran.append(match_marcha_entre.group(2).strip())
                                else:
                                    # Patrón: "Entra X por Y"
                                    match_entra = re.search(r'[Ee]ntra (?:(?:el|la) \w+ )?([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s\-\.]+?) por ([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s\-\.]+?)(?:\.|\s*\'|$)', texto)
                                    if match_entra:
                                        jugadores_entran.append(match_entra.group(1).strip())
                                        jugadores_salen.append(match_entra.group(2).strip())
                                    else:
                                        # Patrón: "X entra por Y" (nombre antes de entra)
                                        # Ej: "Cestero entra por Fede Valverde ahora."
                                        match_x_entra = re.search(r'([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s\-\.]+?)\s+entra por\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s\-\.]+?)(?:\s+ahora|\s+en\s|\.|\'|$)', texto)
                                        if match_x_entra:
                                            jugadores_entran.append(match_x_entra.group(1).strip())
                                            jugadores_salen.append(match_x_entra.group(2).strip())
                    
                    # Usar nombre_equipo si no lo extrajimos del texto
                    if not equipo_cambio:
                        equipo_cambio = nombre_equipo
                    
                    # VALIDACIÓN: Verificar que los nombres extraídos parecen reales
                    # Descartar textos narrativos como "el lanzamiento lejano del" o "por su propio pie"
                    _palabras_descarte = [
                        'fuera', 'directamente', 'lanzamiento', 'remate', 'disparo',
                        'balón', 'córner', 'falta', 'tiro', 'centro', 'platea',
                        'grada', 'propio', 'rostro', 'lejano', 'bien', 'mal',
                        'portería', 'cabeza', 'pie', 'área', 'obligado',
                        'el ', 'la ', 'un ', 'una ', 'del ', 'por ', 'que ', 'su ',
                    ]
                    
                    def _nombre_cambio_valido(nombre):
                        """Verifica si un nombre extraído de cambio es válido"""
                        if not nombre or len(nombre.strip()) < 2:
                            return False
                        n_lower = nombre.lower().strip()
                        if any(n_lower.startswith(p) or f' {p}' in f' {n_lower}' for p in _palabras_descarte):
                            return False
                        if not any(c.isupper() for c in nombre):
                            return False
                        if len(nombre.split()) > 5:
                            return False
                        return True
                    
                    # Filtrar nombres inválidos
                    jugadores_salen = [j for j in jugadores_salen if _nombre_cambio_valido(j)]
                    jugadores_entran = [j for j in jugadores_entran if _nombre_cambio_valido(j)]
                    
                    # Si se parsearon jugadores válidos, marcar como evento importante
                    if jugadores_salen or jugadores_entran:
                        es_evento_importante = True
                    
                    # Determinar parte del partido para el formato
                    try:
                        min_num_cambio = int(re.sub(r'[^\d]', '', minuto.split('+')[0]) or '0')
                        if min_num_cambio <= 45:
                            parte_cambio = "1ª"
                        elif min_num_cambio <= 90:
                            parte_cambio = "2ª"
                        elif min_num_cambio <= 105:
                            parte_cambio = "1ª PRO"
                        else:
                            parte_cambio = "2ª PRO"
                    except:
                        parte_cambio = ""
                    parte_cambio_fmt = f" - {parte_cambio} Parte" if parte_cambio else ""
                    
                    # Si no tenemos equipo_cambio, intentar deducir de alineaciones
                    if not equipo_cambio and jugadores_entran:
                        for j in jugadores_entran:
                            for p in reversed(j.split()):
                                if p in alineaciones:
                                    eq = alineaciones[p]
                                    if eq.lower() in equipo_local.lower() or equipo_local.lower() in eq.lower():
                                        equipo_cambio = equipo_local
                                    elif eq.lower() in equipo_visitante.lower() or equipo_visitante.lower() in eq.lower():
                                        equipo_cambio = equipo_visitante
                                    else:
                                        equipo_cambio = eq
                                    break
                            if equipo_cambio:
                                break
                    if not equipo_cambio and jugadores_salen:
                        for j in jugadores_salen:
                            for p in reversed(j.split()):
                                if p in alineaciones:
                                    eq = alineaciones[p]
                                    if eq.lower() in equipo_local.lower() or equipo_local.lower() in eq.lower():
                                        equipo_cambio = equipo_local
                                    elif eq.lower() in equipo_visitante.lower() or equipo_visitante.lower() in eq.lower():
                                        equipo_cambio = equipo_visitante
                                    else:
                                        equipo_cambio = eq
                                    break
                            if equipo_cambio:
                                break
                    
                    # Formatear mensaje UNIFICADO (mismo formato que Segunda División)
                    # Singular/plural según número de jugadores: Sale/Salen, Entra/Entran
                    lbl_sale  = "Salen:" if len(jugadores_salen)  > 1 else "Sale:"
                    lbl_entra = "Entran:" if len(jugadores_entran) > 1 else "Entra:"
                    if jugadores_salen and jugadores_entran:
                        salen_str = ", ".join(jugadores_salen)
                        entran_str = ", ".join(jugadores_entran)
                        if equipo_cambio:
                            mensaje_evento = f"{liga_formato} \x033¡¡¡\x034C\x032ambi\x032o\x033!!!\x03 \x032del:\x03 \x02\x034{equipo_cambio}\x03\x02 \x033»\x03 \x034{lbl_sale}\x03 \x02\x0312{salen_str}\x03\x02 \x033»\x03 \x032{lbl_entra}\x03 \x02\x0312{entran_str}\x03\x02 \x032(Min:\x0312 {minuto}{parte_cambio_fmt}\x032)\x03"
                        else:
                            mensaje_evento = f"{liga_formato} \x033¡¡¡\x034C\x032ambi\x032o\x033!!!\x03 \x033»\x03 \x034{lbl_sale}\x03 \x02\x0312{salen_str}\x03\x02 \x033»\x03 \x032{lbl_entra}\x03 \x02\x0312{entran_str}\x03\x02 \x032(Min:\x0312 {minuto}{parte_cambio_fmt}\x032)\x03"
                    elif jugadores_salen:
                        salen_str = ", ".join(jugadores_salen)
                        if equipo_cambio:
                            mensaje_evento = f"{liga_formato} \x033¡¡¡\x034C\x032ambi\x032o\x033!!!\x03 \x032del:\x03 \x02\x034{equipo_cambio}\x03\x02 \x033»\x03 \x034{lbl_sale}\x03 \x02\x0312{salen_str}\x03\x02 \x032(Min:\x0312 {minuto}{parte_cambio_fmt}\x032)\x03"
                        else:
                            mensaje_evento = f"{liga_formato} \x033¡¡¡\x034C\x032ambi\x032o\x033!!!\x03 \x033»\x03 \x034{lbl_sale}\x03 \x02\x0312{salen_str}\x03\x02 \x032(Min:\x0312 {minuto}{parte_cambio_fmt}\x032)\x03"
                    elif jugadores_entran:
                        entran_str = ", ".join(jugadores_entran)
                        if equipo_cambio:
                            mensaje_evento = f"{liga_formato} \x033¡¡¡\x034C\x032ambi\x032o\x033!!!\x03 \x032del:\x03 \x02\x034{equipo_cambio}\x03\x02 \x033»\x03 \x032{lbl_entra}\x03 \x02\x0312{entran_str}\x03\x02 \x032(Min:\x0312 {minuto}{parte_cambio_fmt}\x032)\x03"
                        else:
                            mensaje_evento = f"{liga_formato} \x033¡¡¡\x034C\x032ambi\x032o\x033!!!\x03 \x033»\x03 \x032{lbl_entra}\x03 \x02\x0312{entran_str}\x03\x02 \x032(Min:\x0312 {minuto}{parte_cambio_fmt}\x032)\x03"
                    else:
                        # Fallback si no pudimos parsear
                        mensaje_titulo = None
                        mensaje_evento = f"{liga_formato} \x0314⚽\x03 {minuto}' \x033»\x03 {texto} \x033»\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03-\x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                    mensaje_titulo = None
                    
                elif _texto_es_gol and not es_gol_icono:  # Gol detectado por texto (icono incorrecto: accion27, accion6, none, etc.)
                    # Extraer goleador y equipo del texto narrativo
                    gol_jugador = jugador or ''
                    gol_equipo = nombre_equipo or ''
                    es_autogol = 'autogol' in texto.lower() or 'propia puerta' in texto.lower() or 'propia meta' in texto.lower() or 'en propia' in texto.lower()
                    
                    # Detectar autogol por "gol-pp" en match-header-resume (ya parseado en goleadores_resumen)
                    
                    # Extraer equipo del texto: "gol del Villarreal", "golazo del Espanyol"
                    if not gol_equipo:
                        m_gol_eq = re.search(r'(?:go+l|go+lazo)\w*\s+(?:del|para)\s+(?:el\s+|la\s+)?([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s]+?)(?:!|[.\s,\']|$)', texto, re.IGNORECASE)
                        if m_gol_eq:
                            eq_txt = m_gol_eq.group(1).strip().rstrip("!.'\" ")
                            for eq in [equipo_local, equipo_visitante]:
                                if eq and (eq_txt.lower() in eq.lower() or eq.lower() in eq_txt.lower()):
                                    gol_equipo = eq
                                    break
                            if not gol_equipo:
                                gol_equipo = eq_txt
                    
                    # Extraer goleador: "Gol de Mikautadze", "Golazo de Pépé"
                    if not gol_jugador:
                        m_gol_jug = re.search(r'(?:go+l|go+lazo)\w*\s+de\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s\.\-]+?)(?:\s+que|\s+tras|\s+para|\s+en|\s+desde|[,\.!]|$)', texto, re.IGNORECASE)
                        if m_gol_jug:
                            gol_jugador = m_gol_jug.group(1).strip().rstrip("!.'\" ")
                    
                    # Si es autogol, buscar "autogol de X"
                    if es_autogol and not gol_jugador:
                        m_auto = re.search(r'autogol\s+de\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s\.\-]+?)(?:\s|[,\.!]|$)', texto, re.IGNORECASE)
                        if m_auto:
                            gol_jugador = m_auto.group(1).strip()
                    
                    # Buscar en match-header-resume para marcador y datos
                    marcador_gol = f"{goles_local} - {goles_visitante}"
                    
                    # Deducir equipo del goleador si falta
                    if gol_jugador and not gol_equipo:
                        for p_jug in reversed(gol_jugador.split()):
                            if p_jug in alineaciones:
                                eq_deducido = alineaciones[p_jug]
                                for eq in [equipo_local, equipo_visitante]:
                                    if eq and (eq_deducido.lower() in eq.lower() or eq.lower() in eq_deducido.lower()):
                                        gol_equipo = eq
                                        break
                                if not gol_equipo:
                                    gol_equipo = eq_deducido
                                break
                    
                    # Si no hay equipo, buscar en texto "del Villarreal", "el primero del Villarreal"
                    if not gol_equipo:
                        for eq in [equipo_local, equipo_visitante]:
                            if eq and eq.lower() in texto.lower():
                                gol_equipo = eq
                                break
                    
                    # Formatear mensaje
                    if es_autogol:
                        if gol_jugador and gol_equipo:
                            mensaje_evento = f"{liga_formato} \x033¡¡¡\x034AUTOGOL\x033!!!\x03 \x032en propia puerta de\x03 \x02\x0312{gol_jugador}\x03\x02 \x032del\x03 \x02\x034{gol_equipo}\x03\x02 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03 \x033»\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03 \x03- \x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                        elif gol_jugador:
                            mensaje_evento = f"{liga_formato} \x033¡¡¡\x034AUTOGOL\x033!!!\x03 \x032en propia puerta de\x03 \x02\x0312{gol_jugador}\x03\x02 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03 \x033»\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03 \x03- \x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                        else:
                            mensaje_evento = f"{liga_formato} \x033¡¡¡\x034AUTOGOL\x033!!!\x03 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03 \x033»\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03 \x03- \x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                    else:
                        if gol_jugador and gol_equipo:
                            mensaje_evento = f"{liga_formato} \x033¡¡¡\x034GOO\x032OO\x034L\x033!!!\x03 \x032del\x03 \x02\x034{gol_equipo}\x03\x02 \x033»\x03 \x032Marcó:\x03 \x02\x0312{gol_jugador}\x03\x02 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03 \x033»\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03 \x03- \x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                        elif gol_equipo:
                            mensaje_evento = f"{liga_formato} \x033¡¡¡\x034GOO\x032OO\x034L\x033!!!\x03 \x032del\x03 \x02\x034{gol_equipo}\x03\x02 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03 \x033»\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03 \x03- \x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                        elif gol_jugador:
                            mensaje_evento = f"{liga_formato} \x033¡¡¡\x034GOO\x032OO\x034L\x033!!!\x03 \x032Marcó:\x03 \x02\x0312{gol_jugador}\x03\x02 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03 \x033»\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03 \x03- \x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                        else:
                            mensaje_evento = f"{liga_formato} \x033¡¡¡\x034GOO\x032OO\x034L\x033!!!\x03 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03 \x033»\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03 \x03- \x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                    mensaje_titulo = None
                    es_evento_importante = True
                    logging.info(f"⚽ Gol detectado por TEXTO (icono={icono}): {gol_jugador} ({gol_equipo}) autogol={es_autogol}")
                
                elif _texto_es_cambio:  # Cambio detectado por texto (icono no estándar)
                    # Intentar parsear como cambio
                    jug_entra = ''
                    jug_sale = ''
                    eq_cambio = ''
                    
                    # Patrón "Entra/Sale - Jugador (Equipo)"
                    m_struct = re.search(r'(?:Entra|Sale)[^-]*-\s*([^(]+)\s*\(([^)]+)\)', texto, re.IGNORECASE)
                    if m_struct:
                        nombre_parsed = m_struct.group(1).strip()
                        eq_cambio = m_struct.group(2).strip()
                        if 'entra' in texto[:20].lower():
                            jug_entra = nombre_parsed
                        else:
                            jug_sale = nombre_parsed
                    
                    # Patrón "X entra por Y"
                    if not jug_entra:
                        m_entra_por = re.search(r"([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s.\-]+?)\s+entra por\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s.\-]+?)[.\s,]", texto)
                        if m_entra_por:
                            jug_entra = m_entra_por.group(1).strip()
                            jug_sale = m_entra_por.group(2).strip()
                    
                    # Patrón "Sale X y entra Y"
                    if not jug_entra:
                        m_sale_entra = re.search(r"(?:Sale|Se retira)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s.\-]+?)\s+y\s+entra\s+(?:en\s+su\s+lugar\s+)?([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s.\-]+?)[.\s,]", texto, re.IGNORECASE)
                        if m_sale_entra:
                            jug_sale = m_sale_entra.group(1).strip()
                            jug_entra = m_sale_entra.group(2).strip()

                    # Patrón "quita a X y entra Y" / "saca a X y mete a Y" (Primera División narrativo)
                    # Ejemplos reales:
                    #   "Último cambio de Arbeloa: quita a Vinicius y entra Álvaro Carreras"
                    #   "saca a Valverde y mete a Bellingham"
                    if not jug_entra:
                        _texto_q = texto
                        # Extraer quién sale: "quita/saca/retira a X" hasta "y" o ","
                        m_sale_q = re.search(
                            r"(?:quita|saca|retira)\s+a\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s.\-]+?)(?=\s+y\s|\s*[,.])",
                            _texto_q, re.IGNORECASE
                        )
                        # Extraer quién entra: después de "entra/mete a/da entrada a"
                        m_entra_q = re.search(
                            r"(?:entra|mete\s+a|da\s+entrada\s+a)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s.\-]+?)(?=[.,!'\s]{2}|$)",
                            _texto_q, re.IGNORECASE
                        )
                        if m_sale_q:
                            jug_sale = m_sale_q.group(1).strip().rstrip('.,! ')
                        if m_entra_q:
                            jug_entra = m_entra_q.group(1).strip().rstrip(".,!' ")
                    
                    # Deducir equipo desde alineaciones si falta
                    if not eq_cambio and (jug_entra or jug_sale):
                        nombre_buscar = jug_entra or jug_sale
                        palabras_j = nombre_buscar.split()
                        if palabras_j:
                            apellido = palabras_j[-1]
                            if apellido in alineaciones:
                                eq_cambio = alineaciones[apellido]
                    
                    # Determinar parte
                    try:
                        min_c = int(re.sub(r'[^\d]', '', minuto.split('+')[0]) or '0')
                    except:
                        min_c = 0
                    if min_c <= 45:
                        parte_c = " - 1ª Parte"
                    elif min_c <= 90:
                        parte_c = " - 2ª Parte"
                    elif min_c <= 105:
                        parte_c = " - 1ª PRO Parte"
                    else:
                        parte_c = " - 2ª PRO Parte"
                    parte_c_fmt = f"'{parte_c}" if parte_c else "'"
                    
                    if jug_sale and jug_entra:
                        if eq_cambio:
                            mensaje_evento = f"{liga_formato} \x033¡¡¡\x034C\x032ambi\x032o\x033!!!\x03 \x032del:\x03 \x02\x034{eq_cambio}\x03\x02 \x033»\x03 \x034Sale:\x03 \x02\x0312{jug_sale}\x03\x02 \x033»\x03 \x032Entra:\x03 \x02\x0312{jug_entra}\x03\x02 \x032(Min:\x0312 {minuto}{parte_c_fmt}\x032)\x03"
                        else:
                            mensaje_evento = f"{liga_formato} \x033¡¡¡\x034C\x032ambi\x032o\x033!!!\x03 \x034Sale:\x03 \x02\x0312{jug_sale}\x03\x02 \x033»\x03 \x032Entra:\x03 \x02\x0312{jug_entra}\x03\x02 \x032(Min:\x0312 {minuto}{parte_c_fmt}\x032)\x03"
                    elif jug_entra:
                        if eq_cambio:
                            mensaje_evento = f"{liga_formato} \x033¡¡¡\x034C\x032ambi\x032o\x033!!!\x03 \x032del:\x03 \x02\x034{eq_cambio}\x03\x02 \x033»\x03 \x032Entra:\x03 \x02\x0312{jug_entra}\x03\x02 \x032(Min:\x0312 {minuto}{parte_c_fmt}\x032)\x03"
                        else:
                            mensaje_evento = f"{liga_formato} \x033¡¡¡\x034C\x032ambi\x032o\x033!!!\x03 \x032Entra:\x03 \x02\x0312{jug_entra}\x03\x02 \x032(Min:\x0312 {minuto}{parte_c_fmt}\x032)\x03"
                    elif jug_sale:
                        if eq_cambio:
                            mensaje_evento = f"{liga_formato} \x033¡¡¡\x034C\x032ambi\x032o\x033!!!\x03 \x032del:\x03 \x02\x034{eq_cambio}\x03\x02 \x033»\x03 \x034Sale:\x03 \x02\x0312{jug_sale}\x03\x02 \x032(Min:\x0312 {minuto}{parte_c_fmt}\x032)\x03"
                        else:
                            mensaje_evento = f"{liga_formato} \x033¡¡¡\x034C\x032ambi\x032o\x033!!!\x03 \x034Sale:\x03 \x02\x0312{jug_sale}\x03\x02 \x032(Min:\x0312 {minuto}{parte_c_fmt}\x032)\x03"
                    else:
                        # No pudimos parsear, evento genérico
                        mensaje_titulo = None
                        mensaje_evento = f"{liga_formato} \x0314⚽\x03 {minuto}' \x033»\x03 {texto} \x033»\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03-\x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                    mensaje_titulo = None
                    es_evento_importante = True
                
                else:  # Otros eventos
                    # FIX: Detectar "empieza el segundo tiempo" y añadir contexto de partido
                    if re.search(r'segundo tiempo|segunda parte|2[ªa]\s*parte', texto, re.IGNORECASE) and re.search(r'empieza|comienza|arranca|reanuda', texto, re.IGNORECASE):
                        mensaje_titulo = None
                        mensaje_evento = f"{liga_formato} \x033»\x03 \x0304E\x0302mpieza la 2ª \x0304P\x0302arte\x03 \x033«\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03-\x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                        es_evento_importante = True
                    # Gol anulado / confirmado con VAR / en revisión
                    # Trigger: menciona "anulado", "no sube al marcador" o "fuera de juego"
                    elif re.search(r'anulad[oa]|no\s+(?:va\s+a\s+)?subi(?:r|rá)\s+al\s+marcador|fuera\s+de\s+juego', texto, re.IGNORECASE):
                        texto_lower_var = texto.lower()
                        _es_anulado    = bool(re.search(r'anulad[oa]|no\s+(?:va\s+a\s+)?subi(?:r|rá)\s+al\s+marcador', texto, re.IGNORECASE))
                        _es_confirmado = bool(re.search(r'¡vale!|gol\s+v[aá]lido|var\s+confirm|se\s+mantiene\s+el\s+gol|sube\s+al\s+marcador', texto, re.IGNORECASE))
                        _en_revision   = bool(re.search(r'revis[aá]ndo|se\s+est[aá]\s+revis', texto, re.IGNORECASE))

                        # ── CASO 1: Gol confirmado tras revisión VAR ─────────────────────
                        # "¡Gooooool del PAOK! ... ¡Se está revisando! ... ¡Vale! ¡PAOK 1-2 Celta!"
                        if _es_confirmado and not _es_anulado:
                            # Extraer equipo goleador
                            _eq_gol = ''
                            m_eq_var = re.search(r'go+l\w*\s+del?\s+(?:el\s+|la\s+)?([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s]+?)(?:!|[.,\s])', texto, re.IGNORECASE)
                            if m_eq_var:
                                eq_txt = m_eq_var.group(1).strip().rstrip("!., ")
                                for eq in [equipo_local, equipo_visitante]:
                                    if eq and (eq_txt.lower() in eq.lower() or eq.lower() in eq_txt.lower()):
                                        _eq_gol = eq
                                        break
                                if not _eq_gol:
                                    _eq_gol = eq_txt
                            # Extraer goleador: exclamación tras el gol ("¡Jeremejeeeeeeeff!")
                            _jug_gol = ''
                            m_jug_var = re.search(r'go+l\w*[^!]*!\s*¡([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑE-e]+)', texto, re.IGNORECASE)
                            if m_jug_var:
                                _jug_gol = re.sub(r'(.)\1{2,}', r'\1', m_jug_var.group(1)).strip()
                            # Formatear: mismo estilo que un gol normal
                            if _eq_gol and _jug_gol:
                                mensaje_evento = f"{liga_formato} \x033¡¡¡\x034GOO\x032OO\x034L\x033!!!\x03 \x032del\x03 \x02\x034{_eq_gol}\x03\x02 \x033»\x03 \x032Marcó:\x03 \x02\x0312{_jug_gol}\x03\x02 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03 \x033»\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03 \x03- \x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02 \x034📺 VAR: ¡Confirmado!\x03"
                            elif _eq_gol:
                                mensaje_evento = f"{liga_formato} \x033¡¡¡\x034GOO\x032OO\x034L\x033!!!\x03 \x032del\x03 \x02\x034{_eq_gol}\x03\x02 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03 \x033»\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03 \x03- \x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02 \x034📺 VAR: ¡Confirmado!\x03"
                            else:
                                mensaje_evento = f"{liga_formato} \x033¡¡¡\x034GOO\x032OO\x034L\x033!!!\x03 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03 \x033»\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03 \x03- \x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02 \x034📺 VAR: ¡Confirmado!\x03"
                            mensaje_titulo = None
                            es_evento_importante = True
                            logging.info(f"✅ Gol confirmado VAR: equipo={_eq_gol} jugador={_jug_gol}")

                        # ── CASO 2: Gol anulado ──────────────────────────────────────────
                        # "¡Gooool... anulado a Celta! ¡Fuera de juego de Jutglà!"
                        elif _es_anulado:
                            gol_anulado_equipo = ''
                            m_anulado = re.search(r'anulad[oa]\s+(?:a(?:l)?|para)\s+(?:el\s+|la\s+)?([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s]+?)(?:!|[.,\s]|$)', texto, re.IGNORECASE)
                            if m_anulado:
                                eq_txt = m_anulado.group(1).strip().rstrip("!., ")
                                for eq in [equipo_local, equipo_visitante]:
                                    if eq and (eq_txt.lower() in eq.lower() or eq.lower() in eq_txt.lower()):
                                        gol_anulado_equipo = eq
                                        break
                                if not gol_anulado_equipo:
                                    gol_anulado_equipo = eq_txt
                            if not gol_anulado_equipo:
                                for eq in [equipo_local, equipo_visitante]:
                                    if eq and eq.lower() in texto_lower_var:
                                        gol_anulado_equipo = eq
                                        break
                            gol_anulado_jugador = ''
                            m_jugador_anulado = re.search(r'(?:fuera\s+de\s+juego|offside)(?:\s+\w+){0,3}?\s+de\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÀ-ÖØ-öø-ÿ\s\.\-]+?)(?:!|[.,\s]|$)', texto, re.IGNORECASE)
                            if m_jugador_anulado:
                                gol_anulado_jugador = m_jugador_anulado.group(1).strip().rstrip("!., ")
                            if gol_anulado_equipo and gol_anulado_jugador:
                                mensaje_evento = f"{liga_formato} \x033»\x03 \x034⚑ GOL ANULADO\x03 \x032a\x03 \x02\x034{gol_anulado_equipo}\x03\x02 \x033»\x03 \x032Fuera de juego de\x03 \x02\x0312{gol_anulado_jugador}\x03\x02 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03 \x033»\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03-\x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                            elif gol_anulado_equipo:
                                mensaje_evento = f"{liga_formato} \x033»\x03 \x034⚑ GOL ANULADO\x03 \x032a\x03 \x02\x034{gol_anulado_equipo}\x03\x02 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03 \x033»\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03-\x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                            else:
                                mensaje_evento = f"{liga_formato} \x033»\x03 \x034⚑ GOL ANULADO\x03 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03 \x033»\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03-\x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                            mensaje_titulo = None
                            es_evento_importante = True
                            logging.info(f"⚑ Gol anulado: equipo={gol_anulado_equipo} jugador={gol_anulado_jugador}")

                        # ── CASO 3: Revisión VAR en curso (aún sin resultado) ─────────────
                        # "¡Se está revisando por posible fuera de juego!"
                        else:
                            _eq_rev = next((eq for eq in [equipo_local, equipo_visitante] if eq and eq.lower() in texto_lower_var), '')
                            # FIX Bug 35: Siempre incluir equipos en mensaje VAR
                            marcador_fmt_var = f"\x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03-\x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                            mensaje_evento = f"{liga_formato} \x033»\x03 \x034📺 VAR en curso\x03 \x033«\x03 \x032Revisión de posible fuera de juego\x03 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03 \x033»\x03 {marcador_fmt_var}"
                            mensaje_titulo = None
                            es_evento_importante = True
                            logging.info(f"📺 VAR en curso (fuera de juego): {equipo_local} vs {equipo_visitante}")
                    # FIX: Detectar goles narrativos sin icono de gol ("¡Gol del Brujas!")
                    # GUARD: el texto "gol de falta/cabeza/penalti/disparo..." NO es un gol narrativo;
                    # son descripciones del tipo de acción. Filtrar antes de evaluar.
                    elif re.search(r'go+l(?:azo)?\s+(?:del?|para)\s+', texto, re.IGNORECASE) and not es_gol_icono:
                        # Palabras que indican que "gol de X" describe una acción, NO un equipo goleador
                        _palabras_accion_gol = [
                            'falta', 'cabeza', 'penalti', 'penalty', 'disparo', 'tiro',
                            'córner', 'corner', 'rechace', 'vaselina', 'chilena', 'volea',
                            'espuela', 'autopase', 'exterior', 'interior', 'zurda', 'diestra',
                        ]
                        _texto_lower_narr = texto.lower()
                        _es_accion_no_gol = any(
                            re.search(r'go+l(?:azo)?\s+de\s+' + p, _texto_lower_narr)
                            for p in _palabras_accion_gol
                        )
                        m_gol_narr = re.search(r'go+l(?:azo)?\s+(?:del?|para)\s+(?:el\s+|la\s+)?([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s]+?)(?:!|[.\s,\']|$)', texto, re.IGNORECASE)
                        gol_eq = ''
                        if not _es_accion_no_gol and m_gol_narr:
                            eq_txt = m_gol_narr.group(1).strip().rstrip("!.'\" ")
                            # GUARD: solo aceptar si coincide con uno de los dos equipos del partido
                            for eq in [equipo_local, equipo_visitante]:
                                if eq and (eq_txt.lower() in eq.lower() or eq.lower() in eq_txt.lower()):
                                    gol_eq = eq
                                    break
                            # Si no coincide con ningún equipo, no es un gol narrativo válido
                            if not gol_eq:
                                logging.info(f"⏭️ Gol narrativo descartado: '{eq_txt}' no es equipo del partido (texto: {texto[:60]})")
                        if gol_eq:
                            mensaje_titulo = None
                            mensaje_evento = f"{liga_formato} \x033¡¡¡\x034GOO\x032OO\x034L\x033!!!\x03 \x032del\x03 \x02\x034{gol_eq}\x03\x02 \x032(Min:\x0312 {minuto}{parte_formato}\x032)\x03 \x033»\x03 \x02\x0312{equipo_local}\x03\x02 \x0304{goles_local}\x03 \x03- \x0304{goles_visitante}\x03 \x02\x0312{equipo_visitante}\x03\x02"
                            es_evento_importante = True
                        else:
                            mensaje_titulo = None
                            mensaje_evento = None  # Silenciar: no es gol real, no aporta info al canal
                    else:
                        # Detectar si el texto es SOLO un marcador suelto tipo "PAOK 1-3 Celta"
                        # Esto ocurre cuando la web emite un evento none.png con el marcador actualizado.
                        # No tiene sentido mostrarlo en el canal — la info ya está en el mensaje del gol.
                        _es_solo_marcador = bool(re.match(
                            r'^[A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s\.\-]+\s+\d+\s*[–\-]\s*\d+\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s\.\-]+$',
                            texto.strip()))
                        if _es_solo_marcador:
                            logging.debug(f"⏭️ Marcador suelto ignorado: '{texto.strip()}'")
                            mensaje_evento = None
                            mensaje_titulo = None
                        else:
                            # Evento none.png (narración pura sin acción relevante): silenciar
                            # Solo se envían al canal eventos con icono reconocido (goles, tarjetas,
                            # cambios, VAR, penaltis…). Los textos narrativos sin icono no aportan
                            # valor y generan ruido / mensajes cortados.
                            mensaje_evento = None
                            mensaje_titulo = None
                
                # Enviar a canales apropiados (solo si hay mensaje)
                if mensaje_evento is None:
                    # Evento pendiente (ej: Sale esperando Entra), no enviar nada
                    pass
                # ═══════════════════════════════════════════════════════════
                # DISTRIBUCIÓN DE MENSAJES
                # ───────────────────────────────────────────────────────────
                # #mis_vips (canal interno): recibe TODO sin excepción
                # Canales externos (registrados): solo eventos importantes
                #   Importantes: goles, tarjetas, cambios, VAR, lesiones,
                #                penaltis, descanso, inicio/fin de partido
                # ═══════════════════════════════════════════════════════════
                if mensaje_evento is None:
                    # Evento pendiente (ej: Sale esperando Entra), no enviar nada
                    pass
                else:
                    # 1) SIEMPRE enviar al canal interno #mis_vips
                    if mensaje_titulo:
                        self.bot_callback('message', Config.CANAL_FUTBOL, mensaje_titulo)
                    self.bot_callback('message', Config.CANAL_FUTBOL, mensaje_evento)

                    # 2) Canales EXTERNOS: solo si el evento es importante
                    if es_evento_importante:
                        canales_externos = [c for c in self.db.get_canales_narracion_activa()
                                            if c.lower() != Config.CANAL_FUTBOL.lower()]
                        for canal in canales_externos:
                            if mensaje_titulo:
                                self.bot_callback('message', canal, mensaje_titulo)
                            self.bot_callback('message', canal, mensaje_evento)
                        if canales_externos:
                            self._debug(f"⚽ Evento importante enviado a {len(canales_externos)} canal(es) externo(s)", importante=True)

                    # 3) AUTO-ELIMINAR partido del filtro cuando finaliza
                    if es_evento_importante and 'Fin' in texto and filtro_id and filtro_id > 0 \
                            and not any(x in texto.lower() for x in ['primera mitad', 'primer tiempo', 'primera parte', 'al descanso']):
                        if self.db.del_partido_filtro_por_id(filtro_id):
                            self._debug(f"🗑️ Auto-eliminado del filtro: {equipo_local} vs {equipo_visitante}")
                        if partido_id in self.partidos_activos:
                            del self.partidos_activos[partido_id]
            else:
                logging.debug(f"  ✓ Sin cambios desde la última revisión")
        
            # ── DESCANSO DIFERIDO: anunciar DESPUÉS de procesar eventos ──────────────
            # _buscar_partidos() detecta el cambio de parte a 'Descanso' y guarda el
            # mensaje en 'descanso_pendiente'. Lo publicamos aquí, cuando ya hemos
            # procesado todos los eventos de la crónica (goles del 43'-45'+),
            # garantizando que el orden en el canal siempre sea: Gol → Descanso.
            descanso_pendiente = self.partidos_activos.get(partido_id, {}).get('descanso_pendiente')
            if descanso_pendiente and not self.partidos_activos.get(partido_id, {}).get('descanso_anunciado', False):
                self._encolar_narracion(partido_id, descanso_pendiente, es_importante=True)
                self.partidos_activos[partido_id]['descanso_anunciado'] = True
                del self.partidos_activos[partido_id]['descanso_pendiente']
                logging.info(f"⏸️ Descanso anunciado (diferido, post-eventos): {partido_id}")

            # ── ASISTENCIA PAREADA: verificar eventos[1] ─────────────────────────────
            # El gol es siempre eventos[0] y la asistencia eventos[1]. Como el bot
            # solo monitoriza eventos[0], la asistencia nunca se detecta como nuevo
            # evento. Aquí la procesamos con un hash independiente en memoria.
            if len(eventos) >= 2:
                try:
                    ev1          = eventos[1]
                    ev1_icono    = ev1.get('icono', '')
                    ev1_minuto   = ev1.get('minuto', '')
                    ev1_texto    = ev1.get('texto', '')
                    ev1_jugador  = ev1.get('jugador', '')
                    ev1_equipo   = ev1.get('equipo_nombre', ev1.get('equipo', ''))

                    # FIX Bug 2: traducir 'local'/'visitante' al nombre real del equipo
                    if ev1_equipo == 'local':
                        ev1_equipo = equipo_local
                    elif ev1_equipo == 'visitante':
                        ev1_equipo = equipo_visitante

                    if 'accion22.png' in ev1_icono:
                        # Hash con jugador (estable) en vez de texto (variable entre scrapeos)
                        ev1_hash = self._evento_hash(ev1_minuto, ev1_jugador or ev1_texto[:30], ev1_icono, 'asistencia')
                        ultimo_asist_hash = self.partidos_activos.get(partido_id, {}).get('ultimo_asistencia_hash')

                        if ev1_hash != ultimo_asist_hash:
                            filtro_asist = self.db.partido_en_filtro(equipo_local, equipo_visitante)
                            if filtro_asist is not None:
                                try:
                                    mn = int(re.sub(r'[^\d]', '', ev1_minuto.split('+')[0]) or '0')
                                    parte_asist = '1ª' if mn <= 45 else ('2ª' if mn <= 90 else ('1ª PRO' if mn <= 105 else '2ª PRO'))
                                except:
                                    parte_asist = ''
                                parte_fmt_asist = f" - \x0312{parte_asist} Parte" if parte_asist else ""

                                color_asist  = self.partidos_activos.get(partido_id, {}).get('color', '14')
                                liga_asist   = self.partidos_activos.get(partido_id, {}).get('liga', liga)
                                liga_fmt_asist = f"\x03{color_asist}«{liga_asist}»\x03" if liga_asist else ""

                                if ev1_jugador and ev1_equipo:
                                    msg_asist = f"{liga_fmt_asist} \x033»\x03 \x032Asistencia de\x03 \x02\x0312{ev1_jugador}\x03\x02 \x032del\x03 \x02\x034{ev1_equipo}\x03\x02 \x032(Min:\x0312 {ev1_minuto}{parte_fmt_asist}\x032)\x03"
                                elif ev1_jugador:
                                    msg_asist = f"{liga_fmt_asist} \x033»\x03 \x032Asistencia de\x03 \x02\x0312{ev1_jugador}\x03\x02 \x032(Min:\x0312 {ev1_minuto}{parte_fmt_asist}\x032)\x03"
                                else:
                                    msg_asist = f"{liga_fmt_asist} \x033»\x03 \x032Asistencia\x03 \x032(Min:\x0312 {ev1_minuto}{parte_fmt_asist}\x032)\x03"

                                self.bot_callback('message', Config.CANAL_FUTBOL, msg_asist)
                                canales_ext_asist = [c for c in self.db.get_canales_narracion_activa()
                                                     if c.lower() != Config.CANAL_FUTBOL.lower()]
                                for canal in canales_ext_asist:
                                    self.bot_callback('message', canal, msg_asist)

                            if partido_id in self.partidos_activos:
                                self.partidos_activos[partido_id]['ultimo_asistencia_hash'] = ev1_hash
                            logging.info(f"🤝 Asistencia pareada: {ev1_jugador} [{ev1_minuto}']")
                except Exception as e_asist:
                    logging.warning(f"Error procesando asistencia pareada: {e_asist}")

        except Exception as e:
            logging.error(f"Error revisando partido {partido_id}: {e}", exc_info=True)
    
    def _extraer_marcador(self, soup):
        """Extrae el marcador del partido de resultados-futbol.com
        
        Estructura HTML conocida:
        <div class="resultado resultadoH">
            <span class="marker_box" data-mid1="...">1</span>-
            <span class="marker_box" data-mid2="...">0</span>
        </div>
        """
        try:
            # Método principal: spans con data-mid1/data-mid2 (marker_box)
            span_local = soup.find('span', attrs={'data-mid1': True})
            span_visitante = soup.find('span', attrs={'data-mid2': True})
            
            if span_local and span_visitante:
                gl = span_local.get_text(strip=True)
                gv = span_visitante.get_text(strip=True)
                if gl.isdigit() and gv.isdigit():
                    return f"{gl} - {gv}"
            
            # Fallback: div.resultado con patrón "N-N"
            resultado_div = soup.find('div', class_=re.compile(r'resultado', re.I))
            if resultado_div:
                match = re.search(r'(\d+)\s*-\s*(\d+)', resultado_div.get_text())
                if match:
                    return f"{match.group(1)} - {match.group(2)}"
            
            # Último recurso: clases comunes de marcador
            for clase in ['score', 'marcador', 'final-score', 'match-score']:
                tag = soup.find(['div', 'span'], class_=re.compile(clase, re.I))
                if tag:
                    match = re.search(r'(\d+)\s*-\s*(\d+)', tag.get_text())
                    if match:
                        return f"{match.group(1)} - {match.group(2)}"
            
            return "0 - 0"
        except Exception as e:
            logging.error(f"Error extrayendo marcador: {e}")
            return "0 - 0"
    
    def _registrar_jugador(self, alineaciones, nombre, equipo):
        """Helper: registra un jugador en el diccionario de alineaciones por nombre completo y apellido"""
        if not nombre or len(nombre) < 3:
            return
        nombre = nombre.strip()
        alineaciones[nombre] = equipo
        palabras = nombre.split()
        if palabras:
            alineaciones[palabras[-1]] = equipo

    def _extraer_alineaciones(self, soup, equipo_local, equipo_visitante):
        """Extrae las alineaciones de los equipos del HTML.
        Retorna dict {jugador_o_apellido: equipo}.
        
        Fuentes (por prioridad):
        1. match-header-resume (goleadores → equipo seguro por posición izq/der)
        2. table-cronica: texto "sale con" (alineación inicial)
        3. table-cronica: formato estructurado "Acción - Jugador (Equipo)"
        4. Divs de alineación del HTML (si existen)
        """
        alineaciones = {}
        
        try:
            # === FUENTE 1: match-header-resume (más confiable: posición izq=local, der=visitante) ===
            # HTML: <div class="match-header-resume"><table><tr>
            #   <td class="mhr-name">Jugador Local</td> ... <td class="mhr-name">Jugador Visit</td>
            # </tr></table></div>
            tabla_resumen = soup.find('div', class_='match-header-resume')
            if tabla_resumen:
                for fila in tabla_resumen.find_all('tr'):
                    celdas = fila.find_all('td')
                    if len(celdas) >= 7:
                        # Estructura: [nombre_local, min_local, ico_local, marcador, ico_visit, min_visit, nombre_visit]
                        nombre_local = celdas[0].get_text(strip=True)
                        nombre_visit = celdas[6].get_text(strip=True)
                        
                        if nombre_local:
                            self._registrar_jugador(alineaciones, nombre_local, equipo_local)
                        if nombre_visit:
                            self._registrar_jugador(alineaciones, nombre_visit, equipo_visitante)
            
            # === FUENTE 2 y 3: table-cronica ===
            tabla_cronica = soup.find('table', class_='table-cronica')
            alineaciones_sin_equipo = []  # Guardar alineaciones que no pudimos identificar
            
            if tabla_cronica:
                for fila in tabla_cronica.find_all('tr', class_=re.compile(r'post.*cronica')):
                    content_div = fila.find('div', class_='cronica_content')
                    if not content_div:
                        continue
                    inner_div = content_div.find('div')
                    if not inner_div:
                        continue
                    
                    texto = inner_div.get_text(strip=True)
                    
                    # FUENTE 2: Texto "sale con" o "se la juega con" (alineación inicial)
                    if any(patron in texto.lower() for patron in ["sale con", "saldrá con", "saldra con", "forma con", "se la juega con", "inicia con", "iniciará con", "alineará con", "alinea con", "saldrá de inicio con", "salta con", "saltará con", "arranca con", "arrancará con", "juega con", "jugará con"]):
                        # Detectar equipo mencionado explícitamente
                        equipo = None
                        for eq in [equipo_local, equipo_visitante]:
                            if eq and (eq in texto or f"El {eq}" in texto or f"La {eq}" in texto or f"el {eq}" in texto or f"la {eq}" in texto):
                                equipo = eq
                                break
                        
                        # Extraer lista de jugadores
                        match = re.search(r'(?:sale|saldr[aá]|forma|se la juega|inicia|iniciar[aá]|alinear[aá]|alinea|salta|saltar[aá]|arranca|arrancar[aá]|juega|jugar[aá]) (?:de inicio )?con[:\s]+(.+)', texto, re.IGNORECASE)
                        if match:
                            jugadores_texto = match.group(1)
                            lista_jugadores = []
                            for jugador_raw in re.split(r'[;,]', jugadores_texto):
                                jug = re.sub(r'\s+(en portería|bajo palos|y)\s*$', '', jugador_raw.strip())
                                jug = re.sub(r'^\s*y\s+', '', jug).strip().rstrip('.\'\"')
                                if jug and len(jug) > 2:
                                    lista_jugadores.append(jug)
                            
                            if equipo:
                                # Registrar directamente si conocemos el equipo
                                for jug in lista_jugadores:
                                    self._registrar_jugador(alineaciones, jug, equipo)
                            elif lista_jugadores:
                                # Guardar para asignar después
                                alineaciones_sin_equipo.append(lista_jugadores)
                    
                    # FUENTE 2b: "¡Hay once del EQUIPO!" / "Once del EQUIPO:" (Primera División)
                    # Ejemplos reales:
                    #   "¡Hay once del Madrid! Estos son los elegidos por Arbeloa: Lunin; Dani Carvajal..."
                    #   "¡Hay once del Atlético de Madrid! ... este es su equipo: Musso; Marcos Llorente..."
                    elif re.search(r'(?:hay once|once (?:del?|de la|final))', texto.lower()):
                        equipo_once = None
                        m_once = re.search(r'(?:hay once|once) del?\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s]+?)(?:!|[.,:])', texto, re.IGNORECASE)
                        if m_once:
                            equipo_texto = m_once.group(1).strip()
                            for eq in [equipo_local, equipo_visitante]:
                                if eq and (equipo_texto.lower() in eq.lower() or eq.lower() in equipo_texto.lower()):
                                    equipo_once = eq
                                    break
                        if equipo_once:
                            # La lista de jugadores viene tras el último ":" del texto
                            colon_pos = texto.rfind(':')
                            if colon_pos > 0:
                                lista_texto = texto[colon_pos + 1:]
                                for jugador_raw in re.split(r'[;,]', lista_texto):
                                    for j in re.split(r'\s+y\s+', jugador_raw.strip()):
                                        j = j.strip().rstrip('.\'"')
                                        if j and len(j) > 2 and any(c.isupper() for c in j):
                                            self._registrar_jugador(alineaciones, j, equipo_once)
                                logging.info(f"✅ Fuente 2b ¡Hay once!: {equipo_once} → {list(alineaciones.keys())[-5:]}")
                    
                    # FUENTE 2c: "El XI del EQUIPO:" / "XI del EQUIPO:" (formato resultados-futbol.com)
                    # Ejemplos reales:
                    #   "El XI del Real Betis: Pau López; Aitor Ruibal, ..."
                    #   "El XI del Sporting de Braga: Horníceck; Víctor Gómez, ..."
                    elif re.search(r'\bXI\b', texto, re.IGNORECASE):
                        m_xi = re.search(r'\bXI\s+del?\s+([A-ZÁÉÍÓÚÑ][^:]{2,40}?):\s+(.+)', texto, re.IGNORECASE)
                        if m_xi:
                            equipo_texto_xi = m_xi.group(1).strip().rstrip("'\".,")
                            lista_texto_xi  = m_xi.group(2)
                            # Normalizar nombre de equipo
                            equipo_xi = None
                            for eq in [equipo_local, equipo_visitante]:
                                if eq and (equipo_texto_xi.lower() in eq.lower() or eq.lower() in equipo_texto_xi.lower()):
                                    equipo_xi = eq
                                    break
                            if equipo_xi:
                                for jugador_raw in re.split(r'[;,]', lista_texto_xi):
                                    for j in re.split(r'\s+y\s+', jugador_raw.strip()):
                                        j = j.strip().rstrip(".'\"")
                                        if j and len(j) > 2 and any(c.isupper() for c in j):
                                            self._registrar_jugador(alineaciones, j, equipo_xi)
                                logging.info(f"✅ Fuente 2c XI del: {equipo_xi} → {[k for k in alineaciones if alineaciones[k]==equipo_xi][-5:]}")
            
            # FIX: Asignar equipos a alineaciones pendientes por orden
            # Normalmente: primera alineación = visitante, segunda = local (orden cronológico inverso)
            # Pero esto puede variar, así que usamos heurística simple
            if alineaciones_sin_equipo:
                if len(alineaciones_sin_equipo) == 2:
                    # Dos alineaciones: asignar visitante y local
                    for jug in alineaciones_sin_equipo[0]:
                        self._registrar_jugador(alineaciones, jug, equipo_visitante)
                    for jug in alineaciones_sin_equipo[1]:
                        self._registrar_jugador(alineaciones, jug, equipo_local)
                    logging.info(f"✅ Asignadas 2 alineaciones por orden: [0]→{equipo_visitante}, [1]→{equipo_local}")
                elif len(alineaciones_sin_equipo) == 1:
                    # Una sola alineación: asumir que es del local (más común)
                    for jug in alineaciones_sin_equipo[0]:
                        self._registrar_jugador(alineaciones, jug, equipo_local)
                    logging.info(f"✅ Asignada 1 alineación al equipo local: {equipo_local}")
            
            # Continuar con FUENTE 3 dentro del mismo bucle de tabla_cronica
            if tabla_cronica:
                for fila in tabla_cronica.find_all('tr', class_=re.compile(r'post.*cronica')):
                    content_div = fila.find('div', class_='cronica_content')
                    if not content_div:
                        continue
                    inner_div = content_div.find('div')
                    if not inner_div:
                        continue
                    texto = inner_div.get_text(strip=True)
                    
                    # FUENTE 3: Formato estructurado "Acción - Jugador (Equipo)"
                    match_struct = re.search(r'^[^-]+-\s*([^(]+)\s*\(([^)]+)\)', texto)
                    if match_struct:
                        jug = match_struct.group(1).strip()
                        eq_texto = match_struct.group(2).strip()
                        if jug and eq_texto and len(jug) > 2:
                            # Normalizar nombre de equipo
                            equipo_real = eq_texto
                            for eq in [equipo_local, equipo_visitante]:
                                if eq and (eq_texto.lower() in eq.lower() or eq.lower() in eq_texto.lower()):
                                    equipo_real = eq
                                    break
                            self._registrar_jugador(alineaciones, jug, equipo_real)
            
            # === FUENTE 5: Cambios narrativos en crónica ===
            # Patrones: "X entra por Y", "X entra en lugar de Y", "entra X por Y"
            # Si Y está en alineaciones, X hereda su equipo
            if tabla_cronica:
                for fila in tabla_cronica.find_all('tr', class_=re.compile(r'post.*cronica')):
                    content_div = fila.find('div', class_='cronica_content')
                    if not content_div:
                        continue
                    inner_div = content_div.find('div')
                    if not inner_div:
                        continue
                    texto_cr = inner_div.get_text(strip=True)
                    
                    # Patrón A: "X entra por Y"
                    m_entra = re.search(r"([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s.\-]+?)\s+entra\s+(?:por|en (?:lugar|el lugar) de)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s.\-]+?)[.\s,]", texto_cr)
                    if m_entra:
                        jug_in = m_entra.group(1).strip()
                        jug_out = m_entra.group(2).strip()
                        # Buscar equipo del que sale
                        for p_out in reversed(jug_out.split()):
                            if p_out in alineaciones:
                                self._registrar_jugador(alineaciones, jug_in, alineaciones[p_out])
                                break
                    
                    # Patrón B: "Sale X y entra Y" / "Se retira X y entra Y"
                    m_sale = re.search(r"(?:Sale|Se retira|Se va)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s.\-]+?)\s+y\s+entra\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s.\-]+?)[.\s,]", texto_cr, re.IGNORECASE)
                    if m_sale:
                        jug_out = m_sale.group(1).strip()
                        jug_in = m_sale.group(2).strip()
                        for p_out in reversed(jug_out.split()):
                            if p_out in alineaciones:
                                self._registrar_jugador(alineaciones, jug_in, alineaciones[p_out])
                                break
                    
                    # Patrón C: "Cambio en el Equipo: entra X por Y" / "Cambio del Equipo"
                    m_cambio_eq = re.search(r'[Cc]ambio\s+(?:en el|del?)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s]+?)[\.:,]', texto_cr)
                    if m_cambio_eq:
                        eq_cambio_txt = m_cambio_eq.group(1).strip()
                        equipo_cambio = None
                        for eq in [equipo_local, equipo_visitante]:
                            if eq and (eq_cambio_txt.lower() in eq.lower() or eq.lower() in eq_cambio_txt.lower()):
                                equipo_cambio = eq
                                break
                        if equipo_cambio:
                            # Buscar jugadores mencionados después
                            for m_jug in re.finditer(r'([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)?)', texto_cr[m_cambio_eq.end():]):
                                self._registrar_jugador(alineaciones, m_jug.group(1).strip(), equipo_cambio)
                    
                    # Patrón D: "X entra en el EQUIPO" (nuevo)
                    m_entra_equipo = re.search(r"([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s.\-]+?)\s+entra\s+en\s+(?:el\s+)?([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s]+?)[\.,]", texto_cr)
                    if m_entra_equipo:
                        jug_in = m_entra_equipo.group(1).strip()
                        eq_texto = m_entra_equipo.group(2).strip()
                        # Normalizar equipo
                        for eq in [equipo_local, equipo_visitante]:
                            if eq and (eq_texto.lower() in eq.lower() or eq.lower() in eq_texto.lower()):
                                self._registrar_jugador(alineaciones, jug_in, eq)
                                break
                    
                    # Patrón E: "X en detrimento de Y" (nuevo)
                    m_detrimento = re.search(r"([A-ZÁÉÍÓÚÑÜÖ][a-záéíóúñüöä\s.\-]+?)\s+en\s+detrimento\s+de\s+([A-ZÁÉÍÓÚÑÜÖÄ][a-záéíóúñüöä\s.\-]+?)[.\s]", texto_cr)
                    if m_detrimento:
                        jug_in = m_detrimento.group(1).strip()
                        jug_out = m_detrimento.group(2).strip()
                        # Buscar equipo del que sale
                        for p_out in reversed(jug_out.split()):
                            if p_out in alineaciones:
                                self._registrar_jugador(alineaciones, jug_in, alineaciones[p_out])
                                break
                    
                    # Patrón F: "También lo hace X en detrimento de Y" (nuevo)
                    m_tambien = re.search(r"[Tt]ambién\s+lo\s+hace\s+([\w]+)\s+en\s+detrimento\s+de\s+([\w]+)", texto_cr, re.UNICODE)
                    if m_tambien:
                        jug_in = m_tambien.group(1).strip()
                        jug_out = m_tambien.group(2).strip()
                        # Buscar equipo del que sale
                        for p_out in reversed(jug_out.split()):
                            if p_out in alineaciones:
                                self._registrar_jugador(alineaciones, jug_in, alineaciones[p_out])
                                break
                    
                    # Patrón G: "X, para dentro. Se retira Y en el/la Z"
                    # Ejemplo: "Deossa, para dentro. Se retira Fidalgo en el Real Betis."
                    m_para_dentro = re.search(r"([A-ZÁÉÍÓÚÑ][\wáéíóúñüö.\-]+(?:\s+[\wáéíóúñüö.\-]+)?),?\s+para dentro", texto_cr, re.IGNORECASE)
                    if m_para_dentro:
                        jug_in_g = m_para_dentro.group(1).strip()
                        # Buscar quién se retira
                        m_retira_g = re.search(r"[Ss]e retira\s+([A-ZÁÉÍÓÚÑ][\wáéíóúñüö.\-]+(?:\s+[\wáéíóúñüö.\-]+)?)", texto_cr)
                        if m_retira_g:
                            jug_out_g = m_retira_g.group(1).strip()
                            for p_out in reversed(jug_out_g.split()):
                                if p_out in alineaciones:
                                    self._registrar_jugador(alineaciones, jug_in_g, alineaciones[p_out])
                                    break
                        # También intentar deducir equipo del texto "en el/del Real Betis"
                        if jug_in_g not in alineaciones:
                            for eq in [equipo_local, equipo_visitante]:
                                if eq and eq.lower() in texto_cr.lower():
                                    self._registrar_jugador(alineaciones, jug_in_g, eq)
                                    break
                    
                    # Patrón H: "X reemplaza a Y" / "X sustituye a Y" / "X releva a Y"
                    # Ejemplo: "Gómez reemplaza a Ricardo en el doble cambio del Real Betis."
                    m_reemplaza = re.search(r"([A-ZÁÉÍÓÚÑ][\wáéíóúñüö.\-]+(?:\s+[\wáéíóúñüö.\-]+)?)\s+(?:reemplaza|sustituye|releva)\s+a(?:l)?\s+([A-ZÁÉÍÓÚÑ][\wáéíóúñüö.\-]+(?:\s+[\wáéíóúñüö.\-]+)?)", texto_cr, re.IGNORECASE)
                    if m_reemplaza:
                        jug_in_h = m_reemplaza.group(1).strip()
                        jug_out_h = m_reemplaza.group(2).strip()
                        for p_out in reversed(jug_out_h.split()):
                            if p_out in alineaciones:
                                self._registrar_jugador(alineaciones, jug_in_h, alineaciones[p_out])
                                break
                        # Fallback: equipo del texto
                        if jug_in_h not in alineaciones:
                            for eq in [equipo_local, equipo_visitante]:
                                if eq and eq.lower() in texto_cr.lower():
                                    self._registrar_jugador(alineaciones, jug_in_h, eq)
                                    break
                    
                    # Patrón I: "Se marcha X en el Z. Entra en su lugar Y." / "Se marcha X. Entra Y."
                    # Ejemplo: "Se marcha De Frutos en el Rayo Vallecano. Entra en su lugar Chavarría."
                    m_marcha = re.search(r"[Ss]e march[ao]\s+([A-ZÁÉÍÓÚÑ][\wáéíóúñüö.\-]+(?:\s+[\wáéíóúñüö.\-]+)?)", texto_cr)
                    m_entra_i = re.search(r"[Ee]ntra(?:\s+en su lugar)?\s+([A-ZÁÉÍÓÚÑ][\wáéíóúñüö.\-]+(?:\s+[\wáéíóúñüö.\-]+)?)", texto_cr)
                    if m_marcha and m_entra_i:
                        jug_out_i = m_marcha.group(1).strip()
                        jug_in_i = m_entra_i.group(1).strip()
                        for p_out in reversed(jug_out_i.split()):
                            if p_out in alineaciones:
                                self._registrar_jugador(alineaciones, jug_in_i, alineaciones[p_out])
                                break
                    
                    # Patrón J: "X y Y reemplazan a A y B" (múltiple)
                    # Ejemplo: "Álvaro y Ciss reemplazan a Pérez y Gumbau"
                    m_multi_reemp = re.search(r"([A-ZÁÉÍÓÚÑ][\wáéíóúñüö.\-]+)\s+y\s+([A-ZÁÉÍÓÚÑ][\wáéíóúñüö.\-]+)\s+(?:reemplazan|sustituyen|relevan)\s+a\s+([A-ZÁÉÍÓÚÑ][\wáéíóúñüö.\-]+)\s+y\s+([A-ZÁÉÍÓÚÑ][\wáéíóúñüö.\-]+)", texto_cr, re.IGNORECASE)
                    if m_multi_reemp:
                        ins = [m_multi_reemp.group(1).strip(), m_multi_reemp.group(2).strip()]
                        outs = [m_multi_reemp.group(3).strip(), m_multi_reemp.group(4).strip()]
                        for j_in, j_out in zip(ins, outs):
                            for p_out in reversed(j_out.split()):
                                if p_out in alineaciones:
                                    self._registrar_jugador(alineaciones, j_in, alineaciones[p_out])
                                    break
                    
                    # Patrón K: "Nteka y Díaz forman el doble cambio del Rayo Vallecano. Se marchan Ilias y Pacha."
                    m_forman_cambio = re.search(r"([A-ZÁÉÍÓÚÑ][\wáéíóúñüö.\-]+(?:\s+y\s+[A-ZÁÉÍÓÚÑ][\wáéíóúñüö.\-]+)+)\s+forman?\s+el\s+(?:doble\s+|triple\s+)?cambio\s+del?\s+([A-ZÁÉÍÓÚÑ][\wáéíóúñüöA-ZÁÉÍÓÚÑ\s]+?)[\.,]", texto_cr, re.IGNORECASE)
                    if m_forman_cambio:
                        jug_entran_txt = m_forman_cambio.group(1).strip()
                        eq_txt_k = m_forman_cambio.group(2).strip()
                        equipo_k = None
                        for eq in [equipo_local, equipo_visitante]:
                            if eq and (eq_txt_k.lower() in eq.lower() or eq.lower() in eq_txt_k.lower()):
                                equipo_k = eq
                                break
                        if equipo_k:
                            for jug_name in re.split(r'\s+y\s+', jug_entran_txt):
                                self._registrar_jugador(alineaciones, jug_name.strip(), equipo_k)
            
            # === FUENTE 4: Divs de alineación (si existen) ===
            for side, equipo in [('equipo1', equipo_local), ('equipo2', equipo_visitante)]:
                alin_div = soup.find('div', class_=f'team {side}')
                if alin_div:
                    for tag in alin_div.find_all(['span', 'a'], class_=re.compile(r'player|jugador')):
                        self._registrar_jugador(alineaciones, tag.get_text(strip=True), equipo)
        
        except Exception as e:
            logging.error(f"Error extrayendo alineaciones: {e}")
        
        logging.info(f"📋 Alineaciones extraídas: {len(alineaciones)} jugadores")
        return alineaciones
    
    def _extraer_goleadores_resumen(self, soup):
        """Extrae goleadores del match-header-resume (fuente más confiable).
        
        HTML: <div class="match-header-resume"><table><tr>
            <td class="mhr-name">Jugador Local</td>
            <td class="mhr-min">40'</td>
            <td class="mhr-ico gol"><i></i></td>
            <td class="mhr-marker"><div>0 - 1</div></td>
            <td class="mhr-ico gol"><i></i></td>
            <td class="mhr-min">63'</td>
            <td class="mhr-name">Jugador Visit</td>
        </tr></table></div>
        
        Retorna dict {minuto_str: {jugador, equipo, marcador}}
        """
        goleadores = {}
        tabla_resumen = soup.find('div', class_='match-header-resume')
        if not tabla_resumen:
            return goleadores
        
        tabla = tabla_resumen.find('table')
        if not tabla:
            return goleadores
        
        for fila in tabla.find_all('tr'):
            celdas = fila.find_all('td')
            if len(celdas) < 7:
                continue
            
            # VALIDACIÓN CRÍTICA: Solo procesar si la celda mhr-ico tiene clase 'gol'
            # Índice 2 = icono local, índice 4 = icono visitante
            ico_local = celdas[2]
            ico_visit = celdas[4]
            
            nombre_local = celdas[0].get_text(strip=True)
            min_local = celdas[1].get_text(strip=True).replace("'", "")
            marcador = celdas[3].get_text(strip=True)
            min_visit = celdas[5].get_text(strip=True).replace("'", "")
            nombre_visit = celdas[6].get_text(strip=True)
            
            # Solo agregar si tiene la clase 'gol' Y hay nombre Y minuto
            tiene_gol_local = 'gol' in ico_local.get('class', [])
            tiene_gol_visit = 'gol' in ico_visit.get('class', [])
            
            if tiene_gol_local and nombre_local and min_local:
                goleadores[min_local] = {'jugador': nombre_local, 'equipo': 'local', 'marcador': marcador}
                logging.info(f"✅ Gol LOCAL confirmado: {nombre_local} min {min_local} → {marcador}")
            if tiene_gol_visit and nombre_visit and min_visit:
                goleadores[min_visit] = {'jugador': nombre_visit, 'equipo': 'visitante', 'marcador': marcador}
                logging.info(f"✅ Gol VISITANTE confirmado: {nombre_visit} min {min_visit} → {marcador}")
        
        if goleadores:
            resumen_txt = ', '.join(f"{v['jugador']} ({k}min)" for k, v in goleadores.items())
            logging.info(f"🎯 Goleadores resumen: {resumen_txt}")
        return goleadores

    def _extraer_eventos(self, soup):
        """Extrae los eventos/jugadas del partido de la table-cronica.
        
        HTML por fila:
        <tr class="post... cronica">
            <td class="cronica_time"><b class="cronica_time_value">63</b></td>
            <td><span class="cronica_ico"><img src="...accionN.png"></span></td>
            <td><div class="cronica_content"><div>Texto del evento</div></div></td>
        </tr>
        """
        eventos = []
        
        # Pre-cargar goleadores del resumen (más confiable que la crónica)
        goleadores_info = self._extraer_goleadores_resumen(soup)
        
        try:
            tabla_cronica = soup.find('table', class_='table-cronica')
            if not tabla_cronica:
                return eventos
            
            filas = tabla_cronica.find_all('tr', class_=re.compile(r'post.*cronica'))
            logging.debug(f"🔍 _extraer_eventos: {len(filas)} filas en crónica")
            
            for fila in filas:
                # --- Minuto ---
                time_cell = fila.find('td', class_='cronica_time')
                if not time_cell:
                    continue
                time_b = time_cell.find('b', class_='cronica_time_value')
                if not time_b:
                    continue
                minuto_raw = time_b.get_text(strip=True)
                if 'Prev' in minuto_raw or 'prev' in minuto_raw:
                    continue
                
                evento = {'minuto': minuto_raw + "'"}
                
                # --- Icono ---
                ico_span = fila.find('span', class_='cronica_ico')
                if ico_span:
                    img = ico_span.find('img')
                    if img:
                        match_ico = re.search(r'(accion\d+)\.png', img.get('src', ''))
                        evento['icono'] = (match_ico.group(1) + '.png') if match_ico else (img.get('alt', 'none') + '.png')
                    else:
                        evento['icono'] = 'none.png'
                else:
                    evento['icono'] = 'none.png'
                
                # --- Texto ---
                content_div = fila.find('div', class_='cronica_content')
                if not content_div:
                    continue
                inner_div = content_div.find('div')
                if not inner_div:
                    continue
                texto = inner_div.get_text(strip=True)
                if not texto:
                    continue
                evento['texto'] = texto
                
                # --- Jugador y equipo ---
                minuto_num = minuto_raw.split('+')[0]

                # PASO 1: Parsear jugador Y equipo del TEXTO de crónica.
                # El formato es siempre "Acción - Jugador (Equipo)", ej:
                #   "Gol - Désiré Doué (PSG)"
                #   "Asistencia - B. Barcola (PSG)"
                #   "T. Amarilla - D. Zakaria (Monaco)"
                # Esta es la fuente más fiable para todos los tipos de evento.
                self._parsear_jugador_texto(evento, texto)

                # PASO 2: Para GOLES, refinar con match-header-resume.
                # El resumen proporciona el nombre completo del goleador y el marcador
                # en ese momento exacto. NO incluye asistencias, así que NO tocar
                # eventos accion22. El campo equipo queda como 'local'/'visitante'
                # y se traduce al nombre real en el bloque de asistencia pareada.
                _icono_evento = evento.get('icono', '')
                _es_icono_gol = any(g in _icono_evento for g in ('accion1.png', 'accion2.png', 'accion43.png'))
                if _es_icono_gol and minuto_num in goleadores_info:
                    info = goleadores_info[minuto_num]
                    evento['jugador'] = info['jugador']
                    evento['equipo'] = info['equipo']
                    evento['marcador_gol'] = info['marcador']
                    logging.info(f"✅ Gol resumen: {info['jugador']} ({info['equipo']}) min {minuto_num} → {info['marcador']}")
                elif not evento.get('jugador'):
                    # Fallback: enlace <a> si el texto no tenía jugador
                    enlace = content_div.find('a')
                    if enlace:
                        nombre = enlace.get('title', '') or enlace.get_text(strip=True)
                        if nombre:
                            evento['jugador'] = nombre.strip()
                
                logging.info(f"📝 Evento: [{evento.get('minuto')}] {evento.get('icono')} - {evento.get('jugador', '?')} ({evento.get('equipo', evento.get('equipo_nombre', '?'))})")
                eventos.append(evento)
            
            return eventos
            
        except Exception as e:
            logging.error(f"Error extrayendo eventos: {e}", exc_info=True)
            return eventos
    
    def _parsear_jugador_texto(self, evento, texto):
        """Parsea jugador y equipo del texto de crónica cuando no hay fuente mejor.
        
        Formatos conocidos:
        - Segunda: "T. Amarilla - Jugador (Equipo)" / "Gol - Jugador (Equipo)"
        - Primera: "Amarilla para Jugador por..." / "Roja para Jugador" / "Expulsado Jugador"
        - Primera: "Se la lleva Jugador" / "Amarilla Jugador en la cara/por..."
        """
        # Formato Segunda: "Acción - Jugador (Equipo)"
        match = re.search(r'^[^-]+-\s*([^(]+)\s*\(([^)]+)\)', texto)
        if match:
            evento['jugador'] = match.group(1).strip()
            evento['equipo_nombre'] = match.group(2).strip()
            return
        
        # Formato Primera: "Amarilla para Jugador por/que/,./en la/tras"
        match = re.search(r'[Aa]marilla para ([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s\-\.]+?)(?:\s+por|\s+que|\s+en\s+|\s+tras|,|\.)', texto)
        if match:
            evento['jugador'] = self._limpiar_nombre_jugador(match.group(1).strip())
            return
        
        # Formato Primera: "Amarilla por [razón] para Jugador" (ej: "Amarilla por acoso y derribo para Otamendi, que...")
        match = re.search(r'[Aa]marilla\s+por\s+.+?\s+para\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s\-\.]+?)(?:\s+por|\s+que|\s+en\s+|\s+tras|,|\.)', texto)
        if match:
            evento['jugador'] = self._limpiar_nombre_jugador(match.group(1).strip())
            return
        
        # Formato Primera: "Se la lleva Jugador por..."
        match = re.search(r'[Ss]e la lleva\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s\-\.]+?)(?:\s+por|\s+tras|,|\.|$)', texto)
        if match:
            evento['jugador'] = self._limpiar_nombre_jugador(match.group(1).strip())
            return
        
        # Formato Primera: "Roja para/Expulsado/Expulsión de Jugador"
        match = re.search(r'(?:[Rr]oja para|[Ee]xpulsado|[Ee]xpulsión de) ([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s\-\.]+?)(?:\s+por|\s+que|\s+en\s+|\s+tras|,|\.)', texto)
        if match:
            evento['jugador'] = self._limpiar_nombre_jugador(match.group(1).strip())
            return
        
        # Fallback: "¡¡Es Nombre Apellido!!"
        match = re.search(r'¡+\s*[Ee]s\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)*)', texto)
        if match:
            evento['jugador'] = match.group(1).strip()

    def _equipo_es_local(self, nombre_equipo, equipo_local, equipo_visitante):
        """Determina si un equipo es el local comparando por similitud de nombres.
        
        Maneja abreviaciones y variaciones comunes (ej: 'Viktoria Plzeň' vs 'V. Plzeň').
        Returns True si es local, False si es visitante o desconocido.
        """
        if not nombre_equipo:
            return False
        _ne = nombre_equipo.lower().strip()
        _el = equipo_local.lower().strip() if equipo_local else ''
        _ev = equipo_visitante.lower().strip() if equipo_visitante else ''
        # Coincidencia exacta
        if _ne == _el or _ne in _el or _el in _ne:
            return True
        if _ne == _ev or _ne in _ev or _ev in _ne:
            return False
        # Comparar última palabra (apellido del equipo)
        _ne_last = _ne.split()[-1] if _ne.split() else ''
        _el_last = _el.split()[-1] if _el.split() else ''
        _ev_last = _ev.split()[-1] if _ev.split() else ''
        if _ne_last and _ne_last == _el_last:
            return True
        if _ne_last and _ne_last == _ev_last:
            return False
        return False  # Default: visitante (para no sobrecontar locales)

    def _extraer_jugador_tarjeta(self, texto: str) -> str:
        """Extrae el nombre del jugador de un texto narrativo de tarjeta amarilla.
        Aplica los mismos 5 patrones que el path principal de _revisar_partido.
        Devuelve cadena vacía si no lo encuentra."""
        patrones = [
            # "T. Amarilla - Jugador (Equipo)"
            r'^[^-]+-\s*([^(]+)\s*\([^)]+\)',
            # "Amarilla para Jugador por/que/del/en/tras/,/."
            r'[Aa]marilla para ([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s\-\.]{2,50})'
            r'(?:\s+por|\s+que|\s+del|\s+en\s+|\s+tras|\.|,|$)',
            # "Amarilla [de] Jugador por/en/,/."
            r'[Aa]marilla\s+(?:de\s+)?([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s\-\.]{2,50})'
            r'(?:\s+por|\s+en\s+|\.|,|$)',
            # "Se la lleva Jugador por/,/."
            r'[Ss]e la lleva\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s\-\.]{2,50})'
            r'(?:\s+por|\.|,|$)',
            # "Tarjeta [adjetivo/artículo(s)] Jugador,/por/que"
            r'[Tt]arjeta(?:\s+\w+){1,3}\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s\-\.]{2,40})'
            r'(?:,|\s+por|\s+que|\.)',
        ]
        for pat in patrones:
            m = re.search(pat, texto)
            if m:
                return self._limpiar_nombre_jugador(m.group(1).strip())

        # Último recurso: primer nombre propio seguido de terminador
        _excluir = {'sale', 'entra', 'gol', 'tarjeta', 'amarilla', 'roja',
                    'ya tenemos', 'se la lleva', 'se la llevan'}
        for m in re.finditer(
            r'([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s\-\.]{2,25})'
            r"(?:\s+por|\s+que|\s+en\s+|\.|,|')",
            texto
        ):
            candidato = m.group(1).strip()
            if (candidato.lower() not in _excluir
                    and not any(candidato.lower().startswith(p) for p in _excluir)):
                return self._limpiar_nombre_jugador(candidato)
        return ''

    @staticmethod
    def _limpiar_nombre_jugador(nombre):
        """Elimina texto basura que se pega al nombre del jugador.
        
        Ejemplo: 'Onyeka en la cara' → 'Onyeka'
        """
        # Frases comunes que se pegan al final del nombre
        sufijos_basura = [
            r'\s+en la cara.*', r'\s+en el área.*', r'\s+en el centro.*',
            r'\s+en la frontal.*', r'\s+en el pecho.*', r'\s+en la pierna.*',
            r'\s+en el pie.*', r'\s+en la espalda.*', r'\s+en el tobillo.*',
            r'\s+en mitad.*', r'\s+en una.*', r'\s+sobre el.*',
            r'\s+desde la.*', r'\s+fuera del.*', r'\s+dentro del.*',
            r'\s+a la salida.*', r'\s+a pie.*', r'\s+al borde.*',
        ]
        for sufijo in sufijos_basura:
            nombre = re.sub(sufijo, '', nombre, flags=re.IGNORECASE)
        
        # Si el nombre tiene más de 4 palabras, probablemente hay texto de más
        palabras = nombre.split()
        if len(palabras) > 4:
            nombre = ' '.join(palabras[:3])
        
        return nombre.strip()

    @staticmethod
    def _parsear_lista_jugadores(texto_raw):
        """Parsea una lista de nombres tipo 'A, B y C' → ['A', 'B', 'C'].
        
        Ejemplos:
            'Matías Moreno, Víctor García y Raghouber' → ['Matías Moreno', 'Víctor García', 'Raghouber']
            'Thomas Partey y Renato Veiga' → ['Thomas Partey', 'Renato Veiga']
            'Maturro' → ['Maturro']
        """
        # Limpiar paréntesis y texto extra (ej: "este parece que lesionado")
        texto_raw = re.sub(r',\s*este\s+parece.*$', '', texto_raw, flags=re.IGNORECASE)
        texto_raw = re.sub(r'\([^)]*\)', '', texto_raw).strip()
        
        # Separar por " y " (la última ocurrencia primero)
        if ' y ' in texto_raw:
            partes = texto_raw.rsplit(' y ', 1)
            antes = partes[0].strip()
            ultimo = partes[1].strip().rstrip(".'\"")
            
            # El "antes" puede tener comas: "A, B"
            jugadores = [j.strip() for j in antes.split(',') if j.strip()]
            if ultimo:
                jugadores.append(ultimo)
        else:
            jugadores = [texto_raw.strip().rstrip(".'\"")]
        
        # Filtrar nombres inválidos (muy cortos, solo artículos, etc.)
        resultado = []
        for j in jugadores:
            j = j.strip()
            if len(j) >= 2 and any(c.isupper() for c in j):
                # Limpiar prefijos comunes
                j = re.sub(r'^(?:el|la|los|las|un|una)\s+', '', j, flags=re.IGNORECASE).strip()
                if len(j) >= 2:
                    resultado.append(j)
        
        return resultado

    def _encolar_narracion(self, partido_id, mensaje, es_importante=False):
        """Envía un mensaje de narración a los canales apropiados.
        
        - #mis_vips (canal interno): recibe SIEMPRE todos los mensajes
        - Canales externos: solo si es_importante=True (goles, tarjetas, descanso…)
        """
        try:
            # Siempre enviar al canal interno
            self.bot_callback('message', Config.CANAL_FUTBOL, mensaje)

            if es_importante:
                # Eventos importantes → también a los canales externos
                canales_externos = [c for c in self.db.get_canales_narracion_activa()
                                    if c.lower() != Config.CANAL_FUTBOL.lower()]
                for canal in canales_externos:
                    self.bot_callback('message', canal, mensaje)
                self._debug(
                    f"⚽ Narrado en canal interno + {len(canales_externos)} externo(s)",
                    importante=True
                )
            else:
                self._debug(f"📢 Narrado solo en canal interno")
        except Exception as e:
            logging.error(f"Error encolando narración: {e}")

# ============================ BOT PRINCIPAL ============================
class MircBot:
    def __init__(self):
        # irc.client
        self.reactor    = irc.client.Reactor()
        self.connection = None          # irc.client.ServerConnection activa

        self.connected  = False
        self.identified = False
        self.running    = True
        self.bot_ready  = False         # True cuando el bot está en los canales y listo para narrar
        self.my_host    = ""            # Host asignado por el servidor (para detectar bans)
        self.db         = BotDB()
        self.last_message_time = 0
        self.reconnect_attempts = 0
        self.message_queue = []
        self.lock = threading.Lock()    # Lock para envío de mensajes thread-safe
        self.intro_mostrada = False     # Para mostrar intro solo una vez
        self.pre_reload_hashes = {}     # {partido_id: ultimo_hash} capturado justo antes del reload

        # Preparar scraper pero NO iniciarlo aún (se iniciará cuando el bot esté listo)
        self.scraper = None
        self.scraper_iniciado = False

        # Handlers registrados una sola vez en el reactor — sobreviven reconexiones
        # sin acumularse (registrarlos en connect() los duplicaría en cada reconexión)
        self.reactor.add_global_handler("welcome",    self._on_welcome)
        self.reactor.add_global_handler("disconnect", self._on_disconnect)
        self.reactor.add_global_handler("err_yourebannedcreep", self._on_ban)
        self.reactor.add_global_handler("err_passwdmismatch", self._on_bad_pass)
        self.reactor.add_global_handler("pubmsg",     self._on_pubmsg)
        self.reactor.add_global_handler("privmsg",    self._on_privmsg)
        self.reactor.add_global_handler("kick",       self._on_kick_event)
        self.reactor.add_global_handler("mode",       self._on_mode_event)
        self.reactor.add_global_handler("pong",       self._on_pong)
        self.reactor.add_global_handler("302",        self._on_302)
        self.reactor.add_global_handler("396",        self._on_396)
        self.reactor.add_global_handler("311",        self._on_311)
        self.reactor.add_global_handler("474",        self._on_474)
    
    def _scraper_callback(self, action, target, message):
        """Callback para que el scraper envíe mensajes"""
        # Solo encolar mensajes si el bot está listo (conectado y en canales)
        if not self.bot_ready:
            return
        # El silencio post-reload se gestiona partido a partido en el scraper (pre_reload_hashes)
        if action == 'message':
            self.message_queue.append((target, message))
    
    # -------- Conexión IRC --------
    def connect(self):
        """Establece conexión con el servidor IRC usando irc.client"""
        try:
            # Cerrar conexión anterior si existe
            if self.connection:
                try:
                    self.connection.disconnect("Reconectando...")
                except:
                    pass
                self.connection = None

            nick_with_pass = f"{Config.IRC_NICK}:{Config.IRC_PASS}"
            
            factory = irc.connection.Factory()
            if Config.IRC_PORT == 6697:
                import ssl
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                factory = irc.connection.Factory(wrapper=ssl_context.wrap_socket)

            self.connection = self.reactor.server().connect(
                Config.IRC_SERVER,
                Config.IRC_PORT,
                nick_with_pass,
                ircname=Config.IRC_REALNAME,
                username=Config.IRC_USER,
                connect_factory=factory
            )

            self.connected = True
            self.identified = False
            self.reconnect_attempts = 0
            logging.info(f"✅ Conectado a {Config.IRC_SERVER}:{Config.IRC_PORT}")
            return True

        except irc.client.ServerConnectionError as e:
            logging.error(f"❌ Error de conexión IRC: {e}")
            self.connected = False
            self.identified = False
            self.bot_ready = False
            self.connection = None
            return False
        except Exception as e:
            logging.error(f"❌ Error inesperado en connect(): {e}")
            self.connected = False
            self.identified = False
            self.bot_ready = False
            self.connection = None
            return False

    def reconnect(self):
        """Intenta reconectar al servidor con backoff"""
        self.bot_ready = False
        if Config.MAX_RECONNECT_ATTEMPTS > 0 and self.reconnect_attempts >= Config.MAX_RECONNECT_ATTEMPTS:
            logging.error("⛔ Máximo de intentos de reconexión alcanzado")
            self.running = False
            return False

        # Si tenemos un baneo activo en memoria, esperamos
        if getattr(self, 'banned_until', 0) > time.time():
            remaining = int(self.banned_until - time.time())
            logging.warning(f"⏳ Baneo activo. Esperando {remaining}s más...")
            time.sleep(60) # Revisar cada minuto
            return self.reconnect()

        self.reconnect_attempts += 1
        delay = Config.RECONNECT_DELAY
        logging.info(f"🔄 Intento de reconexión #{self.reconnect_attempts} en {delay}s...")
        time.sleep(delay)
        return self.connect()

    # -------- Handlers irc.client --------
    def _on_welcome(self, connection, event):
        """Servidor nos da la bienvenida (001)"""
        logging.info("✅ Identificado en el servidor")
        self.identified = True
        connection.send_raw(f"USERHOST {Config.IRC_NICK}")
        connection.send_raw(f"WHOIS {Config.IRC_NICK}")
        # Lanzar join en thread separado para no bloquear el reactor
        threading.Thread(target=self._delayed_join, daemon=True).start()

    def _delayed_join(self):
        """Espera a que NickServ identifique el nick y luego entra a los canales."""
        time.sleep(5)   # Margen para que NickServ complete la identificación
        self.join_channels()

    def _on_disconnect(self, connection, event):
        """Desconexión del servidor — lanza reconexión en thread para no bloquear el reactor"""
        # Intentar obtener el motivo de desconexión
        reason = str(event.arguments[0]) if event.arguments else "Motivo desconocido"
        logging.warning(f"⚠️ Desconectado del servidor IRC: {reason}")
        
        self.connected  = False
        self.identified = False
        self.bot_ready  = False
        
        if "banned" in reason.lower() or "g-lined" in reason.lower() or "estás baneado" in reason.lower():
            self._handle_ban("G-line detectado en desconexión")

        if self.running:
            if self.message_queue:
                logging.info(f"🗑️ Limpiando {len(self.message_queue)} mensajes pendientes")
                self.message_queue.clear()
            threading.Thread(target=self.reconnect, daemon=True).start()

    def _on_ban(self, connection, event):
        """Handler para error 465 (You are banned)"""
        reason = str(event.arguments[1]) if len(event.arguments) > 1 else "Baneado de la red"
        self._handle_ban(reason)

    def _on_bad_pass(self, connection, event):
        """Handler para error 464 (Password mismatch)"""
        logging.error("❌ ERROR: Contraseña de NickServ incorrecta!")
        self._handle_ban("Contraseña incorrecta")

    def _handle_ban(self, reason):
        """Configura el tiempo de espera por baneo"""
        logging.error(f"🚫 BANEO/G-LINE DETECTADO: {reason}")
        # Esperar 30 minutos (1800 segundos)
        self.banned_until = time.time() + 1800
        logging.error("🕒 Backoff de 30 minutos activado para evitar abusos.")

    def _on_pubmsg(self, connection, event):
        """Mensaje público en canal"""
        try:
            nick    = irc.client.NickMask(event.source).nick
            target  = event.target
            mensaje = strip_mirc_colors(event.arguments[0])
            self.process_command(nick, target, mensaje, is_private=False)
        except Exception as e:
            logging.error(f"Error en _on_pubmsg: {e}")

    def _on_privmsg(self, connection, event):
        """Mensaje privado"""
        try:
            nick    = irc.client.NickMask(event.source).nick
            mensaje = strip_mirc_colors(event.arguments[0])
            self.process_command(nick, nick, mensaje, is_private=True)
        except Exception as e:
            logging.error(f"Error en _on_privmsg: {e}")

    def _on_kick_event(self, connection, event):
        """Nos echan de un canal"""
        try:
            canal      = event.target
            kicked_nick = event.arguments[0] if event.arguments else ""
            if kicked_nick.lower() == Config.IRC_NICK.lower():
                logging.warning(f"👢 Nos han kickeado de {canal}")
                time.sleep(5)
                connection.join(canal)
        except Exception as e:
            logging.error(f"Error en _on_kick_event: {e}")

    def _on_mode_event(self, connection, event):
        """Cambio de modo en un canal (p.ej. ban +b)"""
        try:
            raw = f"MODE {event.target} {' '.join(event.arguments)}"
            logging.info(f"🔧 MSG MODE: :{event.source} {raw}")
            if "+b" in (event.arguments[0] if event.arguments else ""):
                self._handle_ban(f":{event.source} {raw}")
        except Exception as e:
            logging.error(f"Error en _on_mode_event: {e}")

    def _on_pong(self, connection, event):
        pass  # irc.client gestiona PING/PONG internamente

    def _on_302(self, connection, event):
        """Respuesta USERHOST"""
        try:
            msg = " ".join(event.arguments)
            if '@' in msg:
                self.my_host = msg.split('@')[-1].strip()
                logging.info(f"📍 Mi host (302): {self.my_host}")
        except:
            pass

    def _on_396(self, connection, event):
        """Host virtual/cloak asignado"""
        try:
            if event.arguments:
                self.my_host = event.arguments[0]
                logging.info(f"📍 Mi host (396 cloak): {self.my_host}")
        except:
            pass

    def _on_311(self, connection, event):
        """Respuesta WHOIS"""
        try:
            # event.arguments: [nick, user, host, *, realname]
            if len(event.arguments) >= 3:
                self.my_host = event.arguments[2]
                logging.info(f"📍 Mi host (311 WHOIS): {self.my_host}")
        except:
            pass

    def _on_474(self, connection, event):
        """No podemos entrar a un canal (baneados)"""
        try:
            canal = event.arguments[0] if event.arguments else ""
            if not canal:
                return
            logging.warning(f"🚫 No puedo entrar a {canal} - Estoy baneado")
            self.send_message(Config.CANAL_DEBUG, f"🚫 No puedo entrar a {canal} - Estoy baneado")
            canales_bd = [c[0] for c in self.db.list_canales()]
            if canal in canales_bd:
                self.db.del_canal(canal)
                logging.info(f"🗑️ Canal {canal} eliminado de la BD (baneado)")
        except Exception as e:
            logging.error(f"Error procesando banned from channel: {e}")
    
    def join_channels(self):
        """Se une a todos los canales configurados"""
        self.send_raw(f"JOIN {Config.CANAL_FUTBOL}")
        time.sleep(0.5)
        
        if Config.CANAL_DEBUG != Config.CANAL_FUTBOL:
            self.send_raw(f"JOIN {Config.CANAL_DEBUG}")
            time.sleep(0.5)
        
        # Canales registrados en la BD
        for canal, _, _ in self.db.list_canales():
            self.send_raw(f"JOIN {canal}")
            time.sleep(0.5)
        
        # Intro en canal principal (solo la primera vez)
        if not self.intro_mostrada:
            time.sleep(1)
            self._mostrar_intro()
            self.intro_mostrada = True
        
        # Marcar el bot como listo para narrar
        self.bot_ready = True
        logging.info("✅ Bot listo para narrar")
        
        # Iniciar scraper AHORA que el bot está conectado y en los canales
        if Config.SCRAPER_ENABLED and not self.scraper_iniciado:
            self.scraper = FootballScraper(self.db, self._scraper_callback)
            self.scraper.start()
            self.scraper_iniciado = True
            logging.info("🔍 Scraper de partidos iniciado (bot conectado)")
    
    def _mostrar_intro(self):
        """Muestra la intro del bot al entrar al canal principal"""
        intro_lines = [
            "\x0312⚽\x03 \x02\x0307MaLeFiCo\x03\x02 \x0314·\x03 \x0311Bot de Retransmisión de Fútbol\x03 \x0314·\x03 \x0303v3.5\x03 \x0312⚽\x03",
            "\x0314┌─────────────────────────────────────────────┐\x03",
            "\x0314│\x03  \x0309✔\x03 Conexión IRC establecida",
            "\x0314│\x03  \x0309✔\x03 Base de datos SQLite cargada",
            "\x0314│\x03  \x0309✔\x03 Scraper de partidos activo",
            "\x0314│\x03  \x0309✔\x03 Sistema de narración listo",
            "\x0314└─────────────────────────────────────────────┘\x03",
            "\x0314·\x03 \x0302/msg MaLeFiCo help\x03 para ver los comandos disponibles \x0314·\x03",
        ]
        
        for line in intro_lines:
            self.send_message(Config.CANAL_FUTBOL, line)
            time.sleep(0.4)
    
    # -------- Envío de mensajes --------
    def send_raw(self, msg):
        """Envía un mensaje raw al servidor IRC"""
        if not self.connected or not self.connection:
            return False

        with self.lock:
            # Rate limiting
            if Config.FLOOD_PROTECTION:
                current_time = time.time()
                time_diff = current_time - self.last_message_time
                if time_diff < Config.MESSAGE_DELAY:
                    time.sleep(Config.MESSAGE_DELAY - time_diff)
                self.last_message_time = time.time()

            try:
                self.connection.send_raw(msg)
                logging.debug(f">>> {msg}")
                return True
            except irc.client.ServerNotConnectedError:
                logging.error("❌ Servidor no conectado al enviar mensaje")
                self.connected = False
                self.identified = False
                return False
            except Exception as e:
                logging.error(f"❌ Error enviando: {e}")
                self.connected = False
                self.identified = False
                return False
    
    def send_message(self, target, msg):
        """Envía un mensaje PRIVMSG a un canal o usuario.
        Si el mensaje supera max_len, lo parte por el último espacio
        antes del límite para no cortar palabras a medias.
        """
        max_len = 400
        if len(msg) <= max_len:
            return self.send_raw(f"PRIVMSG {target} :{msg}")
        # Partir por palabras
        partes = []
        while len(msg) > max_len:
            corte = msg.rfind(' ', 0, max_len)
            if corte == -1:
                corte = max_len  # sin espacios, cortar duro
            partes.append(msg[:corte])
            msg = msg[corte:].lstrip()
        if msg:
            partes.append(msg)
        for parte in partes:
            if not self.send_raw(f"PRIVMSG {target} :{parte}"):
                return False
            time.sleep(0.3)
        return True
    
    def send_action(self, target, msg):
        """Envía un ACTION (/me) a un canal o usuario"""
        # ACTION usa formato: PRIVMSG target :\x01ACTION mensaje\x01
        return self.send_raw(f"PRIVMSG {target} :\x01ACTION {msg}\x01")
    
    def send_private(self, nick, msg):
        """Envía un mensaje privado a un usuario"""
        self.send_message(nick, msg)
    
    def _process_message_queue(self):
        """Procesa la cola de mensajes del scraper con anti-flood"""
        # Si no hay conexión, limpiar cola para evitar acumulación
        if not self.connected or not self.identified:
            if self.message_queue:
                logging.warning(f"⚠️ Descartando {len(self.message_queue)} mensajes (sin conexión)")
                self.message_queue.clear()
            return
        
        # Procesar en ráfagas: FLOOD_BURST mensajes, pausa FLOOD_DELAY segundos
        processed = 0
        while self.message_queue and processed < Config.FLOOD_BURST:
            target, message = self.message_queue.pop(0)
            if not self.send_message(target, message):
                # Si falla el envío, salir del bucle
                break
            processed += 1
            time.sleep(Config.MESSAGE_DELAY)  # Delay entre mensajes de la ráfaga
        
        # Si procesamos una ráfaga completa y hay más mensajes, pausa más larga
        if processed >= Config.FLOOD_BURST and self.message_queue:
            time.sleep(Config.FLOOD_DELAY)
    
    # -------- Recepción de mensajes --------
    # -------- Permisos --------
    # Jerarquía: Fundador 👑 > Root 🔑 > Admin ⚙️ > Usuario
    
    def is_fundador(self, nick):
        """Verifica si el usuario es Fundador (jefe absoluto, hardcodeado en Config)"""
        return BotDB.is_fundador(nick)
    
    def is_root(self, nick):
        """Verifica si el usuario es Root (sub-jefe, tabla root_users)"""
        return self.db.is_root(nick)
    
    def is_admin(self, nick):
        """Verifica si el usuario es admin, root o fundador (case-insensitive)"""
        return nick.lower() in [a.lower() for a in self.db.list_admins()] or self.is_root(nick) or self.is_fundador(nick)
    
    # -------- Comandos --------
    def show_help(self, nick, is_admin=False, is_root=False, is_fundador=False):
        """Muestra la ayuda de comandos agrupada en bloques para evitar flood."""
        bloques = []

        # ── Bloque 1: Generales (siempre) ──────────────────────────────────
        bloques.append(
            "🤖 MaLeFiCo Bot — Ayuda | "
            "help · version · stats · live/envivo · score <equipo>"
        )
        bloques.append(
            "👤 Usuarios: alta · baja · puntos | "
            "🎰 Porras: porra apuesta <X-Y> · porra ver · porra estado"
        )

        # ── Bloque 2: Admin ─────────────────────────────────────────────────
        if is_admin or is_root or is_fundador:
            bloques.append(
                "⚙️ ADMIN — Canales: canales list/add/del #canal | "
                "Narración: narracion #canal ON/OFF | "
                "Scan: scan · restart"
            )
            bloques.append(
                "🔍 Partidos: partido add <local> <visit> · partido del #id · "
                "partido list · partido all  14(se auto-eliminan al finalizar)"
            )
            bloques.append(
                "🎰 Porras admin: porra add <local> vs <visit> <premio> · "
                "abrir · cerrar · anuncio · info · resultado <X-Y> · "
                "del · ver <nick> · borrar <nick>"
            )

        # ── Bloque 3: Root ──────────────────────────────────────────────────
        if is_root or is_fundador:
            bloques.append(
                "🔑 ROOT — Staff: root list · admins list/add/del <nick> | "
                "Forbid: forbid add/del/list <nick> | "
                "Sistema: debug · debug ON/OFF"
            )

        # ── Bloque 4: Fundador ──────────────────────────────────────────────
        if is_fundador:
            bloques.append(
                "👑 FUNDADOR — ROOTs: root add/del <nick> | Sistema: quit"
            )

        # ── Enviar con delay entre bloques para no provocar flood ───────────
        for bloque in bloques:
            self.send_private(nick, bloque)
            time.sleep(0.8)
    
    def process_command(self, nick, target, msg, is_private):
        """Procesa comandos del bot (solo por PM)"""
        # Solo procesar comandos enviados por PM (privado)
        if not is_private:
            return
        
        parts = msg.strip().split()
        if not parts:
            return
        
        cmd = parts[0].lower()
        args = parts[1:]
        
        is_fundador = self.is_fundador(nick)
        is_admin = self.is_admin(nick)
        is_root = self.is_root(nick)
        
        # Registrar comando en log
        origen = "PRIVADO" if is_private else target
        nivel = "FUNDADOR" if is_fundador else ("ROOT" if is_root else ("ADMIN" if is_admin else "USER"))
        logging.info(f"📝 CMD [{origen}] {nick} ({nivel}): {msg}")
        
        # -------- Comandos generales --------
        if cmd == "help" or cmd == "ayuda":
            self.show_help(nick, is_admin, is_root, is_fundador)
            return
        
        if cmd == "version":
            self.send_private(nick, "🤖 MaLeFiCo Bot v3.5 — Bot de retransmisión automática de fútbol")
            time.sleep(0.8)
            self.send_private(nick, f"🌐 {Config.IRC_SERVER} | 🔍 {Config.SCRAPER_URL}")
            time.sleep(0.8)
            self.send_private(nick, "✨ Narración en vivo · Filtrado por equipos · Multi-canal · Colores IRC · Debug")
            time.sleep(0.8)
            self.send_private(nick, "⚽ Goles · 📒 Tarjetas · 🎯 Penaltis · 🔄 Cambios · 📺 VAR · 🚑 Lesiones")
            return
        
        if cmd == "stats":
            partidos_activos = len(self.scraper.partidos_activos) if self.scraper else 0
            canales_total = len(self.db.list_canales())
            canales_narr = len(self.db.get_canales_narracion_activa())
            
            self.send_private(nick, "╔══════════════════════════════════════════════╗")
            self.send_private(nick, "║      📊 ESTADÍSTICAS DEL BOT                ║")
            self.send_private(nick, "╚══════════════════════════════════════════════╝")
            self.send_private(nick, "")
            self.send_private(nick, f"⚽ Partidos monitoreados: {partidos_activos}")
            self.send_private(nick, f"📺 Canales registrados: {canales_total}")
            self.send_private(nick, f"🔊 Canales con narración: {canales_narr}")
            self.send_private(nick, "")
            
            # Información del filtro (desde BD)
            partidos_filtro = self.db.list_partidos_filtro()
            if partidos_filtro:
                self.send_private(nick, f"⚽ Filtro activo: {len(partidos_filtro)} partido(s)")
                for f_id, f_local, f_visit, _ in partidos_filtro[:3]:
                    self.send_private(nick, f"   #{f_id} {f_local} vs {f_visit}")
                if len(partidos_filtro) > 3:
                    self.send_private(nick, f"   ... y {len(partidos_filtro) - 3} más")
            else:
                self.send_private(nick, "⚽ Narrando: TODOS los partidos")
            
            self.send_private(nick, "")
            
            # Estado del scraper
            scraper_estado = "✅ Activo" if Config.SCRAPER_ENABLED else "❌ Desactivado"
            self.send_private(nick, f"🔄 Scraper: {scraper_estado}")
            self.send_private(nick, f"⏱️  Intervalo: {Config.SCRAPER_INTERVAL}s")
            
            # Debug
            debug_estado = "📺 Canal" if Config.DEBUG_TO_CHANNEL else "📄 Solo logs"
            self.send_private(nick, f"🐛 Debug: {debug_estado}")
            
            self.send_private(nick, "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            return
        
        # -------- ROOT USERS --------
        if cmd == "root":
            if not is_root and not is_fundador:
                self.send_private(nick, "⛔ Solo ROOT y Fundadores pueden usar este comando")
                return
            
            if not args:
                self.send_private(nick, "Uso: root list|add|del [nick]")
                return
            
            subcmd = args[0].lower()
            
            
            if subcmd == "list":
                fundadores = Config.FUNDADORES
                roots = self.db.list_root()
                self.send_private(nick, f"👑 Fundadores ({len(fundadores)}): {', '.join(fundadores)}")
                if roots:
                    self.send_private(nick, f"🔑 ROOT ({len(roots)}): {', '.join(roots)}")
                else:
                    self.send_private(nick, "🔑 ROOT: (ninguno)")
            
            elif subcmd == "add":
                # Solo los Fundadores pueden agregar otros roots
                if not is_fundador:
                    self.send_private(nick, "⛔ Solo los Fundadores (👑) pueden agregar ROOTs")
                    return
                
                if len(args) < 2:
                    self.send_private(nick, "Uso: root add <nick>")
                    return
                
                root_nick = args[1]
                # Verificar si ya es root
                if root_nick.lower() in [r.lower() for r in self.db.list_root()]:
                    self.send_private(nick, f"⚠️ {root_nick} ya es ROOT")
                    return
                if self.db.add_root(root_nick):
                    self.send_private(nick, f"✅ Usuario ROOT {root_nick} agregado")
                    # También agregarlo como admin
                    self.db.add_admin(root_nick)
                else:
                    self.send_private(nick, f"❌ Error agregando usuario ROOT {root_nick}")
            
            elif subcmd == "del":
                # Solo los Fundadores pueden eliminar otros roots
                if not is_fundador:
                    self.send_private(nick, "⛔ Solo los Fundadores (👑) pueden eliminar ROOTs")
                    return
                
                if len(args) < 2:
                    self.send_private(nick, "Uso: root del <nick>")
                    return
                
                root_nick = args[1]
                
                # No permitir eliminar a un Fundador (case-insensitive)
                if root_nick.lower() in [r.lower() for r in Config.FUNDADORES]:
                    self.send_private(nick, f"⛔ No puedes eliminar a un Fundador ({root_nick} 👑)")
                    return
                
                # Verificar si es root
                if root_nick.lower() not in [r.lower() for r in self.db.list_root()]:
                    self.send_private(nick, f"⚠️ {root_nick} no es ROOT")
                    return
                
                if self.db.del_root(root_nick):
                    self.send_private(nick, f"✅ Usuario ROOT {root_nick} eliminado")
                else:
                    self.send_private(nick, f"❌ Error eliminando usuario ROOT {root_nick}")
            
            else:
                self.send_private(nick, "⛔ Subcomando no reconocido. Usa: list, add o del")
            
            return
        
        # -------- Score (consultar marcador) --------
        if cmd == "score" or cmd == "marcador":
            if not args:
                self.send_message(target, "\x032Sintaxis:\x03 \x0312score <nombre_equipo>\x03")
                return
            
            busqueda = ' '.join(args).lower()
            
            if not self.scraper:
                self.send_message(target, "❌ Scraper no está activo")
                return
            
            # Buscar partido que coincida
            partido_encontrado = None
            for partido_id in self.scraper.partidos_activos.keys():
                partido_bd = self.db.get_partido(partido_id)
                if partido_bd:
                    local = partido_bd[1] if len(partido_bd) > 1 else ""
                    visitante = partido_bd[2] if len(partido_bd) > 2 else ""
                    
                    if busqueda in local.lower() or busqueda in visitante.lower():
                        partido_encontrado = partido_bd
                        break
            
            if not partido_encontrado:
                self.send_message(target, f"\x034No se encontró ningún partido con:\x03 \x0312{busqueda}\x03")
                return
            
            # Extraer info del partido
            local = partido_encontrado[1] if len(partido_encontrado) > 1 else "Local"
            visitante = partido_encontrado[2] if len(partido_encontrado) > 2 else "Visitante"
            estado = partido_encontrado[3] if len(partido_encontrado) > 3 else ""
            
            # Obtener marcador actual de la web
            partido_id = partido_encontrado[0]
            try:
                url_partido = f"{Config.SCRAPER_URL}/partido/{partido_id.replace('_', '/')}"
                response = requests.get(url_partido, timeout=10)
                soup = BeautifulSoup(response.content, 'lxml', from_encoding=response.apparent_encoding)
                
                # Extraer marcador
                resultado_div = soup.find('div', class_='resultado')
                if resultado_div:
                    spans = resultado_div.find_all('span', class_='marker_box')
                    if len(spans) >= 2:
                        goles_local = spans[0].get_text(strip=True)
                        goles_visitante = spans[1].get_text(strip=True)
                    else:
                        goles_local = "0"
                        goles_visitante = "0"
                else:
                    goles_local = "0"
                    goles_visitante = "0"
                
                # Extraer estado (minuto/parte)
                estado_span = soup.find('span', class_='jor-status')
                estado_texto = estado_span.get_text(strip=True) if estado_span else ""
                
                # Determinar estado del partido
                if 'jor-live' in (estado_span.get('class', []) if estado_span else []):
                    # En vivo - extraer minuto
                    estado_color = f"\x032(Min:\x0312 {estado_texto}\x032)\x03"
                elif 'jor-finished' in (estado_span.get('class', []) if estado_span else []):
                    estado_color = "\x034(Finalizado)\x03"
                elif estado_texto:
                    estado_color = f"\x037({estado_texto})\x03"
                else:
                    estado_color = "\x037(No comenzado)\x03"
                
                # Mensaje estilo mIRC
                self.send_message(target, f"\x032Partido:\x03 \x0312{local}\x03 \x0304{goles_local}\x03 - \x0304{goles_visitante}\x03 \x0312{visitante}\x03 {estado_color}")
                
            except Exception as e:
                logging.error(f"Error obteniendo score: {e}")
                self.send_message(target, f"\x032Partido:\x03 \x0312{local}\x03 vs \x0312{visitante}\x03 \x037(Error obteniendo marcador)\x03")
            
            return
        if cmd == "canales":
            if not args:
                self.send_private(nick, "Uso: canales list|add|del [#canal]")
                return
            
            subcmd = args[0].lower()
            
            if subcmd == "list":
                if not (is_admin or is_root):
                    self.send_private(nick, "⛔ Solo admins/root pueden listar canales")
                    return
                
                canales = self.db.list_canales()
                if not canales:
                    self.send_private(nick, "No hay canales registrados")
                    return
                
                self.send_private(nick, f"📺 Canales registrados ({len(canales)}):")
                for i, (canal, founder, narracion) in enumerate(canales, 1):
                    self.send_private(nick, f"  {i}. {canal} - Founder: {founder} (Narración: {narracion})")
            
            elif subcmd == "add":
                if not (is_admin or is_root):
                    self.send_private(nick, "⛔ Solo admins/root pueden agregar canales")
                    return
                
                if len(args) < 2:
                    self.send_private(nick, "Uso: canales add #canal")
                    return
                
                canal = args[1]
                if not canal.startswith('#'):
                    self.send_private(nick, "⛔ El canal debe empezar con #")
                    return
                
                if self.db.add_canal(canal, nick):
                    self.send_private(nick, f"✅ Canal {canal} agregado correctamente")
                    self.send_raw(f"JOIN {canal}")
                else:
                    self.send_private(nick, f"❌ Error agregando canal {canal}")
            
            elif subcmd == "del":
                if not (is_admin or is_root):
                    self.send_private(nick, "⛔ Solo admins/root pueden eliminar canales")
                    return
                
                if len(args) < 2:
                    self.send_private(nick, "Uso: canales del #canal")
                    return
                
                canal = args[1].lower()
                if self.db.del_canal(canal):
                    self.send_private(nick, f"✅ Canal {canal} eliminado correctamente")
                    self.send_raw(f"PART {canal} :Canal eliminado de la lista")
                else:
                    self.send_private(nick, f"❌ Error eliminando canal {canal}")
            
            return
        
        # -------- Narración --------
        if cmd == "narracion":
            if not (is_admin or is_root):
                self.send_private(nick, "⛔ Solo admins/root pueden configurar la narración")
                return
            
            if len(args) < 2:
                self.send_private(nick, "Uso: narracion #canal ON|OFF")
                return
            
            canal = args[0].lower()   # normalizar igual que en BD
            estado = args[1].upper()
            
            if estado not in ['ON', 'OFF']:
                self.send_private(nick, "⛔ Estado debe ser ON u OFF")
                return
            
            # Comprobar si el canal existe y cuál es su estado actual
            # narracion en BD es 0/1 (int), no string
            canales_bd = {c.lower(): int(n) for c, f, n in self.db.list_canales()}
            if canal not in canales_bd:
                self.send_private(nick, f"⛔ El canal {canal} no está registrado")
                return
            
            ya_activa = canales_bd[canal] == 1
            if (estado == 'ON' and ya_activa) or (estado == 'OFF' and not ya_activa):
                self.send_private(nick, f"⚠️ La narración en {canal} ya está {estado}")
                return
            
            if self.db.set_narracion(canal, estado == 'ON'):
                self.send_private(nick, f"✅ Narración {estado} en {canal}")
            else:
                self.send_private(nick, f"❌ Error configurando narración en {canal}")
            
            return
        
        # -------- Admins (root o fundador) --------
        if cmd == "admins":
            if not is_root and not is_fundador:
                self.send_private(nick, "⛔ Solo ROOT puede gestionar admins")
                return
            
            if not args:
                self.send_private(nick, "Uso: admins list|add|del [nick]")
                return
            
            subcmd = args[0].lower()
            
            if subcmd == "list":
                admins = self.db.list_admins()
                self.send_private(nick, f"👥 Admins ({len(admins)}): {', '.join(admins)}")
            
            elif subcmd == "add":
                if len(args) < 2:
                    self.send_private(nick, "Uso: admins add <nick>")
                    return
                
                admin_nick = args[1]
                if admin_nick.lower() in [a.lower() for a in self.db.list_admins()]:
                    self.send_private(nick, f"⚠️ {admin_nick} ya es admin")
                    return
                if self.db.add_admin(admin_nick):
                    self.send_private(nick, f"✅ Admin {admin_nick} agregado")
                else:
                    self.send_private(nick, f"❌ Error agregando admin {admin_nick}")
            
            elif subcmd == "del":
                if len(args) < 2:
                    self.send_private(nick, "Uso: admins del <nick>")
                    return
                
                admin_nick = args[1]
                if BotDB.is_fundador(admin_nick):
                    self.send_private(nick, "⛔ No se puede eliminar a un Fundador (👑) de admins")
                    return
                if self.db.is_root(admin_nick):
                    self.send_private(nick, "⛔ No se puede eliminar a un usuario ROOT de admins")
                    return
                
                if admin_nick.lower() not in [a.lower() for a in self.db.list_admins()]:
                    self.send_private(nick, f"⚠️ {admin_nick} no es admin")
                    return
                
                if self.db.del_admin(admin_nick):
                    self.send_private(nick, f"✅ Admin {admin_nick} eliminado")
                else:
                    self.send_private(nick, f"❌ Error eliminando admin {admin_nick}")
            
            return
        
        # -------- Quit (solo root) --------
        if cmd == "quit" or cmd == "shutdown":
            if not is_fundador:
                self.send_private(nick, "⛔ Solo los Fundadores (👑) pueden apagar el bot")
                return
            
            self.send_private(nick, "👋 Apagando bot...")
            self.shutdown()
            return

        if cmd == "restart":
            if not (is_admin or is_root or is_fundador):
                self.send_private(nick, "⛔ Solo admins/root/fundadores pueden reiniciar el bot")
                return

            self.send_private(nick, "🔄 Reiniciando bot...")
            self.send_message(Config.CANAL_FUTBOL, "🔄 Reiniciando...")
            time.sleep(1)
            import os, sys
            os.execv(sys.executable, [sys.executable] + sys.argv)
            return
        
        # -------- Debug (root o fundador) --------
        if cmd == "debug":
            if not is_root and not is_fundador:
                self.send_private(nick, "⛔ Solo ROOT puede configurar debug")
                return
            
            if not args:
                estado = "ON" if Config.DEBUG_TO_CHANNEL else "OFF"
                self.send_private(nick, f"Debug al canal: {estado}")
                self.send_private(nick, f"Canal debug: {Config.CANAL_DEBUG}")
                self.send_private(nick, "Uso: debug ON|OFF")
                return
            
            subcmd = args[0].upper()
            if subcmd == "ON":
                Config.DEBUG_TO_CHANNEL = True
                self.send_private(nick, f"✅ Debug activado en {Config.CANAL_DEBUG}")
            elif subcmd == "OFF":
                Config.DEBUG_TO_CHANNEL = False
                self.send_private(nick, "✅ Debug desactivado (solo archivo log)")
            else:
                self.send_private(nick, "Uso: debug ON|OFF")
            
            return
        
        # -------- Scan (solo root/admin) --------
        if cmd == "scan":
            if not (is_admin or is_root):
                self.send_private(nick, "⛔ Solo admins/root pueden forzar escaneo")
                return
            
            if self.scraper:
                self.send_private(nick, "🔍 Forzando búsqueda de partidos...")
                # Forzar búsqueda inmediata en un thread
                threading.Thread(target=self._force_scan, daemon=True).start()
            else:
                self.send_private(nick, "❌ Scraper no está activo")
            
            return
        
        # -------- RELOAD (hot-reload del código) --------
        if cmd == "reload":
            if not is_root and not is_fundador:
                self.send_private(nick, "⛔ Solo ROOT puede recargar el código")
                return
            
            try:
                self.send_private(nick, "🔄 Recargando código y reiniciando sistema completo...")
                
                # DETENER SCRAPER COMPLETAMENTE
                if self.scraper:
                    logging.info("🛑 Deteniendo scraper...")
                    self.scraper.stop()
                    time.sleep(1)  # Esperar a que termine
                
                # LIMPIAR TODO EL ESTADO
                logging.info("🧹 Limpiando estado de partidos activos...")
                # Nota: NO restauramos partidos_activos, forzamos redescubrimiento
                
                # Recargar el módulo
                import importlib
                import sys
                
                # El módulo actual es __main__, necesitamos recargarlo de otra forma
                # Leer el archivo y ejecutar las clases actualizadas
                with open(__file__, 'r', encoding='utf-8') as f:
                    code = f.read()
                
                # Crear nuevo namespace para las clases
                new_globals = {
                    '__name__': '__reload__',
                    '__file__': __file__,
                }
                exec(compile(code, __file__, 'exec'), new_globals)
                
                # Actualizar la clase FootballScraper
                global FootballScraper
                FootballScraper = new_globals['FootballScraper']
                
                # Capturar hashes pre-reload de todos los partidos activos en BD
                # Esto permite al nuevo scraper seguir en silencio hasta sincronizarse
                pre_reload_hashes = {}
                n_partidos_activos = 0
                try:
                    rows = _fetch_all(
                        "SELECT id, ultima_jugada FROM ef_partidos "
                        "WHERE ultima_jugada IS NOT NULL AND ultima_jugada != '' AND ultima_jugada != 'PARTIDO_FINALIZADO'"
                    )
                    for row in rows:
                        pid, uj = row["id"], row["ultima_jugada"]
                        if uj:
                            pre_reload_hashes[pid] = uj
                            n_partidos_activos += 1
                except Exception as e_hash:
                    logging.warning(f"No se pudieron capturar hashes pre-reload: {e_hash}")

                # Crear nuevo scraper DESDE CERO (sin estado previo)
                logging.info(f"🆕 Creando nuevo scraper desde cero ({n_partidos_activos} partidos en silencio inteligente)...")
                self.scraper = FootballScraper(self.db, self._scraper_callback)
                # Pasar los hashes pre-reload al scraper para silencio inteligente partido a partido
                self.scraper.pre_reload_hashes = pre_reload_hashes
                self.scraper.start()

                # Limpiar cola de mensajes pendientes
                if self.message_queue:
                    logging.info(f"🗑️ Limpiando {len(self.message_queue)} mensajes pendientes post-reload")
                    self.message_queue.clear()

                self.send_private(nick, "✅ Código recargado. Sistema reiniciado desde cero.")
                self.send_private(nick, f"🔍 Silencio inteligente activo en {n_partidos_activos} partido(s) — se romperá automáticamente al detectar eventos nuevos.")
                # Anunciar el reload en el canal de debug
                self.send_message(Config.CANAL_DEBUG, f"🔄 RELOAD ejecutado por {nick} — Silencio inteligente en {n_partidos_activos} partido(s). Se romperá solo cuando aparezca un evento nuevo en cada partido.")
                logging.info(f"🔄 Hot-reload con reinicio completo ejecutado por {nick}")
                
            except Exception as e:
                self.send_private(nick, f"❌ Error en reload: {str(e)[:100]}")
                logging.error(f"Error en hot-reload: {e}", exc_info=True)
                
                # Intentar restaurar scraper
                if not self.scraper or not self.scraper.running:
                    try:
                        self.scraper = FootballScraper(self.db, self._scraper_callback)
                        self.scraper.start()
                        self.send_private(nick, "⚠️ Scraper restaurado desde cero")
                    except:
                        pass
            
            return
        
        # -------- Live/EnVivo (listar partidos en directo y próximos) --------
        if cmd == "live" or cmd == "envivo" or cmd == "directo":
            if not self.scraper:
                self.send_private(nick, "❌ Scraper no está activo")
                return
            
            partidos_activos = self.scraper.partidos_activos
            
            if not partidos_activos:
                self.send_private(nick, "📭 No hay partidos en seguimiento actualmente")
                return
            
            # Clasificar usando datos de partidos_activos (más fiables y completos)
            en_vivo = []
            proximos = []
            separador = "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬"
            
            for partido_id, info in partidos_activos.items():
                local     = info.get('local', '')
                visitante = info.get('visitante', '')
                liga      = info.get('liga', '')
                color     = info.get('color', '03')
                marcador  = info.get('marcador', '0 - 0')
                parte     = info.get('parte', '')
                
                if not local or not visitante:
                    nombre_fallback = partido_id.replace('_', ' vs ').replace('-', ' ').title()
                    local = nombre_fallback
                    visitante = ''
                
                liga_fmt = f"\x03{color}«{liga}»\x03" if liga else ""
                
                # Mapear parte interna a texto legible
                partes_texto = {
                    '1ª': '1ª Parte', '2ª': '2ª Parte',
                    'Descanso': 'Descanso', 'Des PRO': 'Descanso Prórroga',
                    '1ª PRO': '1ª Prórroga', '2ª PRO': '2ª Prórroga',
                }
                parte_display = partes_texto.get(parte, parte)
                
                if parte and parte not in ('', 'Próximo'):
                    # Partido en juego
                    if visitante:
                        linea = f"  {liga_fmt} {local} {marcador} {visitante} ({parte_display})"
                    else:
                        linea = f"  {liga_fmt} {local} ({parte_display})"
                    en_vivo.append(linea)
                else:
                    # Partido próximo
                    if visitante:
                        linea = f"  {liga_fmt} {local} vs {visitante}"
                    else:
                        linea = f"  {liga_fmt} {local}"
                    proximos.append(linea)
            
            self.send_private(nick, f"⚽ Partidos en seguimiento ({len(partidos_activos)}):")
            self.send_private(nick, separador)
            
            # Mostrar en vivo
            if en_vivo:
                self.send_private(nick, f"🔴 EN DIRECTO ({len(en_vivo)}):")
                for linea in en_vivo:
                    self.send_private(nick, linea)
            
            # Mostrar próximos
            if proximos:
                self.send_private(nick, f"📅 PRÓXIMOS ({len(proximos)}):")
                for linea in proximos:
                    self.send_private(nick, linea)
            
            return
        
        # -------- Partido (solo root/admin) --------
        if cmd == "partido" or cmd == "partidos":
            if not (is_admin or is_root):
                self.send_private(nick, "⛔ Solo admins/root pueden configurar partidos")
                return
            
            partidos = self.db.list_partidos_filtro()
            
            if not args:
                # Error de sintaxis - mostrar uso
                self.send_private(nick, "❌ Error de sintaxis")
                self.send_private(nick, "Uso: partido <add|del|list|all>")
                self.send_private(nick, "  partido add <local> <visitante> - Agrega partido")
                self.send_private(nick, "  partido del #id - Elimina partido")
                self.send_private(nick, "  partido list - Lista partidos")
                self.send_private(nick, "  partido all - Narra todos")
                self.send_private(nick, "ℹ️ Los partidos se auto-eliminan al finalizar")
                return
            
            subcmd = args[0].lower()
            
            if subcmd == "add":
                if len(args) < 3:
                    self.send_private(nick, "❌ Error de sintaxis")
                    self.send_private(nick, "Uso: partido add <local> <visitante>")
                    self.send_private(nick, "Ejemplo: partido add Real Madrid Barcelona")
                    return
                
                # Buscar los dos equipos - pueden tener espacios en sus nombres
                # Estrategia: dividir args[1:] a la mitad aproximadamente
                palabras = args[1:]
                
                # Intentar detectar si hay un separador explícito (vs, -, contra)
                texto_completo = " ".join(palabras)
                separadores = [' vs ', ' VS ', ' Vs ', ' contra ', ' - ']
                equipo_local = None
                equipo_visitante = None
                
                for sep in separadores:
                    if sep in texto_completo:
                        partes = texto_completo.split(sep, 1)
                        if len(partes) == 2:
                            equipo_local = partes[0].strip()
                            equipo_visitante = partes[1].strip()
                            break
                
                # Si no hay separador, dividir a la mitad
                if not equipo_local or not equipo_visitante:
                    mitad = len(palabras) // 2
                    if mitad < 1:
                        mitad = 1
                    equipo_local = " ".join(palabras[:mitad])
                    equipo_visitante = " ".join(palabras[mitad:])
                
                if not equipo_local or not equipo_visitante:
                    self.send_private(nick, "❌ Formato incorrecto. Usa: partido add <local> <visitante>")
                    self.send_private(nick, "Ejemplo: partido add Real Madrid Barcelona")
                    return
                
                # Buscar el partido en la web para obtener la liga
                self.send_private(nick, f"🔍 Buscando {equipo_local} vs {equipo_visitante}...")
                liga_encontrada = None
                
                if self.scraper:
                    liga_encontrada = self.scraper.buscar_partido_en_web(equipo_local, equipo_visitante)
                
                # Agregar partido al filtro con la liga (si se encontró)
                if self.db.add_partido_filtro(equipo_local, equipo_visitante, nick, liga_encontrada):
                    if liga_encontrada:
                        # Obtener color de la liga
                        color_liga = self.scraper._obtener_color_liga(liga_encontrada) if self.scraper else "14"
                        liga_formato = f"\x03{color_liga}«{liga_encontrada}»\x03"
                        self.send_private(nick, f"✅ Partido agregado: {equipo_local} vs {equipo_visitante}")
                        self.send_private(nick, f"📋 Liga: {liga_formato}")
                    else:
                        self.send_private(nick, f"✅ Partido agregado: {equipo_local} vs {equipo_visitante}")
                        self.send_private(nick, f"⚠️ Liga no encontrada (se buscará al detectar el partido)")
                    
                    partidos_actuales = self.db.list_partidos_filtro()
                    self.send_private(nick, f"📊 Total partidos en filtro: {len(partidos_actuales)}")
                else:
                    self.send_private(nick, f"⚠️ El partido ya existe en el filtro")
            
            elif subcmd == "del" or subcmd == "remove":
                if len(args) < 2:
                    self.send_private(nick, "Uso: partido del <#id> o partido del <local> <visitante>")
                    return
                
                # Verificar si es un ID (#1, #2, etc)
                if args[1].startswith('#'):
                    try:
                        filtro_id = int(args[1][1:])
                        if self.db.del_partido_filtro_por_id(filtro_id):
                            self.send_private(nick, f"✅ Partido #{filtro_id} eliminado")
                        else:
                            self.send_private(nick, f"❌ Partido #{filtro_id} no encontrado")
                        return
                    except ValueError:
                        pass
                
                # Intentar parsear como "local visitante"
                palabras = args[1:]
                texto_completo = " ".join(palabras)
                separadores = [' vs ', ' VS ', ' Vs ', ' contra ', ' - ']
                equipo_local = None
                equipo_visitante = None
                
                for sep in separadores:
                    if sep in texto_completo:
                        partes = texto_completo.split(sep, 1)
                        if len(partes) == 2:
                            equipo_local = partes[0].strip()
                            equipo_visitante = partes[1].strip()
                            break
                
                # Si no hay separador, dividir a la mitad
                if not equipo_local or not equipo_visitante:
                    if len(palabras) >= 2:
                        mitad = len(palabras) // 2
                        if mitad < 1:
                            mitad = 1
                        equipo_local = " ".join(palabras[:mitad])
                        equipo_visitante = " ".join(palabras[mitad:])
                
                if equipo_local and equipo_visitante:
                    if self.db.del_partido_filtro(equipo_local, equipo_visitante):
                        self.send_private(nick, f"✅ Partido eliminado: {equipo_local} vs {equipo_visitante}")
                    else:
                        self.send_private(nick, f"❌ Partido no encontrado")
                else:
                    self.send_private(nick, "❌ Formato incorrecto. Usa: partido del #id o partido del <local> <visitante>")
            
            elif subcmd == "all" or subcmd == "clear" or subcmd == "todos":
                cantidad = len(partidos)
                self.db.clear_partidos_filtro()
                if cantidad > 0:
                    self.send_private(nick, f"✅ Lista limpiada ({cantidad} partidos eliminados)")
                self.send_private(nick, "📢 Ahora narrando TODOS los partidos")
            
            elif subcmd == "list" or subcmd == "lista":
                if partidos:
                    self.send_private(nick, f"⚽ Narrando {len(partidos)} partidos:")
                    for registro in partidos:
                        # Soportar tanto formato nuevo (5 campos con liga) como viejo (4 campos sin liga)
                        if len(registro) == 5:
                            filtro_id, local, visitante, agregado_por, liga = registro
                        else:
                            filtro_id, local, visitante, agregado_por = registro
                            liga = None
                        
                        if liga:
                            # Obtener color de la liga
                            color_liga = self.scraper._obtener_color_liga(liga) if self.scraper else "14"
                            liga_formato = f"\x03{color_liga}«{liga}»\x03"
                            self.send_private(nick, f"  #{filtro_id}. {local} vs {visitante} {liga_formato}")
                        else:
                            self.send_private(nick, f"  #{filtro_id}. {local} vs {visitante}")
                else:
                    self.send_private(nick, "✅ Narrando TODOS los partidos")
            
            else:
                self.send_private(nick, "Uso: partido add|del|list|all")
                self.send_private(nick, "Ejemplo: partido add Real Madrid vs Barcelona")
            
            return
        
        # -------- REGISTRO DE USUARIOS (Alta/Baja) --------
        if cmd == "alta" or cmd == "registro" or cmd == "registrar":
            # Verificar si está prohibido
            if self.db.usuario_forbid(nick):
                self.send_private(nick, " 2«MaLe4FiCo2» Usted tiene prohibida la utilización de este servicio")
                return
            
            # Verificar si ya está registrado
            if self.db.usuario_registrado(nick):
                usuario = self.db.get_usuario(nick)
                fecha = usuario[3] if usuario and len(usuario) > 3 else "desconocida"
                self.send_private(nick, f" 2«MaLe4FiCo2» Usted ya está registrado desde el \x0312{fecha}\x03")
                return
            
            # Registrar usuario
            if self.db.registrar_usuario(nick):
                self.send_private(nick, " 2«MaLe4FiCo2» Usted ha sido registrado correctamente en la base de datos.")
                # Notificar en canal de fútbol
                self.send_message(Config.CANAL_FUTBOL, f" 2«MaLe4FiCo2» El nick \x0312{nick}\x03 acaba de registrarse en la base de datos.")
            else:
                self.send_private(nick, " 2«MaLe4FiCo2» Error al registrarse")
            return
        
        if cmd == "baja" or cmd == "desregistrar":
            # Verificar si está registrado
            if not self.db.usuario_registrado(nick):
                self.send_private(nick, " 2«MaLe4FiCo2» Usted no está registrado.")
                return
            
            # Dar de baja
            if self.db.baja_usuario(nick):
                self.send_private(nick, " 2«MaLe4FiCo2» Usted ha sido eliminado correctamente de la base de datos.")
                self.send_message(Config.CANAL_FUTBOL, f" 2«MaLe4FiCo2» El nick \x0312{nick}\x03 acaba de darse de baja en la base de datos.")
            else:
                self.send_private(nick, " 2«MaLe4FiCo2» Error al darse de baja")
            return
        
        if cmd == "puntos" or cmd == "mispuntos":
            if not self.db.usuario_registrado(nick):
                self.send_private(nick, " 2«MaLe4FiCo2» No estás registrado. Usa \x0312alta\x03 para registrarte.")
                return
            
            usuario = self.db.get_usuario(nick)
            puntos = usuario[2] if usuario and len(usuario) > 2 else 0
            self.send_private(nick, f" 2«MaLe4FiCo2» Tienes \x0303{puntos}\x03 puntos")
            return
        
        # -------- FORBID (root o fundador) --------
        if cmd == "forbid":
            if not is_root and not is_fundador:
                self.send_private(nick, "⛔ Solo ROOT puede gestionar usuarios prohibidos")
                return
            
            if not args:
                self.send_private(nick, "Uso: forbid add|del|list [nick] [motivo]")
                return
            
            subcmd = args[0].lower()
            
            if subcmd == "add":
                if len(args) < 2:
                    self.send_private(nick, "Uso: forbid add <nick> [motivo]")
                    return
                target_nick = args[1]
                motivo = " ".join(args[2:]) if len(args) > 2 else "Sin motivo"
                if self.db.forbid_usuario(target_nick, motivo, nick):
                    self.send_private(nick, f"✅ Usuario {target_nick} prohibido")
                else:
                    self.send_private(nick, f"❌ Error prohibiendo usuario")
            
            elif subcmd == "del":
                if len(args) < 2:
                    self.send_private(nick, "Uso: forbid del <nick>")
                    return
                target_nick = args[1]
                if self.db.unforbid_usuario(target_nick):
                    self.send_private(nick, f"✅ Prohibición de {target_nick} eliminada")
                else:
                    self.send_private(nick, f"❌ Usuario no estaba prohibido")
            
            elif subcmd == "list":
                with self.db.lock:
                    self.db.cursor.execute("SELECT nick, motivo FROM usuarios_forbid")
                    forbids = self.db.cursor.fetchall()
                if forbids:
                    self.send_private(nick, f"🚫 Usuarios prohibidos ({len(forbids)}):")
                    for f_nick, f_motivo in forbids:
                        self.send_private(nick, f"  • {f_nick}: {f_motivo}")
                else:
                    self.send_private(nick, "✅ No hay usuarios prohibidos")
            
            return
        
        # -------- PORRAS --------
        if cmd == "porra":
            if not args:
                self.send_private(nick, " 2«MaLe4FiCo2» Sintaxis: \x0312porra <apuesta/ver/estado>\x03")
                return
            
            subcmd = args[0].lower()
            porra = self.db.get_porra_activa()
            
            # Comandos de admin (solo root/admin)
            if subcmd == "add" or subcmd == "crear":
                if not (is_admin or is_root):
                    self.send_private(nick, "⛔ Solo admins pueden crear porras")
                    return
                
                if porra:
                    self.send_private(nick, " 2«MaLe4FiCo2» Ya hay una porra activa, no se pueden abrir más")
                    return
                
                if len(args) < 4:
                    self.send_private(nick, "Uso: porra add <equipo_local> vs <equipo_visitante> <premio>")
                    return
                
                # Parsear equipos y premio
                texto = " ".join(args[1:])
                # Buscar "vs" o "-" como separador
                for sep in [' vs ', ' VS ', ' - ']:
                    if sep in texto:
                        partes = texto.split(sep, 1)
                        equipo_local = partes[0].strip()
                        resto = partes[1].strip().rsplit(' ', 1)
                        if len(resto) == 2 and resto[1].isdigit():
                            equipo_visitante = resto[0].strip()
                            premio = int(resto[1])
                        else:
                            self.send_private(nick, "Uso: porra add <equipo_local> vs <equipo_visitante> <premio>")
                            return
                        break
                else:
                    self.send_private(nick, "Uso: porra add <equipo_local> vs <equipo_visitante> <premio>")
                    return
                
                if self.db.crear_porra("", equipo_local, equipo_visitante, premio, nick):
                    self.send_private(nick, f" 2«MaLe4FiCo2» Porra creada: \x0312{equipo_local}\x03 vs \x0312{equipo_visitante}\x03 - Premio: \x0303{premio}\x03 puntos")
                    self.send_private(nick, "Usa \x0312porra anuncio\x03 para anunciarla")
                else:
                    self.send_private(nick, "❌ Error creando porra")
                return
            
            elif subcmd == "anuncio" or subcmd == "anunciar":
                if not (is_admin or is_root):
                    self.send_private(nick, "⛔ Solo admins pueden anunciar porras")
                    return
                
                if not porra:
                    self.send_private(nick, " 2«MaLe4FiCo2» No hay ninguna porra disponible")
                    return
                
                equipo_local = porra[2]
                equipo_visitante = porra[3]
                estado = porra[5]
                
                if estado == "ABIERTA":
                    for canal in self.db.get_canales_narracion_activa():
                        self.send_message(canal, f" 2«MaLe4FiCo2» La porra para el partido \x0312{equipo_local}\x03 - \x0312{equipo_visitante}\x03 está \x0303ABIERTA\x03, para apostar: \x0312porra apuesta <resultado>\x03")
                else:
                    for canal in self.db.get_canales_narracion_activa():
                        self.send_message(canal, f" 2«MaLe4FiCo2» La porra para el partido \x0312{equipo_local}\x03 - \x0312{equipo_visitante}\x03 está \x0304CERRADA\x03, no se puede apostar.")
                return
            
            elif subcmd == "abrir":
                if not (is_admin or is_root):
                    self.send_private(nick, "⛔ Solo admins pueden abrir porras")
                    return
                
                if not porra:
                    self.send_private(nick, " 2«MaLe4FiCo2» No hay ninguna porra disponible")
                    return
                
                if porra[5] == "ABIERTA":
                    self.send_private(nick, " 2«MaLe4FiCo2» La porra ya está abierta")
                    return
                
                if self.db.abrir_porra():
                    equipo_local = porra[2]
                    equipo_visitante = porra[3]
                    for canal in self.db.get_canales_narracion_activa():
                        self.send_message(canal, f" 2«MaLe4FiCo2» Se acaba de abrir la porra para el partido: \x0312{equipo_local}\x03 - \x0312{equipo_visitante}\x03 para apostar: \x0312porra apuesta <resultado>\x03")
                return
            
            elif subcmd == "cerrar":
                if not (is_admin or is_root):
                    self.send_private(nick, "⛔ Solo admins pueden cerrar porras")
                    return
                
                if not porra:
                    self.send_private(nick, " 2«MaLe4FiCo2» No hay ninguna porra disponible")
                    return
                
                if porra[5] != "ABIERTA":
                    self.send_private(nick, " 2«MaLe4FiCo2» La porra ya está cerrada")
                    return
                
                if self.db.cerrar_porra():
                    equipo_local = porra[2]
                    equipo_visitante = porra[3]
                    for canal in self.db.get_canales_narracion_activa():
                        self.send_message(canal, f" 2«MaLe4FiCo2» Se acaba de cerrar la porra para el partido: \x0312{equipo_local}\x03 - \x0312{equipo_visitante}\x03, desde este momento NO se puede apostar.")
                return
            
            elif subcmd == "del" or subcmd == "eliminar":
                if not (is_admin or is_root):
                    self.send_private(nick, "⛔ Solo admins pueden eliminar porras")
                    return
                
                if not porra:
                    self.send_private(nick, " 2«MaLe4FiCo2» No hay ninguna porra disponible")
                    return
                
                if self.db.eliminar_porra(porra[0]):
                    self.send_private(nick, f" 2«MaLe4FiCo2» Porra eliminada correctamente")
                return
            
            elif subcmd == "info":
                if not porra:
                    self.send_private(nick, " 2«MaLe4FiCo2» No hay ninguna porra disponible")
                    return
                
                equipo_local = porra[2]
                equipo_visitante = porra[3]
                premio = porra[4]
                estado = porra[5]
                creado_por = porra[6]
                fecha = porra[7]
                
                self.send_private(nick, " 2«MaLe4FiCo2» Información de la porra:")
                estado_color = "\x0303ABIERTA\x03" if estado == "ABIERTA" else "\x0304CERRADA\x03"
                self.send_private(nick, f"  Estado: {estado_color}")
                self.send_private(nick, f"  Local: \x0312{equipo_local}\x03")
                self.send_private(nick, f"  Visitante: \x0312{equipo_visitante}\x03")
                self.send_private(nick, f"  Premio: \x0303{premio}\x03 puntos")
                self.send_private(nick, f"  Creada por: \x0312{creado_por}\x03")
                self.send_private(nick, f"  Fecha: \x0314{fecha}\x03")
                
                # Contar apuestas
                apuestas = self.db.get_apuestas_porra(porra[0])
                self.send_private(nick, f"  Apuestas: \x0303{len(apuestas)}\x03")
                return
            
            elif subcmd == "ver":
                if not porra:
                    self.send_private(nick, " 2«MaLe4FiCo2» No hay ninguna porra disponible")
                    return
                
                # Ver apuesta propia o de otro (admin)
                if len(args) > 1 and (is_admin or is_root):
                    target_nick = args[1]
                else:
                    target_nick = nick
                
                apuesta = self.db.get_apuesta(porra[0], target_nick)
                if apuesta:
                    goles_local = apuesta[3]
                    goles_visitante = apuesta[4]
                    self.send_private(nick, f" 2«MaLe4FiCo2» Apuesta de \x0312{target_nick}\x03: \x0303{goles_local}-{goles_visitante}\x03")
                else:
                    if target_nick == nick:
                        self.send_private(nick, " 2«MaLe4FiCo2» No has realizado ninguna apuesta")
                    else:
                        self.send_private(nick, f" 2«MaLe4FiCo2» El usuario \x0312{target_nick}\x03 no ha apostado")
                return
            
            elif subcmd == "borrar" and (is_admin or is_root):
                if not porra:
                    self.send_private(nick, " 2«MaLe4FiCo2» No hay ninguna porra disponible")
                    return
                
                if len(args) < 2:
                    self.send_private(nick, "Uso: porra borrar <nick>")
                    return
                
                target_nick = args[1]
                if self.db.eliminar_apuesta(porra[0], target_nick):
                    self.send_private(nick, f" 2«MaLe4FiCo2» Apuesta de \x0312{target_nick}\x03 eliminada")
                else:
                    self.send_private(nick, f" 2«MaLe4FiCo2» El usuario \x0312{target_nick}\x03 no ha apostado")
                return
            
            elif subcmd == "resultado" and (is_admin or is_root):
                if not porra:
                    self.send_private(nick, " 2«MaLe4FiCo2» No hay ninguna porra disponible")
                    return
                
                if len(args) < 2 or '-' not in args[1]:
                    self.send_private(nick, "Uso: porra resultado <X-Y>")
                    return
                
                try:
                    partes = args[1].split('-')
                    goles_local = int(partes[0])
                    goles_visitante = int(partes[1])
                except:
                    self.send_private(nick, "Formato incorrecto. Usa: porra resultado 2-1")
                    return
                
                equipo_local = porra[2]
                equipo_visitante = porra[3]
                premio = porra[4]
                
                # Buscar ganadores
                ganadores = self.db.get_ganadores_porra(porra[0], goles_local, goles_visitante)
                
                # Anunciar resultado en todos los canales
                for canal in self.db.get_canales_narracion_activa():
                    self.send_message(canal, f" 2«MaLe4FiCo2» Resultado final: \x0312{equipo_local}\x03 \x0304{goles_local}\x03 - \x0304{goles_visitante}\x03 \x0312{equipo_visitante}\x03")
                    time.sleep(0.3)
                    
                    if ganadores:
                        premio_individual = premio // len(ganadores) if len(ganadores) > 0 else premio
                        # Dar puntos a ganadores
                        for ganador in ganadores:
                            self.db.add_puntos_usuario(ganador, premio_individual)
                        
                        # Anunciar cada ganador con ACTION (/me)
                        for ganador in ganadores:
                            self.send_action(canal, f"en el partido \x0312{equipo_local}\x03 vs \x0312{equipo_visitante}\x03 ha acertado \x0303{ganador}\x03 ... \x0304¡¡¡FELICIDADES!!!\x03 (+{premio_individual} puntos)")
                            time.sleep(0.5)
                    else:
                        self.send_message(canal, f" 2«MaLe4FiCo2» \x0304Nadie acertó el resultado\x03")
                
                # Finalizar porra
                self.db.finalizar_porra(porra[0])
                self.send_private(nick, "✅ Porra finalizada")
                return
            
            # Comandos de usuario
            elif subcmd == "apuesta" or subcmd == "apostar":
                # Verificar registro
                if not self.db.usuario_registrado(nick):
                    self.send_private(nick, f" 2«MaLe4FiCo2» \x0312{nick}\x03 no estás registrado, para hacerlo usa \x0312alta\x03")
                    return
                
                if not porra:
                    self.send_private(nick, " 2«MaLe4FiCo2» No hay ninguna porra disponible para apostar")
                    return
                
                if porra[5] != "ABIERTA":
                    self.send_private(nick, " 2«MaLe4FiCo2» La porra está cerrada, no se puede apostar")
                    return
                
                # Verificar si ya apostó
                if self.db.get_apuesta(porra[0], nick):
                    self.send_private(nick, " 2«MaLe4FiCo2» Usted ya ha apostado, no puede volver a apostar")
                    return
                
                if len(args) < 2:
                    self.send_private(nick, " 2«MaLe4FiCo2» Sintaxis: \x0312porra apuesta <resultado>\x03 (Ejemplo: porra apuesta 2-1)")
                    return
                
                if '-' not in args[1]:
                    self.send_private(nick, " 2«MaLe4FiCo2» La apuesta no es válida. Formato: X-Y")
                    return
                
                try:
                    partes = args[1].split('-')
                    goles_local = int(partes[0])
                    goles_visitante = int(partes[1])
                except:
                    self.send_private(nick, " 2«MaLe4FiCo2» La apuesta no es válida. Formato: X-Y")
                    return
                
                if self.db.crear_apuesta(porra[0], nick, goles_local, goles_visitante):
                    self.send_private(nick, f" 2«MaLe4FiCo2» \x0312{nick}\x03 tu apuesta \x0303{goles_local}-{goles_visitante}\x03 ha sido registrada")
                    self.send_message(Config.CANAL_FUTBOL, f" 2«MaLe4FiCo2» \x0312{nick}\x03 ha realizado una APUESTA de \x0303{goles_local}-{goles_visitante}\x03")
                else:
                    self.send_private(nick, " 2«MaLe4FiCo2» Error al registrar apuesta")
                return
            
            elif subcmd == "estado":
                if not porra:
                    self.send_private(nick, " 2«MaLe4FiCo2» No hay ninguna porra disponible")
                    return
                
                equipo_local = porra[2]
                equipo_visitante = porra[3]
                estado = porra[5]
                estado_color = "\x0303ABIERTA\x03" if estado == "ABIERTA" else "\x0304CERRADA\x03"
                self.send_private(nick, f" 2«MaLe4FiCo2» La porra para el partido: \x0312{equipo_local}\x03 - \x0312{equipo_visitante}\x03 está {estado_color}")
                return
            
            else:
                self.send_private(nick, " 2«MaLe4FiCo2» Subcomando no reconocido. Usa: apuesta, ver, estado")
            
            return
        
        # Comando no reconocido
        if is_private:
            self.send_private(nick, f"⛔ Comando '{cmd}' no reconocido. Usa 'help' para ver comandos")
    
    def _force_scan(self):
        """Fuerza un escaneo inmediato de partidos"""
        try:
            if self.scraper:
                self.scraper._buscar_partidos()
                partidos = len(self.scraper.partidos_activos)
                for partido_id in list(self.scraper.partidos_activos.keys())[:10]:  # Revisar primeros 10
                    self.scraper._revisar_partido(partido_id)
                    time.sleep(1)
                logging.info(f"✅ Scan completado: {partidos} partidos en seguimiento")
        except Exception as e:
            logging.error(f"Error en scan forzado: {e}")
    
    # -------- Manejo de KICK y BAN --------
    def _handle_kick(self, msg):
        """Maneja cuando nos echan de un canal con KICK (legacy, usado desde _on_kick_event)"""
        pass  # La lógica está en _on_kick_event

    def _handle_ban(self, msg):
        """Maneja cuando nos ponen BAN en un canal (llamado desde _on_mode_event)"""
        try:
            parts = msg.split()
            if len(parts) >= 5 and "+b" in msg:
                banner   = parts[0][1:].split('!')[0] if '!' in parts[0] else parts[0][1:]
                canal    = parts[2]
                mascara  = parts[4] if len(parts) > 4 else "desconocida"
                if mascara.startswith(':'):
                    mascara = mascara[1:]

                my_nick = Config.IRC_NICK.lower()
                my_user = Config.IRC_USER.lower()
                my_host = getattr(self, 'my_host', '').lower()

                mascara_lower = mascara.lower()

                if '!' in mascara_lower and '@' in mascara_lower:
                    mask_nick = mascara_lower.split('!')[0]
                    mask_rest = mascara_lower.split('!')[1]
                    mask_user = mask_rest.split('@')[0]
                    mask_host = mask_rest.split('@')[1]
                elif '@' in mascara_lower:
                    mask_nick = '*'
                    mask_user = mascara_lower.split('@')[0]
                    mask_host = mascara_lower.split('@')[1]
                else:
                    mask_nick = mascara_lower
                    mask_user = '*'
                    mask_host = '*'

                def match_wildcard(pattern, text):
                    if pattern == '*': return True
                    if not text:       return False
                    if '*' not in pattern: return pattern == text
                    if pattern.startswith('*') and pattern.endswith('*'):
                        return pattern[1:-1] in text
                    elif pattern.startswith('*'): return text.endswith(pattern[1:])
                    elif pattern.endswith('*'):   return text.startswith(pattern[:-1])
                    return pattern == text

                host_match = match_wildcard(mask_host, my_host) if my_host else (mask_host == '*')
                if match_wildcard(mask_nick, my_nick) and match_wildcard(mask_user, my_user) and host_match:
                    logging.warning(f"🚫 BAN en {canal} por {banner}: {mascara}")
                    self.send_message(Config.CANAL_DEBUG, f"🚫 Me han baneado en {canal} por {banner}: {mascara}")
        except Exception as e:
            logging.error(f"Error procesando BAN: {e}")

    # -------- Loop principal --------
    def run(self):
        """Loop principal del bot — irc.client corre en thread daemon"""
        logging.info("🤖 Iniciando bot...")
        irc.client.ServerConnection.buffer_class = buffer.LenientDecodingLineBuffer

        # Conexión inicial
        if not self.connect():
            logging.error("❌ No se pudo conectar. Abortando.")
            return

        # El reactor corre en su propio thread daemon (process_forever)
        # La reconexión se dispara automáticamente desde _on_disconnect
        threading.Thread(target=self.reactor.process_forever, daemon=True).start()

        # Loop principal: solo procesa la cola de mensajes del scraper
        try:
            while self.running:
                if self.identified:
                    self._process_message_queue()
                time.sleep(0.1)
        except KeyboardInterrupt:
            logging.info("\n⚠️ Interrupción de teclado detectada")
            self.shutdown()

    # -------- Apagar bot --------
    def shutdown(self):
        """Apaga el bot de forma ordenada"""
        logging.info("👋 Apagando bot...")
        self.running = False

        if self.scraper:
            self.scraper.stop()

        if self.connected and self.connection:
            try:
                self.send_raw(f"PART {Config.CANAL_FUTBOL} :Bot apagándose")
                if Config.CANAL_DEBUG != Config.CANAL_FUTBOL:
                    self.send_raw(f"PART {Config.CANAL_DEBUG} :Bot apagándose")
                for canal, _, _ in self.db.list_canales():
                    self.send_raw(f"PART {canal} :Bot apagándose")
                time.sleep(0.5)
                self.connection.quit("Bot apagándose")
                time.sleep(0.5)
            except:
                pass

        self.db.close()
        logging.info("✅ Bot apagado correctamente")

# ============================ EJECUCIÓN ============================
if __name__ == "__main__":
    try:
        import requests
        from bs4 import BeautifulSoup
        import irc.client
        from jaraco.stream import buffer
    except ImportError as e:
        print(f"❌ Error: Faltan dependencias — {e}")
        print("Instala con: pip install requests beautifulsoup4 irc jaraco.stream --break-system-packages")
        exit(1)

    bot = MircBot()
    try:
        bot.run()
    except Exception as e:
        logging.error(f"Error fatal: {e}", exc_info=True)
    finally:
        bot.shutdown()