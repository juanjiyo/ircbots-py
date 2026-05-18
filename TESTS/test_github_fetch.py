#!/usr/bin/env python3
import requests
url = "https://github.com/forrestchang/andrej-karpathy-skills"
headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
try:
    r = requests.get(url, headers=headers, timeout=15)
    print(f"Status: {r.status_code}, Len: {len(r.text)}")
    import re
    text = re.sub(r'<[^>]+>', ' ', r.text)
    text = re.sub(r'\s+', ' ', text).strip()
    print(f"Text preview: {text[:400]}")
except Exception as e:
    print(f"Error: {e}")
