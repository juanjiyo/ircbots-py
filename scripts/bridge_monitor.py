#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monitor del bridge — lee el log del bridge en tiempo real.
NO compite con getUpdates (usa tail -f del log).
"""

import subprocess
import sys
import os

LOG_FILE = "/home/irc/qwen_privado/qwen_privado.log"
SEPARATOR = "━" * 70

def main():
    print(SEPARATOR)
    print("📡 MONITOR DEL BRIDGE — Tiempo real (hora España)")
    print(SEPARATOR)
    print(f"Log: {LOG_FILE}")
    print("Ctrl+C para detener")
    print(SEPARATOR)

    try:
        # tail -f del log
        proc = subprocess.Popen(
            ["tail", "-f", LOG_FILE],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        for line in proc.stdout:
            line = line.rstrip()
            if not line:
                continue

            # Colorear según tipo
            if "CMD" in line:
                prefix = "🔧"
            elif "CHAT" in line:
                prefix = "💬"
            elif "📷" in line:
                prefix = "📷"
            elif "ERROR" in line or "Error" in line or "❌" in line:
                prefix = "❌"
            elif "✅" in line:
                prefix = "✅"
            elif "[IMG]" in line:
                prefix = "🖼️"
            elif "[IA]" in line:
                prefix = "🧠"
            elif "[DEBUG]" in line:
                prefix = "🐛"
            else:
                prefix = "  "

            print(f"{prefix} {line}")
            sys.stdout.flush()

    except KeyboardInterrupt:
        print(f"\n⛔ Monitor detenido")

if __name__ == "__main__":
    main()
