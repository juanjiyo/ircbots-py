import requests

signs = [
    "aries", "tauro", "geminis", "cancer", "leo", "virgo",
    "libra", "escorpio", "sagitario", "capricornio", "acuario", "piscis"
]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

for sign in signs:
    url = f'https://www.hola.com/horoscopo/{sign}/'
    r = requests.get(url, headers=headers)
    print(f'{sign}: {r.status_code}')
