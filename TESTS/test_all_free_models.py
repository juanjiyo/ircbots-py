#!/usr/bin/env python3
"""Test completo de TODOS los modelos OpenRouter free tier desde VPS2."""
import requests, json, time

API_KEY = "OPENROUTER_API_KEY"
URL = "https://openrouter.ai/api/v1/chat/completions"

# Lista completa de modelos :free en OpenRouter
models = [
    # Meta
    "meta-llama/llama-3.3-70b-instruct:free",
    "meta-llama/llama-3.1-70b-instruct:free",
    "meta-llama/llama-3.2-3b-instruct:free",
    "meta-llama/llama-3.1-8b-instruct:free",
    # Google
    "google/gemma-3-27b-it:free",
    "google/gemma-3-12b-it:free",
    "google/gemma-3-4b-it:free",
    "google/gemma-2-9b-it:free",
    "google/gemma-2-2b-it:free",
    # Mistral
    "mistralai/mistral-7b-instruct:free",
    # Other
    "nousresearch/hermes-3-llama-3.1-70b:free",
    "sophosympatheia/midnight-rose-70b:free",
    "openchat/openchat-7b:free",
]

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://github.com/JuanJo-Server/ircbots",
    "X-Title": "IRC Bots Bridge Test"
}

working = []
failed = []

print(f"🧪 Probando {len(models)} modelos free tier...\n")

for model_name in models:
    short = model_name.split("/")[-1][:40]
    print(f"Testing: {model_name}", end="", flush=True)
    start = time.time()
    try:
        resp = requests.post(URL, headers=headers, json={
            "model": model_name,
            "messages": [{"role": "user", "content": "hola"}],
            "max_tokens": 50,
            "temperature": 0.1
        }, timeout=20)
        elapsed = time.time() - start
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get("choices") and data["choices"][0].get("message"):
                working.append((model_name, elapsed))
                print(f" ✅ {elapsed:.1f}s")
            else:
                failed.append((model_name, "No choices"))
                print(f" ❌ No choices")
        else:
            failed.append((model_name, f"HTTP {resp.status_code}"))
            print(f" ❌ HTTP {resp.status_code}")
    except Exception as e:
        elapsed = time.time() - start
        failed.append((model_name, str(e)[:50]))
        print(f" ❌ Error ({elapsed:.1f}s)")

print(f"\n{'='*60}")
print(f"✅ FUNCIONAN ({len(working)}):")
for m, t in sorted(working, key=lambda x: x[1]):
    print(f"  {m} ({t:.1f}s)")

print(f"\n❌ FALLARON ({len(failed)}):")
for m, err in failed:
    print(f"  {m} — {err}")

if working:
    fastest = sorted(working, key=lambda x: x[1])[0]
    print(f"\n🏆 MEJOR: {fastest[0]} ({fastest[1]:.1f}s)")
