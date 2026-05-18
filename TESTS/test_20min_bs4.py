import requests
from bs4 import BeautifulSoup
import re

def get_20minutos(sign):
    url = f"https://www.20minutos.es/horoscopo/{sign}/"
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        soup = BeautifulSoup(r.text, 'html.parser')
        paragraphs = soup.find_all('p')
        valid_p = []
        for p in paragraphs:
            text = p.text.strip()
            # Filter out short paragraphs and copyright
            if len(text) > 80 and "Queda prohibida toda" not in text and "Si algo resalta de" not in text:
                valid_p.append(text)
        if valid_p:
            # Usually the first valid paragraph that isn't the general sign description
            # Actually, "Si algo resalta de estos nativos" is the general sign description for Aries.
            # Let's just return the first valid paragraph that doesn't start with general words.
            return valid_p[-1] if valid_p else None
    return None

print("20minutos:", get_20minutos("aries"))
