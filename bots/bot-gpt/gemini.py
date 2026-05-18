import requests
import time
import irc.client
import threading
import re
import configparser
import json
import ssl
from pathlib import Path
from jaraco.stream import buffer

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

config = configparser.ConfigParser()
config.read('gemini.conf')

# ── Proveedores IA con cadena de fallback: Gemini → OpenRouter → Groq → DeepSeek
api_key             = config.get('api', 'api_key')
model_name          = config.get('api', 'model_name')
_system_prompt_base = config.get('api', 'system_prompt', fallback='')

openrouter_api_key = config.get('openrouter', 'api_key',    fallback='')
openrouter_model   = config.get('openrouter', 'model_name', fallback='openai/gpt-oss-120b:free')

groq_api_key = config.get('groq', 'api_key',    fallback='')
groq_model   = config.get('groq', 'model_name', fallback='llama-3.3-70b-versatile')

deepseek_api_key = config.get('deepseek', 'api_key',    fallback='')
deepseek_model   = config.get('deepseek', 'model_name', fallback='deepseek-chat')

mistral_api_key = config.get('mistral', 'api_key',    fallback='')
mistral_model   = config.get('mistral', 'model_name', fallback='mistral-small-latest')

# Instrucciones ortográficas inyectadas siempre en el system prompt.
_ORTHO_INSTRUCTIONS = (
    "IMPORTANTE — Reglas de formato para IRC:\n"
    "1. Escribe siempre con ortografía correcta: separa cada palabra con un espacio.\n"
    "2. Nunca fusiones artículos, preposiciones o conjunciones con la palabra siguiente "
    "(correcto: 'la tentación', 'de pronto', 'en el'; incorrecto: 'latentación', 'depronto', 'enel').\n"
    "3. Coloca siempre un espacio después de cada signo de puntuación (coma, punto, etc.).\n"
    "4. No uses markdown (asteriscos, guiones bajos, backticks): el canal IRC no lo renderiza.\n"
    "5. Respuestas concisas: máximo 3-4 oraciones por turno.\n"
)

system_prompt = (
    f"{_system_prompt_base}\n\n{_ORTHO_INSTRUCTIONS}".strip()
    if _system_prompt_base
    else _ORTHO_INSTRUCTIONS.strip()
)
max_history   = config.getint('api', 'max_history', fallback=20)
max_parts     = config.getint('api', 'max_parts',   fallback=3)

# IRC
server     = config.get('irc', 'server')
port       = config.getint('irc', 'port')
nickname   = config.get('irc', 'nickname')
ident      = config.get('irc', 'ident')
realname   = config.get('irc', 'realname')
channels   = [ch.strip() for ch in config.get('irc', 'channels').split(',')]
password   = config.get('irc', 'password')
user_modes = config.get('irc', 'user_modes', fallback='')

# Administradores
admin_nicks = [nick.strip() for nick in config.get('admins', 'nicks').split(',')]

# Reconexión global
reconnecting = False
shutdown     = False

# Estado ON/OFF por canal (silenciar/despertar)
_silenced_channels: dict[str, bool] = {}

# ── Cliente OpenAI opcional (Qwen, DeepSeek) ──
try:
    from openai import OpenAI as _OpenAI
    _HAS_OPENAI = True
except ImportError:
    _HAS_OPENAI = False
    _OpenAI = None

# ---------------------------------------------------------------------------
# Memoria conversacional (por canal)
# ---------------------------------------------------------------------------

_conversation_history: dict[str, list[dict]] = {}
_history_lock = threading.Lock()


def history_add(channel: str, role: str, content: str) -> None:
    """Añade un turno al historial del canal y recorta si supera max_history."""
    with _history_lock:
        hist = _conversation_history.setdefault(channel, [])
        hist.append({"role": role, "content": content})
        if len(hist) > max_history:
            _conversation_history[channel] = hist[-max_history:]


def history_get(channel: str) -> list[dict]:
    """Devuelve una copia del historial del canal."""
    with _history_lock:
        return list(_conversation_history.get(channel, []))


def history_clear(channel: str) -> bool:
    """Limpia el historial del canal. Devuelve True si existía."""
    with _history_lock:
        if channel in _conversation_history:
            del _conversation_history[channel]
            return True
        return False


def history_revert_last_user(channel: str) -> None:
    """Elimina el último mensaje de usuario si quedó sin respuesta."""
    with _history_lock:
        hist = _conversation_history.get(channel, [])
        if hist and hist[-1]["role"] == "user":
            _conversation_history[channel] = hist[:-1]

# ---------------------------------------------------------------------------
# Persistencia de canales autojoin
# ---------------------------------------------------------------------------

AUTOJOIN_FILE = Path("autojoin.json")


def load_autojoin_channels() -> dict:
    if AUTOJOIN_FILE.exists():
        with open(AUTOJOIN_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_autojoin_channels(data: dict) -> None:
    with open(AUTOJOIN_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


autojoin_channels = load_autojoin_channels()

# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def strip_mirc_colors(text: str) -> str:
    return re.sub(r"(\x03\d{1,2}(,\d{1,2})?)|[\x02\x1F\x16\x0F]", "", text)

# ---------------------------------------------------------------------------
# Excepciones tipadas de la capa API
# ---------------------------------------------------------------------------

class ApiError(Exception):
    """Base para todos los errores de API."""
class InvalidApiKeyError(ApiError):
    pass
class QuotaExceededError(ApiError):
    pass
class InsufficientCreditsError(ApiError):
    pass
class ApiTimeoutError(ApiError):
    pass
class NetworkError(ApiError):
    pass
class ModelNotFoundError(ApiError):
    pass
class MaxRetriesExceededError(ApiError):
    pass
class ApiError400(ApiError):
    pass

_FALLBACK_ERRORS = (QuotaExceededError, MaxRetriesExceededError, ApiTimeoutError, NetworkError)

# ---------------------------------------------------------------------------
# Proveedores IA — cada uno lanza excepciones tipadas para el router
# ---------------------------------------------------------------------------

def _gemini(messages: list[dict], timeout: int = 30, max_retries: int = 2) -> tuple[str, str]:
    """Llama a la API nativa de Gemini con historial multi-turn."""
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model_name}:generateContent?key={api_key}"
    )
    headers = {"Content-Type": "application/json"}

    contents = [
        {"role": "model" if msg["role"] == "assistant" else "user",
         "parts": [{"text": msg["content"]}]}
        for msg in messages
    ]
    payload: dict = {"contents": contents}
    if system_prompt:
        payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=timeout)
            if response.status_code == 200:
                text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
                return text, model_name
            elif response.status_code == 404:
                raise ModelNotFoundError(model_name)
            elif response.status_code == 429:
                error_data = response.json()
                retry_delay = 7
                for detail in error_data.get("error", {}).get("details", []):
                    if detail.get("@type") == "type.googleapis.com/google.rpc.RetryInfo":
                        retry_str = detail.get("retryDelay", "7s")
                        retry_delay = int(retry_str.replace('s', '').split('.')[0])
                if attempt < max_retries - 1:
                    print(f"[Gemini] Rate limit. Reintentando en {retry_delay}s...")
                    time.sleep(retry_delay)
                    continue
                raise QuotaExceededError()
            else:
                raise ApiError(f"HTTP {response.status_code}")
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                print(f"[Gemini] Timeout en intento {attempt + 1}. Reintentando...")
                time.sleep(2)
                continue
            raise ApiTimeoutError()
        except requests.exceptions.RequestException as e:
            raise NetworkError(str(e))
    raise MaxRetriesExceededError()


def _openrouter(messages: list[dict], timeout: int = 30, max_retries: int = 2) -> tuple[str, str]:
    """Llama a OpenRouter con historial completo (doble intento de system prompt)."""
    if not openrouter_api_key:
        raise ApiError("OpenRouter no configurado")
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {openrouter_api_key}",
        "Content-Type": "application/json",
    }

    for include_system in (True, False):
        if include_system and system_prompt:
            full_messages = [{"role": "system", "content": system_prompt}] + list(messages)
        else:
            full_messages = list(messages)

        payload = {"model": openrouter_model, "messages": full_messages}

        for attempt in range(max_retries):
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=timeout)
                if response.status_code == 200:
                    result = response.json()
                    text = result["choices"][0]["message"]["content"]
                    model_used = result.get("model", openrouter_model)
                    if not include_system:
                        print(f"[OpenRouter] Modelo sin soporte de system prompt.")
                    return text, model_used
                elif response.status_code == 400:
                    error_body = response.text
                    if include_system and "instruction is not enabled" in error_body:
                        print("[OpenRouter] Modelo rechaza system prompt. Reintentando sin él...")
                        break  # pasa a include_system=False
                    raise ApiError400(error_body)
                elif response.status_code == 429:
                    if attempt < max_retries - 1:
                        print("[OpenRouter] Rate limit. Reintentando en 5s...")
                        time.sleep(5)
                        continue
                    raise QuotaExceededError()
                elif response.status_code == 402:
                    raise InsufficientCreditsError()
                elif response.status_code == 401:
                    raise InvalidApiKeyError()
                else:
                    raise ApiError(f"HTTP {response.status_code}")
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    print(f"[OpenRouter] Timeout en intento {attempt + 1}. Reintentando...")
                    time.sleep(2)
                    continue
                raise ApiTimeoutError()
            except requests.exceptions.RequestException as e:
                raise NetworkError(str(e))
        # El bucle interior reintentará; si agota intentos, pasa al siguiente include_system

    raise MaxRetriesExceededError()


def _groq(messages: list[dict], timeout: int = 30, max_retries: int = 2) -> tuple[str, str]:
    """Llama a Groq (API compatible con OpenAI)."""
    if not groq_api_key:
        raise ApiError("Groq no configurado")
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {groq_api_key}",
        "Content-Type": "application/json",
    }
    if system_prompt:
        full_messages = [{"role": "system", "content": system_prompt}] + list(messages)
    else:
        full_messages = list(messages)

    payload = {"model": groq_model, "messages": full_messages}

    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=timeout)
            if response.status_code == 200:
                result = response.json()
                text = result["choices"][0]["message"]["content"]
                return text, groq_model
            elif response.status_code == 429:
                if attempt < max_retries - 1:
                    print("[Groq] Rate limit. Reintentando en 5s...")
                    time.sleep(5)
                    continue
                raise QuotaExceededError()
            elif response.status_code == 401:
                raise InvalidApiKeyError()
            else:
                raise ApiError(f"HTTP {response.status_code}")
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                print(f"[Groq] Timeout en intento {attempt + 1}. Reintentando...")
                time.sleep(2)
                continue
            raise ApiTimeoutError()
        except requests.exceptions.RequestException as e:
            raise NetworkError(str(e))
    raise MaxRetriesExceededError()


def _deepseek(messages: list[dict], timeout: int = 30, max_retries: int = 2) -> tuple[str, str]:
    """Llama a DeepSeek — API compatible con OpenAI."""
    if not deepseek_api_key:
        raise ApiError("DeepSeek no configurado")
    if not _HAS_OPENAI:
        raise ApiError("DeepSeek requiere 'openai'. pip install openai")

    if system_prompt:
        full_messages = [{"role": "system", "content": system_prompt}] + list(messages)
    else:
        full_messages = list(messages)

    client = _OpenAI(api_key=deepseek_api_key, base_url="https://api.deepseek.com/v1")

    for attempt in range(max_retries):
        try:
            completion = client.chat.completions.create(
                model=deepseek_model, messages=full_messages, timeout=timeout)
            return completion.choices[0].message.content, deepseek_model
        except Exception as e:
            err = str(e).lower()
            if "401" in err or "invalid_api_key" in err or "authentication" in err:
                raise InvalidApiKeyError(str(e))
            if "429" in err or "rate_limit" in err or "quota" in err:
                if attempt < max_retries - 1:
                    print("[DeepSeek] Rate limit. Reintentando en 5s...")
                    time.sleep(5)
                    continue
                raise QuotaExceededError()
            if "400" in err or "invalid" in err:
                raise ApiError400(str(e))
            if "timeout" in err or "timed out" in err:
                if attempt < max_retries - 1:
                    print(f"[DeepSeek] Timeout en intento {attempt + 1}. Reintentando...")
                    time.sleep(2)
                    continue
                raise ApiTimeoutError()
            raise NetworkError(str(e))
    raise MaxRetriesExceededError()


def _mistral(messages: list[dict], timeout: int = 30, max_retries: int = 2) -> tuple[str, str]:
    """Llama a Mistral AI — API compatible con OpenAI."""
    if not mistral_api_key:
        raise ApiError("Mistral no configurado")
    if not _HAS_OPENAI:
        raise ApiError("Mistral requiere 'openai'. pip install openai")

    if system_prompt:
        full_messages = [{"role": "system", "content": system_prompt}] + list(messages)
    else:
        full_messages = list(messages)

    client = _OpenAI(api_key=mistral_api_key, base_url="https://api.mistral.ai/v1")

    for attempt in range(max_retries):
        try:
            completion = client.chat.completions.create(
                model=mistral_model, messages=full_messages, timeout=timeout)
            return completion.choices[0].message.content, mistral_model
        except Exception as e:
            err = str(e).lower()
            if "401" in err or "invalid_api_key" in err or "authentication" in err:
                raise InvalidApiKeyError(str(e))
            if "429" in err or "rate_limit" in err or "quota" in err:
                if attempt < max_retries - 1:
                    print("[Mistral] Rate limit. Reintentando en 5s...")
                    time.sleep(5)
                    continue
                raise QuotaExceededError()
            if "400" in err or "invalid" in err:
                raise ApiError400(str(e))
            if "timeout" in err or "timed out" in err:
                if attempt < max_retries - 1:
                    print(f"[Mistral] Timeout en intento {attempt + 1}. Reintentando...")
                    time.sleep(2)
                    continue
                raise ApiTimeoutError()
            raise NetworkError(str(e))
    raise MaxRetriesExceededError()

# ---------------------------------------------------------------------------
# Router con cadena de fallback: Gemini → OpenRouter → Groq → Qwen → DeepSeek → Mistral
# ---------------------------------------------------------------------------

def generate_response(
    messages: list[dict],
    timeout: int = 30,
    max_retries: int = 2,
) -> tuple[str, str]:
    """Intenta proveedores en orden. Devuelve (texto_respuesta, modelo_usado)."""
    # Intento 1: Gemini
    try:
        return _gemini(messages, timeout, max_retries)
    except _FALLBACK_ERRORS as e:
        print(f"[Router] Gemini falló ({type(e).__name__}).")

    # Intento 2: OpenRouter
    if openrouter_api_key:
        try:
            print("[Router] Intentando OpenRouter...")
            return _openrouter(messages, timeout, max_retries)
        except _FALLBACK_ERRORS as e:
            print(f"[Router] OpenRouter falló ({type(e).__name__}).")
    else:
        print("[Router] OpenRouter no configurado, saltando.")

    # Intento 3: Groq
    if groq_api_key:
        try:
            print("[Router] Intentando Groq...")
            return _groq(messages, timeout, max_retries)
        except _FALLBACK_ERRORS as e:
            print(f"[Router] Groq falló ({type(e).__name__}).")
    else:
        print("[Router] Groq no configurado, saltando.")

    # Intento 4: DeepSeek
    if deepseek_api_key:
        try:
            print("[Router] Intentando DeepSeek...")
            return _deepseek(messages, timeout, max_retries)
        except _FALLBACK_ERRORS as e:
            print(f"[Router] DeepSeek falló ({type(e).__name__}).")
    else:
        print("[Router] DeepSeek no configurado, saltando.")

    # Intento 5: Mistral
    if mistral_api_key:
        try:
            print("[Router] Intentando Mistral...")
            return _mistral(messages, timeout, max_retries)
        except _FALLBACK_ERRORS as e:
            print(f"[Router] Mistral falló ({type(e).__name__}).")
    else:
        print("[Router] Mistral no configurado, saltando.")

    raise MaxRetriesExceededError("Todos los proveedores IA fallaron o no están configurados.")

# ---------------------------------------------------------------------------
# Procesado de respuestas IA
# ---------------------------------------------------------------------------

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


def split_into_irc_parts(text: str, max_length: int = 350) -> list[str]:
    """Divide texto en partes aptas para IRC respetando oraciones."""
    sentence_endings = re.compile(r'(?<=[.!?])\s+|(?<=[,;])\s+')
    raw_chunks = sentence_endings.split(text.strip())
    chunks = [c for c in raw_chunks if c]

    parts: list[str] = []
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


def process_ai_response(client, target: str, channel: str, message: str) -> None:
    """Añade mensaje al historial, llama IA y envía respuesta al canal."""
    try:
        history_add(channel, "user", message)
        messages = history_get(channel)

        response_text, model_used = generate_response(messages)
        history_add(channel, "assistant", response_text)

        print(f"[Router] Modelo seleccionado: {model_used}")

        response_text = response_text.strip().replace('\r', '')
        response_text = re.sub(
            r'[\u3000-\u9fff\uac00-\ud7ff\uf900-\ufaff\uff00-\uffef]',
            '', response_text)
        response_text = fix_word_spacing(response_text)
        response_text = re.sub(r'\*{1,2}(.+?)\*{1,2}', r'\1', response_text)
        response_text = re.sub(r'`(.+?)`', r'\1', response_text)

        parts = split_into_irc_parts(response_text, max_length=350)
        if len(parts) > max_parts:
            parts = parts[:max_parts]
            parts[-1] += " [...]"

        for i, part in enumerate(parts):
            part = part.replace('\r', '').replace('\n', ' ').strip()
            if not part:
                continue
            client.privmsg(target, part)
            if i < len(parts) - 1:
                time.sleep(0.8)

    except Exception as e:
        history_revert_last_user(channel)
        print(f"Error en la respuesta de la API: {e}")

        error_map = {
            InvalidApiKeyError:       "⚠️ Error: API key inválida.",
            ModelNotFoundError:       "⚠️ Error: El modelo no existe.",
            ApiError400:              "⚠️ Error: ID de modelo inválido.",
            QuotaExceededError:       "⚠️ Cuota de API excedida. Intenta más tarde.",
            InsufficientCreditsError: "⚠️ Créditos insuficientes en OpenRouter.",
            ApiTimeoutError:          "⏱️ La solicitud tardó demasiado.",
            NetworkError:             "🌐 Error de conexión con la API.",
            MaxRetriesExceededError:  "⚠️ No se pudo obtener respuesta.",
        }
        for exc_type, msg in error_map.items():
            if isinstance(e, exc_type):
                client.privmsg(target, msg)
                return
        client.privmsg(target, "⚠️ Error al procesar la respuesta.")

# ---------------------------------------------------------------------------
# Comando !autojoin
# ---------------------------------------------------------------------------

def handle_autojoin_command(client, event, message: str) -> None:
    nick   = irc.client.NickMask(event.source).nick
    target = event.target if irc.client.is_channel(event.target) else nick
    parts  = message.strip().split()

    if nick not in admin_nicks:
        client.privmsg(target, f"\x0304⛔ {nick}: No tienes permisos.\x03")
        return

    if len(parts) < 2 or parts[1].lower() == "help":
        client.privmsg(target, "\x0302📘 Comandos \x0310!autojoin\x03:")
        client.privmsg(target, "\x0303• add <#canal>\x0302 – Añade canal")
        client.privmsg(target, "\x0303• del <#canal>\x0302 – Elimina canal")
        client.privmsg(target, "\x0303• list\x0302 – Lista canales registrados")
        client.privmsg(target, "\x0303• info <#canal>\x0302 – Info del canal")
        client.privmsg(target, "\x0303• addall\x0302 – Registra canales actuales")
        client.privmsg(target, "\x0303• rejoin\x0302 – Reunirse a canales registrados")
        return

    subcommand = parts[1].lower()

    if subcommand == "add":
        if len(parts) < 3 or not parts[2].startswith('#'):
            client.privmsg(target, "\x0302Uso: !autojoin add <#canal>\x03")
            return
        canal = parts[2]
        if canal in autojoin_channels:
            client.privmsg(target, f"\x0310⚠️ {canal} ya está registrado.\x03")
        else:
            autojoin_channels[canal] = {
                "registrado_por": nick,
                "fecha": time.strftime("%d/%m/%Y"),
                "hora":  time.strftime("%H:%M:%S"),
            }
            save_autojoin_channels(autojoin_channels)
            client.join(canal)
            client.privmsg(target, f"\x0303✅ {canal} registrado y unido.\x03")

    elif subcommand == "del":
        if len(parts) < 3 or not parts[2].startswith('#'):
            client.privmsg(target, "\x0302Uso: !autojoin del <#canal>\x03")
            return
        canal = parts[2]
        if canal in autojoin_channels:
            del autojoin_channels[canal]
            save_autojoin_channels(autojoin_channels)
            client.part(canal, "Canal eliminado por admin.")
            client.privmsg(target, f"\x0304🗑️ {canal} eliminado.\x03")
        else:
            client.privmsg(target, f"\x0310⚠️ {canal} no registrado.\x03")

    elif subcommand == "list":
        if not autojoin_channels:
            client.privmsg(target, "\x0310📭 Sin canales registrados.\x03")
        else:
            client.privmsg(target, "\x0302📜 Canales registrados:\x03")
            for c in autojoin_channels:
                client.privmsg(target, f"\x0302• {c}\x03")

    elif subcommand == "info":
        if len(parts) < 3:
            client.privmsg(target, "\x0302Uso: !autojoin info <#canal>\x03")
            return
        canal = parts[2]
        info = autojoin_channels.get(canal)
        if info:
            client.privmsg(target, f"\x0302ℹ️ {canal}: por {info['registrado_por']} el {info['fecha']} {info['hora']}\x03")
        else:
            client.privmsg(target, f"\x0310❓ Sin info de {canal}.\x03")

    elif subcommand == "addall":
        current = list(client.connection.channels.keys())
        new_count = 0
        for chan in current:
            if chan not in autojoin_channels:
                autojoin_channels[chan] = {
                    "registrado_por": nick,
                    "fecha": time.strftime("%d/%m/%Y"),
                    "hora":  time.strftime("%H:%M:%S"),
                }
                new_count += 1
        save_autojoin_channels(autojoin_channels)
        client.privmsg(target, f"\x0303✅ {new_count} canales añadidos.\x03")

    elif subcommand == "rejoin":
        client.privmsg(target, "\x0302🔁 Reuniéndose a canales registrados...\x03")
        for canal in autojoin_channels:
            client.join(canal)

# ---------------------------------------------------------------------------
# Manejadores de eventos IRC
# ---------------------------------------------------------------------------

def on_message(client, event) -> None:
    try:
        if not irc.client.is_channel(event.target):
            return

        raw_message     = event.arguments[0]
        cleaned_message = strip_mirc_colors(raw_message)
        channel         = event.target
        nick            = irc.client.NickMask(event.source).nick

        if cleaned_message.startswith("!autojoin"):
            handle_autojoin_command(client, event, cleaned_message)
            return

        if cleaned_message.strip().lower() == "!olvida":
            if nick not in admin_nicks:
                client.privmsg(channel, f"\x0304⛔ {nick}: Solo admins.\x03")
                return
            if history_clear(channel):
                client.privmsg(channel, f"\x0303✅ Historial limpiado en {channel}.\x03")
            else:
                client.privmsg(channel, "\x0310ℹ️ Sin historial.\x03")
            return

        # Silenciar/despertar el bot (solo admins)
        if nick in admin_nicks:
            cmd = cleaned_message.strip().lower()
            if any(cmd.startswith(sc) for sc in ('cállate', 'callate', 'silencio', 'shut up', 'shutup', 'mute', 'cayate')):
                _silenced_channels[channel] = True
                client.privmsg(channel, f"\x0303🔇 Silenciado en {channel}.\x03")
                return
            if any(cmd.startswith(ac) for ac in ('habla', 'sigue', 'vuelve', 'despierta', 'unmute')):
                _silenced_channels.pop(channel, None)
                client.privmsg(channel, f"\x0303🔊 Reactivado en {channel}.\x03")
                return

        # Si el canal está silenciado, ignorar
        if _silenced_channels.get(channel, False):
            return

        pattern = rf"\b{re.escape(nickname)}\b"
        if re.search(pattern, cleaned_message, re.IGNORECASE):
            message = re.sub(pattern, "", cleaned_message, flags=re.IGNORECASE).strip()
            threading.Thread(
                target=process_ai_response,
                args=(client, channel, channel, message),
                daemon=True,
            ).start()

    except Exception as e:
        print(f"Error en on_message: {e}")


def on_disconnect(client, event) -> None:
    global reconnecting
    if shutdown:
        return
    if not reconnecting:
        reconnecting = True
        intentar_reconectar()

# ---------------------------------------------------------------------------
# Conexión y reconexión
# ---------------------------------------------------------------------------

client = None  # referencia global para handlers


def conectar() -> None:
    """Conecta al IRC y bloquea en process_forever()."""
    global client, reconnecting
    reactor = irc.client.Reactor()
    try:
        nick_with_password = f"{nickname}:{password}" if password else nickname
        client = reactor.server().connect(
            server, port, nick_with_password,
            ircname=realname, username=ident
        )
        reconnecting = False
        print(
            f"✅ Conectado al servidor IRC\n"
            f"   Servidor: {server}:{port}"
        )

        def on_welcome(client, event) -> None:
            if user_modes:
                client.send_raw(f"MODE {nickname} {user_modes}")
            for channel in channels:
                client.join(channel)
            for canal in autojoin_channels:
                client.join(canal)

        client.add_global_handler("welcome",    on_welcome)
        client.add_global_handler("disconnect", on_disconnect)
        client.add_global_handler("pubmsg",     on_message)
        # privmsg intencionalmente no registrado: el bot solo responde en canal

        reactor.process_forever()

    except KeyboardInterrupt:
        raise
    except Exception as e:
        print(f"Error al intentar conectar: {e}")
        intentar_reconectar()


def intentar_reconectar() -> None:
    global reconnecting
    delay = 10
    while reconnecting and not shutdown:
        print(f"Reconectando en {delay} segundos...")
        time.sleep(delay)
        try:
            conectar()
            return
        except Exception as e:
            print(f"Error al reconectar: {e}")

# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    irc.client.ServerConnection.buffer_class = buffer.LenientDecodingLineBuffer
    print("🤖 Iniciando BoT-GPT con IA multi-proveedor...")
    print(f"📡 Fallback chain: Gemini → OpenRouter → Groq → DeepSeek")
    try:
        conectar()
    except KeyboardInterrupt:
        shutdown = True
        print("\n🛑 Bot detenido por el usuario.")
