#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monitor en tiempo real del grupo Telegram privado (JuanJo + Qwen)
Muestra un timeline de mensajes y estados para depurar dónde se corta.
"""

import requests
import json
import time
from datetime import datetime, timezone, timedelta

# Hora de España (CEST UTC+2 en verano, CET UTC+1 en invierno)
TZ_ESPANA = timezone(timedelta(hours=2))  # Verano CEST

# ==========================================
# CONFIGURACIÓN
# ==========================================
TELEGRAM_TOKEN = "TELEGRAM_TOKEN"
CHAT_ID = "-1003808302723"
OFFSET_FILE = "telegram_monitor_offset.json"

SEPARATOR = "─" * 70

def send_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    for cid in ["-1003808302723"]:
        try:
            requests.post(url, json={"chat_id": cid, "text": text[:4000]}, timeout=5)
        except:
            pass

def load_offset():
    try:
        with open(OFFSET_FILE, 'r') as f:
            return json.load(f).get("offset", 0)
    except:
        return 0

def save_offset(offset):
    with open(OFFSET_FILE, 'w') as f:
        json.dump({"offset": offset}, f)

def format_update(u):
    """Formatea un update de Telegram de forma legible."""
    msg = u.get("message", {})
    up_id = u.get("update_id", "?")
    fr = msg.get("from", {})
    uid = fr.get("id", "?")
    name = fr.get("first_name", "?")
    username = fr.get("username", "?")
    text = msg.get("text", "")
    photos = msg.get("photo", [])
    caption = msg.get("caption", "")
    doc = msg.get("document", {})

    timestamp = datetime.now(TZ_ESPANA).strftime("%H:%M:%S")
    
    lines = []
    lines.append(f"[{timestamp}] Update #{up_id} — {name} (uid:{uid}, @{username})")
    
    if text:
        lines.append(f"   💬 Texto: {text[:120]}")
    if caption:
        lines.append(f"   📝 Caption: {caption[:120]}")
    if photos:
        lines.append(f"   📷 Fotos: {len(photos)} (tamaños: {[p.get('width','?') for p in photos]})")
        # Mostrar file_id de la mejor foto
        best = photos[-1]
        lines.append(f"   📷 file_id: {best.get('file_id','')[:40]}...")
    if doc:
        lines.append(f"   📄 Doc: {doc.get('file_name','?')} ({doc.get('file_size',0)//1024}KB, {doc.get('mime_type','?')})")
    
    return "\n".join(lines)

def main():
    print(SEPARATOR)
    print("📡 TELEGRAM MONITOR — Canal Privado")
    print(SEPARATOR)
    print(f"Grupo: {CHAT_ID}")
    print(f"Escuchando mensajes en tiempo real...")
    print(f"Pulsa Ctrl+C para detener")
    print(SEPARATOR)
    
    offset = load_offset()
    print(f"Offset inicial: {offset}")
    print(SEPARATOR)
    
    msg_count = 0
    
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
            params = {"offset": offset, "timeout": 30}
            
            r = requests.get(url, params=params, timeout=35)
            data = r.json()
            
            if not data.get("ok"):
                print(f"⚠️ API error: {data}")
                time.sleep(5)
                continue
            
            updates = data.get("result", [])
            
            if updates:
                print(f"\n📨 {len(updates)} nuevo(s) mensaje(s):")
                print(SEPARATOR)
                
                for u in updates:
                    msg_count += 1
                    offset = max(offset, u["update_id"] + 1)
                    
                    print(f"\n[{msg_count}] {format_update(u)}")
                    print(SEPARATOR)
                
                save_offset(offset)
                print(f"📊 Offset actualizado: {offset}")
                print(SEPARATOR)
            else:
                # Sin mensajes nuevos — heartbeat silencioso
                now = datetime.now(TZ_ESPANA).strftime("%H:%M:%S")
                print(f"[{now}] ... esperando (offset={offset})", end="\r")
                
        except KeyboardInterrupt:
            print(f"\n\n⛔ Monitor detenido")
            send_message("🔴 Monitor detenido")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
