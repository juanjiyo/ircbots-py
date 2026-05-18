import json
import os
import time
import random

class Economia:
    def __init__(self):
        self.archivo_datos = os.path.join(os.path.dirname(__file__), "..", "datos", "economia.json")
        self.archivo_bote = os.path.join(os.path.dirname(__file__), "..", "datos", "bote.json")
        self.datos = self._cargar_datos()
        self.bote = self._cargar_bote()
        self.premio_cooldowns = {}
        self.duelos_pendientes = {} # {id_duelo: {retador, retado, apuesta, tiempo}}
        
        # Precios del mercado (Actualizados al 50% segun Logs)
        self.PRECIOS = {
            "tickets": {"compra": 5000000, "venta": 2500000},
            "lingotes": {"compra": 25000000, "venta": 12500000},
            "diamantes": {"compra": 100000000, "venta": 50000000},
            "esmeraldas": {"compra": 2000, "venta": 1000}, # En Diamantes!
            "llaves": {"compra": 10000000, "venta": 5000000},
            "fichas": {"compra": 1, "venta": 1}
        }

    def _cargar_datos(self):
        if os.path.exists(self.archivo_datos):
            try:
                with open(self.archivo_datos, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[Economia] Error cargando datos: {e}")
        return {}

    def _guardar_datos(self):
        try:
            with open(self.archivo_datos, 'w', encoding='utf-8') as f:
                json.dump(self.datos, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[Economia] Error guardando datos: {e}")

    def _cargar_bote(self):
        if os.path.exists(self.archivo_bote):
            try:
                with open(self.archivo_bote, 'r', encoding='utf-8') as f:
                    b = json.load(f)
                    if "llaves" not in b: b["llaves"] = 5
                    if "tiradas" not in b: b["tiradas"] = 2500
                    if "fichas" not in b: b["fichas"] = 10000
                    if "esmeraldas" not in b: b["esmeraldas"] = 2
                    if "maldiciones" not in b: b["maldiciones"] = 0
                    if "ultimo_tiempo" not in b: b["ultimo_tiempo"] = time.time()
                    return b
            except Exception as e:
                print(f"[Economia] Error cargando bote: {e}")
        return {
            "euros": 100000000, "tickets": 20, "lingotes": 10, "diamantes": 5, 
            "esmeraldas": 2, "llaves": 3, "tiradas": 1000, "fichas": 5000,
            "maldiciones": 0, "ultimo_ganador": "Nadie", "ultimo_tiempo": time.time()
        }

    def _guardar_bote(self):
        try:
            with open(self.archivo_bote, 'w', encoding='utf-8') as f:
                json.dump(self.bote, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[Economia] Error guardando bote: {e}")

    def get_user(self, nick):
        nick = nick.lower()
        if nick not in self.datos:
            self.datos[nick] = {
                "mano": {"euros": 500000, "tickets": 50, "lingotes": 10, "diamantes": 10, "esmeraldas": 0, "llaves": 0, "fichas": 0, "tiradas": 500},
                "banco": {"euros": 0, "tickets": 0, "lingotes": 0, "diamantes": 0, "esmeraldas": 0, "fichas": 0},
                "vip": False,
                "deuda": 0,
                "respeto": 0,
                "maldiciones": 0,
                "botes_ganados": 0,
                "intentos_sin_tiradas": 0,
                "ultima_recompensa": 0
            }
            self._guardar_datos()
        else:
            u = self.datos[nick]
            if "deuda" not in u: u["deuda"] = 0
            if "respeto" not in u: u["respeto"] = 0
            if "vip" not in u: u["vip"] = False
            if "maldiciones" not in u: u["maldiciones"] = 0
            if "botes_ganados" not in u: u["botes_ganados"] = 0
            if "intentos_sin_tiradas" not in u: u["intentos_sin_tiradas"] = 0
            for k in ["euros", "tickets", "lingotes", "diamantes", "esmeraldas", "llaves", "fichas", "tiradas"]:
                if k not in u["mano"]: u["mano"][k] = 0
            for k in ["euros", "tickets", "lingotes", "diamantes", "esmeraldas", "fichas"]:
                if k not in u["banco"]: u["banco"][k] = 0
        return self.datos[nick]

    def check_daily_spins(self, nick):
        """Verifica y entrega 1000 tiradas diarias silenciosamente."""
        u = self.get_user(nick)
        ahora = time.time()
        if ahora - u.get("ultima_tirada_diaria", 0) >= 86400:
            u["mano"]["tiradas"] += 1000
            u["ultima_tirada_diaria"] = ahora
            self._guardar_datos()
        return []

    def trigger_maldicion(self, user):
        u = self.get_user(user)
        u["maldicion_hasta"] = time.time() + 28800 # 8 horas
        u["maldiciones"] += 1
        u["intentos_sin_tiradas"] = 0
        self._guardar_datos()
        return [f"\x0304[Maldicion]\x0F \x02LA MALDICIÓN DEL BOTIJO!!!\x0F \x02{user}\x02 no podrá jugar durante las próximas 8 Horas por intentar jugar sin tiradas repetidamente."]

    def cobrar_embargo(self, nick, cantidad):
        u = self.get_user(nick)
        if u["deuda"] <= 0:
            u["mano"]["euros"] += cantidad
            self._guardar_datos()
            return cantidad, 0, ""
        
        # Umbral de la Banca Omnisciente (50k)
        if u["mano"]["euros"] <= 50000:
            u["mano"]["euros"] += cantidad
            self._guardar_datos()
            return cantidad, 0, " (\x0303[Escudo]\x0F Umbral de supervivencia)"
        
        # Tasa Dinámica por Respeto
        res = u.get("respeto", 0)
        tasa_base = 0.35 if u["vip"] else 0.70
        
        # Cada punto de respeto reduce un 0.5% (0.005)
        # +100 Respeto = -50% tasa. -100 Respeto = +50% tasa.
        tasa = tasa_base - (res / 200.0)
        tasa = max(0.10, min(1.20, tasa)) # Límites seguros
        
        cobrado = min(u["deuda"], int(cantidad * tasa))
        u["deuda"] -= cobrado
        self.sumar_al_bote("euros", cobrado)
        recibe = cantidad - cobrado
        u["mano"]["euros"] += recibe
        self._guardar_datos()
        
        info_r = f" (Respeto: {res})"
        return recibe, cobrado, f" (\x0304[Embargo]\x0F Embargados \x0304{self.formatear_dinero(cobrado)}€\x0F por deuda de la Calle{info_r})"

    def formatear_dinero(self, cantidad):
        return f"{cantidad:,}".replace(",", ".")

    def comando_prestamo(self, nick):
        u = self.get_user(nick)
        u["mano"]["euros"] += 1000000
        u["deuda"] += 1200000
        self._guardar_datos()
        return [f"\x0312[Banco]\x0F \x0312Banco:\x0F {nick}, se te han concedido \x021.000.000€\x02. Deberás devolver \x021.200.000€\x02 (20% interés)."]

    def comando_devuelve(self, nick):
        u = self.get_user(nick)
        if u["deuda"] <= 0: return ["\x0304[Error]\x0F No tienes deudas."]
        pago = min(u["mano"]["euros"], u["deuda"])
        if pago <= 0: return ["\x0304[Error]\x0F No tienes dinero en mano."]
        u["mano"]["euros"] -= pago
        u["deuda"] -= pago
        self._guardar_datos()
        return [f"\x0312[Banco]\x0F \x0312Banco:\x0F Pagados \x0303{self.formatear_dinero(pago)}€\x0F. Deuda: {self.formatear_dinero(u['deuda'])}€."]

    def comando_limpiar(self, nick):
        u = self.get_user(nick)
        if u["deuda"] <= 0 and u["respeto"] >= 0:
            return ["\x0304[Error]\x0F No tienes deudas ni mala reputación que limpiar."]
        
        if u["mano"]["esmeraldas"] < 1:
            return ["\x0304[Error]\x0F Necesitas \x03031 Esmeralda\x0F para sobornar a la Banca."]
            
        u["mano"]["esmeraldas"] -= 1
        u["respeto"] = min(100, u.get("respeto", 0) + 30)
        # Reducción simbólica de deuda por el soborno
        reduccion = int(u["deuda"] * 0.10)
        u["deuda"] -= reduccion
        
        self._guardar_datos()
        return [
            f"\x0303[Hecho]\x0F \x02{nick}\x02, has entregado una \x0303Esmeralda\x0F.",
            f"\x0303[Subida]\x0F Tu respeto sube a \x02{u['respeto']}\x02 y tu deuda baja un 10%. ¡Los cobradores sonríen!"
        ]

    def comando_maldicion(self, executor, args):
        u_exec = self.get_user(executor)
        partes = args.split()
        if len(partes) < 2:
            return ["Uso: !maldicion <Nick> <info/borrar> (Borrar cuesta 10 Diamantes)"]

        target = partes[0]
        accion = partes[1].lower()
        u_target = self.get_user(target)

        ahora = time.time()

        if accion == "info":
            if u_target.get("maldicion_hasta", 0) <= ahora:
                return [f"El jugador \x02{target}\x02 no tiene actualmente ninguna maldición."]
            else:
                restante = int((u_target["maldicion_hasta"] - ahora) // 60)
                return [f"El jugador \x02{target}\x02 tiene actualmente una maldición. Tiempo restante: \x02{restante}\x02 min."]

        if accion == "borrar":
            if u_target.get("maldicion_hasta", 0) <= ahora:
                return [f"El jugador \x02{target}\x02 no tiene actualmente ninguna maldición."]

            if u_exec["mano"]["diamantes"] < 10:
                return [f"\x0304[Error]\x0F {executor}, no dispones de suficientes Diamantes para anular la maldición de {target}. (Coste: 10)"]

            u_exec["mano"]["diamantes"] -= 10
            u_target["maldicion_hasta"] = 0
            self.sumar_al_bote("diamantes", 10)
            self._guardar_datos()
            return [f"\x0303[Hecho]\x0F La maldición de \x02{target}\x02 ha sido eliminada con éxito por \x02{executor}\x02."]

        return ["Acción no reconocida. Usa info o borrar."]

    def comando_saldo(self, nick):
        u = self.get_user(nick)
        m = u["mano"]
        vip = "SI" if u["vip"] else "NO"
        color_vip = "03" if u["vip"] else "04"
        linea = (f"[\x03{color_vip}V.I.P. {vip}\x0F] \x0312{nick}\x0F tiene \x0312{self.formatear_dinero(m['euros'])}\x0F Euros, "
                  f"\x0312{m['tickets']}\x0F Tickets, \x0312{self.formatear_dinero(m['lingotes'])}\x0F Lingotes de oro, "
                  f"\x0312{self.formatear_dinero(m['diamantes'])}\x0F Diamantes y \x0312{m['esmeraldas']}\x0F Esmeraldas. "
                  f"Fichas de casino: \x0312{self.formatear_dinero(m['fichas'])}\x0F "
                  f"Tiradas disponibles: \x0312{self.formatear_dinero(m['tiradas'])}\x0F "
                  f"Llaves del tesoro: \x0312{m['llaves']}\x0F")
        msg = [linea]
        if u["deuda"] > 0: msg.append(f"\x0308[Deuda]\x0F \x0304DEUDA:\x0F Debes \x02{self.formatear_dinero(u['deuda'])}€\x02 a la Calle.")
        if u.get("maldicion_hasta", 0) > time.time():
            res = int((u["maldicion_hasta"] - time.time()) // 60)
            msg.append(f"\x0307[Maldicion]\x0F MALDICIÓN:\x0F Te quedan {res} min. Usa \x02!maldicion borrar\x02.")
        return msg
    def comando_duelo(self, user, args):
        partes = args.split()
        if len(partes) < 2: return ["Uso: !duelo <Nick> <Cantidad>"]
        target, cant_str = partes[0], partes[1]
        try: apuesta = int(cant_str)
        except Exception: return ["La apuesta debe ser un número."]
        if apuesta < 1000: return ["Mínimo 1.000€ para un duelo."]
        u = self.get_user(user)
        if u["mano"]["euros"] < apuesta: return ["\x0304[Error]\x0F No tienes suficiente dinero en mano."]
        
        duelo_id = "".join(random.choices("ABCDEF123456", k=4))
        self.duelos_pendientes[duelo_id] = {"de": user, "para": target, "apuesta": apuesta, "tiempo": time.time()}
        return [f"\x0304[Duelo]\x0F \x02Duelo:\x02 \x02{user}\x02 reta a \x02{target}\x02 por \x0312{self.formatear_dinero(apuesta)}€\x02!",
                f"Para aceptar, \x02{target}\x02 escribe: \x0303!aceptar {duelo_id}\x0F"]

    def comando_aceptar_duelo(self, user, args):
        duelo_id = args.strip().upper()
        if duelo_id not in self.duelos_pendientes: return ["Código de duelo no válido o expirado."]
        d = self.duelos_pendientes[duelo_id]
        if d["para"].lower() != user.lower(): return ["Este duelo no es para ti."]
        
        u_retado = self.get_user(user)
        u_retador = self.get_user(d["de"])
        if u_retado["mano"]["euros"] < d["apuesta"]: return ["\x0304[Error]\x0F Ya no tienes suficiente dinero para aceptar."]
        if u_retador["mano"]["euros"] < d["apuesta"]: return [f"\x0304[Error]\x0F {d['de']} ya no tiene el dinero para el duelo."]
        
        del self.duelos_pendientes[duelo_id]
        ganador, perdedor = (user, d["de"]) if random.randint(0, 1) == 0 else (d["de"], user)
        u_gana, u_pierde = self.get_user(ganador), self.get_user(perdedor)
        u_pierde["mano"]["euros"] -= d["apuesta"]
        self.cobrar_embargo(ganador, d["apuesta"])
        self._guardar_datos()
        return [f"\x0304[Duelo]\x0F \x02Duelo a muerte:\x02 \x02{ganador}\x02 ha derrotado a \x02{perdedor}\x02!",
                f"\x0307[Oro]\x0F Se lleva el botín de \x0312{self.formatear_dinero(d['apuesta'])}€\x02. ¡Sangre y gloria!"]

    def get_top_items(self, category, n=5):
        cat_map = {"winis": "euros", "fichas": "fichas", "euros": "euros", "tickets": "tickets", "lingotes": "lingotes", "diamantes": "diamantes", "esmeraldas": "esmeraldas", "llaves": "llaves", "maldiciones": "maldiciones", "botes": "botes_ganados"}
        key = cat_map.get(category.lower())
        if not key: return None
        ranking = []
        for nick, data in self.datos.items():
            if key in ["maldiciones", "botes_ganados"]: val = data.get(key, 0)
            else: val = data["mano"].get(key, 0) + data["banco"].get(key, 0)
            if val > 0: ranking.append((nick, val))
        ranking = sorted(ranking, key=lambda x: x[1], reverse=True)[:n]
        if not ranking: return [f"No hay registros para {category}."]
        p = [f"{i+1}º \x02{name}\x02 ({self.formatear_dinero(v)})" for i, (name, v) in enumerate(ranking)]
        return [f"Top{n} {category.capitalize()}: {' '.join(p)}"]

    def get_rpg_top(self, category, data_dict, label, n=5):
        ranking = []
        for nick, data in data_dict.items():
            val = data.get(category, 0)
            if val > 0: ranking.append((nick, val))
        ranking = sorted(ranking, key=lambda x: x[1], reverse=True)[:n]
        if not ranking: return [f"Aun no hay registros para el Ranking de {label}."]
        p = [f"{i+1}º \x02{name}\x02 ({val:,})" for i, (name, val) in enumerate(ranking)]
        return [f"Top{n} {label}: {' '.join(p)}"]

    def sumar_al_bote(self, objeto, cantidad):
        self.bote[objeto.lower()] = self.bote.get(objeto.lower(), 0) + cantidad
        self._guardar_bote()

    def comando_bote(self):
        b = self.bote
        dif = int(time.time() - b.get("ultimo_tiempo", time.time()))
        return [f"El bote actual es de\x0303 {self.formatear_dinero(b['euros'])} \x03Euros, \x0303{b['tickets']}\x03 Tickets, \x0303{b['lingotes']}\x03 Lingotes, \x0303{b['diamantes']}\x03 Diamantes, \x0303{b.get('esmeraldas', 0)}\x03 Esmeraldas, \x0303{b.get('llaves', 0)}\x03 Llaves, \x0303{self.formatear_dinero(b.get('fichas', 0))}\x03 Fichas, \x0303{self.formatear_dinero(b.get('tiradas', 0))}\x03 Tiradas. El ultimo salio hace \x0312{dif//60}mins {dif%60}segs\x03."]

    def comando_precio(self, args):
        partes = args.split()
        if not partes or partes[0].lower() not in self.PRECIOS:
            return ["Sintaxis incorrecta:\x02\x0312 \x0312\x1F!precio\x1F\x03 \x0312\x1FTICKETS/LINGOTES/DIAMANTES/ESMERALDAS\x0F"]
        objeto = partes[0].lower()
        p = self.PRECIOS[objeto]
        moneda = "Winiuros" if objeto != "esmeraldas" else "Diamantes"
        precio = self.formatear_dinero(p['compra'])
        return [f"El precio actual de los {objeto} es de \x0312{precio} {moneda}\x0F."]

    def comando_banco(self, nick, args):
        u = self.get_user(nick)
        partes = args.split()
        if not partes or partes[0] == "info":
            b = u["banco"]
            return [f"El usuario \x0312{nick}\x0F tiene en el banco: \x0312{self.formatear_dinero(b['euros'])}\x0F Euros, \x0312{b['tickets']}\x0F Tickets, \x0312{b['lingotes']}\x0F Lingotes, \x0312{b['diamantes']}\x0F Diamantes y \x0312{b['esmeraldas']}\x0F Esmeraldas."]

        if len(partes) < 3: return ["Uso: !banco <depositar/sacar> <Objeto> <cantidad>"]
        accion, objeto, cant_str = partes[0].lower(), partes[1].lower(), partes[2]
        try: cantidad = int(cant_str)
        except Exception: return ["La cantidad debe ser un numero."]
        if cantidad <= 0: return ["Cantidad invalida."]
        mapa_obj = {"euros": "euros", "tickets": "tickets", "lingotes": "lingotes", "diamantes": "diamantes", "esmeraldas": "esmeraldas", "fichas": "fichas"}
        obj_key = mapa_obj.get(objeto)
        if objeto == "llaves": return ["\x0304[Error]\x0F Las Llaves no se pueden guardar en el banco."]
        if not obj_key: return ["Objeto no valido."]
        if accion == "depositar":
            if u["mano"][obj_key] < cantidad: return [f"\x0304[Error]\x0F No tienes suficientes {objeto}."]
            comision = int(cantidad * 0.10)
            u["mano"][obj_key] -= cantidad
            u["banco"][obj_key] += (cantidad - comision)
            if comision > 0: self.sumar_al_bote(obj_key, comision)
            self._guardar_datos()
            return [f"\x0303[OK]\x0F Depositados {self.formatear_dinero(cantidad)} {objeto}. (10% de comision al Bote aplicada)"]
        elif accion == "sacar":
            if u["banco"][obj_key] < cantidad: return [f"\x0304[Error]\x0F No tienes suficiente en el banco."]
            u["banco"][obj_key] -= cantidad
            u["mano"][obj_key] += cantidad
            self._guardar_datos()
            return [f"\x0312[Cajero]\x0F Sacados {self.formatear_dinero(cantidad)} {objeto}."]
        return ["Accion no reconocida."]

    def comando_comprar(self, nick, args):
        u = self.get_user(nick)
        partes = args.split()
        if len(partes) < 2: return ["Uso: !comprar <Objeto> <Cantidad>"]
        obj, cant = partes[0].lower(), int(partes[1])
        if obj not in self.PRECIOS: return ["Objeto no disponible."]
        coste = self.PRECIOS[obj]["compra"] * cant
        if obj == "esmeraldas":
            if u["mano"]["diamantes"] < coste: return [f"\x0304[Error]\x0F No tienes suficientes Diamantes. Necesitas {self.formatear_dinero(coste)} Diamantes."]
            u["mano"]["diamantes"] -= coste
        else:
            if u["mano"]["euros"] < coste: return [f"\x0304[Error]\x0F No tienes suficientes Euros. Necesitas {self.formatear_dinero(coste)} Euros."]
            u["mano"]["euros"] -= coste
        u["mano"][obj] += cant
        self._guardar_datos()
        return [f"\x0307[Compra]\x0F Comprados {cant} {obj} por {self.formatear_dinero(coste)} {'Diamantes' if obj == 'esmeraldas' else 'Euros'}."]

    def comando_vender(self, nick, args):
        u = self.get_user(nick)
        partes = args.split()
        if len(partes) < 2: return ["Uso: !vender <Objeto> <Cantidad>"]
        obj, cant = partes[0].lower(), int(partes[1])
        if obj not in self.PRECIOS: return ["Objeto no vendible."]
        if u["mano"][obj] < cant: return ["\x0304[Error]\x0F No tienes suficientes."]
        ganancia = self.PRECIOS[obj]["venta"] * cant
        u["mano"][obj] -= cant
        if obj == "esmeraldas":
            u["mano"]["diamantes"] += ganancia
            msg = f"Enhorabuena \x0312{nick}\x0F!!! Has vendido \x02{cant}\x02 {obj} por un valor de \x02{self.formatear_dinero(ganancia)}\x02 Diamantes."
        else:
            u["mano"]["euros"] += ganancia
            msg = f"Enhorabuena \x0312{nick}\x0F!!! Has vendido \x02{cant}\x02 {obj} por un valor de \x02{self.formatear_dinero(ganancia)}\x02 Winiuros."
        self._guardar_datos()
        return [msg]

    def comando_premio(self, nick):
        u = self.get_user(nick)
        ahora = time.time()
        if nick in self.premio_cooldowns:
            if ahora - self.premio_cooldowns[nick] < 10: return [f"\x0308[Espera]\x0F {nick}, espera {int(10-(ahora-self.premio_cooldowns[nick]))}s."]
        self.premio_cooldowns[nick] = ahora
        if random.choice(["euros", "tiradas"]) == "euros":
            regalo = random.randint(50000, 150000)
            if u["deuda"] > 50000:
                recibe, emb, e_msg = self.cobrar_embargo(nick, regalo)
                msg = f"Enhorabuena \x0312{nick}\x0F! Tu premio contenia \x0312{self.formatear_dinero(recibe)}\x0F Euros.{e_msg}"
            else:
                u["mano"]["euros"] += regalo
                msg = f"Enhorabuena \x0312{nick}\x0F! Tu premio contenia \x0312{self.formatear_dinero(regalo)}\x0F Euros."
        else:
            u["mano"]["tiradas"] += 10
            msg = f"Enhorabuena \x0312{nick}\x0F! Tu premio contenia \x031210\x0F tiradas."
        u["intentos_sin_tiradas"] = 0
        self._guardar_datos()
        return [msg]

    def comando_transferir(self, user, args):
        u = self.get_user(user)
        partes = args.split()
        if len(partes) < 3: return ["Uso: !transferir <Nick> <Objeto> <Cantidad>"]
        target, obj, cant = partes[0], partes[1].lower(), int(partes[2])
        if obj == "llaves": return ["\x0304[Error]\x0F Las llaves son intransferibles."]
        mapa = {"euros": "euros", "tickets": "tickets", "lingotes": "lingotes", "diamantes": "diamantes", "esmeraldas": "esmeraldas", "fichas": "fichas"}
        key = mapa.get(obj)
        if not key or u["banco"].get(key, 0) < cant: return ["\x0304[Error]\x0F No puedes transferir eso."]
        t = self.get_user(target)
        com = int(cant * 0.35)
        u["banco"][key] -= cant
        t["banco"][key] += (cant - com)
        if com > 0: self.sumar_al_bote(key, com)
        self._guardar_datos()
        return [f"\x0303[OK]\x0F Transferidos {self.formatear_dinero(cant)} {obj} a \x02{target}\x02. (35% comision al Bote)"]

    def comando_dar(self, executor, args, gestor_p):
        if not gestor_p or not gestor_p.es_super_root(executor): return ["\x0304[Error]\x0F Solo Staff."]
        partes = args.split()
        if len(partes) < 3: return ["!dar <Nick> <Objeto> <Cantidad>"]
        target, obj, cant = partes[0], partes[1].lower(), int(partes[2])
        u = self.get_user(target)
        if obj == "vip":
            u["vip"] = cant > 0
            self._guardar_datos()
            return [f"\x0303[Regalo]\x0F Staff {'dio' if cant > 0 else 'quitó'} VIP a {target}."]
        if obj == "euros": self.cobrar_embargo(target, cant)
        elif obj in ["tickets", "lingotes", "diamantes", "esmeraldas", "llaves", "tiradas", "fichas"]:
            u["mano"][obj] = u["mano"].get(obj, 0) + cant
            self._guardar_datos()
        else:
            return [f"\x0304[Error]\x0F Objeto '{obj}' no válido. Usa: euros, tickets, lingotes, diamantes, esmeraldas, llaves, tiradas, fichas, vip."]
        return [f"\x0303[Regalo]\x0F Staff entrego {self.formatear_dinero(cant)} {obj} a {target}."]

    def comando_baja(self, nick):
        nick_l = nick.lower()
        if nick_l in self.datos:
            del self.datos[nick_l]
            self._guardar_datos()
            return [f"\x0303[OK]\x0F \x0312{nick}\x0F, has sido dado de \x0304Baja\x0F de la base de datos de juegos. Tus ahorros y progresos han sido eliminados."]
        return [f"\x0304[Error]\x0F {nick}, no estas registrado en el bot."]
