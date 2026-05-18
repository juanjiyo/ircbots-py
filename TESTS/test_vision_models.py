#!/usr/bin/env python3
import requests, json

TOKEN = 'TELEGRAM_TOKEN'
OR_KEY = 'OPENROUTER_API_KEY'

print("Getting last updates...")
r = requests.get(f'https://api.telegram.org/bot{TOKEN}/getUpdates', params={'offset': 0, 'limit': 10}, timeout=15)
data = r.json()
print(f'Updates: {len(data.get("result",[]))}')

for u in reversed(data.get('result', [])):
    msg = u.get('message', {})
    photos = msg.get('photo', [])
    if photos:
        fid = photos[-1]['file_id']
        r2 = requests.get(f'https://api.telegram.org/bot{TOKEN}/getFile?file_id={fid}', timeout=10)
        fd = r2.json()
        if fd.get('ok'):
            path = fd['result']['file_path']
            furl = f'https://api.telegram.org/file/bot{TOKEN}/{path}'
            print(f'Image URL: {furl[:80]}...')

            # Test 1: OpenRouter gpt-4o-mini
            print("\nTest 1: OpenRouter gpt-4o-mini...")
            try:
                resp = requests.post('https://openrouter.ai/api/v1/chat/completions', headers={
                    'Authorization': f'Bearer {OR_KEY}',
                    'Content-Type': 'application/json',
                    'HTTP-Referer': 'https://github.com/qwen-code/qwen-code'
                }, json={
                    'model': 'openai/gpt-4o-mini',
                    'messages': [{'role': 'user', 'content': [
                        {'type': 'image_url', 'image_url': {'url': furl}},
                        {'type': 'text', 'text': 'Describe en 2 frases'}
                    ]}],
                    'max_tokens': 300
                }, timeout=30)
                print(f'  Status: {resp.status_code}')
                rj = resp.json()
                if 'error' in rj:
                    print(f'  ERROR: {json.dumps(rj["error"])}')
                elif 'choices' in rj:
                    print(f'  OK: {rj["choices"][0]["message"]["content"][:300]}')
                else:
                    print(f'  Unknown: {str(rj)[:300]}')
            except Exception as e:
                print(f'  Exception: {e}')

            # Test 2: OpenRouter claude-3.5-sonnet
            print("\nTest 2: OpenRouter claude-3-5-sonnet...")
            try:
                resp2 = requests.post('https://openrouter.ai/api/v1/chat/completions', headers={
                    'Authorization': f'Bearer {OR_KEY}',
                    'Content-Type': 'application/json',
                    'HTTP-Referer': 'https://github.com/qwen-code/qwen-code'
                }, json={
                    'model': 'anthropic/claude-3.5-sonnet:beta',
                    'messages': [{'role': 'user', 'content': [
                        {'type': 'image_url', 'image_url': {'url': furl}},
                        {'type': 'text', 'text': 'Describe en 2 frases'}
                    ]}],
                    'max_tokens': 300
                }, timeout=30)
                print(f'  Status: {resp2.status_code}')
                rj2 = resp2.json()
                if 'error' in rj2:
                    print(f'  ERROR: {json.dumps(rj2["error"])}')
                elif 'choices' in rj2:
                    print(f'  OK: {rj2["choices"][0]["message"]["content"][:300]}')
                else:
                    print(f'  Unknown: {str(rj2)[:300]}')
            except Exception as e:
                print(f'  Exception: {e}')

            # Test 3: Mistral Pixtral con formato correcto
            print("\nTest 3: Mistral Pixtral...")
            try:
                resp3 = requests.post('https://api.mistral.ai/v1/chat/completions', headers={
                    'Authorization': 'Bearer OPENROUTER_API_KEY_OLD',
                    'Content-Type': 'application/json',
                }, json={
                    'model': 'pixtral-12b-2409',
                    'messages': [{'role': 'user', 'content': [
                        {'type': 'image_url', 'image_url': {'url': furl}},
                        {'type': 'text', 'text': 'Describe en 2 frases'}
                    ]}],
                    'max_tokens': 300
                }, timeout=60)
                print(f'  Status: {resp3.status_code}')
                rj3 = resp3.json()
                if 'error' in rj3:
                    print(f'  ERROR: {json.dumps(rj3["error"])}')
                elif 'choices' in rj3:
                    print(f'  OK: {rj3["choices"][0]["message"]["content"][:300]}')
                else:
                    print(f'  Unknown: {str(rj3)[:500]}')
            except Exception as e:
                print(f'  Exception: {e}')

            break
else:
    print('No photos in updates. Envía una foto al grupo primero.')
