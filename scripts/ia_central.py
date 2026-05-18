import json
import os
import requests
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Configuración de Rutas
def _find_config():
    # 1. Rutas absolutas conocidas para entornos de producción (Linux)
    paths = [
        "/home/juanjo/ircbots/AGENTS_COOP/GLOBAL_AI_HUB.json",  # PC B
        "/home/irc/ircbots/AGENTS_COOP/GLOBAL_AI_HUB.json",    # VPS 2
        "/home/irc/scripts/GLOBAL_AI_HUB.json"                # VPS 2 (alt)
    ]
    for p in paths:
        if Path(p).exists():
            return Path(p)

    # 2. Búsqueda relativa para desarrollo (Local)
    current = Path(__file__).resolve().parent
    for _ in range(3):
        prob = current / "AGENTS_COOP" / "GLOBAL_AI_HUB.json"
        if prob.exists():
            return prob
        current = current.parent
    
    return Path(__file__).parent / "GLOBAL_AI_HUB.json"

CONFIG_PATH = _find_config()

# OpenAI-compatible client (para DeepSeek y Mistral)
_OpenAI = None
try:
    from openai import OpenAI
    _OpenAI = OpenAI
    _HAS_OPENAI = True
except ImportError:
    _HAS_OPENAI = False


class AICentralHub:
    """Gestor centralizado de APIs de IA para el ecosistema de bots."""

    def __init__(self):
        self.config = self._load_config()
        self.log = logging.getLogger("AI_HUB")

    def _load_config(self) -> Dict[str, Any]:
        try:
            if CONFIG_PATH.exists():
                return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Error cargando Hub Global: {e}")
        
        # Fallback de seguridad si el archivo no existe
        return {
            "api_keys": {},
            "preferred_models": {"chat": "meta-llama/llama-3.3-70b-instruct:free"},
            "fallbacks": ["groq", "openrouter"]
        }

    def has_keys(self) -> bool:
        return bool(self.config.get("api_keys", {}))

    def get_key(self, provider: str) -> str:
        return self.config.get("api_keys", {}).get(provider.lower(), "")

    def get_model(self, category: str = "chat") -> str:
        return self.config.get("preferred_models", {}).get(category, "meta-llama/llama-3.3-70b-instruct:free")

    # ─── Interfaz principal: prompt simple (para moderación) ──────────────────

    def call_ai(
        self,
        prompt: str,
        system_prompt: str = "",
        category: str = "chat",
        max_tokens: int = 80,
        timeout: int = 10,
    ) -> Tuple[Optional[str], str]:
        """
        Llama a la IA con un prompt simple (una sola vuelta).
        Devuelve (texto_respuesta, proveedor) o (None, "") si todo falla.
        """
        fallbacks = self.config.get("fallbacks", ["nvidia", "groq", "openrouter"])
        
        for provider in fallbacks:
            key = self.get_key(provider)
            if not key:
                print(f"[AI_HUB] ⏭️ {provider}: sin key, saltando...")
                continue

            print(f"[AI_HUB] 🔄 Intentando {provider}...")
            res, model_used = self._dispatch_call(
                provider, key, prompt, system_prompt, category,
                max_tokens=max_tokens, timeout=timeout,
            )
            if res:
                print(f"[AI_HUB] ✅ {provider}/{model_used}: respuesta OK")
                return res, f"{provider}/{model_used}"
            else:
                print(f"[AI_HUB] ❌ {provider}/{model_used}: falló")
        
        print("[AI_HUB] 💀 Todos los proveedores fallaron")
        return None, ""

    # ─── Interfaz multi-turn: mensajes (para chat) ────────────────────────────

    def call_ai_messages(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str = "",
        category: str = "chat",
        max_tokens: int = 1024,
        timeout: int = 30,
    ) -> Tuple[Optional[str], str]:
        """
        Llama a la IA con historial multi-turn (para chatbots).
        Devuelve (texto_respuesta, proveedor) o (None, "") si todo falla.
        """
        fallbacks = self.config.get("fallbacks", ["nvidia", "groq", "openrouter"])
        
        for provider in fallbacks:
            key = self.get_key(provider)
            if not key:
                print(f"[AI_HUB] ⏭️ {provider}: sin key, saltando...")
                continue

            print(f"[AI_HUB] 🔄 Intentando {provider} (multi-turn)...")
            res, model_used = self._dispatch_call_messages(
                provider, key, messages, system_prompt, category,
                max_tokens=max_tokens, timeout=timeout,
            )
            if res:
                print(f"[AI_HUB] ✅ {provider}/{model_used}: respuesta OK")
                return res, f"{provider}/{model_used}"
            else:
                print(f"[AI_HUB] ❌ {provider}/{model_used}: falló")
        
        print("[AI_HUB] 💀 Todos los proveedores fallaron")
        return None, ""

    # ─── Dispatch por proveedor (prompt simple) ───────────────────────────────

    def _dispatch_call(
        self, provider: str, key: str, prompt: str,
        system: str, cat: str,
        max_tokens: int = 80, timeout: int = 10,
    ) -> Tuple[Optional[str], str]:
        if provider == "groq":
            return self._call_groq(key, prompt, system, cat, max_tokens, timeout)
        elif provider == "nvidia":
            return self._call_nvidia(key, prompt, system, cat, max_tokens, timeout)
        elif provider == "openrouter":
            return self._call_openrouter(key, prompt, system, cat, max_tokens, timeout)
        elif provider == "gemini":
            return self._call_gemini(key, prompt, system, cat, max_tokens, timeout)
        elif provider == "deepseek":
            return self._call_deepseek(key, prompt, system, cat, max_tokens, timeout)
        elif provider == "cerebras":
            return self._call_cerebras(key, prompt, system, cat, max_tokens, timeout)
        elif provider == "cloudflare":
            return self._call_cloudflare(key, prompt, system, cat, max_tokens, timeout)
        elif provider == "huggingface":
            return self._call_huggingface(key, prompt, system, cat, max_tokens, timeout)
        elif provider == "cohere":
            return self._call_cohere(key, prompt, system, cat, max_tokens, timeout)
        return None, ""

    # ─── Dispatch por proveedor (multi-turn) ──────────────────────────────────

    def _dispatch_call_messages(
        self, provider: str, key: str,
        messages: List[Dict[str, str]], system: str, cat: str,
        max_tokens: int = 1024, timeout: int = 30,
    ) -> Tuple[Optional[str], str]:
        if provider == "groq":
            return self._call_groq_messages(key, messages, system, cat, max_tokens, timeout)
        elif provider == "nvidia":
            return self._call_nvidia_messages(key, messages, system, cat, max_tokens, timeout)
        elif provider == "openrouter":
            return self._call_openrouter_messages(key, messages, system, cat, max_tokens, timeout)
        elif provider == "gemini":
            return self._call_gemini_messages(key, messages, system, cat, max_tokens, timeout)
        elif provider == "deepseek":
            return self._call_deepseek_messages(key, messages, system, cat, max_tokens, timeout)
        elif provider == "cerebras":
            return self._call_cerebras_messages(key, messages, system, cat, max_tokens, timeout)
        elif provider == "cloudflare":
            return self._call_cloudflare_messages(key, messages, system, cat, max_tokens, timeout)
        elif provider == "huggingface":
            return self._call_huggingface_messages(key, messages, system, cat, max_tokens, timeout)
        elif provider == "cohere":
            return self._call_cohere_messages(key, messages, system, cat, max_tokens, timeout)
        return None, ""

    # ═══════════════════════════════════════════════════════════════════════════
    #  GROQ
    # ═══════════════════════════════════════════════════════════════════════════

    def _call_groq(
        self, key: str, prompt: str, system: str, cat: str,
        max_tokens: int = 80, timeout: int = 10,
    ) -> Tuple[Optional[str], str]:
        model = self.config.get("models", {}).get("groq", "llama-3.3-70b-versatile")
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 0}
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=timeout)
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"], model
            elif r.status_code == 429:
                self.log.warning("[Groq] Rate limit.")
        except requests.exceptions.Timeout:
            self.log.warning("[Groq] Timeout.")
        except Exception as e:
            self.log.warning("[Groq] Error: %s", e)
        return None, model

    def _call_groq_messages(
        self, key: str, messages: List[Dict[str, str]], system: str, cat: str,
        max_tokens: int = 1024, timeout: int = 30,
    ) -> Tuple[Optional[str], str]:
        model = self.config.get("models", {}).get("groq", "llama-3.3-70b-versatile")
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        full_messages = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)
        payload = {"model": model, "messages": full_messages, "max_tokens": max_tokens, "temperature": 0.7}
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=timeout)
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"], model
        except Exception as e:
            self.log.warning("[Groq] Error: %s", e)
        return None, model

    # ═══════════════════════════════════════════════════════════════════════════
    #  NVIDIA NIM
    # ═══════════════════════════════════════════════════════════════════════════

    def _call_nvidia(
        self, key: str, prompt: str, system: str, cat: str,
        max_tokens: int = 80, timeout: int = 10,
    ) -> Tuple[Optional[str], str]:
        model = self.config.get("models", {}).get("nvidia", "meta/llama-3.3-70b-instruct")
        url = "https://integrate.api.nvidia.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {"model": model, "messages": messages, "temperature": 0.5, "max_tokens": max_tokens}
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=timeout)
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"], model
        except Exception as e:
            self.log.warning("[NVIDIA] Error: %s", e)
        return None, model

    def _call_nvidia_messages(
        self, key: str, messages: List[Dict[str, str]], system: str, cat: str,
        max_tokens: int = 1024, timeout: int = 30,
    ) -> Tuple[Optional[str], str]:
        model = self.config.get("models", {}).get("nvidia", "meta/llama-3.3-70b-instruct")
        url = "https://integrate.api.nvidia.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        full_messages = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)
        payload = {"model": model, "messages": full_messages, "temperature": 0.5, "max_tokens": max_tokens}
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=timeout)
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"], model
        except Exception as e:
            self.log.warning("[NVIDIA] Error: %s", e)
        return None, model

    # ═══════════════════════════════════════════════════════════════════════════
    #  OPENROUTER
    # ═══════════════════════════════════════════════════════════════════════════

    _OPENROUTER_FALLBACK_CHAIN: List[str] = [
        "google/gemma-3-27b-it:free",
        "google/gemma-3-12b-it:free",
        "google/gemma-3-4b-it:free",
        "google/gemma-3n-4b-it:free",
        "google/gemma-3n-2b-it:free",
        "openrouter/free",
    ]

    def _build_openrouter_chain(self, preferred: str) -> List[str]:
        chain = []
        if preferred:
            chain.append(preferred)
        for m in self._OPENROUTER_FALLBACK_CHAIN:
            if m not in chain:
                chain.append(m)
        return chain

    def _call_openrouter(
        self, key: str, prompt: str, system: str, cat: str,
        max_tokens: int = 80, timeout: int = 10,
    ) -> Tuple[Optional[str], str]:
        preferred = self.config.get("models", {}).get("openrouter", "openai/gpt-oss-120b:free")
        chain = self._build_openrouter_chain(preferred)
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

        for model in chain:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 0}
            try:
                r = requests.post(url, json=payload, headers=headers, timeout=timeout)
                if r.status_code == 200:
                    raw = r.json().get("choices", [{}])[0].get("message", {}).get("content") or ""
                    return self._limpiar_respuesta(raw), model
                elif r.status_code == 429:
                    self.log.warning("[OpenRouter] Rate limit (%s). Siguiente...", model)
                    time.sleep(5)
                    continue
                elif r.status_code in (401, 402):
                    self.log.error("[OpenRouter] Auth/creditos (%d).", r.status_code)
                    return None, model
                else:
                    continue
            except requests.exceptions.Timeout:
                continue
            except Exception as e:
                self.log.warning("[OpenRouter] Error (%s): %s", model, e)
                continue
        return None, ""

    def _call_openrouter_messages(
        self, key: str, messages: List[Dict[str, str]], system: str, cat: str,
        max_tokens: int = 1024, timeout: int = 30,
    ) -> Tuple[Optional[str], str]:
        preferred = self.config.get("models", {}).get("openrouter", "openai/gpt-oss-120b:free")
        chain = self._build_openrouter_chain(preferred)
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

        for model in chain:
            full_messages = []
            if system:
                full_messages.append({"role": "system", "content": system})
            full_messages.extend(messages)
            payload = {"model": model, "messages": full_messages, "max_tokens": max_tokens, "temperature": 0.7}
            try:
                r = requests.post(url, json=payload, headers=headers, timeout=timeout)
                if r.status_code == 200:
                    result = r.json()
                    text = result["choices"][0]["message"]["content"]
                    return text, result.get("model", model)
                elif r.status_code == 429:
                    time.sleep(5)
                    continue
                elif r.status_code in (401, 402):
                    return None, model
                else:
                    continue
            except Exception:
                continue
        return None, ""

    # ═══════════════════════════════════════════════════════════════════════════
    #  GEMINI
    # ═══════════════════════════════════════════════════════════════════════════

    def _call_gemini(
        self, key: str, prompt: str, system: str, cat: str,
        max_tokens: int = 80, timeout: int = 10,
    ) -> Tuple[Optional[str], str]:
        model = self.config.get("models", {}).get("gemini", "gemini-2.5-flash")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        payload: Dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0},
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        try:
            r = requests.post(url, json=payload, timeout=timeout)
            if r.status_code == 200:
                return r.json()["candidates"][0]["content"]["parts"][0]["text"], model
            elif r.status_code == 429:
                self.log.warning("[Gemini] Rate limit.")
        except requests.exceptions.Timeout:
            self.log.warning("[Gemini] Timeout.")
        except Exception as e:
            self.log.warning("[Gemini] Error: %s", e)
        return None, model

    def _call_gemini_messages(
        self, key: str, messages: List[Dict[str, str]], system: str, cat: str,
        max_tokens: int = 1024, timeout: int = 30,
    ) -> Tuple[Optional[str], str]:
        model = self.config.get("models", {}).get("gemini", "gemini-2.5-flash")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        contents = [
            {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
            for m in messages
        ]
        payload: Dict[str, Any] = {"contents": contents}
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        try:
            r = requests.post(url, json=payload, timeout=timeout)
            if r.status_code == 200:
                return r.json()["candidates"][0]["content"]["parts"][0]["text"], model
        except Exception as e:
            self.log.warning("[Gemini] Error: %s", e)
        return None, model

    # ═══════════════════════════════════════════════════════════════════════════
    #  DEEPSEEK
    # ═══════════════════════════════════════════════════════════════════════════

    def _call_deepseek(
        self, key: str, prompt: str, system: str, cat: str,
        max_tokens: int = 80, timeout: int = 10,
    ) -> Tuple[Optional[str], str]:
        if not _HAS_OPENAI:
            self.log.error("[DeepSeek] Requiere 'openai'. pip install openai")
            return None, ""
        model = self.config.get("models", {}).get("deepseek", "deepseek-chat")
        client = _OpenAI(api_key=key, base_url="https://api.deepseek.com/v1")
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            c = client.chat.completions.create(
                model=model, messages=messages, max_tokens=max_tokens, temperature=0, timeout=timeout,
            )
            return c.choices[0].message.content, model
        except Exception as e:
            err = str(e).lower()
            if "429" in err or "rate_limit" in err:
                self.log.warning("[DeepSeek] Rate limit.")
            elif "timeout" in err:
                self.log.warning("[DeepSeek] Timeout.")
            else:
                self.log.warning("[DeepSeek] Error: %s", e)
        return None, ""

    def _call_deepseek_messages(
        self, key: str, messages: List[Dict[str, str]], system: str, cat: str,
        max_tokens: int = 1024, timeout: int = 30,
    ) -> Tuple[Optional[str], str]:
        if not _HAS_OPENAI:
            return None, ""
        model = self.config.get("models", {}).get("deepseek", "deepseek-chat")
        client = _OpenAI(api_key=key, base_url="https://api.deepseek.com/v1")
        full_messages = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)
        try:
            c = client.chat.completions.create(
                model=model, messages=full_messages, max_tokens=max_tokens, temperature=0.7, timeout=timeout,
            )
            return c.choices[0].message.content, model
        except Exception as e:
            self.log.warning("[DeepSeek] Error: %s", e)
        return None, ""

    # ─── Utilidades ───────────────────────────────────────────────────────────

    # ═══════════════════════════════════════════════════════════════════════════
    #  CLOUDFLARE WORKERS AI
    # ═══════════════════════════════════════════════════════════════════════════

    def _call_cloudflare(
        self, key: str, prompt: str, system: str, cat: str,
        max_tokens: int = 80, timeout: int = 15,
    ) -> Tuple[Optional[str], str]:
        account_id = "ecfabc647ba017d73510efb7b61954df"
        model = self.config.get("models", {}).get("cloudflare", "@cf/meta/llama-3-8b-instruct")
        url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        payload = {"messages": messages, "max_tokens": max_tokens}
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=timeout)
            if r.status_code == 200:
                result = r.json()
                if result.get("success"):
                    return result["result"]["response"], model
                else:
                    self.log.warning("[Cloudflare] Error in result: %s", result.get("errors"))
            else:
                self.log.warning("[Cloudflare] HTTP %d: %s", r.status_code, r.text)
        except Exception as e:
            self.log.warning("[Cloudflare] Error: %s", e)
        return None, model

    def _call_cloudflare_messages(
        self, key: str, messages: List[Dict[str, str]], system: str, cat: str,
        max_tokens: int = 1024, timeout: int = 30,
    ) -> Tuple[Optional[str], str]:
        account_id = "ecfabc647ba017d73510efb7b61954df"
        model = self.config.get("models", {}).get("cloudflare", "@cf/meta/llama-3-8b-instruct")
        url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        
        full_messages = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)
        
        payload = {"messages": full_messages, "max_tokens": max_tokens}
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=timeout)
            if r.status_code == 200:
                result = r.json()
                if result.get("success"):
                    return result["result"]["response"], model
        except Exception as e:
            self.log.warning("[Cloudflare] Error: %s", e)
        return None, model

    # ═══════════════════════════════════════════════════════════════════════════
    #  CEREBRAS
    # ═══════════════════════════════════════════════════════════════════════════

    def _call_cerebras(
        self, key: str, prompt: str, system: str, cat: str,
        max_tokens: int = 80, timeout: int = 10,
    ) -> Tuple[Optional[str], str]:
        try:
            from cerebras.cloud.sdk import Cerebras
        except ImportError:
            self.log.error("[Cerebras] Requiere 'cerebras-cloud-sdk'. pip install cerebras-cloud-sdk")
            return None, ""
        model = self.config.get("models", {}).get("cerebras", "gpt-oss-120b")
        client = Cerebras(api_key=key)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            completion = client.chat.completions.create(
                messages=messages, model=model,
                max_completion_tokens=max_tokens, temperature=0.2, timeout=timeout,
            )
            return completion.choices[0].message.content, model
        except Exception as e:
            self.log.warning("[Cerebras] Error: %s", e)
        return None, ""

    def _call_cerebras_messages(
        self, key: str, messages: List[Dict[str, str]], system: str, cat: str,
        max_tokens: int = 1024, timeout: int = 30,
    ) -> Tuple[Optional[str], str]:
        try:
            from cerebras.cloud.sdk import Cerebras
        except ImportError:
            return None, ""
        model = self.config.get("models", {}).get("cerebras", "gpt-oss-120b")
        client = Cerebras(api_key=key)
        full_messages = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)
        try:
            completion = client.chat.completions.create(
                messages=full_messages, model=model,
                max_completion_tokens=max_tokens, temperature=0.7, timeout=timeout,
            )
            return completion.choices[0].message.content, model
        except Exception as e:
            self.log.warning("[Cerebras] Error: %s", e)
        return None, ""

    # ═══════════════════════════════════════════════════════════════════════════
    #  COHERE
    # ═══════════════════════════════════════════════════════════════════════════

    def _call_cohere(
        self, key: str, prompt: str, system: str, cat: str,
        max_tokens: int = 80, timeout: int = 10,
    ) -> Tuple[Optional[str], str]:
        model = self.config.get("models", {}).get("cohere", "command-a-03-2025")
        url = "https://api.cohere.ai/v1/chat"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        payload = {
            "model": model,
            "message": prompt,
            "max_tokens": max_tokens,
            "temperature": 0,
        }
        if system:
            payload["preamble"] = system
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=timeout)
            if r.status_code == 200:
                return r.json()["text"], model
            elif r.status_code == 429:
                self.log.warning("[Cohere] Rate limit.")
        except requests.exceptions.Timeout:
            self.log.warning("[Cohere] Timeout.")
        except Exception as e:
            self.log.warning("[Cohere] Error: %s", e)
        return None, model

    def _call_cohere_messages(
        self, key: str, messages: List[Dict[str, str]], system: str, cat: str,
        max_tokens: int = 1024, timeout: int = 30,
    ) -> Tuple[Optional[str], str]:
        model = self.config.get("models", {}).get("cohere", "command-a-03-2025")
        url = "https://api.cohere.ai/v1/chat"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        chat_history = []
        for m in messages:
            role = "USER" if m["role"] == "user" else "CHATBOT"
            chat_history.append({"role": role, "message": m["content"]})
        payload = {
            "model": model,
            "message": chat_history[-1]["message"] if chat_history else "",
            "max_tokens": max_tokens,
            "temperature": 0.7,
        }
        if chat_history:
            payload["chat_history"] = chat_history[:-1]
        if system:
            payload["preamble"] = system
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=timeout)
            if r.status_code == 200:
                return r.json()["text"], model
        except Exception as e:
            self.log.warning("[Cohere] Error: %s", e)
        return None, model

    # ═══════════════════════════════════════════════════════════════════════════
    #  HUGGING FACE ROUTER
    # ═══════════════════════════════════════════════════════════════════════════

    def _call_huggingface(
        self, key: str, prompt: str, system: str, cat: str,
        max_tokens: int = 80, timeout: int = 10,
    ) -> Tuple[Optional[str], str]:
        model = self.config.get("models", {}).get("huggingface", "meta-llama/Llama-3.3-70B-Instruct")
        url = "https://router.huggingface.co/v1/chat/completions"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 0}
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=timeout)
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"], model
            elif r.status_code == 429:
                self.log.warning("[HuggingFace] Rate limit.")
        except requests.exceptions.Timeout:
            self.log.warning("[HuggingFace] Timeout.")
        except Exception as e:
            self.log.warning("[HuggingFace] Error: %s", e)
        return None, model

    def _call_huggingface_messages(
        self, key: str, messages: List[Dict[str, str]], system: str, cat: str,
        max_tokens: int = 1024, timeout: int = 30,
    ) -> Tuple[Optional[str], str]:
        model = self.config.get("models", {}).get("huggingface", "meta-llama/Llama-3.3-70B-Instruct")
        url = "https://router.huggingface.co/v1/chat/completions"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        full_messages = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)
        payload = {"model": model, "messages": full_messages, "max_tokens": max_tokens, "temperature": 0.7}
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=timeout)
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"], model
        except Exception as e:
            self.log.warning("[HuggingFace] Error: %s", e)
        return None, model

    @staticmethod
    def _limpiar_respuesta(texto: str) -> str:
        """Limpia la respuesta cruda antes de parsear JSON."""
        import re
        texto = texto.replace("\r", "")
        texto = re.sub(r"[\u3000-\u9fff\uac00-\ud7ff\uf900-\ufaff\uff00-\uffef]", "", texto)
        texto = re.sub(r"```(?:json)?|```", "", texto)
        return texto.strip()


# Instancia global para ser importada
hub = AICentralHub()
