import requests

def test_url(sign):
    url = f"https://www.hola.com/horoscopo/{sign}/"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        print(f"Sign: {sign} | Final URL: {r.url} | Status: {r.status_code} | Size: {len(r.content)}")
    except Exception as e:
        print(f"Error {sign}: {str(e)}")

for s in ["aries", "virgo", "leo", "libra", "geminis", "tauro"]:
    test_url(s)
