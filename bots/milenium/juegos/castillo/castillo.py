import random
import time
import os
import json

class Castillo:
    def __init__(self, economia):
        self.eco = economia
        self.archivo_datos = os.path.join(os.path.dirname(__file__), "..", "datos", "castillos.json")
        self.castillos = self._cargar_datos()

    def _cargar_datos(self):
        if os.path.exists(self.archivo_datos):
            try:
                with open(self.archivo_datos, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[Castillo] Error cargando datos: {e}")
        return {}

    def _guardar_datos(self):
        try:
            os.makedirs(os.path.dirname(self.archivo_datos), exist_ok=True)
            with open(self.archivo_datos, 'w', encoding='utf-8') as f:
                json.dump(self.castillos, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[Castillo] Error guardando datos: {e}")

    def get_castillo(self, nick):
        return self.castillos.get(nick.lower())

    def comando_castillo(self, user, args):
        partes = args.split()
        target = partes[0].lower() if partes else user.lower()
        
        c = self.get_castillo(target)
        if c:
            return [f"\x0307[Castillo]\x0F \x02Castillo:\x02 [\x02{target}\x02] tiene el \x0312{c['nombre']}\x0F. Torres: \x02{c['torres']}\x02. Recursos: {c['oro']} Oro, {c['madera']} Madera, {c['hierro']} Hierro."]
        
        if target == user.lower():
            return [f"\x0304[Error]\x0F No tienes un Castillo. Funda uno con \x02!fundar <Nombre>\x02."]
        return [f"\x0304[Error]\x0F {partes[0]} no tiene un Castillo."]

    def comando_fundar(self, user, args):
        c = self.get_castillo(user)
        if c:
            return [f"\x0304[Error]\x0F Ya tienes un Castillo: \x0312{c['nombre']}\x0F."]
        
        nombre_castillo = args.strip() if args.strip() else f"Alcazar de {user}"
        self.castillos[user.lower()] = {
            "nombre": nombre_castillo,
            "oro": 0, "diamantes": 0, "soldados": 0, "ps": 0,
            "hierro": 0, "madera": 0, "rehenes": 0, "torres": 0,
            "espadas": 0, "escudos": 0, "armaduras": 0,
            "alas": 0, "pociones": 0, "libro": 0,
            "timers": {}
        }
        self._guardar_datos()
        return [f"\x0307[Castillo]\x0F \x02Castillo:\x02 [\x02{user}\x02] ¡Felicidades! Has fundado el \x0312{nombre_castillo}\x0F. Ahora tus Guardianes protegen tus tierras."]

    def comando_minas(self, user):
        c = self.get_castillo(user)
        if not c: return ["\x0304[Error]\x0F No tienes un Castillo. Funda uno con \x02!Castillo <Nombre>\x02."]
        
        ahora = time.time()
        if ahora < c["timers"].get("minas", 0):
            espera = int(c["timers"]["minas"] - ahora)
            return [f"\x0308[Espera]\x0F Tus mineros estan agotados. Espera {espera} segundos."]

        oro = random.randint(100, 1100)
        diam = random.randint(5, 20)
        ps = random.randint(2, 10)
        hierro = random.randint(10, 200)
        
        c["oro"] += oro
        c["diamantes"] += diam
        c["ps"] += ps
        c["hierro"] += hierro
        c["timers"]["minas"] = ahora + random.randint(60, 120)
        self._guardar_datos()
        
        return [f"\x0307[Minas]\x0F \x0306Minas:\x0F Tus mineros han extraído: \x02{oro}\x02 Oro, \x02{diam}\x02 Diamantes, \x02{ps}\x02 Piedras de Fuego y \x02{hierro}\x02 Hierro."]

    def comando_talar(self, user):
        c = self.get_castillo(user)
        if not c: return ["\x0304[Error]\x0F No tienes un Castillo."]
        ahora = time.time()
        if ahora < c["timers"].get("talar", 0):
            return [f"\x0308[Espera]\x0F Espera a que crezcan mas arboles."]
        
        madera = random.randint(20, 200)
        c["madera"] += madera
        c["timers"]["talar"] = ahora + 90
        self._guardar_datos()
        return [f"\x0303[Bosque]\x0F \x0303Talar:\x0F Tus taladores han conseguido \x02{madera}\x02 unidades de Madera."]

    def comando_construir(self, user):
        c = self.get_castillo(user)
        if not c: return ["\x0304[Error]\x0F No tienes un Castillo."]
        
        if c["madera"] < 500 or c["hierro"] < 200:
            return ["\x0304[Error]\x0F Necesitas al menos 500 de Madera y 200 de Hierro para construir una Torre."]
            
        c["madera"] -= 500
        c["hierro"] -= 200
        c["torres"] += 1
        # Recompensa en Euros por mejorar el imperio
        gana = random.randint(5000, 15000)
        self.eco.get_user(user)["mano"]["euros"] += gana
        
        self._guardar_datos()
        self.eco._guardar_datos()
        return [f"\x0307[Obra]\x0F \x02Construir:\x02 ¡Nueva Torre levantada! Ganas \x0312{self.eco.formatear_dinero(gana)}€\x0F por prosperidad."]

    def comando_contratar(self, user, args):
        c = self.get_castillo(user)
        if not c: return ["\x0304[Error]\x0F No tienes un Castillo."]
        
        partes = args.split()
        if len(partes) < 2: return ["Uso: !contratar <soldados/arqueros/jinetes/esclavos> <cantidad>"]
        
        tipo = partes[0].lower()
        try: cant = int(partes[1])
        except Exception: return ["Cantidad invalida."]
        
        u_eco = self.eco.get_user(user)
        # Precios originales: Soldado 1k, Arquero 2.5k, Jinete 5k, Esclavo 10k
        precios = {"soldados": 1000, "arqueros": 2500, "jinetes": 5000, "esclavos": 10000}
        if tipo not in precios: return ["Solo puedes contratar: soldados, arqueros, jinetes o esclavos."]
        
        coste = cant * precios[tipo]
        if u_eco["mano"]["euros"] < coste:
            return [f"\x0304[Error]\x0F Necesitas {self.eco.formatear_dinero(coste)}€ para contratar a esa gente."]
            
        u_eco["mano"]["euros"] -= coste
        # Almacenamos arqueros y jinetes también
        if tipo == "soldados": c["soldados"] += cant
        elif tipo == "arqueros": c["arqueros"] = c.get("arqueros", 0) + cant
        elif tipo == "jinetes": c["jinetes"] = c.get("jinetes", 0) + cant
        elif tipo == "esclavos": c["rehenes"] += cant
        
        self._guardar_datos()
        self.eco._guardar_datos()
        return [f"\x0312[Ejercito]\x0F \x02Contratar:\x02 Has reclutado \x02{cant}\x02 {tipo} para tu imperio."]

    def comando_invadir(self, user, args):
        c_ataca = self.get_castillo(user)
        if not c_ataca or c_ataca["soldados"] < 10:
            return ["\x0304[Error]\x0F Necesitas un Ejercito de al menos 10 soldados para invadir."]
            
        target = args.split()[0] if args else ""
        c_defiende = self.get_castillo(target)
        if not c_defiende: return [f"\x0304[Error]\x0F {target} no tiene un Castillo para invadir."]
        
        if target.lower() == user.lower(): return ["\x0304[Error]\x0F No puedes invadirte a ti mismo."]

        ahora = time.time()
        if ahora < c_ataca["timers"].get("invadir", 0):
            espera = int(c_ataca["timers"]["invadir"] - ahora)
            return [f"\x0308[Espera]\x0F Tu ejercito esta descansando. Espera {espera} segundos."]

        # Fuerza combinada (Soldados + Arqueros*2 + Jinetes*3)
        f_ataca = c_ataca["soldados"] + (c_ataca.get("arqueros", 0) * 2) + (c_ataca.get("jinetes", 0) * 3)
        f_defiende = c_defiende["soldados"] + (c_defiende.get("arqueros", 0) * 2) + (c_defiende.get("jinetes", 0) * 3)
        
        total_fuerza = f_ataca + f_defiende
        chance = (f_ataca / total_fuerza) * 100 if total_fuerza > 0 else 50
        
        victoria = random.randint(1, 100) <= chance
        c_ataca["timers"]["invadir"] = ahora + 1800 # 30 min
        
        if victoria:
            # Saqueo avanzado (Regla mIRC)
            oro_robado = int(c_defiende["oro"] * 0.20)
            ps_robadas = int(c_defiende.get("ps", 0) * 0.20)
            dia_robados = int(c_defiende["diamantes"] * 0.20)
            rehenes_capturados = random.randint(1, 5)
            desertores = int(c_defiende["soldados"] * 0.10)
            
            c_ataca["oro"] += oro_robado
            c_defiende["oro"] -= oro_robado
            c_ataca["ps"] += ps_robadas
            c_defiende["ps"] -= ps_robadas
            c_ataca["diamantes"] += dia_robados
            c_defiende["diamantes"] -= dia_robados
            c_ataca["rehenes"] += rehenes_capturados
            c_defiende["rehenes"] = max(0, c_defiende["rehenes"] - rehenes_capturados)
            c_ataca["soldados"] += desertores
            c_defiende["soldados"] -= desertores
            
            self._guardar_datos()
            return [
                f"\x0304[Combate]\x0F \x0304\x02INVASION:\x02\x0F ¡Asalto exitoso al \x02{c_defiende['nombre']}\x02!",
                f"\x0307[Oro]\x0F Botin: \x02{oro_robado}\x02 Oro, \x02{ps_robadas}\x02 PS, \x02{dia_robados}\x02 Diamantes, \x02{rehenes_capturados}\x02 Rehenes y \x02{desertores}\x02 desertores."
            ]
        else:
            # Derrota
            perdida = int(c_ataca["soldados"] * 0.15)
            c_ataca["soldados"] -= perdida
            self._guardar_datos()
            return [
                f"\x0304[Combate]\x0F \x0314Invasion Fallida:\x0F Tu ejercito vuelve diezmado. Pierdes \x02{perdida}\x02 soldados."
            ]

    def comando_crear(self, user):
        c = self.get_castillo(user)
        if not c: return ["\x0304[Error]\x0F No tienes un Castillo."]
        
        ahora = time.time()
        if ahora < c["timers"].get("crear", 0):
            return ["\x0308[Espera]\x0F Tus herreros estan descansando."]

        if c["oro"] < 100: return ["\x0304[Error]\x0F Necesitas al menos 100 de Oro."]
        
        c["oro"] -= 100
        esp, esc, arm = random.randint(1, 5), random.randint(1, 5), random.randint(1, 5)
        c["espadas"] += esp
        c["escudos"] += esc
        c["armaduras"] += arm
        c["timers"]["crear"] = ahora + 120
        
        self._guardar_datos()
        return [f"\x0304[Combate]\x0F \x02Crear:\x02 Tus herreros forjan \x02{esp}\x02 Espadas, \x02{esc}\x02 Escudos y \x02{arm}\x02 Armaduras."]

    def comando_mercader(self, user, args):
        c = self.get_castillo(user)
        if not c: return ["\x0304[Error]\x0F No tienes un Castillo."]
        
        partes = args.split()
        if not partes: return ["Uso: !mercader <oro/madera/hierro/alas/pociones/libro> <cantidad>"]
        
        recurso = partes[0].lower()
        try: cant = int(partes[1])
        except Exception: cant = 1
        
        u_eco = self.eco.get_user(user)
        
        # Precios de Venta (Usuario vende al Mercader)
        precios_v = {"oro": 100, "madera": 10, "hierro": 25}
        # Precios de Compra (Usuario compra al Mercader)
        precios_c = {"alas": 1000000, "pociones": 10000, "libro": 100000}
        
        if recurso in precios_v:
            if c.get(recurso, 0) < cant: return [f"\x0304[Error]\x0F No tienes suficiente {recurso}."]
            ganancia = cant * precios_v[recurso]
            c[recurso] -= cant
            self.eco.get_user(user)["mano"]["euros"] += ganancia
            self._guardar_datos()
            self.eco._guardar_datos()
            return [f"\x0307[Trato]\x0F \x02Mercader:\x02 Has vendido \x02{cant}\x02 de {recurso} por \x0312{self.eco.formatear_dinero(ganancia)}€\x0F."]
            
        elif recurso in precios_c:
            coste = cant * precios_c[recurso]
            if u_eco["mano"]["euros"] < coste:
                return [f"\x0304[Error]\x0F Necesitas {self.eco.formatear_dinero(coste)}€ para comprar eso."]
            
            u_eco["mano"]["euros"] -= coste
            c[recurso] = c.get(recurso, 0) + cant
            self._guardar_datos()
            self.eco._guardar_datos()
            return [f"\x0307[Trato]\x0F \x02Mercader:\x02 Has comprado \x02{cant}\x02 {recurso} por \x0312{self.eco.formatear_dinero(coste)}€\x0F. Enviados a tu Almacen."]
        
        return ["El mercader no comercia con ese objeto."]

    def comando_beber(self, user, dragones_obj=None, hechicero_obj=None):
        c = self.get_castillo(user)
        if not c: return ["\x0304[Error]\x0F No tienes un Castillo ni suministros."]
        
        if c.get("pociones", 0) < 1:
            return ["\x0304[Error]\x0F No tienes \x02Pociones (Vino)\x02 en tu almacen. Compraselas al \x02!mercader\x02."]
        
        c["pociones"] -= 1
        ahora = time.time()
        
        # 1. Reducir timers del Castillo
        for k in ["minas", "talar", "invadir", "crear"]:
            if c["timers"].get(k, 0) > ahora:
                restante = c["timers"][k] - ahora
                c["timers"][k] = ahora + (restante / 2)
        
        # 2. Reducir timers del Dragon (si se pasa el objeto)
        msg_extra = ""
        if dragones_obj:
            d = dragones_obj.get_dragon(user)
            if d and "timers" in d:
                for k in ["mision", "morder", "fight_timer"]:
                    if d["timers"].get(k, 0) > ahora:
                        restante = d["timers"][k] - ahora
                        d["timers"][k] = ahora + (restante / 2)
                dragones_obj._guardar_dragones()
                msg_extra += " ¡Tu Dragon recupera energias!"

        # 3. Reducir timers del Hechicero
        if hechicero_obj:
            h = hechicero_obj.get_hechicero(user)
            if h and "timers" in h:
                for k in ["conjuro", "pelea", "capturar_timer", "combate_timer"]:
                    if h["timers"].get(k, 0) > ahora:
                        restante = h["timers"][k] - ahora
                        h["timers"][k] = ahora + (restante / 2)
                hechicero_obj._guardar_datos()
                msg_extra += " ¡Tu Hechicero siente el poder fluyendo!"

        self._guardar_datos()
        return [f"\x0305[Vino]\x0F \x02Beber:\x02 [\x02{user}\x02] Bebes una poción de vino añejo. Todos tus tiempos de espera se han reducido a la mitad.{msg_extra}"]

    def comando_info(self, user, args):
        partes = args.split()
        sub = partes[0].lower() if partes else "castillo"
        c = self.get_castillo(user)
        if not c: return ["\x0304[Error]\x0F No tienes un Castillo."]
        
        if sub == "almacen":
            return [f"\x0307[Caja]\x0F \x02Almacen de {user}:\x02 Oro: {c['oro']} | Hierro: {c['hierro']} | Madera: {c['madera']} | Alas: {c.get('alas', 0)} | Pociones: {c.get('pociones', 0)} | Libros: {c.get('libro', 0)}"]
        elif sub == "cuartel":
            return [f"\x0312[Ejercito]\x0F \x02Cuartel de {user}:\x02 Soldados: {c['soldados']} | Rehenes: {c['rehenes']} | Torres: {c['torres']}"]
        
        return self.comando_castillo(user, "")
