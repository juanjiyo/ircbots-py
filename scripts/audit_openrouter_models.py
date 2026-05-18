import requests
import json
import time
import sys
from pathlib import Path

# --- CONFIGURACIÓN ---
API_KEY = "OPENROUTER_API_KEY"
URL = "https://openrouter.ai/api/v1/chat/completions"
MODELS_URL = "https://openrouter.ai/api/v1/models"
OUTPUT_JSON = Path(r"C:\Users\WinterOS\Documents\ircbots\scripts\openrouter_status_check.json")
OUTPUT_TXT = Path(r"C:\Users\WinterOS\Documents\ircbots\scripts\openrouter_modelos_activos.txt")

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")
    sys.stdout.flush()

def get_free_models():
    try:
        resp = requests.get(MODELS_URL)
        if resp.status_code == 200:
            all_models = resp.json()["data"]
            # Filtrar solo modelos gratuitos
            return [m["id"] for m in all_models if m.get("pricing", {}).get("prompt") == "0"]
    except Exception as e:
        log(f"❌ Error al obtener modelos de OpenRouter: {e}")
    return []

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
        elif resp.status_code == 429:
            return "RATE_LIMIT", elapsed, "429"
        else:
            return "ERROR", elapsed, f"Status {resp.status_code}"
    except Exception as e:
        return "TIMEOUT/FALLO", 15, str(e)

def main():
    free_models = get_free_models()
    if not free_models:
        log("❌ No se detectaron modelos gratuitos. Abortando.")
        return

    log(f"🚀 Auditando {len(free_models)} modelos gratuitos en OpenRouter...")
    
    results = {}
    activos = []

    for i, mid in enumerate(free_models):
        log(f"[{i+1}/{len(free_models)}] Probando: {mid}...")
        status, elapsed, extra = check_model(mid)
        
        results[mid] = {"status": status, "latency": f"{elapsed:.2f}s", "info": extra}
        
        if status == "ACTIVO":
            log(f"  ✅ OK ({elapsed:.2f}s)")
            activos.append(mid)
        
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

        # OpenRouter gratuito es sensible, damos un respiro
        time.sleep(2)

    with open(OUTPUT_TXT, "w", encoding="utf-8") as f:
        f.write(f"=== MODELOS OPENROUTER GRATUITOS ACTIVOS ({time.strftime('%Y-%m-%d %H:%M:%S')}) ===\n")
        for m in sorted(activos):
            f.write(f"  [OK] {m}\n")
    
    log(f"🏁 Auditoría completada. {len(activos)} modelos activos.")

if __name__ == "__main__":
    main()
