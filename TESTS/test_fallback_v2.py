import requests
import re
import html

def get_horoscope_fallback(sign):
    url = "https://www.hola.com/horoscopo/"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.encoding = 'utf-8'
        match_link = re.search(r'href=["\'](https://www.hola.com/horoscopo/\d+/[^"\']+)["\'][^>]*>Horóscopo de hoy', r.text, re.IGNORECASE)
        if not match_link:
            return None
            
        daily_url = match_link.group(1)
        r_daily = requests.get(daily_url, headers=headers, timeout=10)
        r_daily.encoding = 'utf-8'
        content = r_daily.text
        
        # Don't use .*? across elements. Match specifically:
        # <h[1-4]...>[^<]*SIGN[^<]*</h[1-4]><p>...</p>
        # Actually, in Hola it's <h3>... <span>ARIES</span> ... </h3> <p>...</p>
        # Let's find all <h3... to <p...</p> and see which has the sign.
        sections = re.findall(r'<h[1-4][^>]*>(.*?)</h[1-4]>\s*<p[^>]*>(.*?)</p>', content, re.DOTALL | re.IGNORECASE)
        for h, p in sections:
            if sign.lower() in h.lower():
                text = re.sub(r'<[^>]+>', '', p).strip()
                return html.unescape(text)
            
    except Exception as e:
        print("Fallback error:", e)
    return None

print("Aries:", get_horoscope_fallback("aries"))
print("Escorpio:", get_horoscope_fallback("escorpio"))
