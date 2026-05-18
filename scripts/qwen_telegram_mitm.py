#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qwen Code Telegram Bridge (Man in the Middle)

Intercepta mensajes de SitioChat y responde directamente:
- MODO BOT: Ejecuta comandos (WSL, local, etc.)
- MODO CHAT: Responde con IA (OpenRouter)
"""

import sys
import io

# Fix Windows console encoding
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding and sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import requests
import subprocess
import re
import time
import json
from datetime import datetime

# ==========================================
# CONFIGURACIÓN
# ==========================================
TELEGRAM_TOKEN = "TELEGRAM_TOKEN"
CHAT_ID = "-1003348942954"  # Grupo SitioChat
BOT_USERNAME = "SitioChatBot"  # Username del bot (sin @)

# Usuarios autorizados (role: "admin" = bot + chat, "chat" = solo chat IA)
AUTHORIZED_USERS = {
    "293821102": {"name": "JuanJo", "role": "admin"},
    "2041787743": {"name": "Ana", "role": "chat"},
}

# OpenRouter API
OPENROUTER_API_KEY = "OPENROUTER_API_KEY"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "openai/gpt-oss-120b:free"

# System prompt con instrucciones ortográficas (adoptado de Gemini)
_ORTHO_INSTRUCTIONS = (
    "IMPORTANTE — Reglas de formato para IRC/Telegram:\n"
    "1. Escribe siempre con ortografía correcta: separa cada palabra con un espacio.\n"
    "2. Nunca fusiones artículos, preposiciones o conjunciones con la palabra siguiente "
    "(correcto: 'la tentación', 'de pronto', 'en el'; incorrecto: 'latentación', 'depronto', 'enel').\n"
    "3. Coloca siempre un espacio después de cada signo de puntuación (coma, punto, etc.).\n"
    "4. No uses markdown (asteriscos, guiones bajos, backticks): Telegram/IRC no lo renderiza bien.\n"
    "5. Respuestas concisas: máximo 3-4 oraciones por turno.\n"
    "6. Escribe en español de España (tuteo), de forma natural y cercana.\n"
)

# Offset para getUpdates
OFFSET_FILE = "telegram_offset.json"

# ==========================================
# MINI-JUEGOS / ENTRETENIMIENTO
# ==========================================
# Frases como "dale un beso a...", "dile un poema a..." se detectan aquí.
# NO ejecutan comandos shell — generan respuestas creativas.

FUN_PATTERNS = [
    r"dile?\s+(un|una)?\s*(poema|verso|cancion|serenata)",
    r"dale?\s+(un|una)?\s*(beso|abrazo|piropo|cumplido)",
    r"cuenta?\s+(un|me)?\s*(chiste|acertijo|adivinanza|cuento|historia)",
    r"hazme\s+(reir|reír)",
    r"(dime|cuentame|cuéntame)\s+(algo)",
    r"juega\s+(con|a)",
    r"quiero\s+(jugar|un juego|algo divertido)",
]

def is_fun_command(text):
    """Detecta si es un mini-juego o petición de entretenimiento"""
    text_lower = text.lower().strip()
    for pattern in FUN_PATTERNS:
        if re.search(pattern, text_lower):
            return True
    return False

def handle_fun_command(text, user_name="Usuario"):
    """
    Ejecuta un mini-juego y devuelve texto para Telegram.
    Usa IA para generar contenido creativo.
    """
    text_lower = text.lower().strip()

    # Determinar qué tipo de mini-juego es
    if "poema" in text_lower or "verso" in text_lower or "serenata" in text_lower:
        prompt = (
            f"Escribe un poema de amor, bonito y romántico. "
            f"Si se menciona a alguien llamado/a '{user_name}', dedícaselo. "
            f"El poema debe ser tierno, original y hacer sonreír. "
            f"Máximo 4 estrofas."
        )
    elif "beso" in text_lower:
        prompt = (
            f"Envía un beso virtual muy cariñoso y divertido. "
            f"Hazlo creativo, con humor y ternura. Máximo 3 líneas."
        )
    elif "abrazo" in text_lower:
        prompt = (
            f"Envía un abrazo virtual cálido y reconfortante. "
            f"Hazlo creativo y emotivo. Máximo 3 líneas."
        )
    elif "piropo" in text_lower or "cumplido" in text_lower:
        prompt = (
            f"Dice un piropo simpático, respetuoso y con buen humor. "
            f"Que sea original y saque una sonrisa. Máximo 2 líneas."
        )
    elif "chiste" in text_lower:
        prompt = (
            f"Cuenta un chiste corto, limpio y divertido. "
            f"Que sea apto para todo el mundo. Máximo 4 líneas."
        )
    elif "acertijo" in text_lower or "adivinanza" in text_lower:
        prompt = (
            f"Plantea un acertijo divertido con la respuesta oculta. "
            f"Después de una línea vacía, pon 'Respuesta: ...'. "
            f"Que sea ingenioso pero no imposible."
        )
    elif "cuento" in text_lower or "historia" in text_lower:
        prompt = (
            f"Cuenta una micro-historia de entre 3 y 5 frases. "
            f"Que sea entretenida y con un toque sorprendente."
        )
    elif "reir" in text_lower or "reír" in text_lower:
        prompt = (
            f"Haz algo que haga reír: un chiste corto, una situación absurda, "
            f"o algo ingenioso. Máximo 4 líneas."
        )
    else:
        prompt = (
            f"Responde de forma divertida y creativa a: '{text}'. "
            f"Que sea entretenido y saque una sonrisa. Máximo 4 líneas."
        )

    return chat_response(prompt)


# ==========================================
# DETECCIÓN DE INTENCIONES
# ==========================================
# Solo se considera BOT order si EMPIEZA con un comando reconocible.
# Frases como "Dile a Ana un poema" → CHAT (nunca BOT).
BOT_COMMAND_PREFIXES = [
    "wsl", "bash", "python", "python3", "ssh",
    "dir", "cd", "tail", "cat", "ls",
    "pkill", "kill", "nohup", "screen",
    "ps aux", "tasklist", "systemctl",
    "estado", "status",
    "reinicia", "reiniciar", "arranca", "arrancar",
    "para ", "parar ", "mata ", "matar ",
    "inicia", "iniciar",
]

def is_bot_order(text):
    """
    Solo retorna True si el texto es CLARAMENTE un comando.
    Frases conversacionales como "dale un beso" → False.
    Órdenes administrativas como "revisa el status" → True.
    """
    text_lower = text.lower().strip()

    # 1. Patrones de comando al inicio de la línea
    command_patterns = [
        r"^wsl\s", r"^bash\s", r"^python[3]?\s", r"^ssh\s",
        r"^dir\s", r"^cd\s", r"^tail\s", r"^cat\s", r"^ls\s",
        r"^pkill\s", r"^kill\s", r"^nohup\s", r"^screen\s",
        r"^ps\s", r"^tasklist", r"^systemctl\s",
        r"^estado\s", r"^status\s",
        r"^reinicia(r)?\s", r"^arranca(r)?\s",
        r"^inicia(r)?\s",
        r"^para(r)?\s", r"^mata(r)?\s",
    ]
    for pattern in command_patterns:
        if re.search(pattern, text_lower):
            return True

    # 2. Si el texto EMPIEZA con un prefijo de comando reconocido
    for prefix in BOT_COMMAND_PREFIXES:
        if text_lower.startswith(prefix):
            return True

    # 3. Órdenes administrativas contextuales (contiene verbo de acción + objetivo)
    admin_patterns = [
        r"(revisa|revisar|comprueba|comprobar|verifica|verificar|chequea)\b",
        r"\b(estado|status)\b.*\b(bot|vps|servidor|puente|bridge|telegram|iabot|falkian|milenium|indomita)\b",
        r"\b(bot|vps|servidor|puente|bridge|telegram)\b.*\b(estado|status|activo|apagad|caid|funcionand)\b",
        r"(apagad|caid|detenid)\b",
        r"(conecta|conectar|arranca|inicia|enciende)\b.*\b(bot|puente|bridge|telegram|irc)\b",
        r"\b(bot|puente|bridge|telegram|irc)\b.*\b(apagad|caid|detenid)\b",
        r"dile\s+a\s+qwen",
        r"(revisa|comprueba|verifica).*\b(bots|vps|servidor|activo)\b",
        r"\b(activo|funcionand|corriend)\b.*\b(bot|vps|servidor|telegram)\b",
        r"\b(bot|vps|servidor|telegram)\b.*\b(activo|funcionand|corriend)\b",
    ]
    for pattern in admin_patterns:
        if re.search(pattern, text_lower):
            return True

    # 4. Por defecto → CHAT
    return False


def is_mentioned(text):
    """
    Verifica que el bot ha sido mencionado con @SitioChatBot
    o que el mensaje empieza con un comando reconocible.
    """
    mentions = [
        f"@{BOT_USERNAME}",
        BOT_USERNAME.lower(),
        "sitiochat",
    ]
    text_lower = text.lower()
    for m in mentions:
        if m in text_lower:
            return True
    return False


# ==========================================
# PROCESAMIENTO DE TEXTO (adoptado de Gemini)
# ==========================================
def fix_word_spacing(text: str) -> str:
    """Corrige fusiones de palabras habituales de los LLMs."""
    function_words = [
        'unos', 'unas',
        'hasta', 'desde', 'hacia',
        'pero', 'aunque', 'porque', 'cuando',
    ]
    pattern = (
        r'\b(' + '|'.join(function_words) + r')'
        r'([a-záéíóúñA-ZÁÉÍÓÚÑ]{5,})\b'
    )
    text = re.sub(pattern, r'\1 \2', text, flags=re.IGNORECASE)
    text = re.sub(
        r'\b(l[aeo])(t[aeiouáéíóú][a-záéíóúñ]{3,})\b',
        r'\1 \2', text, flags=re.IGNORECASE
    )
    text = re.sub(r' {2,}', ' ', text)
    return text


def strip_cjk(text: str) -> str:
    """Elimina caracteres chinos/japoneses/coreanos del texto."""
    return re.sub(
        r'[\u3000-\u9fff\uac00-\ud7ff\uf900-\ufaff\uff00-\uffef]',
        '', text
    )


def strip_markdown(text: str) -> str:
    """Elimina markdown (asteriscos, backticks) para IRC/Telegram."""
    text = re.sub(r'\*{1,2}(.+?)\*{1,2}', r'\1', text)  # **bold** → bold
    text = re.sub(r'`(.+?)`', r'\1', text)              # `code` → code
    text = re.sub(r'_(.+?)_', r'\1', text)              # _italic_ → italic
    return text


def split_for_telegram(text: str, max_length: int = 400) -> list[str]:
    """Divide texto en partes aptas para Telegram respetando oraciones."""
    sentence_endings = re.compile(r'(?<=[.!?])\s+|(?<=[,;])\s+')
    raw_chunks = sentence_endings.split(text.strip())
    chunks = [c for c in raw_chunks if c]

    parts = []
    current = ""
    for chunk in chunks:
        if len(chunk) > max_length:
            if current:
                parts.append(current.strip())
                current = ""
            words = chunk.split()
            buf = ""
            for word in words:
                if len(buf) + len(word) + 1 <= max_length:
                    buf = f"{buf} {word}" if buf else word
                else:
                    if buf:
                        parts.append(buf.strip())
                    buf = word
            if buf:
                parts.append(buf.strip())
            continue
        candidate = f"{current} {chunk}" if current else chunk
        if len(candidate) <= max_length:
            current = candidate
        else:
            if current:
                parts.append(current.strip())
            current = chunk
    if current:
        parts.append(current.strip())
    return [p for p in parts if p]


def process_ai_text(text: str, max_parts: int = 3) -> list[str]:
    """
    Procesa texto de IA con todos los filtros:
    1. Elimina CJK (chino/japonés/coreano)
    2. Corrige espaciado de palabras
    3. Elimina markdown
    4. Divide en partes para Telegram
    """
    text = text.strip().replace('\r', '')
    text = strip_cjk(text)
    text = fix_word_spacing(text)
    text = strip_markdown(text)
    
    parts = split_for_telegram(text, max_length=400)
    if len(parts) > max_parts:
        parts = parts[:max_parts]
        parts[-1] += " [...]"
    
    return [p.replace('\n', ' ').strip() for p in parts if p]

# ==========================================
# TELEGRAM
# ==========================================
def send_message(text, parse_mode="HTML", reply_to=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": text[:4000],
        "parse_mode": parse_mode
    }
    if reply_to:
        data["reply_to_message_id"] = reply_to
    try:
        response = requests.post(url, json=data, timeout=10)
        return response.json().get("ok", False)
    except Exception as e:
        print(f"Error Telegram: {e}")
        return False

def get_updates(offset=0, timeout=30):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    params = {"offset": offset, "timeout": timeout}
    try:
        response = requests.get(url, params=params, timeout=timeout + 5)
        result = response.json()
        if result.get("ok"):
            return result.get("result", []), offset
        return [], offset
    except:
        return [], offset

def load_offset():
    try:
        with open(OFFSET_FILE, 'r') as f:
            return json.load(f).get("offset", 0)
    except:
        return 0

def save_offset(offset):
    try:
        with open(OFFSET_FILE, 'w') as f:
            json.dump({"offset": offset}, f)
    except:
        pass

# ==========================================
# MODO CHAT (OpenRouter IA)
# ==========================================
def chat_response(question):
    try:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/qwen-code/qwen-code",
            "X-Title": "Qwen Code Telegram Bot"
        }
        
        data = {
            "model": OPENROUTER_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Eres un asistente útil y amable. "
                        "Responde en español de España (tuteo), conciso pero completo.\n\n"
                        f"{_ORTHO_INSTRUCTIONS}"
                    )
                },
                {"role": "user", "content": question}
            ],
            "temperature": 0.7,
            "max_tokens": 1000
        }
        
        response = requests.post(OPENROUTER_URL, json=data, headers=headers, timeout=30)
        result = response.json()
        
        if result.get("choices"):
            return result["choices"][0]["message"]["content"]
        return "Lo siento, no pude procesar tu pregunta 😕"
    except Exception as e:
        return f"Error IA: {str(e)}"

# ==========================================
# MODO BOT (Ejecutar comandos)
# ==========================================
def parse_order(text):
    order = text.lower()

    # Órdenes administrativas contextuales
    if "dile a qwen" in order or "dile a qwen code" in order:
        if any(k in order for k in ["revisa", "status", "estado", "conect", "inicia", "arranca"]):
            return "wsl ps aux | grep -E 'iabot|falkian' | grep -v grep"

    if "revisa" in order or "comprueba" in order or "verifica" in order:
        if any(k in order for k in ["status", "estado", "vps", "servidor", "bots", "activo", "funcionand", "telegram"]):
            return "wsl ps aux | grep -E 'iabot|falkian' | grep -v grep"

    if "apagad" in order or "caid" in order or "detenid" in order:
        if any(k in order for k in ["bot", "puente", "bridge", "telegram", "iabot", "falkian"]):
            return "wsl ps aux | grep -E 'iabot|falkian|telegram' | grep -v grep"

    if "activo" in order or "funcionand" in order or "corriend" in order:
        if any(k in order for k in ["bot", "vps", "servidor", "telegram", "iabot", "falkian"]):
            return "wsl ps aux | grep -E 'iabot|falkian|telegram' | grep -v grep"

    if "conecta" in order or "conectar" in order or "enciende" in order or "inicia" in order or "arranca" in order:
        if any(k in order for k in ["bot", "puente", "bridge", "telegram", "irc"]):
            return "wsl ps aux | grep -E 'telegram|iabot|falkian' | grep -v grep"

    if "milenium" in order or "iabot" in order:
        if "entra" in order or "inicia" in order or "arranca" in order:
            return "wsl cd /home/irc/iabot && nohup python3 iabot.py > iabot.log 2>&1 &"
        elif "reinicia" in order:
            return "wsl pkill -f iabot.py && cd /home/irc/iabot && nohup python3 iabot.py > iabot.log 2>&1 &"
        elif "estado" in order:
            return "wsl ps aux | grep iabot | grep -v grep"
        elif "log" in order:
            return "wsl tail -20 /home/irc/iabot/iabot.log"

    if "indomita" in order or "falkian" in order or "modbot" in order:
        if "entra" in order or "inicia" in order or "arranca" in order:
            return "wsl cd /home/irc/modbot && nohup python3 falkian.py > falkian.log 2>&1 &"
        elif "reinicia" in order:
            return "wsl pkill -f falkian.py && cd /home/irc/modbot && nohup python3 falkian.py > falkian.log 2>&1 &"
        elif "estado" in order:
            return "wsl ps aux | grep falkian | grep -v grep"
        elif "log" in order:
            return "wsl tail -20 /home/irc/modbot/falkian.log"

    if "bots" in order and "estado" in order:
        return "wsl ps aux | grep -E 'iabot|falkian' | grep -v grep"

    if "reinicia" in order and "bots" in order:
        return "wsl bash /home/irc/iniciar_bots.sh"

    if order.startswith("wsl"):
        return text

    return f"wsl {text}"

def run_command(command):
    try:
        if command.startswith("wsl"):
            wsl_cmd = command[4:] if command.startswith("wsl ") else command
            result = subprocess.run(
                ["wsl", "-d", "Ubuntu", "-u", "irc", "-e", "bash", "-c", wsl_cmd],
                capture_output=True, text=True, timeout=120
            )
        else:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=120
            )
        
        return {
            "success": result.returncode == 0,
            "output": result.stdout.strip(),
            "error": result.stderr.strip()
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "output": "", "error": "⏱️ Timeout (120s)"}
    except Exception as e:
        return {"success": False, "output": "", "error": str(e)}

# ==========================================
# PROCESAR MENSAJE (MITM)
# ==========================================
def process_message(text, message_id, user_role="chat", user_name="Usuario"):
    timestamp = datetime.now().strftime("%H:%M:%S")

    # 1. ¿Es un mini-juego? (poemas, chistes, besos, etc.)
    if is_fun_command(text):
        print(f"[{timestamp}] 🎮 FUN ({user_name}): {text[:50]}...")
        send_message(f"🎪 <b>[{timestamp}]</b>\n<preparando algo divertido...>", reply_to=message_id)

        response = handle_fun_command(text, user_name)
        parts = process_ai_text(response, max_parts=3)

        for i, part in enumerate(parts):
            if i == 0:
                send_message(f"🎪 <b>[{timestamp}]</b>\n{part}")
            else:
                send_message(part)
            if i < len(parts) - 1:
                time.sleep(0.3)
        return

    # 2. ¿Es un comando de bot? (wsl, bash, reinicia, etc.)
    if is_bot_order(text):
        # MODO BOT — solo para admins
        if user_role != "admin":
            send_message(
                f"⚠️ {user_name}, este comando es solo para administradores. "
                f"Puedes preguntarme lo que quieras como chat normal.",
                reply_to=message_id
            )
            return

        print(f"[{timestamp}] 🤖 BOT ({user_name}): {text[:50]}...")
        send_message(f"🤖 <b>[{timestamp}] Ejecutando:</b>\n<code>{text[:200]}</code>", reply_to=message_id)

        command = parse_order(text)
        result = run_command(command)

        if result["success"]:
            response = f"✅ <b>[{timestamp}] Completado:</b>\n<code>{text[:100]}</code>\n\n"
            if result["output"]:
                response += f"<b>Salida:</b>\n<code>{result['output'][:3000]}</code>"
            else:
                response += "<i>Sin salida</i>"
        else:
            response = f"❌ <b>[{timestamp}] Error:</b>\n<code>{result['error'][:2000]}</code>"

        send_message(response)
        return

    # 3. Por defecto → CHAT con IA
    print(f"[{timestamp}] 💬 CHAT ({user_name}): {text[:50]}...")
    send_message(f"💬 <b>[{timestamp}] Pensando...</b>", reply_to=message_id)

    response = chat_response(text)

    # Aplicar filtros de texto (adoptados de Gemini)
    parts = process_ai_text(response, max_parts=3)

    for i, part in enumerate(parts):
        if i == 0:
            send_message(f"💬 <b>[{timestamp}]</b>\n{part}")
        else:
            send_message(part)
        if i < len(parts) - 1:
            time.sleep(0.3)

# ==========================================
# MAIN
# ==========================================
def main():
    print("=" * 60)
    print("Qwen Code Telegram Bridge (Man in the Middle)")
    print("=" * 60)
    print(f"Grupo: {CHAT_ID} (SitioChat)")
    print(f"Bot: @{BOT_USERNAME}")
    print(f"Usuarios autorizados: {', '.join(u['name'] + ' (' + u['role'] + ')' for u in AUTHORIZED_USERS.values())}")
    print(f"Regla: Solo responde con @mencion")
    print("=" * 60)
    
    send_message(
        "🟢 <b>Qwen Code Bridge ACTIVO</b>\n\n"
        "📋 Solo respondo si me mencionas con <code>@SitioChatBot</code>\n\n"
        "🤖 <b>Admins:</b> <code>@SitioChatBot estado de los bots</code>\n"
        "💬 <b>Chat:</b> <code>@SitioChatBot ¿qué es la relatividad?</code>\n"
        "🎪 <b>Mini-juegos:</b> <code>@SitioChatBot dile un poema a Ana</code>"
    )
    
    offset = load_offset()
    print(f"▶️ Escuchando mensajes... (offset={offset})")
    
    while True:
        try:
            updates, offset = get_updates(offset=offset, timeout=30)
            
            for update in updates:
                message = update.get("message", {})
                msg_id = update.get("update_id", 0)
                message_id = message.get("message_id", 0)

                # Actualizar offset
                offset = max(offset, msg_id + 1)
                save_offset(offset)

                # Verificar usuario autorizado
                from_user = message.get("from", {})
                user_id = str(from_user.get("id", ""))
                if user_id not in AUTHORIZED_USERS:
                    continue

                user_info = AUTHORIZED_USERS[user_id]
                user_name = user_info.get("name", "Desconocido")
                user_role = user_info.get("role", "chat")

                text = message.get("text", "").strip()
                if not text or text.startswith("/"):
                    continue

                # REQUERIDO: El bot debe ser mencionado con @SitioChatBot
                if not is_mentioned(text):
                    continue

                # Limpiar el @mention del texto antes de procesar
                text_clean = re.sub(r'@' + re.escape(BOT_USERNAME), '', text, flags=re.IGNORECASE).strip()
                if not text_clean:
                    continue

                # Procesar mensaje (MITM) — pasa el role para restringir
                process_message(text_clean, message_id, user_role, user_name)
            
        except KeyboardInterrupt:
            print("\n⛔ Detenido por usuario")
            send_message("🔴 <b>Qwen Code Bridge DETENIDO</b>")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
