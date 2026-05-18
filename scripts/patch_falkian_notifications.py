#!/usr/bin/env python3
import sys

f = '/home/juanjo/ircbots/bots/indomita/falkian.py'
with open(f, 'r') as fh:
    lines = fh.readlines()

start = None
for i, line in enumerate(lines):
    if 'def _notify_telegram(self, msg: str) -> None:' in line:
        start = i
        break

if start is None:
    print("ERROR: No se encontró '_notify_telegram'")
    sys.exit(1)

end = None
for i in range(start + 1, len(lines)):
    stripped = lines[i].strip()
    if stripped and not lines[i][:8].isspace() and not stripped.startswith('#'):
        # Encontramos la siguiente línea que no está indentada dentro de la función
        # Pero esta función está dentro de una clase, así que buscamos algo con menos de 8 espacios si la clase tiene 0
        # O simplemente buscamos la siguiente def con la misma indentación
        if lines[i].startswith('    def ') or lines[i].startswith('    UMBRAL_MAYUS'):
            end = i
            break

if end is None:
    print("ERROR: No se encontró el final de _notify_telegram")
    sys.exit(1)

print(f"Encontrado _notify_telegram en líneas {start+1}-{end}")

new_func = '''    def _notify_telegram(self, msg: str) -> None:
        """Envía una notificación al chat de administración en Telegram."""
        token = "TELEGRAM_TOKEN_C2"
        target_ids = ["-1003808302723"]
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        try:
            # Limpiar colores IRC para que sea legible en Telegram
            clean_msg = strip_mirc_colors(msg)
            for chat_id in target_ids:
                payload = {"chat_id": chat_id, "text": f"🤖 <b>{self.cfg.nick}</b>\\n{clean_msg}", "parse_mode": "HTML"}
                requests.post(url, json=payload, timeout=5)
        except Exception as e:
            self.log.error(f"Error al enviar notify a Telegram: {e}")

'''

lines[start:end] = [new_func]

with open(f, 'w') as fh:
    fh.writelines(lines)

print("OK: falkian.py parcheado con notificaciones duales")
