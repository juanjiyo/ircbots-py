import requests

url_aries = 'https://www.hola.com/horoscopo/aries/'
url_escorpio = 'https://www.hola.com/horoscopo/escorpio/'

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "es-ES,es;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Referer": "https://www.hola.com/horoscopo/"
}

r_aries = requests.get(url_aries, headers=headers)
print('Aries:', r_aries.status_code)

r_escorpio = requests.get(url_escorpio, headers=headers)
print('Escorpio:', r_escorpio.status_code)
