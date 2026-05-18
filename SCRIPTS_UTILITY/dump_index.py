import urllib.request
import re

req = urllib.request.Request('https://www.hola.com/horoscopo/', headers={'User-Agent': 'Mozilla/5.0'})
try:
    html = urllib.request.urlopen(req).read().decode('utf-8')
    links = re.findall(r'href=[\'"](.*?)[\'"]', html)
    print("Links with aries:")
    for l in links:
        if 'aries' in l.lower():
            print(l)
except Exception as e:
    print("Error:", e)
