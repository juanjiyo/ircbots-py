import random
import time
import os
import json

class Hechicero:
    def __init__(self, economia):
        self.eco = economia
        self.archivo_datos = os.path.join(os.path.dirname(__file__), "..", "datos", "hechiceros.json")
        self.datos = self._cargar_datos()
        
        self.CLASES = ["Kragg", "Volkmar", "Magnus", "Visir", "Drachenfels", "Mortuori", 
                       "Aruspice", "Morgrim", "Grungni", "Thorek Cejohierro", "Aenarion", 
                       "Niv Mizzet", "GurMag", "Blomane"]

    def _cargar_datos(self):
        if os.path.exists(self.archivo_datos):
            try:
                with open(self.archivo_datos, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[Hechicero] Error cargando datos: {e}")
        return {}

    def _guardar_datos(self):
        try:
            os.makedirs(os.path.dirname(self.archivo_datos), exist_ok=True)
            with open(self.archivo_datos, 'w', encoding='utf-8') as f:
                json.dump(self.datos, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[Hechicero] Error guardando datos: {e}")

    def get_hechicero(self, nick):
        return self.datos.get(nick.lower())

    def comando_infohechicero(self, user, args):
        partes = args.split()
        target = partes[0].lower() if partes else user.lower()
        h = self.get_hechicero(target)
        if not h: return [f"❌ {target} no es un Hechicero."]
        
        next_lvl = int(80 * (1 + h["lvl"]) ** 2.35)
        return [
            f"🧙 \x02Info Hechicero:\x02 [\x02{target}\x02] Clase: \x02{h['tipo']}\x02 | Etapa: \x02{h['age']}\x02",
            f"📈 Nivel: \x02{h['lvl']}\x02 | XP: \x02{h['exp']}/{next_lvl}\x02 | Gremio: \x02{h.get('gremio', 'Ninguno')}\x02"
        ]

    def comando_gmision(self, user):
        h = self.get_hechicero(user)
        if not h: return ["❌ No eres un Hechicero."]
        
        if not h.get("quest"):
            quests = ["capturar", "combate"]
            h["quest"] = random.choice(quests)
            h["quest_count"] = random.randint(3, 7)
            self._guardar_datos()
        
        return [f"🛡️ \x0306G-Mision:\x0F Tu gremio te ordena \x02{h['quest'].upper()}\x02 [\x02{h['quest_count']}\x02] enemigos. Escribe \x02!{h['quest']}\x02."]

    def _ejecutar_mision(self, user, tipo, castillo_obj=None):
        h = self.get_hechicero(user)
        if not h or h.get("quest") != tipo:
            return [f"❌ No tienes ninguna G-Mision de {tipo}. Escribe \x02!Gmision\x02."]
        
        ahora = time.time()
        timer_key = f"{tipo}_timer"
        if ahora < h.get("timers", {}).get(timer_key, 0):
            return [f"⏳ Tu Hechicero esta agotado. Espera."]

        # Lógica de éxito
        h["quest_count"] -= 1
        exp = random.randint(700, 1300)
        
        msg_extra = ""
        if castillo_obj:
            c = castillo_obj.get_castillo(user)
            if c and c.get("libro", 0) > 0:
                bonus = int(exp * 0.30)
                exp += bonus
                msg_extra = f" (📖 Bonus de Libro \x02+{bonus} XP\x02!)"
                if random.randint(1, 15) == 1:
                    c["libro"] -= 1
                    msg_extra += " \x0304[Libro agotado]\x0F"
                    castillo_obj._guardar_datos()

        h["exp"] += exp
        if "timers" not in h: h["timers"] = {}
        h["timers"][timer_key] = ahora + random.randint(30, 90)
        
        msg = [f"⚡ \x0306{tipo.capitalize()}:\x0F Tu Hechicero sale de su isla y gana \x02{exp}\x02 XP.{msg_extra}"]
        lvl = self._check_lvl_up(user)
        if lvl: msg.append(lvl)
        if h["quest_count"] <= 0:
            h["quest"] = None
            msg.append("✅ ¡G-Mision Completa!")
        
        self._guardar_datos()
        return msg

    def comando_capturar(self, user, c_obj=None): return self._ejecutar_mision(user, "capturar", c_obj)
    def comando_combate(self, user, c_obj=None): return self._ejecutar_mision(user, "combate", c_obj)

    def _get_age(self, lvl):
        if lvl < 20: return "Aprendiz"
        return "Experimentado"

    def _check_lvl_up(self, nick):
        h = self.datos[nick.lower()]
        next_lvl_exp = int(80 * (1 + h["lvl"]) ** 2.35)
        if h["exp"] >= next_lvl_exp:
            h["lvl"] += 1
            h["age"] = self._get_age(h["lvl"])
            self._guardar_datos()
            return f"🆙 ¡Nuevo Nivel! Tu Hechicero \x02{h['tipo']}\x02 es ahora \x02{h['age']}\x02 Nivel \x02{h['lvl']}\x02."
        return None

    def comando_hechicero(self, user, args):
        partes = args.split()
        target = partes[0].lower() if partes else user.lower()
        
        h = self.get_hechicero(target)
        if not h:
            if target == user.lower():
                tipo = random.choice(self.CLASES)
                self.datos[user.lower()] = {
                    "tipo": tipo, "age": "Aprendiz", "exp": 0, "lvl": 0,
                    "gremio": "Ninguno", "timers": {}
                }
                self._guardar_datos()
                return [f"🧙 \x02Hechicero:\x02 [\x02{user}\x02] ¡Felicidades! Has sido iniciado en las artes misticas como un \x0312{tipo}\x0F."]
            return [f"❌ {partes[0]} no es un Hechicero."]

        return [f"🧙 \x02Hechicero:\x02 [\x02{target}\x02] es un \x02{h['age']} {h['tipo']}\x02 con nivel \x02{h['lvl']}\x02 (Exp: {h['exp']})"]

    def comando_conjuro(self, user, castillo_obj=None):
        h = self.get_hechicero(user)
        if not h or h["lvl"] < 30:
            return ["❌ Necesitas un Hechicero de nivel \x0230\x02 para lanzar Conjuros."]
            
        ahora = time.time()
        if ahora < h["timers"].get("conjuro", 0):
            return [f"⏳ Tus energias magicas estan agotadas. Espera un momento."]

        conjuros = ["Deuda con los Inmortales", "Niebla Lunar", "Resistencia"]
        rivales = ["Darien rey de Kjeldor", "Sedris rey traidor", "Hechicero de Sigmar"]
        
        c_name = random.choice(conjuros)
        r = random.choice(rivales)
        exp = random.randint(100000, 600000)
        
        msg_extra = ""
        if castillo_obj:
            c = castillo_obj.get_castillo(user)
            if c and c.get("libro", 0) > 0:
                bonus = int(exp * 0.50)
                exp += bonus
                c["libro"] -= 1
                msg_extra = f" (📜 ¡Poder de Libro! \x02+{self.eco.formatear_dinero(bonus)} XP\x02)"
                castillo_obj._guardar_datos()

        h["exp"] += exp
        h["timers"]["conjuro"] = ahora + 600
        msg = [f"🔮 \x02Conjuro:\x02 Tu Hechicero \x02{h['tipo']}\x02 lanza \x02{c_name}\x02 contra \x02{r}\x02. ¡Ganas \x0312{self.eco.formatear_dinero(exp)}\x02 XP!{msg_extra}"]
        lvl = self._check_lvl_up(user)
        if lvl: msg.append(lvl)
        
        self._guardar_datos()
        return msg

    def comando_pelear(self, user, args, castillo_obj=None):
        h_ataca = self.get_hechicero(user)
        if not h_ataca: return ["❌ No eres un Hechicero."]
        
        target = args.split()[0] if args else ""
        h_defiende = self.get_hechicero(target)
        if not h_defiende: return [f"❌ {target} no es un Hechicero."]

        ahora = time.time()
        if ahora < h_ataca["timers"].get("pelea", 0):
            return [f"⏳ Tu Hechicero debe descansar."]

        exp_juego = random.randint(6000, 11000)
        h_ataca["timers"]["pelea"] = ahora + 300
        
        # Victoria basada en nivel
        base_chance = 50 + (h_ataca["lvl"] - h_defiende["lvl"]) * 2
        
        msg_extra = ""
        if castillo_obj:
            c = castillo_obj.get_castillo(user)
            if c and c.get("ps", 0) >= 2:
                base_chance += 10
                c["ps"] -= 2
                msg_extra = " (💉 ¡Piedras de Sangre usadas! +10% éxito)"
                castillo_obj._guardar_datos()

        chance = max(10, min(95, base_chance))
        
        if random.randint(1, 100) <= chance:
            h_ataca["exp"] += exp_juego
            h_defiende["exp"] = max(0, h_defiende["exp"] - exp_juego)
            res = [f"⚡ \x02Duelo Magico:\x02 ¡Victoria! Has derrotado a \x02{target}\x02 y le robas \x02{exp_juego}\x02 XP.{msg_extra}"]
        else:
            h_ataca["exp"] = max(0, h_ataca["exp"] - exp_juego)
            h_defiende["exp"] += exp_juego
            res = [f"⚡ \x02Duelo Magico:\x02 Has sido derrotado por \x02{target}\x02. Pierdes \x02{exp_juego}\x02 XP.{msg_extra}"]

        self._guardar_datos()
        return res
