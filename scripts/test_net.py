import time
import requests
import sys

SENTINEL_URL = "http://93.93.116.244:4471/heartbeat/TEST_NODE"

def test():
    print("Iniciando prueba de red...", flush=True)
    try:
        r = requests.post(SENTINEL_URL, json={"status": "ALIVE"}, timeout=5)
        print(f"Respuesta del servidor: {r.status_code}", flush=True)
    except Exception as e:
        print(f"Error en el envio: {e}", flush=True)

if __name__ == "__main__":
    test()
