import requests
import re
import html

def test_sign(sign):
    url = f"https://www.hola.com/horoscopo/{sign}/"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        content = r.text
        # Buscar el h3 que contiene el signo o la palabra hoy
        m = re.search(r'<h3[^>]*>(.*?)</h3>', content, re.IGNORECASE | re.DOTALL)
        h3_text = m.group(1) if m else "NO H3 FOUND"
        print(f"Signo: {sign} | H3: {h3_text.strip()}")
        
        # Intentar capturar el parrafo
        m2 = re.search(r'<h3[^>]*>.*?</h3>.*?<p[^>]*>(.*?)</p>', content, re.DOTALL | re.IGNORECASE)
        if m2:
            print(f"  Texto encontrado: {m2.group(1)[:50]}...")
        else:
            print("  FALLO: No se encontro el parrafo despues del H3")
            
    except Exception as e:
        print(f"  ERROR: {str(e)}")

for s in ["aries", "virgo", "leo", "libra", "geminis", "tauro"]:
    test_sign(s)
