#!/usr/bin/env python3
"""
Agent Control — Herramienta C2 para enviar comandos a bots y VPS remotos.

Usa la API del Sentinel (heartbeat_server.py) en el Panel para:
  - Inyectar comandos bash en los bots (se ejecutan en PC B en el próximo latido)
  - Ejecutar comandos directamente en el VPS Panel

Uso:
  python agent_control.py bot <nombre_bot> "<comando>"
  python agent_control.py vps "<comando>"
  python agent_control.py status

Ejemplos:
  python agent_control.py bot MiLeNiUm "pip install requests"
  python agent_control.py bot iND0MiTa "git pull"
  python agent_control.py vps "df -h"
  python agent_control.py status
"""

import json
import sys
import io
import requests

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ── Configuración ────────────────────────────────────────────────────────────
SENTINEL_URL  = "http://93.93.116.244:4471"
ADMIN_TOKEN   = "antigravity_admin_master_2026"
HEADERS       = {"X-Admin-Token": ADMIN_TOKEN, "Content-Type": "application/json"}
TIMEOUT       = 30


def send_bot_command(bot_name: str, cmd: str) -> None:
    """Encola un comando para que el bot lo recoja en su próximo latido."""
    url = f"{SENTINEL_URL}/admin/execute"
    payload = {"target": "bot", "bot": bot_name, "cmd": cmd}
    try:
        r = requests.post(url, headers=HEADERS, json=payload, timeout=TIMEOUT)
        data = r.json()
        if data.get("ok"):
            print(f"✅ Comando encolado para {bot_name}: {cmd}")
            print(f"   Se ejecutará en el próximo latido (máx 60s).")
        else:
            print(f"❌ Error: {data}")
    except Exception as e:
        print(f"❌ No se pudo contactar al Sentinel: {e}")


def send_vps_command(cmd: str) -> None:
    """Ejecuta un comando directamente en el VPS Panel."""
    url = f"{SENTINEL_URL}/admin/execute"
    payload = {"target": "vps", "cmd": cmd}
    try:
        r = requests.post(url, headers=HEADERS, json=payload, timeout=TIMEOUT)
        data = r.json()
        if data.get("ok"):
            print(f"✅ Comando ejecutado en Panel:")
            print(data.get("output", "(sin salida)"))
        else:
            print(f"❌ Error: {data.get('error', data)}")
    except Exception as e:
        print(f"❌ No se pudo contactar al Sentinel: {e}")


def get_status() -> None:
    """Consulta el estado de todos los bots."""
    url = f"{SENTINEL_URL}/admin/health"
    try:
        r = requests.post(url, headers=HEADERS, json={}, timeout=TIMEOUT)
        state = r.json()
        bots = state.get("bots", {})
        if not bots:
            print("⚠️  No hay bots registrados.")
            return
        print("┌─────────────────────────────────────────────────┐")
        print("│          SENTINEL v4.0 — ESTADO C2              │")
        print("├──────────────┬──────────┬───────────────────────┤")
        print("│ Bot          │ Estado   │ Último Latido         │")
        print("├──────────────┼──────────┼───────────────────────┤")
        for name, data in bots.items():
            status = data.get("status", "???")
            icon = "🟢" if status == "ONLINE" else "🔴"
            time_str = data.get("time_str", "---")
            print(f"│ {icon} {name:<10} │ {status:<8} │ {time_str:<21} │")
        print("└──────────────┴──────────┴───────────────────────┘")
        incidents = state.get("incidents", [])
        if incidents:
            print(f"\n⚠️  {len(incidents)} incidente(s) registrado(s).")
    except Exception as e:
        print(f"❌ No se pudo contactar al Sentinel: {e}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    mode = sys.argv[1].lower()

    if mode == "bot":
        if len(sys.argv) < 4:
            print("Uso: python agent_control.py bot <nombre_bot> \"<comando>\"")
            sys.exit(1)
        send_bot_command(sys.argv[2], sys.argv[3])

    elif mode == "vps":
        if len(sys.argv) < 3:
            print("Uso: python agent_control.py vps \"<comando>\"")
            sys.exit(1)
        send_vps_command(sys.argv[2])

    elif mode == "status":
        get_status()

    else:
        print(f"Modo desconocido: {mode}")
        print("Modos válidos: bot, vps, status")
        sys.exit(1)


if __name__ == "__main__":
    main()
