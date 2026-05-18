#!/usr/bin/env python3
import requests, base64, json, sys

TOKEN = 'TELEGRAM_TOKEN'
MISTRAL_KEY = 'OPENROUTER_API_KEY_OLD'

print("1. Checking Telegram updates...")
r = requests.get(f'https://api.telegram.org/bot{TOKEN}/getUpdates', params={'offset': 0, 'limit': 10}, timeout=15)
data = r.json()
print(f'   Updates found: {len(data.get("result",[]))}')

for u in reversed(data.get('result', [])):
    msg = u.get('message', {})
    photos = msg.get('photo', [])
    if photos:
        fid = photos[-1]['file_id']
        print(f'2. Found photo, file_id={fid[:40]}...')

        r2 = requests.get(f'https://api.telegram.org/bot{TOKEN}/getFile?file_id={fid}', timeout=10)
        fd = r2.json()
        if not fd.get('ok'):
            print(f'   ERROR getting file info: {fd}')
            sys.exit(1)

        path = fd['result']['file_path']
        furl = f'https://api.telegram.org/file/bot{TOKEN}/{path}'
        print(f'3. Downloading image from {furl[:60]}...')
        r3 = requests.get(furl, timeout=30)
        img = r3.content
        print(f'   Image size: {len(img)} bytes')

        print("4. Encoding to base64...")
        b64 = base64.b64encode(img).decode()
        data_uri = f'data:image/jpeg;base64,{b64}'
        print(f'   Base64 length: {len(b64)}')

        print("5. Calling Pixtral API...")
        resp = requests.post(
            'https://api.mistral.ai/v1/chat/completions',
            headers={'Authorization': f'Bearer {MISTRAL_KEY}', 'Content-Type': 'application/json'},
            json={
                'model': 'pixtral-12b-2409',
                'messages': [{
                    'role': 'user',
                    'content': [
                        {'type': 'image_url', 'image_url': data_uri},
                        {'type': 'text', 'text': 'Describe esta imagen en 2 frases'}
                    ]
                }],
                'max_tokens': 300
            },
            timeout=30
        )
        print(f'   Status: {resp.status_code}')
        result = resp.json()
        if result.get('choices'):
            print(f'   Response: {result["choices"][0]["message"]["content"]}')
        else:
            print(f'   Full response: {json.dumps(result, indent=2)[:800]}')
        break
else:
    print('No photos found in recent updates. Sending a test image...')
    sys.exit(1)
