import requests
import re
import sys
import html

def get_horoscope(sign):
    url = f"https://www.hola.com/horoscopo/{sign}/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        content = response.text
        
        # Buscar el h3 que contiene "hoy"
        # Estructura: <h3 ...>Signo hoy DD de mes</h3>
        match_h3 = re.search(r'<h3[^>]*>.*?hoy.*?</h3>', content, re.IGNORECASE)
        if not match_h3:
            return "Error: No se encontró la sección de hoy."
            
        start_pos = match_h3.end()
        
        # Buscar el primer párrafo <p> después de ese h3
        match_p = re.search(r'<p[^>]*>(.*?)</p>', content[start_pos:], re.DOTALL)
        if not match_p:
            return "Error: No se encontró el texto de la predicción."
            
        text = match_p.group(1)
        # Limpiar HTML y entidades
        text = re.sub(r'<[^>]+>', '', text)
        text = html.unescape(text).strip()
        
        return text

    except Exception as e:
        return f"Error en la conexión: {str(e)}"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 hola_scraper.py <signo>")
    else:
        sign = sys.argv[1].lower()
        print(get_horoscope(sign))
