import requests
import json
import time
import sys
from pathlib import Path

# --- CONFIGURACIÓN ---
API_KEY = "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"
URL = "https://integrate.api.nvidia.com/v1/chat/completions"
MODELS_JSON = Path(r"C:\Users\WinterOS\Documents\ircbots\scripts\nvidia_nim_models.json")
OUTPUT_JSON = Path(r"C:\Users\WinterOS\Documents\ircbots\scripts\nvidia_status_check.json")
OUTPUT_TXT = Path(r"C:\Users\WinterOS\Documents\ircbots\scripts\nvidia_modelos_activos.txt")

# Límites de la API: 40 RPM -> 1 consulta cada 1.5 segundos
DELAY = 1.6 

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")
    sys.stdout.flush()

def check_model(model_id):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 5
    }
    try:
        start_t = time.time()
        resp = requests.post(URL, headers=headers, json=payload, timeout=15)
        elapsed = time.time() - start_t
        
        if resp.status_code == 200:
            return "ACTIVO", elapsed, ""
        elif resp.status_code == 404:
            return "NO_ENCONTRADO", elapsed, "404"
        elif resp.status_code == 429:
            return "RATE_LIMIT", elapsed, "429"
        else:
            return "ERROR", elapsed, f"Status {resp.status_code}"
    except requests.exceptions.Timeout:
        return "TIMEOUT", 15, "Read Timeout"
    except Exception as e:
        return "FALLO_TECNICO", 0, str(e)

def main():
    if not MODELS_JSON.exists():
        log("❌ No se encontró el archivo de modelos. Abortando.")
        return

    with open(MODELS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    all_models = [m["id"] for m in data["data"]]
    log(f"🚀 Iniciando auditoría de {len(all_models)} modelos...")
    
    results = {}
    activos = []

    for i, mid in enumerate(all_models):
        log(f"[{i+1}/{len(all_models)}] Probando: {mid}...")
        status, elapsed, extra = check_model(mid)
        
        results[mid] = {
            "status": status,
            "latency": f"{elapsed:.2f}s",
            "info": extra
        }
        
        if status == "ACTIVO":
            log(f"  ✅ OK ({elapsed:.2f}s)")
            activos.append(mid)
        else:
            log(f"  ❌ {status} {extra}")

        # Guardar progreso parcial
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

        # Respetar RPM
        time.sleep(DELAY)

    # Generar informe final TXT
    with open(OUTPUT_TXT, "w", encoding="utf-8") as f:
        f.write(f"=== INFORME DE MODELOS NVIDIA NIM ({time.strftime('%Y-%m-%d %H:%M:%S')}) ===\n")
        f.write(f"Total analizados: {len(all_models)}\n")
        f.write(f"Total activos: {len(activos)}\n\n")
        f.write("=== LISTA DE MODELOS OPERATIVOS ===\n")
        for m in sorted(activos):
            f.write(f"  [OK] {m}\n")
    
    log(f"🏁 Auditoría completada. {len(activos)} modelos activos.")
    log(f"Informe guardado en: {OUTPUT_TXT}")

if __name__ == "__main__":
    main()
