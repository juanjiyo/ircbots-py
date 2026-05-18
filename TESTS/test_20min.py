import requests
from bs4 import BeautifulSoup
import re

url = "https://www.20minutos.es/horoscopo/aries/"
headers = {"User-Agent": "Mozilla/5.0"}
fr = requests.get(url, headers=headers)
fr.encoding = 'utf-8'
fcontent = fr.text
article_match = re.search(r'<div class="article-text"[^>]*>(.*?)</div>', fcontent, re.DOTALL | re.IGNORECASE)
if article_match:
    fparagraphs = re.findall(r'<p[^>]*>(.*?)</p>', article_match.group(1), re.DOTALL)
    print("Found paragraphs:", len(fparagraphs))
    if len(fparagraphs) >= 2:
        print("Fallback text:", re.sub(r'<[^>]+>', '', fparagraphs[1]).strip())
    elif len(fparagraphs) == 1:
        print("Fallback text:", re.sub(r'<[^>]+>', '', fparagraphs[0]).strip())
else:
    print("Article text not found.")
