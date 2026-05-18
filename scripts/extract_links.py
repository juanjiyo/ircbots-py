import re

with open("/home/irc/horoscopo_main.html", "r", encoding="utf-8") as f:
    content = f.read()

links = re.findall(r'href="([^"]*horoscopo/[^"/]+/?)"', content)
for link in sorted(set(links)):
    print(link)
