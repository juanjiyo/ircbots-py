import json
import sys
from collections import defaultdict

JSON_FILE = "nvidia_nim_models.json"
TXT_FILE  = "nvidia_nim_modelos.txt"

try:
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        datos = json.load(f)
except FileNotFoundError:
    print(f"[ERROR] No se encontró {JSON_FILE}. Ejecuta primero el bat para descargarlo.")
    sys.exit(1)

# Agrupamos por empresa, eliminando duplicados
empresas = defaultdict(set)
for modelo in datos["data"]:
    empresas[modelo["owned_by"]].add(modelo["id"])

# Generamos el txt
lineas = []
total = 0
for empresa in sorted(empresas.keys()):
    lineas.append(f"=== {empresa} ===")
    for modelo in sorted(empresas[empresa]):
        lineas.append(f"  {modelo}")
        total += 1
    lineas.append("")

with open(TXT_FILE, "w", encoding="utf-8") as f:
    f.write("\n".join(lineas))

print(f"[OK] {total} modelos de {len(empresas)} empresas guardados en '{TXT_FILE}'")
