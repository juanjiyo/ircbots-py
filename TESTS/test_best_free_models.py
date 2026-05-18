#!/usr/bin/env python3
"""Test los mejores modelos free tier desde VPS2."""
import requests, json, time

API_KEY = "OPENROUTER_API_KEY"
URL = "https://openrouter.ai/api/v1/chat/completions"

# Candidatos más prometedores de la lista de 24
candidates = [
    # Texto general
    "openai/gpt-oss-120b:free",
    "openai/gpt-oss-20b:free",
    "google/gemma-3-27b-it:free",
    "google/gemma-3-12b-it:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    # Visión (imágenes)
    "google/gemma-3n-e4b-it:free",
    "nvidia/nemotron-nano-12b-v2-vl:free",
]

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://github.com/JuanJo-Server/ircbots",
    "X-Title": "IRC Bots Bridge Test"
}

print("🧪 Testeando modelos free tier candidatos desde VPS2...\n")
working = []

for model in candidates:
    print(f"Testing: {model}", end="", flush=True)
    start = time.time()
    try:
        resp = requests.post(URL, headers=headers, json={
            "model": model,
            "messages": [{"role": "user", "content": "hola"}],
            "max_tokens": 50,
            "temperature": 0.1
        }, timeout=20)
        elapsed = time.time() - start
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get("choices") and data["choices"][0].get("message"):
                working.append((model, elapsed))
                print(f" ✅ {elapsed:.1f}s")
            else:
                print(f" ❌ No choices")
        else:
            err = resp.json().get("error", {}).get("message", "")[:60]
            print(f" ❌ HTTP {resp.status_code} ({err})")
    except Exception as e:
        print(f" ❌ Error: {str(e)[:40]}")

print(f"\n{'='*60}")
print(f"✅ MODELOS QUE FUNCIONAN ({len(working)}):")
for m, t in sorted(working, key=lambda x: x[1]):
    print(f"  {m} → {t:.1f}s")

if working:
    # Top 3 por velocidad
    top3 = sorted(working, key=lambda x: x[1])[:3]
    print(f"\n🏆 TOP 3 (por velocidad):")
    for i, (m, t) in enumerate(top3, 1):
        print(f"  {i}. {m} ({t:.1f}s)")
