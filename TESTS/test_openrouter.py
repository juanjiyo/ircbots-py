import requests

key = "OPENROUTER_API_KEY"
headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
payload = {
    "model": "google/gemma-3-27b-it:free",
    "messages": [{"role": "user", "content": "responde solo: OK"}],
    "max_tokens": 5
}

r = requests.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers, timeout=15)
print(f"Status: {r.status_code}")
print(r.text[:300])
