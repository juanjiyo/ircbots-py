#!/bin/bash

# 🔧 DIAGNÓSTICO: BUCLE INFINITO EN NANOBOT
# Analyzes why agent generates multiple responses for single message

echo "🔍 DIAGNÓSTICO: BUCLE INFINITO EN AGENT NANOBOT"
echo "================================================"
echo ""

# Función para imprimir secciones
print_section() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "▶ $1"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

# ============================================
print_section "1. REVISAR INSTRUCTIONS (Punto #1: Vagas/Genéricas)"
# ============================================

CONFIG_FILE=~/.nanobot/config.json

if [ -f "$CONFIG_FILE" ]; then
    echo "📄 Config encontrado en: $CONFIG_FILE"
    echo ""
    echo "📝 INSTRUCTIONS actuales:"
    echo "────────────────────────"
    python3 -c "import json; data=json.load(open('$CONFIG_FILE')); print(json.dumps(data.get('agents', {}).get('defaults', {}), indent=2))" 2>/dev/null | grep -A 20 "instructions"
    
    echo ""
    echo "⚠️  ANÁLISIS:"
    echo "   • Si dice: 'Eres un administrador...', 'Eres un asistente...'"
    echo "   • ❌ PROBLEMA: Muy vago, genera contenido indefinidamente"
    echo "   • ✅ SOLUCIÓN: Especificar tarea única y clara"
else
    echo "❌ Config no encontrado en $CONFIG_FILE"
fi

# ============================================
print_section "2. REVISAR PARÁMETROS DEL MODEL"
# ============================================

echo "Buscando parámetros de generación..."
python3 << 'EOFPYTHON'
import json
import os

config_file = os.path.expanduser('~/.nanobot/config.json')

try:
    with open(config_file) as f:
        config = json.load(f)
    
    # Buscar max_tokens, temperature, etc
    model_config = config.get('agents', {}).get('defaults', {})
    
    print("⚙️  PARÁMETROS DEL MODEL:")
    print("─" * 40)
    
    if 'max_tokens' in model_config:
        print(f"✓ max_tokens: {model_config['max_tokens']}")
    else:
        print("❌ max_tokens: NO ESPECIFICADO (usa default infinito?)")
    
    if 'temperature' in model_config:
        print(f"✓ temperature: {model_config['temperature']}")
    else:
        print("❌ temperature: NO ESPECIFICADO")
    
    if 'top_p' in model_config:
        print(f"✓ top_p: {model_config['top_p']}")
    else:
        print("❌ top_p: NO ESPECIFICADO")
    
    print("")
    print("💡 RECOMENDACIÓN:")
    print("   Agregar límite: \"max_tokens\": 500")
    
except Exception as e:
    print(f"Error: {e}")
EOFPYTHON

# ============================================
print_section "3. ANALIZAR LOG DE EJECUCIÓN"
# ============================================

echo "📊 Estadísticas del bucle infinito:"
echo ""

# Si existe log reciente
LOG_FILE=~/.nanobot/nanobot.log
if [ -f "$LOG_FILE" ]; then
    echo "📝 Analizando últimos 50 eventos..."
    
    # Contar tool calls
    TOOL_CALLS=$(grep -c "Tool call: message" "$LOG_FILE" 2>/dev/null || echo 0)
    MESSAGE_INPUTS=$(grep -c "Processing message from" "$LOG_FILE" 2>/dev/null || echo 0)
    
    echo "   • Tool calls (respuestas): $TOOL_CALLS"
    echo "   • Mensajes procesados: $MESSAGE_INPUTS"
    echo "   • Ratio: $(echo "scale=2; $TOOL_CALLS / ($MESSAGE_INPUTS + 1)" | bc) respuestas/mensaje"
    
    if [ "$TOOL_CALLS" -gt $((MESSAGE_INPUTS * 5)) ]; then
        echo "   🔴 CRÍTICO: Más de 5 respuestas por mensaje"
    fi
    
    # Rate limit errors
    RATE_LIMITS=$(grep -c "429\|too many requests" "$LOG_FILE" 2>/dev/null || echo 0)
    echo "   • Rate limit errors: $RATE_LIMITS"
else
    echo "❌ No se encontró log en $LOG_FILE"
fi

# ============================================
print_section "4. BUSCAR PARÁMETROS OCULTOS"
# ============================================

echo "🔎 Buscando parámetros relacionados con respuestas..."
echo ""

python3 << 'EOFPYTHON'
import json
import os

config_file = os.path.expanduser('~/.nanobot/config.json')

try:
    with open(config_file) as f:
        data = json.load(f)
    
    # Buscar todos los campos en agent defaults
    defaults = data.get('agents', {}).get('defaults', {})
    
    print("📋 TODOS LOS PARÁMETROS EN agents.defaults:")
    print("─" * 40)
    for key, value in defaults.items():
        if key == 'instructions':
            val_str = value[:80] + "..." if len(value) > 80 else value
            print(f"  • {key}: {val_str}")
        else:
            print(f"  • {key}: {value}")
    
    # Buscar si existe algo como "response_limit", "max_responses", "stop_after_first"
    suspicious_keys = ['response_limit', 'max_responses', 'stop_after_first', 
                       'single_response', 'max_messages', 'response_count']
    
    print("")
    print("🔍 Parámetros que DEBERÍAN existir pero no:")
    print("─" * 40)
    for key in suspicious_keys:
        if key not in defaults:
            print(f"  ❌ {key} (no existe)")

except Exception as e:
    print(f"Error: {e}")
EOFPYTHON

# ============================================
print_section "5. SOLUCIONES PROPUESTAS"
# ============================================

echo "✅ SOLUCIONES RÁPIDAS (en orden de prioridad):"
echo ""
echo "1️⃣  CAMBIAR INSTRUCTIONS (CRÍTICO)"
echo "   Reemplazar por algo específico:"
echo ""
echo "   \"instructions\": \"Eres un bot asistente. "
echo "   Cuando recibas un mensaje del usuario, responde "
echo "   con UNA ÚNICA frase breve y útil. No generes "
echo "   múltiples respuestas. Máximo 2 oraciones.\","
echo ""
echo "   Comando para editar:"
echo "   nano ~/.nanobot/config.json"
echo ""

echo "2️⃣  AGREGAR max_tokens (IMPORTANTE)"
echo "   Después de \"model\": \"meta/llama-3.3-70b-instruct\","
echo "   Agregar:"
echo "   \"max_tokens\": 500,"
echo ""

echo "3️⃣  PROBAR OTRO MODELO (alternativa)"
echo "   Si el problema persiste, cambiar a:"
echo "   \"model\": \"mistralai/codestral-22b-instruct-v0.1\","
echo ""
echo "   (Mistral tiende a ser más controlable)"
echo ""

echo "4️⃣  REVISAR SOURCE CODE (investigación profunda)"
echo "   cd ~/.nanobot/"
echo "   python3 -c \"import nanobot; print(nanobot.__file__)\""
echo ""

echo "5️⃣  MONITOREAR EN TIEMPO REAL"
echo "   tail -f ~/.nanobot/nanobot.log | grep 'Tool call: message'"
echo ""

# ============================================
print_section "6. TEST RÁPIDO DESPUÉS DE CAMBIOS"
# ============================================

echo "🧪 Para probar después de hacer cambios:"
echo ""
echo "1. Parar nanobot:"
echo "   pkill -f nanobot"
echo ""
echo "2. Reiniciar:"
echo "   ./start_nanobot.sh"
echo ""
echo "3. Enviar mensaje de prueba en Telegram"
echo ""
echo "4. Verifica que SOLO genere 1-2 respuestas:"
echo "   grep -c 'Tool call: message' ~/.nanobot/nanobot.log"
echo ""

echo ""
echo "✨ FIN DEL DIAGNÓSTICO"
echo ""
