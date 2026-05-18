# IRC Bots

Ecosistema de bots IRC modulares escritos en Python. Cada bot es autocontenido (`.py` + configuración) y se conecta a redes IRC como ChatZona o ChatHispano.

## Bots

| Bot | Red | Propósito |
|-----|-----|-----------|
| **MiLeNiUm** | ChatZona | Chatbot conversacional con IA multi-proveedor, clima y horóscopo |
| **iND0MiTa** | ChatZona | Bot moderador con sanciones, protecciones y detección de evasión |
| **BoT-GPT** | ChatHispano | Chatbot conversacional con IA |
| **CiberBot** | ChatHispano | Asistente de ciberseguridad |
| **TelegramBot** | Telegram | Bot puente entre IRC y Telegram |

## Stack

- **Python 3.10+** — `irc.client`, `jaraco.stream`
- **AI multi-proveedor** — NVIDIA, Groq, OpenRouter, Gemini, DeepSeek (vía `scripts/ia_central.py`)
- **Testing** — pytest (ver `tests/`)

## Requisitos

```bash
pip install -r requirements.txt
```

## Configuración

Cada bot tiene un archivo `.conf.example` en su directorio. Cópialo sin la extensión `.example` y rellena tus claves:

```bash
cp bots/milenium/iabot.conf.example bots/milenium/iabot.conf
# Editar iabot.conf con tus API keys y datos de IRC
```

## Uso

```bash
cd bots/milenium/
python3 iabot.py
```

O en una sesión screen:

```bash
screen -dmS MiLeNiUm bash -c "cd bots/milenium && python3 iabot.py"
```

## Licencia

Uso personal.
