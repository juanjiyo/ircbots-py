#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Enviar mensaje a Telegram desde CLI"""

import sys
import io
import requests
import json

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

TELEGRAM_TOKEN = "TELEGRAM_TOKEN"
CHAT_IDS = ["-1003348942954"]

def send(text, parse_mode="HTML"):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    results = []
    for chat_id in CHAT_IDS:
        data = {
            "chat_id": chat_id,
            "text": text[:4000],
            "parse_mode": parse_mode
        }
        try:
            resp = requests.post(url, json=data, timeout=10)
            result = resp.json()
            if result.get("ok"):
                print(f"Mensaje enviado correctamente a {chat_id}")
            else:
                print(f"Error en {chat_id}: {result}")
            results.append(result)
        except Exception as e:
            print(f"Excepción en {chat_id}: {e}")
    return results

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python send_telegram.py <mensaje>")
        sys.exit(1)
    message = " ".join(sys.argv[1:])
    # Convertir \\n a \n reales
    message = message.replace("\\n", "\n")
    send(message)
