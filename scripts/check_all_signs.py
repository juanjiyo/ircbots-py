import requests
import re
import html

SIGNS = ["aries", "tauro", "geminis", "cancer", "leo", "virgo", "libra", "escorpion", "sagitario", "capricornio", "acuario", "piscis"]

def get_clean_text(sign, raw_text):
    if not raw_text: return "EMPTY"
    final_text = html.unescape(raw_text).strip()
    clean_regex = rf'^(.*?{sign}|.*?hoy|.*?\d{{1,2}}\s+de\s+\w+).*?(\d{{4}})?\s*'
    temp_text = re.sub(clean_regex, '', final_text, flags=re.IGNORECASE).strip()
    return temp_text if len(temp_text) > 10 else final_text

def test_all_signs():
    headers = {"User-Agent": "Mozilla/5.0"}
    for sign in SIGNS:
        url = f"https://www.hola.com/horoscopo/{sign}/"
        try:
            r = requests.get(url, headers=headers, timeout=10)
            content = r.text
            patterns = [
                rf'<h[1-3][^>]*>.*?{sign}.*?hoy.*?</h[1-3]>.*?<p[^>]*>(.*?)</p>',
                rf'<h[1-3][^>]*>.*?hoy.*?</h[1-3]>.*?<p[^>]*>(.*?)</p>',
                rf'<h[1-3][^>]*>.*?{sign}.*?</h[1-3]>.*?<p[^>]*>(.*?)</p>',
                r'<div class="ho-article-body">.*?<p[^>]*>(.*?)</p>'
            ]
            raw_text = None
            for pattern in patterns:
                m = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
                if m:
                    raw_text = re.sub(r'<[^>]+>', '', m.group(1))
                    break
            
            clean = get_clean_text(sign, raw_text)
            print(f"Signo: {sign.capitalize()} | Inicio: {clean[:60]}...")
        except Exception as e:
            print(f"Signo: {sign.capitalize()} | ERROR: {str(e)}")

test_all_signs()
