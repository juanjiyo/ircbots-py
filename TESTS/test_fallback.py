import requests
from bs4 import BeautifulSoup
import re

def get_20minutos(sign):
    url = f"https://www.20minutos.es/horoscopo/{sign}/"
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        soup = BeautifulSoup(r.text, 'html.parser')
        # The daily horoscope is usually in a paragraph. 
        # Let's see what class it uses.
        article = soup.find('div', class_='article-text')
        if article:
            return article.text.strip()
    return None

def get_lecturas(sign):
    url = f"https://www.lecturas.com/horoscopo/{sign}"
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        soup = BeautifulSoup(r.text, 'html.parser')
        txt = soup.find('div', class_='txt')
        if txt:
            return txt.text.strip()
    return None

print("20minutos:", get_20minutos("aries"))
print("lecturas:", get_lecturas("aries"))
