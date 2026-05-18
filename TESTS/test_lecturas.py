import requests
import re

url = "https://www.lecturas.com/horoscopo/aries"
headers = {"User-Agent": "Mozilla/5.0"}
fr = requests.get(url, headers=headers)
fr.encoding = 'utf-8'
fcontent = fr.text
article_match = re.search(r'<div class="txt">(.*?)</div>', fcontent, re.DOTALL | re.IGNORECASE)
if article_match:
    print(article_match.group(1).strip()[:100])
else:
    print("Not found")
