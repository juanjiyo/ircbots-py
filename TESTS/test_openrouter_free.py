#!/usr/bin/env python3
"""Test rápido de modelos OpenRouter free tier desde VPS2."""
import requests, json, time

API_KEY = "OPENROUTER_API_KEY"
URL = "https://openrouter.ai/api/v1/chat/completions"

models = [
    ("gemma-3-27b-it:free", [{"role": "user", "content": "Hola, ¿qué tal?"}]),
    ("llama-3.3-70b-instruct:free", [{"role": "user", "content": "Hola, ¿qué tal?"}]),
    ("mistralai/mistral-small-3.1-24b-instruct:free", [{"role": "user", "content": "Hola, ¿qué tal?"}]),
]

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://github.com/JuanJo-Server/ircbots",
    "X-Title": "IRC Bots Bridge Test"
}

for model_name, messages in models:
    print(f"\n🧪 Probando: {model_name}")
    start = time.time()
    try:
        resp = requests.post(URL, headers=headers, json={
            "model": model_name,
            "messages": messages,
            "max_tokens": 100,
            "temperature": 0.7
        }, timeout=25)
        elapsed = time.time() - start
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get("choices"):
                text = data["choices"][0]["message"]["content"][:120]
                print(f"  ✅ {elapsed:.1f}s → {text}")
            else:
                print(f"  ⚠️ {elapsed:.1f}s → Sin choices: {json.dumps(data)[:200]}")
        else:
            print(f"  ❌ HTTP {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        elapsed = time.time() - start
        print(f"  ❌ Error: {e} ({elapsed:.1f}s)")

print("\n🏁 Test completado")
