import requests

key = "OPENROUTER_API_KEY"
headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

models = [
    "google/gemma-3-27b-it:free",
    "stepfun/step-3.5-flash:free",
    "google/gemma-3-12b-it:free",
    "google/gemma-3-4b-it:free",
    "google/gemma-3n-4b-it:free",
]

for model in models:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "responde solo: OK"}],
        "max_tokens": 5
    }
    try:
        r = requests.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers, timeout=15)
        if r.status_code == 200:
            print(f"✅ {model}: OK")
            break
        else:
            print(f"❌ {model}: {r.status_code}")
    except Exception as e:
        print(f"❌ {model}: {e}")
