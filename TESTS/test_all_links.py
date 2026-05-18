import requests
from bs4 import BeautifulSoup

url = "https://www.hola.com/horoscopo/"
headers = {"User-Agent": "Mozilla/5.0"}
r = requests.get(url, headers=headers)
soup = BeautifulSoup(r.text, 'html.parser')

links = soup.find_all('a', href=True)
for a in links:
    href = a['href']
    if 'horoscopo' in href.lower() and len(href.split('/')) > 4:
        print(href)
