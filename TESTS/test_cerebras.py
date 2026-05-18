import sys
sys.path.insert(0, '/home/juanjo/ircbots/scripts')
from ia_central import hub

print("Probando Cerebras...")
result, model = hub._call_cerebras(
    key=hub.get_key("cerebras"),
    prompt="responde solo: OK",
    system="", cat="chat",
    max_tokens=10, timeout=15
)
if result:
    print(f"✅ Cerebras ({model}): {result[:80]}")
else:
    print(f"❌ Cerebras falló")
