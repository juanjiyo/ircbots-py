import requests
import re

def get_20minutos_regex(sign):
    url = f"https://www.20minutos.es/horoscopo/{sign}/"
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers)
    r.encoding = 'utf-8'
    if r.status_code == 200:
        paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', r.text, re.DOTALL)
        valid_p = []
        for p in paragraphs:
            # clean html
            text = re.sub(r'<[^>]+>', '', p).strip()
            if len(text) > 80 and "Queda prohibida toda" not in text and "Si algo resalta de" not in text:
                valid_p.append(text)
        if valid_p:
            return valid_p[-1]
    return None

print("20minutos regex:", get_20minutos_regex("aries"))
