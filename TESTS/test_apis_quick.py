#!/usr/bin/env python3
"""Test de APIs IA — Lee conf de MiLeNiUm y prueba cada proveedor."""
import configparser, requests, sys

CONF = "/home/juanjo/ircbots/bots/milenium/iabot.conf"
PROMPT = "responde solo: OK"

config = configparser.ConfigParser()
config.read(CONF)

tests = []

# NVIDIA (desde GLOBAL_AI_HUB.json)
import json
hub_path = "/home/juanjo/ircbots/AGENTS_COOP/GLOBAL_AI_HUB.json"
try:
    hub = json.loads(open(hub_path).read())
    nvidia_key = hub.get("api_keys", {}).get("nvidia", "")
    nvidia_model = hub.get("models", {}).get("nvidia", "meta/llama-3.3-70b-instruct")
    if nvidia_key:
        tests.append(("NVIDIA", nvidia_key, nvidia_model, "nvidia"))
except: pass

# Groq
groq_key = config.get("groq", "api_key", fallback="")
groq_model = config.get("groq", "model_name", fallback="llama-3.3-70b-versatile")
if groq_key:
    tests.append(("Groq", groq_key, groq_model, "groq"))

# OpenRouter
or_key = config.get("openrouter", "api_key", fallback="")
or_model = config.get("openrouter", "model", fallback="google/gemma-3-27b-it:free")
if or_key:
    tests.append(("OpenRouter", or_key, or_model, "openrouter"))

# DeepSeek
ds_key = config.get("deepseek", "api_key", fallback="")
ds_model = config.get("deepseek", "model_name", fallback="deepseek-chat")
if ds_key:
    tests.append(("DeepSeek", ds_key, ds_model, "deepseek"))

print("=" * 60)
print("  TEST APIs IA")
print("=" * 60)

passed = 0
failed = 0

for name, key, model, provider in tests:
    print(f"\n🔷 {name} ({model})...")
    try:
        if provider == "nvidia":
            url = "https://integrate.api.nvidia.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            payload = {"model": model, "messages": [{"role": "user", "content": PROMPT}], "max_tokens": 10}
            r = requests.post(url, json=payload, headers=headers, timeout=15)
        elif provider == "groq":
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            payload = {"model": model, "messages": [{"role": "user", "content": PROMPT}], "max_tokens": 10}
            r = requests.post(url, json=payload, headers=headers, timeout=15)
        elif provider == "openrouter":
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            payload = {"model": model, "messages": [{"role": "user", "content": PROMPT}], "max_tokens": 10}
            r = requests.post(url, json=payload, headers=headers, timeout=15)
        elif provider == "deepseek":
            from openai import OpenAI
            client = OpenAI(api_key=key, base_url="https://api.deepseek.com/v1")
            c = client.chat.completions.create(model=model, messages=[{"role": "user", "content": PROMPT}], max_tokens=10, timeout=15)
            print(f"  ✅ {c.choices[0].message.content[:80]}")
            passed += 1
            continue

        if r.status_code == 200:
            data = r.json()
            text = data.get("choices", [{}])[0].get("message", {}).get("content", "")[:80]
            print(f"  ✅ {text}")
            passed += 1
        else:
            print(f"  ❌ HTTP {r.status_code}: {r.text[:120]}")
            failed += 1
    except Exception as e:
        print(f"  ❌ {e}")
        failed += 1

print(f"\n{'=' * 60}")
print(f"  RESULTADO: {passed} pasados | {failed} fallidos")
print(f"{'=' * 60}")
