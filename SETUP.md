# Guía de instalación y despliegue

## Requisitos

- Python 3.10 o superior
- pip
- screen (opcional, para mantener bots corriendo en segundo plano)

## Instalación

```bash
# Clonar el repo
git clone https://github.com/juanjiyo/ircbots-py.git
cd ircbots-py

# Instalar dependencias
pip install -r requirements.txt
```

## Configurar un bot

Cada bot tiene un archivo de configuración de ejemplo:

```bash
# Para MiLeNiUm
cp bots/milenium/iabot.conf.example bots/milenium/iabot.conf

# Para iND0MiTa
cp bots/indomita/falkian.conf.example bots/indomita/falkian.conf
```

Edita el `.conf` con tus datos:

```ini
[irc]
server = irc.ejemplo.org
port = 6667
nickname = TuBot
ident = TuBot
password = tu_password_irc

[groq]
api_key = tu_api_key
```

### Proveedores de IA

Los bots usan un sistema de fallback multi-proveedor. Necesitas al menos una API key:

| Proveedor | Cómo obtenerla |
|-----------|---------------|
| **Groq** | https://console.groq.com (gratis, 1000 req/día) |
| **OpenRouter** | https://openrouter.ai (gratis con modelos free) |
| **Gemini** | https://aistudio.google.com (gratis) |
| **DeepSeek** | https://platform.deepseek.com |

Las claves se configuran en el `.conf` del bot o globalmente en `scripts/GLOBAL_AI_HUB.json`.

## Ejecutar un bot

Directamente:

```bash
cd bots/milenium
python3 iabot.py
```

Con screen (recomendado para producción):

```bash
screen -dmS MiLeNiUm bash -c "cd bots/milenium && python3 iabot.py"
```

Para ver la sesión:

```bash
screen -r MiLeNiUm
```

Para desconectarte sin cerrarla: `Ctrl+A`, luego `D`.

### Detener un bot

```bash
# Si está en screen
screen -S MiLeNiUm -X quit

# O matar el proceso
pkill -f "python3 iabot.py"
```

## Redes IRC soportadas

| Red | Autenticación |
|-----|--------------|
| **ChatZona** | `PRIVMSG NiCK IDENTIFY <password>` en evento welcome |
| **ChatHispano** | `NICK:PASSWORD` en connect (`username=ident` requerido) |

Ver `AGENTS.md` para más detalles técnicos.

## Tests

```bash
pytest tests/
```

## Linting

```bash
ruff check .
ruff format .
```
