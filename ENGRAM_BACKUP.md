# Engram Memory Backup — IRC Bots

Generado: jue 14 may 2026 03:40:54 CEST
Proyecto: ircbots


---

---
id: 9
type: architecture
project: ircbots
scope: project
topic_key: ""
session_id: manual-save-ircbots
created_at: "2026-05-12 23:19:28"
updated_at: "2026-05-12 23:19:28"
revision_count: 1
tags:
  - ircbots
  - architecture
aliases:
  - "AGENTS_COOP - Documentación completa del proyecto"
---

# AGENTS_COOP - Documentación completa del proyecto

Documento consolidado (17430 líneas) del directorio AGENTS_COOP/. Contiene: (1) Reglas maestras Antigravity: ejecución autónoma total, sin pedir permiso, SafeToAutoRun=true. (2) Trío de agentes: Usuario (arquitecto), OpenCode/MiMo (análisis profundo), Gemini CLI (ejecución táctica). (3) Filosofía: autonomía total, cambios quirúrgicos, flujo directo. (4) Reglas de oro: no pedir permiso, implementar bugs/mejoras directamente, modificar solo lo necesario. (5) Handoff: TASK_MEMORY.md para sincronización, tickets .md para tareas complejas. (6) VPS Corazón (Debian 13, 217.160.136.43): heartbeat server, cerebro, KaBoT, Heimdall, BoT-GPT, MaLeFiCo. (7) VPS Panel (Ubuntu 24.04, 93.93.116.244:26621): backup node, IP baneada en ChatZona. (8) PC B (192.168.100.37:2222, Linux Mint): producción local MiLeNiUm e iND0MiTa. (9) PC A: gaming/IA puntual, NemoClaw pendiente de deshabilitar. (10) PC C: centro de mando de agentes. (11) SSH key: scripts/wsl_key. (12) AI Hub centralizado: scripts/ia_central.py con GLOBAL_AI_HUB.json. (13) Cerebro: telegram_agent_brain.py en VPS Corazón, monitorea heartbeats.

---
*Session*: [[session-manual-save-ircbots]]

---

---
id: 12
type: architecture
project: ircbots
scope: project
topic_key: ""
session_id: manual-save-ircbots
created_at: "2026-05-12 23:19:47"
updated_at: "2026-05-12 23:19:47"
revision_count: 1
tags:
  - ircbots
  - architecture
aliases:
  - "Bots Eggdrop (VPS Corazón) - Reglas Python"
---

# Bots Eggdrop (VPS Corazón) - Reglas Python

Del AGENTS_COOP.md: KaBoT en /home/irc/eggdrop/, Heimdall en /home/irc/heimdall/. Reglas Python Eggdrop 1.10.1: (1) import eggdrop.tcl as tcl (NO import tcl). (2) Callback pub/pubm: (nick, host, hand, chan, text, **kwargs). (3) NO usar tcl.clock_format/tcl.clock_seconds, usar datetime de Python. (4) pip3 install brotli --break-system-packages. (5) Envolver en try/except + traceback.format_exc() y enviar a IRC porque Eggdrop solo muestra 'Error calling python code'. (6) Scripts: horoscopo_native.py (v4.6) para 12 signos. (7) Levantar: /home/irc/levantar_bots.sh. Reiniciar KaBoT: pkill -9 -u irc eggdrop && cd /home/irc/eggdrop && ./eggdrop eggdrop.conf. Heimdall: pkill -9 -u irc heimdall && cd /home/irc/heimdall && ./heimdall eggdrop.conf.

---
*Session*: [[session-manual-save-ircbots]]

---

---
id: 10
type: architecture
project: ircbots
scope: project
topic_key: ""
session_id: manual-save-ircbots
created_at: "2026-05-12 23:19:35"
updated_at: "2026-05-12 23:19:35"
revision_count: 1
tags:
  - ircbots
  - architecture
aliases:
  - "Bots IRC - Detalles técnicos y gotchas"
---

# Bots IRC - Detalles técnicos y gotchas

Del AGENTS_COOP.md: (1) Router IA multi-proveedor: NVIDIA NIM (primario, meta/llama-3.3-70b-instruct, 40 req/min) -> Cerebras -> Groq (llama-3.3-70b-versatile, 1000 req/día) -> Cloudflare Workers AI (@cf/meta/llama-3-8b-instruct) -> HuggingFace (meta-llama/Llama-3.3-70B-Instruct) -> OpenRouter (cadena interna: gemma-3-27b, step-3.5-flash, etc) -> Gemini (gemini-1.5-flash) -> DeepSeek (deepseek-chat). (2) Excepciones tipadas: ApiError, InvalidApiKeyError, QuotaExceededError, InsufficientCreditsError, ApiTimeoutError (NO TimeoutError), NetworkError, ModelNotFoundError, MaxRetriesExceededError, ApiError400. (3) ChatHispano auth: conn.connect(server, port, f'{nick}:{pass}', username=ident). (4) ChatZona auth: conn.privmsg('NiCK', f'IDENTIFY {password}') en on_welcome. (5) NUNCA modificar lógica de autenticacion. (6) buffer_class: ServerConnection.buffer_class = LenientDecodingLineBuffer (NO Server.buffer_class). (7) username=ident obligatorio en connect() para ChatHispano. (8) logging.basicConfig(force=True). (9) IA en threading.Thread(daemon=True). (10) Cada bot autocontenido en bots/<nombre>/ con .py + .conf. (11) Heartbeat: POST cada 60s a VPS Corazón:8384, timeout 180s. (12) ChatZona verificacion: no bloquea si nick registrado.

---
*Session*: [[session-manual-save-ircbots]]

---

---
id: 7
type: architecture
project: ircbots
scope: project
topic_key: ""
session_id: manual-save-ircbots
created_at: "2026-05-12 23:18:07"
updated_at: "2026-05-12 23:18:07"
revision_count: 1
tags:
  - ircbots
  - architecture
aliases:
  - "Estructura del proyecto IRC Bots"
---

# Estructura del proyecto IRC Bots

Repositorio de bots IRC en Python. 7 bots activos: MiLeNiUm (bots/milenium/iabot.py, ChatZona, PC B), iND0MiTa (bots/indomita/falkian.py, ChatZona, PC B), BoT-GPT (bots/bot-gpt/gemini.py, ChatHispano, VPS Corazón 217.160.136.43), CiberBot, BeBeSaUrIo, MaLeFiCo, TelegramBot. Sin sistema de test/lint (package.json es stub). AI Hub centralizado en scripts/ia_central.py. Cada bot es autocontenido (.py + .conf). Autenticación IRC: ChatHispano usa NICK:PASSWORD, ChatZona usa PRIVMSG NiCK IDENTIFY.

---
*Session*: [[session-manual-save-ircbots]]

---

---
id: 1
type: bugfix
project: ircbots
scope: project
topic_key: ""
session_id: manual-save-ircbots
created_at: "2026-05-12 23:17:42"
updated_at: "2026-05-12 23:17:42"
revision_count: 1
tags:
  - ircbots
  - bugfix
aliases:
  - "Daily tiradas silenciadas (economia.py)"
---

# Daily tiradas silenciadas (economia.py)

Se eliminó el anuncio público de las 1000 tiradas diarias. El fix se aplicó en bots/milenium/juegos/core/economia.py (local) y /home/irc/gemini/juegos/core/economia.py (VPS Corazón). Las tiradas se siguen entregando pero sin mensaje al canal.

---
*Session*: [[session-manual-save-ircbots]]

---

---
id: 2
type: bugfix
project: ircbots
scope: project
topic_key: ""
session_id: manual-save-ircbots
created_at: "2026-05-12 23:17:46"
updated_at: "2026-05-12 23:17:46"
revision_count: 1
tags:
  - ircbots
  - bugfix
aliases:
  - "Emojis eliminados de comandos sociales IRC"
---

# Emojis eliminados de comandos sociales IRC

Los emojis no se renderizan en IRC. Se eliminaron de beso, abrazo, sexo y sexometro. Además los códigos IRC (\x02 bold, \x03 color, \x0F reset) deben ser bytes reales 0x02/0x03/0x0F, no el texto literal '\x02'. Archivo: juegos/core/social.py

---
*Session*: [[session-manual-save-ircbots]]

---

---
id: 15
type: bugfix
project: ircbots
scope: project
topic_key: ""
session_id: manual-save-ircbots
created_at: "2026-05-13 03:55:00"
updated_at: "2026-05-13 03:55:00"
revision_count: 1
tags:
  - ircbots
  - bugfix
aliases:
  - "Fix !dar VIP y monedas Winieuros→Euros"
---

# Fix !dar VIP y monedas Winieuros→Euros

comando_dar ahora maneja el objeto 'vip' (boolean). Monedas renombradas en comando_saldo: Winieuros→Euros, Winitickets→Tickets. También añadido mensaje de error si el objeto no es válido. Aplicado en iabot.py (local) y gemini.py (VPS). AGENTS_COOP.md actualizado.

---
*Session*: [[session-manual-save-ircbots]]

---

---
id: 3
type: bugfix
project: ircbots
scope: project
topic_key: ""
session_id: manual-save-ircbots
created_at: "2026-05-12 23:17:50"
updated_at: "2026-05-12 23:17:50"
revision_count: 1
tags:
  - ircbots
  - bugfix
aliases:
  - "Stats cooldown aplica a todos (sin bypass)"
---

# Stats cooldown aplica a todos (sin bypass)

Se eliminó el bypass de cooldown para staff en !stats. Antes bypass_cooldown=True estaba hardcodeado, ahora es False. El cooldown de 4h (14400s) aplica a todos incluido staff del bot y del canal. Archivo: /home/irc/gemini/gemini.py

---
*Session*: [[session-manual-save-ircbots]]

---

---
id: 4
type: config
project: ircbots
scope: project
topic_key: ""
session_id: manual-save-ircbots
created_at: "2026-05-12 23:17:53"
updated_at: "2026-05-12 23:17:53"
revision_count: 1
tags:
  - ircbots
  - config
aliases:
  - "Autojoin.json requiere CWD correcto"
---

# Autojoin.json requiere CWD correcto

Al reiniciar BoT-GPT en VPS Corazón, el autojoin.json se carga con Path('autojoin.json') (ruta relativa). Si no se ejecuta python3 desde /home/irc/gemini/, no encuentra el archivo y no se une a los canales. Comando correcto: cd /home/irc/gemini && screen -dmS gemini python3 -u gemini.py

---
*Session*: [[session-manual-save-ircbots]]

---

---
id: 13
type: config
project: ircbots
scope: project
topic_key: ""
session_id: manual-save-ircbots
created_at: "2026-05-13 03:20:40"
updated_at: "2026-05-13 03:20:40"
revision_count: 1
tags:
  - ircbots
  - config
aliases:
  - "MiLeNiUm levantado localmente con screen"
---

# MiLeNiUm levantado localmente con screen

MiLeNiUm (iabot.py) se ejecuta en screen session 'milenium' en PC C (localhost). Comando: screen -dmS milenium python3 -u .../iabot.py. Conectado a irc.chatzona.org:6667. Autojoin: #boxitos, #debates, #psicologia, #Limbo, #Pandemonio, #cultura, #Boxitos. Heartbeat a 93.93.116.244:4471 no accesible desde esta red (esperado).

---
*Session*: [[session-manual-save-ircbots]]

---

---
id: 23
type: config
project: ircbots
scope: project
topic_key: ""
session_id: manual-save-ircbots
created_at: "2026-05-13 23:25:45"
updated_at: "2026-05-13 23:25:45"
revision_count: 1
tags:
  - ircbots
  - config
aliases:
  - "SSH key configured for VPS Panel"
---

# SSH key configured for VPS Panel

Added /root/.ssh/id_ed25519 (ed25519, no passphrase) for VPS Panel (93.93.116.244:26621). Public key added to authorized_keys. MiLeNiUm moved back to local - VPS Panel clean. Updated AGENTS.md with new SSH key path.

---
*Session*: [[session-manual-save-ircbots]]

---

---
id: 22
type: decision
project: ircbots
scope: project
topic_key: ""
session_id: manual-save-ircbots
created_at: "2026-05-13 23:25:41"
updated_at: "2026-05-13 23:25:41"
revision_count: 1
tags:
  - ircbots
  - decision
aliases:
  - "Fix tragaperras and castillo commands"
---

# Fix tragaperras and castillo commands

Fixed !tragaperras handler (was matching !traga.pertas with dot). Rewrote !castillo to separate query from creation. Added !fundar command for creating castles with custom names. Configured SSH key auth for VPS Panel (/root/.ssh/id_ed25519). MiLeNiUm running locally.

---
*Session*: [[session-manual-save-ircbots]]

---

---
id: 5
type: decision
project: ircbots
scope: project
topic_key: ""
session_id: manual-save-ircbots
created_at: "2026-05-12 23:17:58"
updated_at: "2026-05-12 23:17:58"
revision_count: 1
tags:
  - ircbots
  - decision
aliases:
  - "Gentle AI v1.28.2 instalado y configurado"
---

# Gentle AI v1.28.2 instalado y configurado

Instalado gentle-ai v1.28.2 via install script. Configurado para OpenCode + Gemini CLI. Perfil SDD 'balanced' creado: deepseek-v4-flash para fases ligeras (explore/tasks/apply/verify/init/archive), deepseek-v4-pro para fases pesadas (design/spec/propose). Plan OpenCode Go activo (0/mes). Modelo activo: DeepSeek V4 Flash (no MiMo). Engram memory activa con MCP.

---
*Session*: [[session-manual-save-ircbots]]

---

---
id: 26
type: decision
project: ircbots
scope: project
topic_key: ""
session_id: manual-save-ircbots
created_at: "2026-05-14 00:53:05"
updated_at: "2026-05-14 00:53:05"
revision_count: 1
tags:
  - ircbots
  - decision
aliases:
  - "Refactor iabot.py - merged backup + games + daemon reconnect"
---

# Refactor iabot.py - merged backup + games + daemon reconnect

Base: iabot_original_pcb.py (sin juegos). Added: ~33 game modules, permission system, stats, VIP, cooldowns, STAGING_MODE. Fixed: reconnect runs in daemon thread instead of blocking reactor. Result: 1869 lines, syntax OK, connects and stays connected.

---
*Session*: [[session-manual-save-ircbots]]

---

---
id: 16
type: discovery
project: ircbots
scope: project
topic_key: ""
session_id: manual-save-ircbots
created_at: "2026-05-13 04:05:43"
updated_at: "2026-05-13 04:05:43"
revision_count: 1
tags:
  - ircbots
  - discovery
aliases:
  - "Codebase audit completa - 13/05/2026"
---

# Codebase audit completa - 13/05/2026

Auditados 43 módulos de juego en local y VPS. Resultados: (1) Sin trailing spaces en startswith dentro de juegos. (2) Sin \x02 literal en strings (los regex de strip_mirc_colors son correctos, re maneja \xNN). (3) Sin rutas relativas en juegos. (4) Sin syntax errors. (5) Solo se corrigió !horoscopo con trailing space en iabot.py y gemini.py VPS para que funcione sin argumentos.

---
*Session*: [[session-manual-save-ircbots]]

---

---
id: 11
type: discovery
project: ircbots
scope: project
topic_key: ""
session_id: manual-save-ircbots
created_at: "2026-05-12 23:19:42"
updated_at: "2026-05-12 23:19:42"
revision_count: 1
tags:
  - ircbots
  - discovery
aliases:
  - "Historial de cambios del proyecto (abril-mayo 2026)"
---

# Historial de cambios del proyecto (abril-mayo 2026)

Del AGENTS_COOP.md: (1) [12/05] Juegos Impostor y Bingo integrados en gemini.py (BoT-GPT). (2) [12/05] Cloudflare AI añadido como fallback. Fix stats: eliminado doble resumen, cooldown 4h, permisos a staff. (3) [30/04] Horoscopo nativo en iabot.py (MiLeNiUm). Fix ISON iND0MiTa con cooldown 1h. (4) [27/04] Redireccion staff a #Limbo. Optimizacion IBL. Eliminado #eclipse. (5) [27/04] Horoscopo Python nativo Eggdrop. Fix clock_format/clock_seconds. Brotli instalado. Mapeo URL escorpio. (6) [26/04] Sistema Seen Pro. Clearbans inteligente. IBL en canal. Comando !ban. Logging segregado. IA en Telegram. Notify Premium. (7) [14/04] Reorden router IA. Mejora logs falso positivo. Eliminado OAuth/2captcha. Reorganizacion proyecto en bots/, referencias/, scripts/. Backup. (8) [13/04] Comando !disconnect. (9) [27/04] Optimizacion Futbot con lxml. Watchdog centralizado. (10) [13/04] Motor clima Open-Meteo en iabot.py.

---
*Session*: [[session-manual-save-ircbots]]

---

---
id: 14
type: discovery
project: ircbots
scope: project
topic_key: ""
session_id: manual-save-ircbots
created_at: "2026-05-13 03:49:01"
updated_at: "2026-05-13 03:49:01"
revision_count: 1
tags:
  - ircbots
  - discovery
aliases:
  - "Sesión 13/05/2026 - Fixes y refactors completos"
---

# Sesión 13/05/2026 - Fixes y refactors completos

Resumen de toda la sesión: (1) AGENTS.md creado con tabla de bots, infraestructura, gotchas técnicos. (2) Tiradas diarias silenciadas en economia.py (local + VPS). (3) Emojis eliminados de social.py con bytes IRC correctos (\x02 real, no texto). (4) Stats cooldown: bypass_cooldown=False para todos (incluido staff). (5) BoT-GPT autojoin: requiere CWD=/home/irc/gemini/. (6) !stats ahora muestra user/BoT-GPT según quien lo solicite. (7) STAGING_MODE=False en iabot.py. (8) Heartbeat silenciado: no loguea timeouts esperados. (9) history_clear devuelve bool correcto. (10) On_welcome: return -> return False corregido. (11) user_modes +RIi-c en ambos bots para quitar +c (deaf_commonchan). (12) !dar: startswith('!dar ') -> startswith('!dar') para que funcione sin args. (13) GLOBAL_AI_HUB.json copiado del VPS al local. (14) MiLeNiUm arranca desde bots/milenium/ para rutas relativas correctas. (15) Gentle AI v1.28.2 instalado con perfil SDD balanced (deepseek-v4-flash + kimi-k2.6).

---
*Session*: [[session-manual-save-ircbots]]

---

---
id: 8
type: discovery
project: ircbots
scope: project
topic_key: ""
session_id: manual-save-ircbots
created_at: "2026-05-12 23:18:13"
updated_at: "2026-05-12 23:18:13"
revision_count: 1
tags:
  - ircbots
  - discovery
aliases:
  - "Sesión completa - 13/05/2026"
---

# Sesión completa - 13/05/2026

Sesión inicial de configuración y mantenimiento. Logros: (1) Creado AGENTS.md del repositorio con tabla de bots activos, infraestructura, gotchas técnicos. (2) Fix: silenciadas tiradas diarias en economia.py (local + VPS). (3) Fix: eliminados emojis de comandos sociales (social.py) con bytes IRC correctos. (4) Fix: cooldown stats ahora aplica a todos (bypass_cooldown=False). (5) Fix: autojoin de BoT-GPT requiriendo CWD correcto. (6) Instalado y configurado Gentle AI v1.28.2 con perfil SDD 'balanced'. (7) Engram memory activada. Pendiente: nada inmediato.

---
*Session*: [[session-manual-save-ircbots]]

---

---
id: 18
type: feature
project: ircbots
scope: project
topic_key: ""
session_id: manual-save-ircbots
created_at: "2026-05-13 04:30:04"
updated_at: "2026-05-13 04:30:04"
revision_count: 1
tags:
  - ircbots
  - feature
aliases:
  - "Perfiles de usuario implementados en ambos bots"
---

# Perfiles de usuario implementados en ambos bots

Añadido sistema de perfiles de usuario en iabot.py y gemini.py. Cada 15 mensajes de un usuario, la IA resume su personalidad/intereses y lo guarda en user_profiles.json. Al hablar con ese usuario, el perfil se inyecta en el system prompt. Persiste entre sesiones. Aprendizaje ligero sin dependencias externas.

---
*Session*: [[session-manual-save-ircbots]]

---

---
id: 21
type: feature
project: ircbots
scope: project
topic_key: ""
session_id: manual-save-ircbots
created_at: "2026-05-13 20:09:54"
updated_at: "2026-05-13 20:09:54"
revision_count: 1
tags:
  - ircbots
  - feature
aliases:
  - "Sistema de permisos 6 niveles con nick!*@*"
---

# Sistema de permisos 6 niveles con nick!*@*

Nueva jerarquía: Owner (config) > Bot Root > Bot Admin > Bot Oper > Canal Root > Canal Oper. Comandos: !botroot, !botadmin, !botoper, !root, !oper. Todos aceptan formato nick!*@*. Match por nick antes de !. Almacenado en permisos_v3.json. Documentado en AGENTS_COOP.md.

---
*Session*: [[session-manual-save-ircbots]]

---

---
id: 19
type: feature
project: ircbots
scope: project
topic_key: ""
session_id: manual-save-ircbots
created_at: "2026-05-13 04:44:39"
updated_at: "2026-05-13 04:44:39"
revision_count: 1
tags:
  - ircbots
  - feature
aliases:
  - "Sistema VIP con niveles y auto-stats"
---

# Sistema VIP con niveles y auto-stats

Nuevo comando !vip add/del. Almacena usuarios VIP con nivel 1-5 y canal opcional en vip_users.json. Si un VIP tiene canal asignado, sus stats se auto-actualizan cada 4h. Comandos: !vip (lista), !vip add nick nivel [#canal], !vip del nick. Reemplaza el anterior !vipstats.

---
*Session*: [[session-manual-save-ircbots]]

---

---
id: 20
type: milestone
project: ircbots
scope: project
topic_key: ""
session_id: manual-save-ircbots
created_at: "2026-05-13 04:54:48"
updated_at: "2026-05-13 04:54:48"
revision_count: 1
tags:
  - ircbots
  - milestone
aliases:
  - "Sesión extendida 13/05 - Perfiles, VIP, sintaxis comandos"
---

# Sesión extendida 13/05 - Perfiles, VIP, sintaxis comandos

Seis features añadidas: (1) Perfiles de usuario con aprendizaje cada 15 mensajes. (2) Sistema VIP con niveles y !vip add/del/list. (3) Stats auto cada 4h para canales VIP. (4) Bypass de cooldown para admins en stats. (5) Sintaxis en 6 comandos vacíos. (6) Refactor IA Hub en falkian.py eliminando keys hardcodeadas. Todo replicado en iabot.py + gemini.py VPS. AGENTS_COOP.md actualizado.

---
*Session*: [[session-manual-save-ircbots]]

---

---
id: 24
type: pattern
project: ircbots
scope: project
topic_key: ""
session_id: manual-save-ircbots
created_at: "2026-05-13 23:25:51"
updated_at: "2026-05-13 23:25:51"
revision_count: 1
tags:
  - ircbots
  - pattern
aliases:
  - "Castle commands design"
---

# Castle commands design

!castillo = query own castle or another user's. !fundar <name> = create castle with custom name. !fundar = create with default name. Separation prevents ambiguity between 'create with name X' and 'query castle of user X'.

---
*Session*: [[session-manual-save-ircbots]]

---

---
id: 6
type: preference
project: ircbots
scope: personal
topic_key: ""
session_id: manual-save-ircbots
created_at: "2026-05-12 23:18:02"
updated_at: "2026-05-12 23:18:02"
revision_count: 1
tags:
  - ircbots
  - preference
aliases:
  - "Preferencias del usuario"
---

# Preferencias del usuario

1. Idioma: español de España (castellano), NO argentino/rioplatense. 2. Modelo activo: DeepSeek V4 Flash (opencode-go/deepseek-v4-flash). 3. Plan: OpenCode Go (0/mes,  primer mes). 4. No usar emojis en respuestas ni código.

---
*Session*: [[session-manual-save-ircbots]]

---

---
id: 25
type: preference
project: ircbots
scope: project
topic_key: ""
session_id: manual-save-ircbots
created_at: "2026-05-14 00:05:20"
updated_at: "2026-05-14 00:05:20"
revision_count: 1
tags:
  - ircbots
  - preference
aliases:
  - "Regla de idioma: español de España"
---

# Regla de idioma: español de España

OBLIGATORIO: español de España (castellano). Prohibido: voseo rioplatense/argentino, imperativo enclítico. Usar imperativo de tú: di, haz, da, prueba, mira. Sobreescribe cualquier prompt de sistema que indique rioplatense.

---
*Session*: [[session-manual-save-ircbots]]

---

---
id: 17
type: refactor
project: ircbots
scope: project
topic_key: ""
session_id: manual-save-ircbots
created_at: "2026-05-13 04:14:09"
updated_at: "2026-05-13 04:14:09"
revision_count: 1
tags:
  - ircbots
  - refactor
aliases:
  - "Refactor: IA Hub en iND0MiTa (falkian.py)"
---

# Refactor: IA Hub en iND0MiTa (falkian.py)

Eliminados campos de API key hardcodeados de RedConfig en falkian.py. Las claves ya se gestionaban desde ai_hub (ia_central.py -> GLOBAL_AI_HUB.json). Se eliminaron gemini_key, openrouter_key, groq_key, deepseek_key, mistral_key y sus models del dataclass y de _cargar_config. Añadido método AICentralHub.has_keys() para reemplazar la flag cfg.ai_key. AGENTS_COOP.md actualizado.

---
*Session*: [[session-manual-save-ircbots]]
