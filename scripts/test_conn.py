import requests
import sys

url = "http://93.93.116.244:4471/heartbeat/test"
print(f"Probando conexión a {url}...")
try:
    r = requests.post(url, timeout=5)
    print(f"STATUS: {r.status_code}")
    print(f"RESPONSE: {r.text}")
except Exception as e:
    print(f"ERROR: {e}")
