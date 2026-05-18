import requests
url = "https://www.hola.com/horoscopo/"
headers = {"User-Agent": "Mozilla/5.0"}
r = requests.get(url, headers=headers)
with open("/home/irc/horoscopo_main.html", "w", encoding="utf-8") as f:
    f.write(r.text)
print("Main page dumped")
