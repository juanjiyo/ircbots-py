import requests

url = "https://www.hola.com/horoscopo/"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Encoding": "gzip, deflate"
}
try:
    r = requests.get(url, headers=headers, timeout=10)
    # Guardar como BINARIO para inspeccion
    with open("/home/irc/horoscopo_main.bin", "wb") as f:
        f.write(r.content)
    print(f"Main page saved as binary. Status: {r.status_code}")
except Exception as e:
    print(f"Error: {str(e)}")
