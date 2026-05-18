#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/juanjo/ircbots/scripts')
try:
    import ia_central
    print("AI Hub import OK")
    print(f"Config path: {ia_central.CONFIG_PATH}")
except Exception as e:
    print(f"Error: {e}")
