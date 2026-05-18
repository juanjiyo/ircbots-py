import requests
import re
import html

def test_sign(sign):
    url = f"https://www.hola.com/horoscopo/{sign}/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "es-ES,es;q=0.9"
    }
    r = requests.get(url, headers=headers)
    r.encoding = 'utf-8'
    content = r.text
    
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
        print(f"{sign}: Found by DIV. Text length: {len(raw_text)}")
    else:
        print(f"{sign}: NOT found by DIV.")
        patterns = [
            rf'<h[1-3][^>]*>.*?{sign}.*?</h[1-3]>.*?<p[^>]*>(.*?)</p>',
            rf'<h[1-3][^>]*>.*?hoy.*?</h[1-3]>.*?<p[^>]*>(.*?)</p>'
        ]
        for pattern in patterns:
            m = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if m:
                raw_text = re.sub(r'<[^>]+>', '', m.group(1))
                print(f"{sign}: Found by HEADING. Text length: {len(raw_text)}")
                break

test_sign("aries")
test_sign("escorpio")
