def fix_file(path):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    import re
    # We find everything from "def _get_horoscope(sign: str) -> Optional[str]:"
    # to "return False" BEFORE "Excepciones tipadas de la capa API"
    start_idx = content.find("def _get_horoscope(sign: str) -> Optional[str]:")
    end_idx = content.find("# ---------------------------------------------------------------------------", start_idx)

    if start_idx == -1 or end_idx == -1:
        print("Could not find boundaries")
        return

    replacement = """def _get_horoscope(sign: str) -> Optional[str]:
    \"\"\"Extrae la predicción diaria para un signo desde hola.com.\"\"\"
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
        
        # Asegurar decodificación correcta (hola.com suele usar utf-8)
        r.encoding = 'utf-8'
        html_content = r.text
        
        # Estrategia robusta: Extraer todos los párrafos del cuerpo del artículo
        body_match = re.search(r'<div class="(?:ho-)?article-body"[^>]*>(.*?)</div>', html_content, re.DOTALL | re.IGNORECASE)
        if not body_match:
            # Backup: article-body sin prefijo ho-
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
        
        # Si falló la extracción por div, intentar el método de patrones antiguos
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
            # Limpiar prefijos de fecha
            meses = "enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre"
            signs_pattern = "|".join(_HOROSCOPO_SIGNS)
            
            # Patrón preciso: Signo + hoy + día + de + mes
            regex_fecha = rf'^(?:{signs_pattern})\\s+hoy\\s+\\d{{1,2}}\\s+de\\s+(?:{meses})(?:\\s+de\\s+\\d{{4}})?'
            final_text = re.sub(regex_fecha, '', final_text, flags=re.IGNORECASE).strip()
            
            # También limpiar si solo empieza con "hoy [fecha]"
            regex_hoy = rf'^hoy\\s+\\d{{1,2}}\\s+de\\s+(?:{meses})(?:\\s+de\\s+\\d{{4}})?'
            final_text = re.sub(regex_hoy, '', final_text, flags=re.IGNORECASE).strip()
            
            return final_text

    except Exception as e:
        print(f"[Horóscopo] Error Scraper ({sign}): {e}")
        
    # Fallback a 20minutos.es si hola.com falla o no devuelve nada
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

def _responder_horoscopo(canal: str, texto: str) -> bool:
    \"\"\"
    Detecta comandos de horóscopo y envía la respuesta por partes.
    Devuelve True si se procesó un comando de horóscopo.
    \"\"\"
    import re
    import time
    import textwrap
    msg = texto.strip().lower()
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

    data = _get_horoscope(signo)
    if data:
        display_name = signo.capitalize()
        if signo == "escorpio" or signo == "escorpion": display_name = "Escorpión"
        fecha = time.strftime("%d-%m-%Y")
        
        header = f"\\x0306[Horóscopo]\\x03 \\x02{display_name}\\x02 (\\x02{fecha}\\x02):"
        client.privmsg(canal, header)
        
        # Enviar en partes para no saturar
        for chunk in textwrap.wrap(data, 420):
            client.privmsg(canal, chunk)
            time.sleep(0.5) # Pequeño delay anti-flood
        return True

    else:
        # Solo responder si fue un comando explícito y falló
        if msg.startswith("!"):
            client.privmsg(canal, f"\\x0310No pude obtener la predicción para \\x02{signo}\\x02.\\x03")
            return True
    return False

"""
    new_content = content[:start_idx] + replacement + content[end_idx:]
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)

fix_file("bots/milenium/iabot.py")
fix_file("bots/milenium/iabot_ollama.py")
