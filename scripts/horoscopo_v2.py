import eggdrop.tcl as tcl
from eggdrop import bind
import requests
import re
import html

# Configuración
VERSION = "2.0 (Native Python)"
AUTHOR = "Antigravity"

SIGNS = [
    "aries", "tauro", "geminis", "cancer", "leo", "virgo", 
    "libra", "escorpio", "sagitario", "capricornio", "acuario", "piscis"
]

def get_horoscope_data(sign):
    url = f"https://www.hola.com/horoscopo/{sign}/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        content = response.text
        
        match_h3 = re.search(r'<h3[^>]*>.*?hoy.*?</h3>', content, re.IGNORECASE)
        if match_h3:
            start_pos = match_h3.end()
            match_p = re.search(r'<p[^>]*>(.*?)</p>', content[start_pos:], re.DOTALL)
            if match_p:
                text = match_p.group(1)
                text = re.sub(r'<[^>]+>', '', text)
                return html.unescape(text).strip()
    except:
        pass
        
    # Fallback to 20minutos
    try:
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
    except:
        pass

    return None

def pub_horoscope(nick, user, hand, chan, text, **kwargs):
    # El comando viene en 'text' o en el bind si usamos uno genérico
    # Para simplificar, capturamos el comando usado
    cmd = kwargs.get('command', '').replace('!', '').lower()
    
    if cmd in SIGNS:
        sign = cmd
        data = get_horoscope_data(sign)
        date = tcl.clock_format(tcl.clock_seconds(), format="%d-%m-%Y")
        
        if data:
            tcl.putserv(f"PRIVMSG {chan} :\00306[Horóscopo]\003 Predicción para hoy \002{date}\002")
            # Cortar el texto si es muy largo (flood protection básica)
            if len(data) > 400:
                tcl.putserv(f"PRIVMSG {chan} :\002{sign.capitalize()}\002 - {data[:400]}...")
            else:
                tcl.putserv(f"PRIVMSG {chan} :\002{sign.capitalize()}\002 - {data}")
        else:
            tcl.putserv(f"PRIVMSG {chan} :Lo siento, no he podido obtener la predicción para {sign}.")

# Registrar los binds para cada signo
for sign in SIGNS:
    bind("pub", "*", f"!{sign}", pub_horoscope)
    bind("pub", "*", f".{sign}", pub_horoscope)

tcl.putlog(f"Horóscopo Nativo Python v{VERSION} cargado correctamente.")
