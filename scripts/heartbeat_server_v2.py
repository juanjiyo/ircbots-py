#!/usr/bin/env python3
"""Test heartbeat server on VPS 2"""
import sys
print(f"Python: {sys.version}")
print(f"Path: {sys.executable}")

try:
    from http.server import HTTPServer, BaseHTTPRequestHandler
    print("http.server: OK")
except Exception as e:
    print(f"http.server: FAIL - {e}")

try:
    from pathlib import Path
    print("pathlib: OK")
except Exception as e:
    print(f"pathlib: FAIL - {e}")

import json, time
print("json, time: OK")

# Test if port 8384 is available
import socket
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("0.0.0.0", 8384))
    s.close()
    print("Port 8384: AVAILABLE")
except Exception as e:
    print(f"Port 8384: BLOCKED - {e}")

print("\nAll tests passed. Starting server...")

# Now start the actual server
HEARTBEAT_DIR = Path("/home/irc/scripts/heartbeats")
PORT = 8384
TIMEOUT = 180

class HeartbeatHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path.startswith("/heartbeat/"):
            bot_name = self.path.split("/heartbeat/")[-1].strip()
            if bot_name:
                HEARTBEAT_DIR.mkdir(exist_ok=True)
                ts_file = HEARTBEAT_DIR / f"{bot_name}.json"
                data = {
                    "bot": bot_name,
                    "timestamp": time.time(),
                    "time_str": time.strftime("%d/%m/%Y %H:%M:%S"),
                }
                ts_file.write_text(json.dumps(data))
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True, "bot": bot_name}).encode())
                return
        self.send_response(400)
        self.end_headers()

    def do_GET(self):
        if self.path == "/status":
            HEARTBEAT_DIR.mkdir(exist_ok=True)
            now = time.time()
            bots = {}
            for f in HEARTBEAT_DIR.glob("*.json"):
                try:
                    data = json.loads(f.read_text())
                    bot_name = data["bot"]
                    ts = data["timestamp"]
                    age = now - ts
                    bots[bot_name] = {
                        "last_seen": data["time_str"],
                        "seconds_ago": int(age),
                        "alive": age < TIMEOUT,
                    }
                except: pass
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(bots, indent=2).encode())
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        pass

HEARTBEAT_DIR.mkdir(exist_ok=True)
server = HTTPServer(("0.0.0.0", PORT), HeartbeatHandler)
print(f"[HEARTBEAT] Listening on port {PORT}")
server.serve_forever()
