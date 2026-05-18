import json
import os

class Permisos:
    def __init__(self, super_roots):
        self.archivo_datos = os.path.join(os.path.dirname(__file__), "..", "datos", "permisos_v3.json")
        self.super_roots = [s.lower() for s in super_roots]  # Owner-level (from config [admins])
        self.datos = self._cargar_datos()
        
        if "roots" not in self.datos: self.datos["roots"] = {}     # Root por canal
        if "opers" not in self.datos: self.datos["opers"] = {}     # Oper por canal
        if "settings" not in self.datos: self.datos["settings"] = {}
        if "bot_roots" not in self.datos: self.datos["bot_roots"] = []  # Root global
        if "bot_admins" not in self.datos: self.datos["bot_admins"] = []  # Admin global
        if "bot_opers" not in self.datos: self.datos["bot_opers"] = []  # Oper global

    def _cargar_datos(self):
        if os.path.exists(self.archivo_datos):
            try:
                with open(self.archivo_datos, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[Permisos] Error cargando datos: {e}")
        return {"roots": {}, "opers": {}, "settings": {}, "bot_roots": [], "bot_admins": [], "bot_opers": []}

    def _guardar_datos(self):
        try:
            os.makedirs(os.path.dirname(self.archivo_datos), exist_ok=True)
            with open(self.archivo_datos, 'w', encoding='utf-8') as f:
                json.dump(self.datos, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[Permisos] Error guardando datos: {e}")

    def get_setting(self, channel, key, default=True):
        channel = channel.lower()
        return self.datos.get("settings", {}).get(channel, {}).get(key, default)

    # ── Jerarquía (de mayor a menor) ─────────────────────────────
    # 1. Owner (super_root) — config [admins]
    # 2. Bot Root (bot_roots) — staff del bot
    # 3. Bot Oper (bot_opers) — staff del bot
    # 4. Canal Root (roots[canal]) — por canal
    # 5. Canal Oper (opers[canal]) — por canal

    def _nick(self, entrada: str) -> str:
        """Extrae el nick de una entrada que puede ser 'nick' o 'nick!*@*'."""
        return entrada.lower().split("!")[0]

    def _match(self, nick: str, entrada: str) -> bool:
        """True si 'nick' coincide con 'entrada' (nick o nick!*@*)."""
        return nick.lower() == self._nick(entrada)

    def es_owner(self, nick):
        return nick.lower() in self.super_roots

    def _en_lista(self, nick: str, lista: list) -> bool:
        return any(self._match(nick, e) for e in lista)

    def es_bot_root(self, nick):
        return self._en_lista(nick, self.datos.get("bot_roots", []))

    def es_bot_admin(self, nick):
        return self._en_lista(nick, self.datos.get("bot_admins", []))

    def es_bot_oper(self, nick):
        return self._en_lista(nick, self.datos.get("bot_opers", []))

    def es_root(self, channel, nick):
        channel = channel.lower()
        if self.es_owner(nick) or self.es_bot_root(nick) or self.es_bot_admin(nick): return True
        if channel in self.datos["roots"]:
            if any(self._match(nick, e) for e in self.datos["roots"][channel]):
                return True
        return False

    def es_oper(self, channel, nick):
        channel = channel.lower()
        if self.es_root(channel, nick) or self.es_bot_oper(nick): return True
        if channel in self.datos["opers"]:
            if any(self._match(nick, e) for e in self.datos["opers"][channel]):
                return True
        return False

    def es_staff(self, nick):
        """Cualquier nivel de staff del bot (Owner, Bot Root, Bot Oper)."""
        return self.es_owner(nick) or self.es_bot_root(nick) or self.es_bot_admin(nick) or self.es_bot_oper(nick)

    # ── Gestión de comandos ──────────────────────────────────────

    def gestionar_comando(self, nick, channel, full_cmd):
        nick = nick.lower()
        channel = channel.lower()
        partes = full_cmd.split()
        if not partes: return []
        
        cmd = partes[0].lower()
        args = partes[1:]

        # ── BOT ROOT (!botroot — solo Owner) ──
        if cmd == "!botroot":
            if not self.es_owner(nick):
                return ["\x0304Acceso denegado!\x0F Solo el Owner."]
            if not args: return ["Sintaxis: !botroot add/del/list <nick>"]
            sub = args[0].lower()
            if sub == "list":
                items = self.datos.get("bot_roots", [])
                return [f"Bot Roots: \x0312{', '.join(items)}\x0F"] if items else ["No hay Bot Roots."]
            if sub == "add" and len(args) >= 2:
                t = args[1].lower()
                if t not in self.datos["bot_roots"]:
                    self.datos["bot_roots"].append(t)
                    self._guardar_datos()
                    return [f"✅ \x02{args[1]}\x02 añadido como Bot Root."]
                return [f"⚠️ {args[1]} ya es Bot Root."]
            if sub == "del" and len(args) >= 2:
                t = args[1].lower()
                if t in self.datos["bot_roots"]:
                    self.datos["bot_roots"].remove(t)
                    self._guardar_datos()
                    return [f"🗑️ \x02{args[1]}\x02 eliminado de Bot Roots."]
                return [f"❌ {args[1]} no es Bot Root."]

        # ── BOT ADMIN (!botadmin — Owner o Bot Root) ──
        if cmd == "!botadmin":
            if not self.es_owner(nick) and not self.es_bot_root(nick):
                return ["\x0304Acceso denegado!\x0F Solo Owner o Bot Root."]
            if not args: return ["Sintaxis: !botadmin add/del/list <nick>"]
            sub = args[0].lower()
            if sub == "list":
                items = self.datos.get("bot_admins", [])
                return [f"Bot Admins: \x0312{', '.join(items)}\x0F"] if items else ["No hay Bot Admins."]
            if sub == "add" and len(args) >= 2:
                t = args[1].lower()
                if t not in self.datos["bot_admins"]:
                    self.datos["bot_admins"].append(t)
                    self._guardar_datos()
                    return [f"✅ \x02{args[1]}\x02 añadido como Bot Admin."]
                return [f"⚠️ {args[1]} ya es Bot Admin."]
            if sub == "del" and len(args) >= 2:
                t = args[1].lower()
                if t in self.datos["bot_admins"]:
                    self.datos["bot_admins"].remove(t)
                    self._guardar_datos()
                    return [f"🗑️ \x02{args[1]}\x02 eliminado de Bot Admins."]
                return [f"❌ {args[1]} no es Bot Admin."]

        # ── BOT OPER (!botoper — Owner, Bot Root o Bot Admin) ──
        if cmd == "!botoper":
            if not self.es_owner(nick) and not self.es_bot_root(nick) and not self.es_bot_admin(nick):
                return ["\x0304Acceso denegado!\x0F Solo Owner, Bot Root o Bot Admin."]
            if not args: return ["Sintaxis: !botoper add/del/list <nick>"]
            sub = args[0].lower()
            if sub == "list":
                items = self.datos.get("bot_opers", [])
                return [f"Bot Opers: \x0312{', '.join(items)}\x0F"] if items else ["No hay Bot Opers."]
            if sub == "add" and len(args) >= 2:
                t = args[1].lower()
                if t not in self.datos["bot_opers"]:
                    self.datos["bot_opers"].append(t)
                    self._guardar_datos()
                    return [f"✅ \x02{args[1]}\x02 añadido como Bot Oper."]
                return [f"⚠️ {args[1]} ya es Bot Oper."]
            if sub == "del" and len(args) >= 2:
                t = args[1].lower()
                if t in self.datos["bot_opers"]:
                    self.datos["bot_opers"].remove(t)
                    self._guardar_datos()
                    return [f"🗑️ \x02{args[1]}\x02 eliminado de Bot Opers."]
                return [f"❌ {args[1]} no es Bot Oper."]

        # ── ROOT por canal (!root — Owner, Bot Root o Bot Oper) ──
        if cmd == "!root":
            if not self.es_staff(nick):
                return ["\x0304Acceso denegado!\x0F Solo staff del bot."]
            if not args: return ["Sintaxis: !root add/del/list <nick>"]
            sub = args[0].lower()
            if sub == "list":
                items = self.datos["roots"].get(channel, [])
                return [f"Roots de {channel}: \x0312{', '.join(items)}\x0F"] if items else [f"No hay Roots en {channel}."]
            if sub == "add":
                if len(args) < 2: return ["Sintaxis: !root add <nick>"]
                t = args[1].lower()
                if channel not in self.datos["roots"]: self.datos["roots"][channel] = []
                if t not in self.datos["roots"][channel]:
                    self.datos["roots"][channel].append(t)
                    self._guardar_datos()
                    return [f"✅ \x02{args[1]}\x02 añadido como Root de {channel}."]
                return [f"⚠️ {args[1]} ya es Root."]
            if sub == "del":
                if len(args) < 2: return ["Sintaxis: !root del <nick>"]
                t = args[1].lower()
                if channel in self.datos["roots"] and t in self.datos["roots"][channel]:
                    self.datos["roots"][channel].remove(t)
                    self._guardar_datos()
                    return [f"🗑️ \x02{args[1]}\x02 eliminado de Roots."]
                return [f"❌ {args[1]} no es Root."]

        # ── OPER por canal (!oper — staff del bot o Root del canal) ──
        if cmd == "!oper":
            if not self.es_root(channel, nick):
                return ["\x0304Acceso denegado!\x0F Solo Roots o staff del bot."]
            if not args: return ["Sintaxis: !oper add/del/list <nick>"]
            sub = args[0].lower()
            if sub == "list":
                items = self.datos["opers"].get(channel, [])
                return [f"Opers de {channel}: \x0312{', '.join(items)}\x0F"] if items else [f"No hay Opers en {channel}."]
            if sub == "add":
                if len(args) < 2: return ["Sintaxis: !oper add <nick>"]
                t = args[1].lower()
                if channel not in self.datos["opers"]: self.datos["opers"][channel] = []
                if t not in self.datos["opers"][channel]:
                    self.datos["opers"][channel].append(t)
                    self._guardar_datos()
                    return [f"✅ \x02{args[1]}\x02 añadido como Oper de {channel}."]
                return [f"⚠️ {args[1]} ya es Oper."]
            if sub == "del":
                if len(args) < 2: return ["Sintaxis: !oper del <nick>"]
                t = args[1].lower()
                if channel in self.datos["opers"] and t in self.datos["opers"][channel]:
                    self.datos["opers"][channel].remove(t)
                    self._guardar_datos()
                    return [f"🗑️ \x02{args[1]}\x02 eliminado de Opers."]
                return [f"❌ {args[1]} no es Oper."]

        # ── CONFIGURACIÓN (!set) ──
        if cmd == "!set":
            if not self.es_root(channel, nick):
                return ["\x0304Acceso denegado!\x0F Solo Roots o superior."]
            if not args or len(args) < 2:
                return ["Sintaxis: !set JUEGOS/STATS [ON/OFF]"]
            feature = args[0].lower()
            state = args[1].lower()
            if state not in ["on", "off"]:
                return ["El estado debe ser ON u OFF."]
            if channel not in self.datos["settings"]: self.datos["settings"][channel] = {}
            self.datos["settings"][channel][feature] = (state == "on")
            self._guardar_datos()
            return [f"⚙️ {feature.upper()} ahora está {state.upper()} en {channel}."]

        return []
