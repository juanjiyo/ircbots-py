#!/usr/bin/env python3
"""Obtiene lista ACTUAL de modelos :free desde la API de OpenRouter."""
import requests, json

URL = "https://openrouter.ai/api/v1/models"

try:
    r = requests.get(URL, timeout=15)
    data = r.json()
    models = data.get("data", [])
    
    # Filtrar solo los free (sin precio o precio 0)
    free = []
    for m in models:
        name = m.get("id", "")
        pricing = m.get("pricing", {})
        # Un modelo es free si no tiene precio o es 0
        is_free = not pricing or all(v == "0" for v in pricing.values())
        if is_free and name.endswith(":free"):
            free.append(name)
    
    print(f"Modelos :free actuales ({len(free)}):")
    for m in sorted(free):
        print(f"  {m}")
    
    # Guardar para referencia
    with open("/tmp/openrouter_free_models.txt", "w") as f:
        for m in sorted(free):
            f.write(m + "\n")
    print(f"\n✅ Lista guardada en /tmp/openrouter_free_models.txt")
    
except Exception as e:
    print(f"Error: {e}")
