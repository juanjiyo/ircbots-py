import requests
from bs4 import BeautifulSoup
import re

def get_elmundo_horoscope(sign):
    url = f"https://www.elmundo.es/yodona/horoscopo/{sign}.html"
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers)
    r.encoding = 'iso-8859-1'
    if r.status_code == 200:
        soup = BeautifulSoup(r.text, 'html.parser')
        # find the horoscope text
        # usually in a div or p
        # let's just print the text of paragraphs
        paragraphs = soup.find_all('p')
        for p in paragraphs:
            print("P:", p.text.strip())

get_elmundo_horoscope("aries")
