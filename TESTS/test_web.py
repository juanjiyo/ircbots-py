import requests
import re
import html

def get_horoscope(sign):
    url = f"https://www.hola.com/horoscopo/{sign}/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        print(f"Conectando a {url}...")
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")
        response.raise_for_status()
        content = response.text
        
        match_h3 = re.search(r'<h3[^>]*>.*?hoy.*?</h3>', content, re.IGNORECASE)
        if not match_h3: 
            print("No se encontro H3")
            return None
            
        start_pos = match_h3.end()
        match_p = re.search(r'<p[^>]*>(.*?)</p>', content[start_pos:], re.DOTALL)
        if not match_p: 
            print("No se encontro P")
            return None
            
        text = match_p.group(1)
        text = re.sub(r'<[^>]+>', '', text)
        return html.unescape(text).strip()
    except Exception as e:
        print(f"Error: {str(e)}")
        return None

res = get_horoscope("aries")
print(f"Resultado: {res}")
