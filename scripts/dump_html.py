import requests
import re
import html

def dump_sign(sign):
    url = f"https://www.hola.com/horoscopo/{sign}/"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        content = r.text
        # Guardar los primeros 50000 caracteres
        with open(f"/home/irc/{sign}_dump.html", "w", encoding="utf-8") as f:
            f.write(content[:50000])
        print(f"Dumped {sign}")
    except Exception as e:
        print(f"Error dumping {sign}: {str(e)}")

dump_sign("virgo")
dump_sign("aries")
