import random
import time
import os
import json

class Dragones:
    def __init__(self, economia):
        self.eco = economia
        self.archivo_datos = os.path.join(os.path.dirname(__file__), "..", "datos", "dragones.json")
        self.dragones = self._cargar_dragones()
        
        self.CLASES = [
            "SynChro", "Kalameet", "BroodMate", "Flama Negra", "RainForest", 
            "FlameBlast", "KoloGan", "Niv-Mizzet", "Skithryx", "Furnace", 
            "Shivano", "Gentrice", "KilnMorh", "Hielo", "Oscuridad", 
            "Luz", "Agua", "Fuego", "Aire", "Cristal", "Diamante", 
            "Mordor", "Ancestral", "Vermithrax", "Sangre", "Skyrim", 
            "Daedra", "Tamriel", "Halado", "Rubí", "Shieldshide", "Ñatita"
        ]

    def _cargar_dragones(self):
        if os.path.exists(self.archivo_datos):
            try:
                with open(self.archivo_datos, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[Dragones] Error cargando datos: {e}")
        return {}

    def _guardar_dragones(self):
        try:
            os.makedirs(os.path.dirname(self.archivo_datos), exist_ok=True)
            with open(self.archivo_datos, 'w', encoding='utf-8') as f:
                json.dump(self.dragones, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[Dragones] Error guardando datos: {e}")

    def get_dragon(self, nick):
        nick = nick.lower()
        return self.dragones.get(nick)

    def comando_morder(self, user):
        d = self.get_dragon(user)
        if not d: return ["❌ No tienes un Dragon."]
        
        ahora = time.time()
        if ahora < d.get("timers", {}).get("morder", 0):
            return ["⏳ Tu dragon tiene la mandíbula cansada. Espera."]

        exp = random.randint(100, 500)
        d["exp"] += exp
        if "timers" not in d: d["timers"] = {}
        d["timers"]["morder"] = ahora + 60
        
        msg = [f"🦷 \x02Morder:\x02 Tu dragon pega un mordisco al aire y gana \x02{exp}\x02 XP."]
        lvl = self._check_lvl_up(user)
        if lvl: msg.append(lvl)
        
        self._guardar_dragones()
        return msg

    def comando_infodragon(self, user, args):
        partes = args.split()
        target = partes[0].lower() if partes else user.lower()
        d = self.get_dragon(target)
        if not d: return [f"❌ {target} no tiene un Dragon."]
        
        next_lvl = int(80 * (1 + d["lvl"]) ** 2.35)
        return [
            f"🐉 \x0306Info Dragon:\x0F [\x02{target}\x02] Clase: \x02{d['clase']}\x02 | Etapa: \x02{d['age']}\x02",
            f"📈 Nivel: \x02{d['lvl']}\x02 | XP: \x02{d['exp']}/{next_lvl}\x02 | Mision: \x02{d.get('quest') or 'Ninguna'}\x02"
        ]

    def _get_age(self, lvl):
        if lvl < 20: return "Cría"
        if lvl < 30: return "Adolescente"
        if lvl < 40: return "Adulto"
        if lvl < 90: return "Esmeralda"
        if lvl < 190: return "Ocre"
        if lvl < 280: return "Plateado"
        if lvl < 375: return "Dorado"
        if lvl < 600: return "Diamante"
        if lvl < 1000: return "Alfa"
        return "Legendario"

    def _check_lvl_up(self, nick):
        d = self.dragones[nick.lower()]
        next_lvl_exp = int(80 * (1 + d["lvl"]) ** 2.35)
        if d["exp"] >= next_lvl_exp:
            d["lvl"] += 1
            d["age"] = self._get_age(d["lvl"])
            self._guardar_dragones()
            return f"🆙 ¡Nuevo Nivel! El Dragón de \x0312{nick}\x0F (\x02{d['clase']}\x02) es ahora \x02{d['age']}\x02 Nivel \x02{d['lvl']}\x02."
        return None

    def comando_dragon(self, user, args):
        u_eco = self.eco.get_user(user)
        partes = args.split()
        target = partes[0].lower() if partes else user.lower()
        
        d = self.get_dragon(target)
        if not d:
            if target == user.lower():
                nueva_clase = random.choice(self.CLASES)
                self.dragones[user.lower()] = {
                    "clase": nueva_clase, "age": "Cría", "exp": 0, "lvl": 0,
                    "quest": None, "quest_count": 0, "timers": {}
                }
                self._guardar_dragones()
                return [f"🐉 \x0306Dragon:\x0F [\x02{user}\x02] ¡Felicidades! Encuentras un Huevo Mágico. Clase: \x0312{nueva_clase}\x0F"]
            else:
                return [f"❌ El usuario \x02{partes[0]}\x02 no tiene un Dragón."]

        return [f"🐉 \x0306Dragon:\x0F [\x02{target}\x02] tiene un Dragón \x02{d['age']}\x02 de clase \x0312{d['clase']}\x0F con nivel \x02{d['lvl']}\x02 (Exp: {d['exp']})"]

    def comando_mision(self, user):
        d = self.get_dragon(user)
        if not d: return ["❌ Necesitas un Dragón."]
        
        if not d.get("quest"):
            quests = ["quemar", "cazar", "matar"]
            d["quest"] = random.choice(quests)
            d["quest_count"] = random.randint(3, 7)
            self._guardar_dragones()
        
        return [f"⚔️ \x0306Misión:\x0F [\x02{d['clase']}\x02] Tu Dragón debe \x02{d['quest'].upper()}\x02 [\x02{d['quest_count']}\x02] objetivos. Escribe \x02!{d['quest']}\x02."]

    def _ejecutar_mision(self, user, tipo, castillo_obj=None):
        d = self.get_dragon(user)
        if not d or d.get("quest") != tipo:
            return [f"❌ No tienes ninguna misión de {tipo}."]
        
        ahora = time.time()
        timer_key = f"{tipo}_timer"
        if ahora < d.get("timers", {}).get(timer_key, 0):
            espera = int(d["timers"][timer_key] - ahora)
            return [f"⏳ Tu Dragón está cansado. Espera {espera} segundos."]

        gain_exp = random.randint(400, 1000)
        msg_extra = ""
        if castillo_obj:
            c = castillo_obj.get_castillo(user)
            if c and c.get("alas", 0) > 0:
                bonus = int(gain_exp * 0.20)
                gain_exp += bonus
                msg_extra = f" (✨ ¡Bonus de Alas \x02+{bonus} XP\x02!)"
                if random.randint(1, 10) == 1:
                    c["alas"] -= 1
                    msg_extra += " \x0304[Alas rotas]\x0F"
                    castillo_obj._guardar_datos()

        d["quest_count"] -= 1
        d["exp"] += gain_exp
        if "timers" not in d: d["timers"] = {}
        d["timers"][timer_key] = ahora + random.randint(30, 90)
        
        msg = [f"🔥 \x0306{tipo.capitalize()}:\x0F Tu Dragón de clase \x02{d['clase']}\x02 ha completado la acción. ¡Ganas \x02{gain_exp}\x02 XP!{msg_extra}"]
        lvl_msg = self._check_lvl_up(user)
        if lvl_msg: msg.append(lvl_msg)
        if d["quest_count"] <= 0:
            d["quest"] = None
            msg.append(f"✅ ¡Misión Completa!")
            
        self._guardar_dragones()
        return msg

    def comando_volar(self, user, c_obj=None): return self._ejecutar_mision(user, "volar", c_obj)
    def comando_destruir(self, user, c_obj=None): return self._ejecutar_mision(user, "destruir", c_obj)
    def comando_cazar(self, user, c_obj=None): return self._ejecutar_mision(user, "cazar", c_obj)
    def comando_matar(self, user, c_obj=None): return self._ejecutar_mision(user, "matar", c_obj)

    def comando_atacar(self, user, args):
        u_dragon = self.get_dragon(user)
        if not u_dragon: return ["❌ Necesitas un Dragon."]
        partes = args.split()
        if not partes: return ["Uso: !atacar <Nick>"]
        target = partes[0]
        t_dragon = self.get_dragon(target)
        if not t_dragon: return [f"❌ {target} no tiene un Dragon."]

        ahora = time.time()
        if ahora < u_dragon.get("timers", {}).get("fight_timer", 0):
            espera = int(u_dragon["timers"]["fight_timer"] - ahora)
            return [f"⏳ Tu Dragon debe descansar {espera}s."]

        diff = u_dragon["lvl"] - t_dragon["lvl"]
        chance = 50 + (diff * 2)
        chance = max(10, min(90, chance))
        exp_juego = random.randint(5000, 10000)
        
        if "timers" not in u_dragon: u_dragon["timers"] = {}
        u_dragon["timers"]["fight_timer"] = ahora + 300

        if random.randint(1, 100) <= chance:
            u_dragon["exp"] += exp_juego
            t_dragon["exp"] = max(0, t_dragon["exp"] - exp_juego)
            res = [f"⚔️ \x02Ataque:\x02 ¡VICTORIA! Ganas \x0312{exp_juego}\x0F XP de \x02{target}\x02."]
        else:
            u_dragon["exp"] = max(0, u_dragon["exp"] - exp_juego)
            t_dragon["exp"] += exp_juego
            res = [f"⚔️ \x02Ataque:\x02 ¡Derrotado! Pierdes \x0304{exp_juego}\x0F XP."]

        self._guardar_dragones()
        return res

    def comando_bolafuego(self, user, args, castillo_obj=None):
        u_eco = self.eco.get_user(user)
        if u_eco["mano"]["llaves"] < 1: return ["❌ Necesitas una \x02Llave Magica\x02."]
        partes = args.split()
        if not partes: return ["Uso: !bola.fuego <Nick>"]
        target = partes[0]
        t_dragon = self.get_dragon(target)
        if not t_dragon: return [f"❌ {target} no tiene un Dragon."]

        c = castillo_obj.get_castillo(user) if castillo_obj else None
        if not c or c.get("ps", 0) < 5:
            return ["❌ Necesitas \x025 Piedras de Sangre\x02 en tu almacen del Castillo."]

        u_eco["mano"]["llaves"] -= 1
        c["ps"] -= 5
        t_dragon["lvl"] = max(0, t_dragon["lvl"] - 1)
        t_dragon["exp"] = 0
        t_dragon["age"] = self._get_age(t_dragon["lvl"])
        
        self._guardar_dragones()
        self.eco._guardar_datos()
        castillo_obj._guardar_datos()
        return [f"💥 \x0304\x02BOLA DE FUEGO:\x02\x0F \x02{user}\x02 consume 5 Piedras de Sangre y una Llave Magica. ¡Dragon de \x02{target}\x02 degradado!"]
