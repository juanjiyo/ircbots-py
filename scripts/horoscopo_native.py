import requests
import re
import html
import textwrap
import traceback
from datetime import datetime
import eggdrop.tcl as tcl
from eggdrop import bind

VERSION = "4.7"
# URLs corregidas: escorpio en lugar de escorpion
SIGNS = ["aries", "tauro", "geminis", "cancer", "leo", "virgo", "libra", "escorpio", "sagitario", "capricornio", "acuario", "piscis"]
DEBUG_CHAN = "#Limbo"

def get_horoscope(sign):
    url = f"https://www.hola.com/horoscopo/{sign}/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "es-ES,es;q=0.9"
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        
        # Asegurar decodificación correcta
        r.encoding = 'utf-8'
        content = r.text
        
        # Estrategia robusta: Extraer todos los párrafos del cuerpo del artículo
        body_match = re.search(r'<div class="(?:ho-)?article-body"[^>]*>(.*?)</div>', content, re.DOTALL | re.IGNORECASE)
        if not body_match:
            body_match = re.search(r'<div class="article-body"[^>]*>(.*?)</div>', content, re.DOTALL | re.IGNORECASE)

        raw_text = ""
        if body_match:
            body_content = body_match.group(1)
            paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', body_content, re.DOTALL)
            clean_paragraphs = []
            for p in paragraphs:
                txt = re.sub(r'<[^>]+>', '', p).strip()
                if txt: clean_paragraphs.append(txt)
            raw_text = " ".join(clean_paragraphs)
        
        # Si falló, intentar patrones antiguos
        if not raw_text:
            patterns = [
                rf'<h[1-3][^>]*>.*?{sign}.*?</h[1-3]>.*?<p[^>]*>(.*?)</p>',
                rf'<h[1-3][^>]*>.*?hoy.*?</h[1-3]>.*?<p[^>]*>(.*?)</p>'
            ]
            for pattern in patterns:
                m = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
                if m:
                    raw_text = re.sub(r'<[^>]+>', '', m.group(1))
                    break

        if raw_text:
            final_text = html.unescape(raw_text).strip()
            # Limpiar prefijos de fecha
            meses = "enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre"
            all_sign_names = "|".join(SIGNS)
            
            # Patrón preciso: Signo + hoy + día + de + mes
            regex_fecha = rf'^(?:{all_sign_names})\s+hoy\s+\d{{1,2}}\s+de\s+(?:{meses})(?:\s+de\s+\d{{4}})?'
            final_text = re.sub(regex_fecha, '', final_text, flags=re.IGNORECASE).strip()
            
            # También limpiar si solo empieza con "hoy [fecha]"
            regex_hoy = rf'^hoy\s+\d{{1,2}}\s+de\s+(?:{meses})(?:\s+de\s+\d{{4}})?'
            final_text = re.sub(regex_hoy, '', final_text, flags=re.IGNORECASE).strip()
            
            return final_text

        return None
    except Exception as e:
        tcl.putlog(f"Error Scraper ({sign}): {str(e)}")
    return None

def horoscopo_handler(nick, host, hand, chan, text, **kwargs):
    """Manejador para !horoscopo [signo]"""
    try:
        words = text.split()
        if len(words) < 1: return
        sign = words[0].lower()
        if sign == "escorpion": sign = "escorpio"
        
        if sign in SIGNS:
            process_sign(chan, sign)
        else:
            tcl.putserv(f"PRIVMSG {chan} :Uso: !horoscopo <signo> (ej: !aries)")
    except Exception:
        log_crash()

def sign_direct_handler(nick, host, hand, chan, text, **kwargs):
    """Manejador para !aries, !tauro, etc."""
    try:
        # El comando ejecutado está en kwargs['cmd'] o podemos sacarlo del trigger
        # Pero en Eggdrop Python bind("pub", ...), el comando no viene directo en text.
        # Necesitamos saber qué comando disparó esto. 
        # Si registramos un handler por signo, es más fácil.
        pass
    except Exception:
        log_crash()

def process_sign(chan, sign):
    data = get_horoscope(sign)
    date = datetime.now().strftime("%d-%m-%Y")
    if data:
        display_name = sign.capitalize()
        if sign == "escorpio": display_name = "Escorpión"
        tcl.putserv(f"PRIVMSG {chan} :\x0306[Horóscopo]\x03 \x02{display_name}\x02 (\x02{date}\x02):")
        for chunk in textwrap.wrap(data, 420):
            tcl.putserv(f"PRIVMSG {chan} :{chunk}")
    else:
        tcl.putserv(f"PRIVMSG {chan} :No pude extraer la predicción de \x02{sign}\x02.")

def log_crash():
    error_info = traceback.format_exc()
    tcl.putlog(f"CRASH FATAL en Python:\n{error_info}")
    try:
        last_line = error_info.splitlines()[-1]
        tcl.putserv(f"PRIVMSG {DEBUG_CHAN} :\x0304[CRASH PYTHON]\x03 {last_line}")
    except: pass

# -------------------------------------------------------------------------
# BINDS (ENLACES)
# -------------------------------------------------------------------------

# 1. Comando general !horoscopo y .horoscopo
bind("pub", "*", "!horoscopo", horoscopo_handler)
bind("pub", "*", ".horoscopo", horoscopo_handler)

# 2. Binds directos para cada signo (ej: !aries, .aries)
def make_sign_handler(s):
    return lambda n, h, ha, c, t, **k: process_sign(c, s)

for sign in SIGNS:
    handler = make_sign_handler(sign)
    bind("pub", "*", f"!{sign}", handler)
    bind("pub", "*", f".{sign}", handler)
    if sign == "escorpio":
        bind("pub", "*", "!escorpion", handler)
        bind("pub", "*", ".escorpion", handler)

tcl.putlog(f"Horóscopo v{VERSION} (Optimized) cargado. Binds específicos activos.")
