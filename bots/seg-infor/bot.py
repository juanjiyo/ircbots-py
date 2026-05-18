import os
import re
import sys
import json
import logging
import configparser
import time
import ssl
import threading
import urllib.request
import urllib.error
from collections import deque
from pathlib import Path
from typing import Any

import irc.bot        # type: ignore[import-untyped]
import irc.client     # type: ignore[import-untyped]
import irc.connection  # type: ignore[import-untyped]
from jaraco.stream import buffer

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("irc_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Instrucciones ortográficas — inyectadas en TODOS los system prompts
# ---------------------------------------------------------------------------
_ORTHO_INSTRUCTIONS = (
    "IMPORTANTE — Reglas de formato para IRC:\n"
    "1. Escribe siempre con ortografía correcta: separa cada palabra con un espacio.\n"
    "2. Nunca fusiones artículos, preposiciones o conjunciones con la palabra siguiente "
    "(correcto: 'la tentación', 'de pronto', 'en el'; incorrecto: 'latentación', 'depronto', 'enel').\n"
    "3. Coloca siempre un espacio después de cada signo de puntuación (coma, punto, etc.).\n"
    "4. No uses markdown (asteriscos, guiones bajos, backticks): el canal IRC no lo renderiza.\n"
    "5. Respuestas concisas: máximo 3-4 oraciones por turno.\n"
)


# ---------------------------------------------------------------------------
# Utilidades IRC
# ---------------------------------------------------------------------------

def strip_mirc_colors(text: str) -> str:
    """Elimina códigos de color y formato mIRC del texto."""
    return re.sub(r"(\x03\d{1,2}(,\d{1,2})?)|[\x02\x1F\x16\x0F]", "", text)


def fix_word_spacing(text: str) -> str:
    """
    Corrige fusiones de palabras habituales que los LLMs producen al tokenizar.
    Ejemplo: "latentación" → "la tentación".
    """
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
    """
    Divide el texto en partes aptas para IRC respetando oraciones completas.
    Solo como último recurso corta por palabras.
    """
    sentence_endings = re.compile(r'(?<=[.!?])\s+|(?<=[,;])\s+')
    raw_chunks = sentence_endings.split(text.strip())

    chunks: list[str] = [c for c in raw_chunks if c]
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


def postprocess_response(text: str) -> str:
    """Pipeline completo de limpieza de respuesta IA para IRC."""
    text = text.strip().replace('\r', '')
    # Filtrar caracteres CJK que cuelan algunos modelos de origen asiático
    text = re.sub(r'[\u3000-\u9fff\uac00-\ud7ff\uf900-\ufaff\uff00-\uffef]', '', text)
    # Eliminar markdown básico
    text = re.sub(r'\*{1,2}(.+?)\*{1,2}', r'\1', text)
    text = re.sub(r'`(.+?)`', r'\1', text)
    text = fix_word_spacing(text)
    return text


# ---------------------------------------------------------------------------
# MemoryManager  (persistente en JSON + thread-safe)
# ---------------------------------------------------------------------------

HISTORY_FILE = Path("conversation_history.json")


class MemoryManager:
    """Gestiona el historial de conversación por canal, persistido en disco."""

    def __init__(self, depth: int = 20) -> None:
        self.depth = depth
        self._lock = threading.Lock()
        self._history: dict[str, list[dict[str, str]]] = {}
        self._load()

    def _load(self) -> None:
        if HISTORY_FILE.exists():
            try:
                with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                    self._history = json.load(f)
                logger.info("Historial cargado desde %s", HISTORY_FILE)
            except Exception as e:
                logger.warning("No se pudo cargar historial: %s", e)

    def _save(self) -> None:
        try:
            with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning("No se pudo guardar historial: %s", e)

    def add_message(self, target: str, role: str, content: str) -> None:
        with self._lock:
            hist = self._history.setdefault(target, [])
            hist.append({"role": role, "content": content})
            if len(hist) > self.depth:
                self._history[target] = hist[-self.depth:]
        self._save()

    def get_context(self, target: str) -> list[dict[str, str]]:
        with self._lock:
            return list(self._history.get(target, []))

    def clear(self, target: str) -> bool:
        """Limpia el historial del canal. Devuelve True si existía."""
        with self._lock:
            if target in self._history:
                del self._history[target]
                self._save()
                return True
            return False

    def revert_last_user(self, target: str) -> None:
        """Elimina el último mensaje de usuario si quedó sin respuesta (rollback)."""
        with self._lock:
            hist = self._history.get(target, [])
            if hist and hist[-1]["role"] == "user":
                self._history[target] = hist[:-1]


# ---------------------------------------------------------------------------
# ChannelStateManager  (ON/OFF persistente por canal)
# ---------------------------------------------------------------------------

STATES_FILE = Path("channel_states.json")


class ChannelStateManager:
    """Gestiona el estado activo/silenciado del bot por canal."""

    def __init__(self) -> None:
        self._states: dict[str, bool] = {}
        self._load()

    def _load(self) -> None:
        if STATES_FILE.exists():
            try:
                with open(STATES_FILE, 'r', encoding='utf-8') as f:
                    self._states = json.load(f)
            except Exception as e:
                logger.warning("No se pudo cargar channel_states: %s", e)

    def _save(self) -> None:
        try:
            with open(STATES_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._states, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning("No se pudo guardar channel_states: %s", e)

    def is_active(self, channel: str) -> bool:
        return self._states.get(channel.lower(), True)

    def set(self, channel: str, active: bool) -> None:
        self._states[channel.lower()] = active
        self._save()


# ---------------------------------------------------------------------------
# AutojoinManager
# ---------------------------------------------------------------------------

AUTOJOIN_FILE = Path("autojoin.json")


class AutojoinManager:
    """Persistencia y gestión de canales autojoin."""

    def __init__(self) -> None:
        self._channels: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if AUTOJOIN_FILE.exists():
            try:
                with open(AUTOJOIN_FILE, 'r', encoding='utf-8') as f:
                    self._channels = json.load(f)
            except Exception as e:
                logger.warning("No se pudo cargar autojoin: %s", e)

    def _save(self) -> None:
        with open(AUTOJOIN_FILE, 'w', encoding='utf-8') as f:
            json.dump(self._channels, f, indent=2, ensure_ascii=False)

    def channels(self) -> list[str]:
        return list(self._channels.keys())

    def add(self, canal: str, nick: str) -> bool:
        if canal in self._channels:
            return False
        self._channels[canal] = {
            "registrado_por": nick,
            "fecha": time.strftime("%d/%m/%Y"),
            "hora":  time.strftime("%H:%M:%S"),
        }
        self._save()
        return True

    def remove(self, canal: str) -> bool:
        if canal not in self._channels:
            return False
        del self._channels[canal]
        self._save()
        return True

    def info(self, canal: str) -> dict | None:
        return self._channels.get(canal)

    def add_all(self, canales: list[str], nick: str) -> int:
        count = 0
        for c in canales:
            if c not in self._channels:
                self._channels[c] = {
                    "registrado_por": nick,
                    "fecha": time.strftime("%d/%m/%Y"),
                    "hora":  time.strftime("%H:%M:%S"),
                }
                count += 1
        self._save()
        return count


# ---------------------------------------------------------------------------
# AIHandler
# ---------------------------------------------------------------------------

class SystemPromptRejected(Exception):
    """El modelo rechazó el system prompt (HTTP 400 instruction is not enabled)."""


class AIHandler:
    """Llama a la API de OpenRouter con soporte para system-prompt fallback."""

    ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, api_key: str, model_name: str, fallback_model: str,
                 system_prompt_base: str) -> None:
        self.api_key        = api_key
        self.model          = model_name
        self.fallback_model = fallback_model
        # Componer system prompt base + instrucciones ortográficas
        self.system_prompt_base = (
            f"{system_prompt_base}\n\n{_ORTHO_INSTRUCTIONS}".strip()
            if system_prompt_base
            else _ORTHO_INSTRUCTIONS.strip()
        )

    def _call(self, model: str, messages: list[dict[str, str]],
              max_retries: int = 3) -> str:
        """Llama a la API con reintentos. Lanza SystemPromptRejected si procede."""
        payload = json.dumps({"model": model, "messages": messages}).encode("utf-8")

        req = urllib.request.Request(
            self.ENDPOINT,
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type":  "application/json",
            },
        )

        for attempt in range(1, max_retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                model_used = data.get("model", model)
                logger.info("Modelo seleccionado por el router: %s", model_used)
                return data["choices"][0]["message"]["content"] or ""

            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace")
                if e.code == 400 and "instruction is not enabled" in body:
                    raise SystemPromptRejected(body)
                if e.code == 429:
                    if attempt < max_retries:
                        logger.warning("Rate limit (429) en '%s', intento %d/%d. Reintentando en 5s...",
                                       model, attempt, max_retries)
                        time.sleep(5)
                        continue
                    raise
                logger.error("OpenRouter HTTP %s en '%s': %s", e.code, model, body)
                raise

            except urllib.error.URLError as e:
                logger.error("OpenRouter URLError en '%s': %s", model, e.reason)
                raise

        raise RuntimeError(f"No se pudo completar la llamada al modelo '{model}'")

    def ask(self, context: list[dict[str, str]], user_input: str,
            channel_prompt: str = "") -> str:
        """
        Llama a la IA con el historial y devuelve la respuesta.
        - channel_prompt sobreescribe el system prompt base (temática restringida).
        - Intenta primero con system prompt; si el modelo lo rechaza (400), reintenta sin él.
        - Si el modelo principal falla, usa el fallback.
        """
        active_prompt = channel_prompt if channel_prompt else self.system_prompt_base

        def _build_and_call(model: str, include_system: bool) -> str:
            if include_system and active_prompt:
                messages = [{"role": "system", "content": active_prompt}] + list(context)
            else:
                messages = list(context)
            messages.append({"role": "user", "content": user_input})
            return self._call(model, messages)

        # Intentar modelo principal
        for model in [m for m in [self.model, self.fallback_model] if m]:
            try:
                return _build_and_call(model, include_system=True)
            except SystemPromptRejected:
                logger.warning("Modelo '%s' rechaza system prompt. Reintentando sin él...", model)
                try:
                    return _build_and_call(model, include_system=False)
                except Exception as e:
                    logger.error("Fallo sin system prompt en '%s': %s", model, e)
            except Exception as e:
                logger.error("Fallo en modelo '%s': %s", model, e)
                if model != self.fallback_model:
                    logger.warning("Usando modelo fallback: '%s'", self.fallback_model)
                continue

        return "Lo siento, ocurrió un error al procesar tu mensaje."


# ---------------------------------------------------------------------------
# CooldownManager
# ---------------------------------------------------------------------------

class CooldownManager:
    """Evita que un mismo nick abuse del bot en poco tiempo."""

    def __init__(self, seconds: int) -> None:
        self.seconds = seconds
        self._lock = threading.Lock()
        self._last: dict[str, float] = {}

    def allowed(self, nick: str) -> bool:
        now = time.monotonic()
        with self._lock:
            if now - self._last.get(nick, 0) >= self.seconds:
                self._last[nick] = now
                return True
        return False


# ---------------------------------------------------------------------------
# OpenRouterBot
# ---------------------------------------------------------------------------

_SILENCIO = re.compile(
    r'\b(c[aá]llate|silencio|no hables?|calla|mutea?te|shut\s*up)\b',
    re.IGNORECASE
)
_DESPERTAR = re.compile(
    r'\b(habla|ya puedes hablar|puedes hablar|desm[uú]tea?te|sigue|continua|vuelve)\b',
    re.IGNORECASE
)


class OpenRouterBot(irc.bot.SingleServerIRCBot):
    """Bot IRC conectado a OpenRouter con arquitectura de clases y features de iabot."""

    # Archivo de configuración que este bot siempre leerá
    CONF_FILE = "config.conf"

    def __init__(self) -> None:
        self.config = configparser.ConfigParser()
        if not os.path.exists(self.CONF_FILE):
            raise FileNotFoundError(f"No se encontró: {self.CONF_FILE}")
        self.config.read(self.CONF_FILE)

        # ── IRC ───────────────────────────────────────────────────────────
        server   = self.config.get('irc', 'server')
        port     = self.config.getint('irc', 'port')
        use_ssl  = self.config.getboolean('irc', 'ssl', fallback=False)
        nickname = self.config.get('irc', 'nickname')
        ident    = self.config.get('irc', 'ident', fallback=nickname)
        realname = self.config.get('irc', 'realname')
        self.nickserv_password  = self.config.get('irc', 'password', fallback=None)
        self.modes_on_connect   = self.config.get('irc', 'user_modes', fallback=None)
        self.channels_to_join   = [c.strip() for c in self.config.get('irc', 'channels').split(',')]

        # ── OpenRouter ────────────────────────────────────────────────────
        api_key        = self.config.get('openrouter', 'api_key')
        model_name     = self.config.get('openrouter', 'model')
        fallback_model = self.config.get('openrouter', 'fallback_model', fallback='')
        system_prompt  = self.config.get('bot', 'system_prompt', fallback='')

        # ── Bot ───────────────────────────────────────────────────────────
        memory_depth    = self.config.getint('bot', 'max_history', fallback=20)
        cooldown_sec    = self.config.getint('bot', 'cooldown', fallback=5)
        self.max_len    = self.config.getint('bot', 'max_response_length', fallback=400)
        self.max_parts  = self.config.getint('bot', 'max_parts', fallback=2)
        # Admins desde [admins] nicks — nicks planos separados por coma
        self.admin_nicks = [
            n.strip().lower()
            for n in self.config.get('admins', 'nicks', fallback='').split(',')
            if n.strip()
        ]

        # ── Temáticas por canal ───────────────────────────────────────────
        self.channel_topics: dict[str, str] = {}
        self._load_channel_topics()

        # ── Componentes ───────────────────────────────────────────────────
        self.ai       = AIHandler(api_key, model_name, fallback_model, system_prompt)
        self.memory   = MemoryManager(depth=memory_depth)
        self.cooldown = CooldownManager(cooldown_sec)
        self.states   = ChannelStateManager()
        self.autojoin = AutojoinManager()
        self._ident   = ident

        # ── Conexión ──────────────────────────────────────────────────────
        connect_factory = irc.connection.Factory()
        if use_ssl:
            ssl_ctx = ssl.create_default_context()
            connect_factory = irc.connection.Factory(
                wrapper=lambda sock: ssl_ctx.wrap_socket(sock, server_hostname=server)
            )

        logger.info("Iniciando '%s' (ident: %s) en %s:%d (SSL: %s)", nickname, ident, server, port, use_ssl)
        logger.info("Modelo: %s | Fallback: %s", model_name, fallback_model or "ninguno")

        super().__init__(
            [(server, port)],
            nickname,
            realname,
            username=ident,
            connect_factory=connect_factory,
        )

    # -----------------------------------------------------------------------
    # Configuración dinámica
    # -----------------------------------------------------------------------

    def _load_channel_topics(self) -> None:
        """Carga o recarga la sección [channel_topics] desde el conf."""
        topics: dict[str, str] = {}
        if self.config.has_section('channel_topics'):
            for ch, topic in self.config.items('channel_topics'):
                topics[f"#{ch}"] = topic.strip()
        self.channel_topics = topics
        logger.info("Temas de canal cargados: %s", list(self.channel_topics.keys()) or "ninguno")

    def _reload_config(self) -> None:
        """Recarga el archivo de configuración completo en caliente."""
        self.config.read(self.CONF_FILE)
        self._load_channel_topics()
        logger.info("Configuración recargada.")

    def get_system_prompt(self, channel: str) -> str:
        """Devuelve el system prompt apropiado para el canal (con temática si procede)."""
        topic = self.channel_topics.get(channel.lower(), "")
        if not topic:
            return ""  # AIHandler usa su prompt base
        restriction = (
            f"RESTRICCIÓN DE CANAL: Este canal está dedicado exclusivamente a {topic}. "
            f"Solo responde sobre ese tema. Si te preguntan algo fuera de este ámbito, "
            f"declina educadamente y redirige la conversación al tema del canal."
        )
        return f"{self.ai.system_prompt_base}\n\n{restriction}".strip()

    # -----------------------------------------------------------------------
    # Eventos IRC
    # -----------------------------------------------------------------------

    def on_welcome(self, c: Any, e: Any) -> None:
        """Autenticación ChatHispano/IRC-Hispano: NICK nickname:password."""
        if self.nickserv_password:
            auth_nick = f"{c.get_nickname()}:{self.nickserv_password}"
            c.nick(auth_nick)
            logger.info("Autenticación enviada: NICK %s", auth_nick)
            time.sleep(1)

        if self.modes_on_connect:
            c.mode(c.get_nickname(), self.modes_on_connect)
            logger.info("Modos aplicados: %s", self.modes_on_connect)

        for channel in self.channels_to_join:
            c.join(channel)
        for canal in self.autojoin.channels():
            c.join(canal)

    def on_nicknameinuse(self, c: Any, e: Any) -> None:
        nuevo = c.get_nickname() + "_"
        logger.warning("Nick en uso, intentando con: %s", nuevo)
        c.nick(nuevo)

    def on_disconnect(self, c: Any, e: Any) -> None:
        """Reconexión automática ante desconexiones no intencionadas."""
        logger.warning("Desconectado del servidor. Reconectando en 15s...")
        time.sleep(15)
        self.jump_server()

    def on_privmsg(self, c: Any, e: Any) -> None:
        """
        Panel de control por mensaje privado (solo admins).

        Comandos:
          ia #canal on/off/status  — activar/desactivar el bot en un canal
          olvida #canal            — limpiar historial de un canal
          autojoin add/del/list/info/addall/rejoin [#canal]
          reload                   — recarga config.conf en caliente
          restart                  — reinicia el proceso del bot
          ayuda                    — muestra esta lista
        """
        sender = e.source.nick
        if sender.lower() not in self.admin_nicks:
            return

        raw = strip_mirc_colors(e.arguments[0]).strip()
        cmd = raw.lower()

        # ia #canal on/off/status
        if cmd.startswith("ia "):
            parts = raw.split()
            if len(parts) < 3:
                c.privmsg(sender, "\x0302Uso: ia <#canal> <on|off|status>\x03")
                return
            canal  = parts[1] if parts[1].startswith("#") else f"#{parts[1]}"
            accion = parts[2].lower()
            if accion == "on":
                self.states.set(canal, True)
                c.privmsg(sender, f"\x0303✅ Bot activado en {canal}.\x03")
                logger.info("Bot activado en %s por %s", canal, sender)
            elif accion == "off":
                self.states.set(canal, False)
                c.privmsg(sender, f"\x0304🔇 Bot desactivado en {canal}.\x03")
                logger.info("Bot desactivado en %s por %s", canal, sender)
            elif accion == "status":
                estado = "✅ activo" if self.states.is_active(canal) else "🔇 desactivado"
                c.privmsg(sender, f"\x0302ℹ️ {canal}: {estado}\x03")
            else:
                c.privmsg(sender, "\x0302Uso: ia <#canal> <on|off|status>\x03")
            return

        # olvida #canal
        if cmd.startswith("olvida"):
            parts = raw.split()
            if len(parts) < 2:
                c.privmsg(sender, "\x0302Uso: olvida <#canal>\x03")
                return
            canal = parts[1] if parts[1].startswith("#") else f"#{parts[1]}"
            if self.memory.clear(canal):
                c.privmsg(sender, f"\x0303✅ Historial limpiado para {canal}.\x03")
            else:
                c.privmsg(sender, f"\x0310ℹ️ No había historial para {canal}.\x03")
            return

        # autojoin
        if cmd.startswith("autojoin"):
            self._handle_autojoin(c, e, raw, sender)
            return

        # reload
        if cmd == "reload":
            self._reload_config()
            temas = ', '.join(self.channel_topics.keys()) or 'ninguno'
            c.privmsg(sender, f"\x0303✅ Config recargada. Temas activos: {temas}\x03")
            return

        # restart
        if cmd == "restart":
            c.privmsg(sender, "\x0310🔄 Reiniciando bot...\x03")
            time.sleep(1)
            try:
                self.die("Reiniciando...")
            except Exception:
                pass
            logger.info("Reinicio solicitado por %s", sender)
            os.execv(sys.executable, [sys.executable] + sys.argv)
            return

        # ayuda
        if cmd == "ayuda":
            msgs = [
                "\x0302📘 Comandos disponibles (solo admins, por PM):\x03",
                "\x0303• ia <#canal> on\x0302 – Activar el bot en un canal",
                "\x0303• ia <#canal> off\x0302 – Desactivar el bot en un canal",
                "\x0303• ia <#canal> status\x0302 – Ver estado del bot en un canal",
                "\x0303• olvida <#canal>\x0302 – Limpiar historial de conversación",
                "\x0303• autojoin add/del/list/info/addall/rejoin\x0302 – Gestión de canales",
                "\x0303• reload\x0302 – Recargar config.conf sin reiniciar",
                "\x0303• restart\x0302 – Reiniciar el bot completamente",
                "\x0303• ayuda\x0302 – Mostrar este mensaje",
            ]
            for m in msgs:
                c.privmsg(sender, m)
            return

        # Cualquier otro mensaje: pasarlo a la IA
        threading.Thread(
            target=self._process_ai_response,
            args=(c, sender, sender, strip_mirc_colors(e.arguments[0]).strip()),
            daemon=True,
        ).start()

    def on_pubmsg(self, c: Any, e: Any) -> None:
        """
        Mensajes de canal.
        - Comandos admin (!olvida, !reload, !restart) se procesan sin necesidad de mención.
        - La IA responde solo si el bot es mencionado y el canal está activo.
        """
        sender  = e.source.nick
        channel = e.target
        msg     = strip_mirc_colors(e.arguments[0])
        msg_stripped = msg.strip()
        bot_nick     = c.get_nickname()

        # Ignorar mensajes propios
        if sender.lower() == bot_nick.lower():
            return

        is_admin = sender.lower() in self.admin_nicks

        # ── Frases naturales de silencio/despertar (solo admins) ──────────
        if is_admin:
            msg_lower  = msg_stripped.lower()
            nick_lower = bot_nick.lower()
            dirigido   = nick_lower in msg_lower
            if dirigido and _SILENCIO.search(msg_lower):
                self.states.set(channel, False)
                c.privmsg(channel, "\x0310🔇 De acuerdo, me callo.\x03")
                logger.info("Bot silenciado en %s por %s", channel, sender)
                return
            if dirigido and _DESPERTAR.search(msg_lower):
                self.states.set(channel, True)
                c.privmsg(channel, "\x0303✅ ¡Aquí estoy de nuevo!\x03")
                logger.info("Bot activado en %s por %s", channel, sender)
                return

        # ── Comandos de canal (solo admins, sin necesidad de mención) ─────
        if is_admin:
            cmd_lower = msg_stripped.lower()

            if cmd_lower == "!olvida":
                if self.memory.clear(channel):
                    c.privmsg(channel, f"\x0303✅ Historial limpiado para {channel}.\x03")
                else:
                    c.privmsg(channel, "\x0310ℹ️ No había historial que limpiar.\x03")
                return

            if cmd_lower == "!reload":
                self._reload_config()
                temas = ', '.join(self.channel_topics.keys()) or 'ninguno'
                c.privmsg(channel, f"\x0303✅ Config recargada. Temas: {temas}\x03")
                logger.info("Conf recargado por %s", sender)
                return

            if cmd_lower == "!restart":
                c.privmsg(channel, "\x0310🔄 Reiniciando bot...\x03")
                time.sleep(1)
                try:
                    self.die("Reiniciando...")
                except Exception:
                    pass
                logger.info("Reinicio solicitado por %s", sender)
                os.execv(sys.executable, [sys.executable] + sys.argv)
                return

            if msg_stripped.lower().startswith("!autojoin"):
                self._handle_autojoin(c, e, msg_stripped, sender)
                return

            if cmd_lower == "!die":
                logger.info("Apagando por orden de %s.", sender)
                self.die("Cerrando por orden del administrador.")
                return

        # ── Ignorar si el canal está silenciado ───────────────────────────
        if not self.states.is_active(channel):
            return

        # ── Responder solo si el bot es mencionado ────────────────────────
        if bot_nick.lower() not in msg.lower():
            return

        if not self.cooldown.allowed(sender):
            return

        # Eliminar el prefijo "BotNick:" o "BotNick," del texto
        text = msg_stripped
        pattern = rf"\b{re.escape(bot_nick)}\b"
        text = re.sub(pattern, "", text, flags=re.IGNORECASE).strip().lstrip(": ,").strip()

        if not text:
            return

        logger.info("Solicitud de %s en %s: %s", sender, channel, text)

        threading.Thread(
            target=self._process_ai_response,
            args=(c, channel, channel, text),
            daemon=True,
        ).start()

    # -----------------------------------------------------------------------
    # Lógica IA (corre en hilo separado para no bloquear el reactor)
    # -----------------------------------------------------------------------

    def _process_ai_response(self, c: Any, target: str, channel: str, text: str) -> None:
        """Añade al historial, llama a la IA y envía la respuesta. Thread-safe."""
        try:
            self.memory.add_message(channel, "user", text)
            context = self.memory.get_context(channel)

            ch_prompt = self.get_system_prompt(channel)
            response  = self.ai.ask(context, text, channel_prompt=ch_prompt)

            if not response:
                self.memory.revert_last_user(channel)
                return

            self.memory.add_message(channel, "assistant", response)
            self._send_response(c, target, response)

        except Exception as e:
            self.memory.revert_last_user(channel)
            logger.error("Error en _process_ai_response: %s", e)

            error_map = {
                "QUOTA_EXCEEDED":       "⚠️ Se ha excedido la cuota de API. Intenta más tarde.",
                "INSUFFICIENT_CREDITS": "⚠️ Créditos insuficientes en OpenRouter.",
                "TIMEOUT":              "⏱️ La solicitud tardó demasiado. Intenta de nuevo.",
                "NETWORK_ERROR":        "🌐 Error de conexión con la API.",
                "MAX_RETRIES_EXCEEDED": "⚠️ No se pudo obtener respuesta tras varios intentos.",
            }
            error_str = str(e)
            for key, msg in error_map.items():
                if key in error_str:
                    c.privmsg(target, msg)
                    return
            c.privmsg(target, "⚠️ Error al procesar la respuesta.")

    def _send_response(self, c: Any, target: str, response: str) -> None:
        """Post-procesa y envía la respuesta al canal respetando max_parts."""
        response = postprocess_response(response)
        parts    = split_into_irc_parts(response, max_length=self.max_len)

        if len(parts) > self.max_parts:
            parts = parts[:self.max_parts]
            parts[-1] += " [...]"

        for i, part in enumerate(parts):
            part = part.replace('\r', '').replace('\n', ' ').strip()
            if not part:
                continue
            c.privmsg(target, part)
            if i < len(parts) - 1:
                time.sleep(0.8)

    # -----------------------------------------------------------------------
    # Gestión de !autojoin
    # -----------------------------------------------------------------------

    def _handle_autojoin(self, c: Any, e: Any, raw: str, sender: str) -> None:
        """Gestiona todos los subcomandos de autojoin."""
        # Destino de respuesta: canal si viene de pubmsg, PM si viene de privmsg
        target = e.target if irc.client.is_channel(e.target) else sender
        parts  = raw.strip().split()

        if len(parts) < 2 or parts[1].lower() in ("help", "ayuda"):
            c.privmsg(target, "\x0302📘 Subcomandos de \x0310!autojoin\x03:")
            c.privmsg(target, "\x0303• add <#canal>\x0302 – Añade un canal a la lista autojoin")
            c.privmsg(target, "\x0303• del <#canal>\x0302 – Elimina un canal de la lista")
            c.privmsg(target, "\x0303• list\x0302 – Muestra los canales registrados")
            c.privmsg(target, "\x0303• info <#canal>\x0302 – Detalles de un canal")
            c.privmsg(target, "\x0303• addall\x0302 – Registra todos los canales actuales")
            c.privmsg(target, "\x0303• rejoin\x0302 – Reunirse a todos los canales registrados")
            return

        sub = parts[1].lower()

        if sub == "add":
            if len(parts) < 3 or not parts[2].startswith('#'):
                c.privmsg(target, "\x0302Uso: autojoin add <#canal>\x03")
                return
            canal = parts[2]
            if self.autojoin.add(canal, sender):
                c.join(canal)
                c.privmsg(target, f"\x0303✅ Canal {canal} registrado y unido.\x03")
            else:
                c.privmsg(target, f"\x0310⚠️ El canal {canal} ya estaba registrado.\x03")

        elif sub == "del":
            if len(parts) < 3 or not parts[2].startswith('#'):
                c.privmsg(target, "\x0302Uso: autojoin del <#canal>\x03")
                return
            canal = parts[2]
            if self.autojoin.remove(canal):
                c.part(canal, "Canal eliminado por el admin.")
                c.privmsg(target, f"\x0304🗑️ Canal {canal} eliminado de la lista.\x03")
            else:
                c.privmsg(target, f"\x0310⚠️ El canal {canal} no estaba registrado.\x03")

        elif sub == "list":
            canales = self.autojoin.channels()
            if not canales:
                c.privmsg(target, "\x0310📭 No hay canales registrados.\x03")
            else:
                c.privmsg(target, "\x0302📜 Canales registrados:\x03")
                for ch in canales:
                    c.privmsg(target, f"\x0302• {ch}\x03")

        elif sub == "info":
            if len(parts) < 3:
                c.privmsg(target, "\x0302Uso: autojoin info <#canal>\x03")
                return
            canal = parts[2]
            info  = self.autojoin.info(canal)
            if info:
                c.privmsg(target, f"\x0302ℹ️ {canal}: registrado por {info['registrado_por']} el {info['fecha']} a las {info['hora']}\x03")
            else:
                c.privmsg(target, f"\x0310❓ No hay información de {canal}.\x03")

        elif sub == "addall":
            current = list(self.channels.keys())  # canales en los que está el bot ahora
            count   = self.autojoin.add_all(current, sender)
            c.privmsg(target, f"\x0303✅ Se añadieron {count} nuevos canales a la lista.\x03")

        elif sub == "rejoin":
            c.privmsg(target, "\x0302🔁 Reuniéndose a todos los canales registrados...\x03")
            for canal in self.autojoin.channels():
                c.join(canal)

        else:
            c.privmsg(target, f"\x0304❌ Subcomando no reconocido: {sub}\x03")


# ---------------------------------------------------------------------------
# Entrada
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    irc.client.ServerConnection.buffer_class = buffer.LenientDecodingLineBuffer
    try:
        bot = OpenRouterBot()
        bot.start()
    except KeyboardInterrupt:
        logger.info("Bot detenido manualmente.")
    except Exception as e:
        logger.critical("Error fatal: %s", e)
