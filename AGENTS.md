# IRC Bots — AGENTS.md

## REGLA DE IDIOMA (OBLIGATORIA)

Idioma: **español de España (castellano)**. Prohibido terminantemente:
- Voseo ("decime", "dame", "levantame", etc.)
- Rioplatense/argentino
- Modo imperativo con pronombre enclítico ("dime" → "di", "hazme" → "haz", "dame" → "da")

Usar siempre imperativo de "tú": "di", "haz", "da", "prueba", "mira".

This is a **Python IRC bot ecosystem**. The `package.json` is a stub (only `autoskills`/`docx`). No test/lint/build system exists.

## Active bots

| Bot | Dir | Network | Host | Entrypoint |
|-----|-----|---------|------|------------|
| MiLeNiUm | `bots/milenium/` | ChatZona | PC B | `iabot.py` |
| iND0MiTa | `bots/indomita/` | ChatZona | PC B | `falkian.py` |
| BoT-GPT | `bots/bot-gpt/` | ChatHispano | VPS Corazón | `gemini.py` |
| CiberBot | `bots/seg-infor/` | ChatHispano | VPS | `bot.py` |
| BeBeSaUrIo | `bots/bebesaurio/` | ChatZona | VPS | `bebesaurio.py` |
| MaLeFiCo | `bots/futbot/` | ChatHispano | VPS Corazón | `futbot.py` |
| TelegramBot | `bots/telegrambot/` | Telegram | local/VPS | `telegram_bot.py` |

Each bot is **self-contained** (`.py` + `.conf` in its folder). Runtime files (`autojoin.json`, `conversation_history.json`, `db/`) are generated on first run.

## AI architecture

- Central AI Hub: `scripts/ia_central.py` (`class AICentralHub`)
- Config: `AGENTS_COOP/GLOBAL_AI_HUB.json`
- Fallback chain: NVIDIA → Cerebras → Groq → Cloudflare → HuggingFace → OpenRouter → Gemini → DeepSeek

## Infrastructure

| Node | Address | Role |
|------|---------|------|
| PC B (Local) | `192.168.100.37:2222` (Linux Mint) | Production host for MiLeNiUm, iND0MiTa |
| VPS Corazón | `217.160.136.43:22` (Debian 13) | Heartbeat server (:8384), Cerebro, Eggdrop bots, BoT-GPT |
| VPS Panel | `93.93.116.244:26621` (Ubuntu 24.04) | Backup node; SSH key auth enabled |

SSH keys:
- PC B: `scripts/wsl_key`
- VPS Panel: `/root/.ssh/id_ed25519` (ed25519, passphrase vacía)

## IRC auth quirks

- **ChatHispano**: `conn.connect(server, port, f"{nickname}:{password}", username=ident)` — `username=ident` is required or connection resets.
- **ChatZona**: `conn.privmsg("NiCK", f"IDENTIFY {password}")` in `on_welcome` event.

## Technical gotchas

- Use `irc.client.ServerConnection.buffer_class = LenientDecodingLineBuffer` (NOT `Server.buffer_class` — doesn't exist in new versions).
- AI calls must run in `threading.Thread(daemon=True)` to not block the IRC reactor.
- Exception naming: `ApiTimeoutError` not `TimeoutError` (collides with built-in).
- `logging.basicConfig(force=True)` to avoid duplicate handlers on re-import.
- Config files in `config/` and `AGENTS_COOP/GLOBAL_AI_HUB.json` contain live API keys — never commit.
- **Always start bots from their own directory** or files loaded with `Path("autojoin.json")` etc (relative paths) won't be found. Correct: `cd bots/milenium/ && python3 iabot.py`.
- **`!comando ` vs `!comando`**: A trailing space in `startswith("!comando ")` makes the command fail when used without arguments. Use `startswith("!comando")`.
- **IRC user_modes**: If a bot has `+c` (deaf_commonchan), users can't send it PRIVMSG. Add `-c` to `user_modes` to remove it.

## Eggdrop bots (VPS Corazón only)

- KaBoT: `/home/irc/eggdrop/`, Heimdall: `/home/irc/heimdall/`
- Python scripts for Eggdrop: `import eggdrop.tcl as tcl` (NOT `import tcl`).
- Callback signature: `(nick, host, hand, chan, text, **kwargs)`.
- Wrap in `try/except` + `traceback.format_exc()` — Eggdrop only shows "Error" with no detail.

## Documentation sources

- `AGENTS_COOP/AGENTS_COOP.md` — comprehensive project docs (Spanish)
- `AGENTS_COOP/GAMES_API.md` — Impostor & Bingo game module APIs
- `.geminirules` / `GEMINI.md` — autonomy directives (Spanish; precede other instructions)
- `skills-lock.json` — autoskills registry

## Commands

```bash
# Run a bot (any)
python3 bots/milenium/iabot.py

# No test/lint/typecheck — none exist
```
