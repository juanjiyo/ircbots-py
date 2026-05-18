import re
def is_command(text):
    text_lower = text.lower().strip()
    if text_lower.startswith(('wsl ', 'bash ', 'python ', 'python3 ', 'ssh ')):
        return True
    if text_lower.startswith('clona '):
        return True
    has_question = '?' in text or text_lower.startswith(('que ', 'como ', 'cual ', 'puede ', 'sirve ', 'vale ', 'es '))
    KW = ['estado', 'status', 'reinicia', 'reiniciar', 'instala', 'instalar', 'clona', 'github.com', 'milenium', 'iabot', 'falkian', 'telegram']
    for kw in KW:
        if kw in text_lower:
            if has_question:
                return False
            return True
    url_only = re.match(r'^https?://\S+$', text_lower)
    if url_only:
        return True
    return False

tests = [
    ('https://github.com/midudev/autoskills ¿Sirve para Qwen Code?', 'IA'),
    ('estado bots', 'CMD'),
    ('Recuerdas el repo que te envie?', 'IA'),
    ('clona https://github.com/midudev/autoskills', 'CMD'),
    ('reinicia milenium', 'CMD'),
    ('https://github.com/ejemplo/repo', 'CMD'),
    ('instala git', 'CMD'),
    ('wsl ps aux', 'CMD'),
    ('que es autoskills?', 'IA'),
]
for t, expected in tests:
    r = 'CMD' if is_command(t) else 'IA'
    ok = 'OK' if r == expected else 'FAIL'
    print(f'[{ok}] Expected:{expected} Got:{r} | {t[:60]}')
