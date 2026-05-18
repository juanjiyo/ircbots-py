#!/usr/bin/env python3
import requests, json

TOKEN = 'TELEGRAM_TOKEN'
MISTRAL_KEY = 'OPENROUTER_API_KEY_OLD'

print("1. Getting updates...")
r = requests.get(f'https://api.telegram.org/bot{TOKEN}/getUpdates', params={'offset': 0, 'limit': 10}, timeout=15)
data = r.json()
print(f'   Updates: {len(data.get("result",[]))}')

for u in reversed(data.get('result', [])):
    msg = u.get('message', {})
    photos = msg.get('photo', [])
    if photos:
        fid = photos[-1]['file_id']
        print(f'2. Got photo file_id')
        
        r2 = requests.get(f'https://api.telegram.org/bot{TOKEN}/getFile?file_id={fid}', timeout=10)
        fd = r2.json()
        if fd.get('ok'):
            path = fd['result']['file_path']
            furl = f'https://api.telegram.org/file/bot{TOKEN}/{path}'
            print(f'3. URL: {furl[:70]}...')
            
            # Test URL accessibility
            r3 = requests.head(furl, timeout=10)
            print(f'   HEAD status: {r3.status_code}')
            print(f'   Content-Length: {r3.headers.get("Content-Length", "N/A")}')
            
            # Test with Mistral Pixtral - using URL directly
            print("4. Testing Pixtral with URL...")
            resp = requests.post(
                'https://api.mistral.ai/v1/chat/completions',
                headers={'Authorization': f'Bearer {MISTRAL_KEY}', 'Content-Type': 'application/json'},
                json={
                    'model': 'pixtral-12b-2409',
                    'messages': [{
                        'role': 'user',
                        'content': [
                            {'type': 'image_url', 'image_url': {'url': furl}},
                            {'type': 'text', 'text': 'Que ves? Responde en 1 frase.'}
                        ]
                    }],
                    'max_tokens': 200
                },
                timeout=45
            )
            print(f'   Status: {resp.status_code}')
            rj = resp.json()
            if 'error' in rj:
                print(f'   ERROR: {json.dumps(rj["error"], ensure_ascii=False)}')
            elif 'choices' in rj:
                print(f'   RESPONSE: {rj["choices"][0]["message"]["content"][:300]}')
            else:
                print(f'   FULL: {json.dumps(rj, indent=2)[:500]}')
        break
else:
    print('No photos found')
