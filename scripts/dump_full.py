import requests
import os

def dump_full(sign):
    url = f"https://www.hola.com/horoscopo/{sign}/"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        with open(f"/home/irc/{sign}_full.html", "w", encoding="utf-8") as f:
            f.write(r.text)
        print(f"Full dump of {sign} saved.")
    except Exception as e:
        print(f"Error dumping {sign}: {str(e)}")

dump_full("aries")
dump_full("virgo")
dump_full("leo")
