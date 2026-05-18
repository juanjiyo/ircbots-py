import requests
def dump(sign):
    url = f"https://www.hola.com/horoscopo/{sign}/"
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers)
    with open(f"/home/irc/{sign}_full.html", "w", encoding="utf-8") as f:
        f.write(r.text)
    print(f"Dumped {sign}")

dump("sagitario")
dump("cancer")
dump("escorpio")
dump("virgo")
