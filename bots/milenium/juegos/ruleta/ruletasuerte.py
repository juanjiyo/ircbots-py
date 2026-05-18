import random
import time

class RuletaSuerte:
    def __init__(self, economia):
        self.eco = economia

    def ejecutar(self, user):
        u = self.eco.get_user(user)
        
        # Mínimos originales MuLTiGaMe
        min_euros = 10000000
        min_lingotes = 10
        min_diamantes = 10
        
        if u["mano"]["tickets"] < 1:
            return [" \x0304¡Error!\x0F No tienes ningún Ticket de la Suerte. Puedes comprarlos con \x02!comprar tickets <cant>\x02."]
            
        if u["mano"]["euros"] < min_euros or u["mano"]["lingotes"] < min_lingotes or u["mano"]["diamantes"] < min_diamantes:
            return [f"\x0304¡Error!\x0F Para jugar necesitas tener en la mano al menos: 10M Euros, 10 Lingotes y 10 Diamantes."]

        # Consumir ticket
        u["mano"]["tickets"] -= 1
        
        # Probabilidad de Bote: 1 entre 150
        if random.randint(1, 150) == 1:
            return [f"\x0312{user}\x0F rueda la Ruleta de la Suerte, y se para en ..... " + self.ganar_bote(u, user)]

        # --- LOGICA DE AMULETOS ---
        amuleto = u.get("amuleto")
        es_falso = u.get("amuleto_falso", False)
        mult = 1
        msg_amuleto = ""

        opciones = [
            ("MALDICION", "LA MALDICIÓN DEL BOTIJO!!!", lambda u, n, mult=1: self.aplicar_maldicion(u, n, multiplicador=mult)),
            ("PERDIDA", "-5% !!!", lambda u, n, mult=1: self.quitar_dinero(u, 0.05, multiplicador=mult)),
            ("PERDIDA", "-10% !!!", lambda u, n, mult=1: self.quitar_dinero(u, 0.10, multiplicador=mult)),
            ("PERDIDA", "-15% !!!", lambda u, n, mult=1: self.quitar_dinero(u, 0.15, multiplicador=mult)),
            ("PERDIDA", "-20% !!!", lambda u, n, mult=1: self.quitar_dinero(u, 0.20, multiplicador=mult)),
            ("PREMIO", "250.000", lambda u, n, mult=1: self.add_dinero(u, 250000, multiplicador=mult)),
            ("PREMIO", "500.000", lambda u, n, mult=1: self.add_dinero(u, 500000, multiplicador=mult)),
            ("PREMIO", "750.000", lambda u, n, mult=1: self.add_dinero(u, 750000, multiplicador=mult)),
            ("PREMIO", "1.000.000", lambda u, n, mult=1: self.add_dinero(u, 1000000, multiplicador=mult)),
            ("PREMIO", "2.000.000", lambda u, n, mult=1: self.add_dinero(u, 2000000, multiplicador=mult)),
            ("PREMIO", "5.000.000", lambda u, n, mult=1: self.add_dinero(u, 5000000, multiplicador=mult)),
            ("PREMIO", "10.000.000", lambda u, n, mult=1: self.add_dinero(u, 10000000, multiplicador=mult)),
            ("PREMIO", "15.000.000", lambda u, n, mult=1: self.add_dinero(u, 15000000, multiplicador=mult)),
            ("PREMIO", "25.000.000", lambda u, n, mult=1: self.add_dinero(u, 25000000, multiplicador=mult)),
            ("PREMIO", "50.000.000", lambda u, n, mult=1: self.add_dinero(u, 50000000, multiplicador=mult)),
            ("PREMIO_TIRADAS", f"{random.randint(1000, 5000):,}".replace(",", "."), lambda u, n, mult=1: self.add_tiradas(u, random.randint(1000, 5000), multiplicador=mult)),
            ("PREMIO_OBJ", "5 Tickets", lambda u, n, mult=1: self.add_obj(u, "tickets", 5, multiplicador=mult)),
            ("PREMIO_OBJ", "2 Lingotes", lambda u, n, mult=1: self.add_obj(u, "lingotes", 2, multiplicador=mult)),
            ("PREMIO_OBJ", "1 Diamante", lambda u, n, mult=1: self.add_obj(u, "diamantes", 1, multiplicador=mult))
        ]
        
        tipo, texto, func = random.choice(opciones)
        msg_base = f"\x0312{user}\x0F rueda la Ruleta de la Suerte, y se para en ..... \x02{texto}\x0F"

        # Aplicar Protección de Amuletos
        if amuleto == "reduccion" and tipo == "PERDIDA":
            u["amuleto"] = None
            if es_falso:
                msg_amuleto = f" |  \x02OOHHHH!!!\x0F El amuleto \x02reduccion\x02 de {user} empieza a brillar y... ¡ERA FALSO! Pierdes el dinero igualmente."
            else:
                msg_amuleto = f" | [Escudo] Tu amuleto \x02reduccion\x02 brilla y te salva de la perdida. El amuleto se desintegra."
                self.eco._guardar_datos()
                return [msg_base + msg_amuleto]

        if amuleto == "maldicion" and tipo == "MALDICION":
            u["amuleto"] = None
            if es_falso:
                msg_amuleto = f" |  \x02OOHHHH!!!\x0F El amuleto \x02maldicion\x02 de {user} empieza a brillar y... ¡ERA FALSO! Te comes la maldicion."
            else:
                msg_amuleto = f" | [Amuleto] Sacas tu amuleto \x02maldicion\x02 y contrarestas el efecto. El amuleto se desintegra."
                self.eco._guardar_datos()
                return [msg_base + msg_amuleto]

        if amuleto in ["x2", "x3", "x5", "x10"] and tipo == "PREMIO":
            mult = int(amuleto[1:])
            u["amuleto"] = None
            if es_falso:
                msg_amuleto = f" |  \x02OOHHHH!!!\x0F El amuleto \x02{amuleto}\x02 de {user} empieza a brillar y... ¡ERA FALSO! Ganas la cantidad normal."
                mult = 1
            else:
                msg_amuleto = f" |  ¡OOHHHH!!! El amuleto \x02{amuleto}\x02 brilla y explota multiplicando tus ganancias. Ganas el \x02{amuleto}\x02!"

        # Ejecutar acción final
        msg_resultado = func(u, user, mult)
        self.eco._guardar_datos()
        # Strip emoji/prefix from result, keep only the amount part
        partes = msg_resultado.split("Has conseguido ")
        if len(partes) > 1:
            result_clean = f"gana {partes[1]}"
        else:
            result_clean = msg_resultado
        return [f"{msg_base}{msg_amuleto} , {user} {result_clean}"]

    def add_dinero(self, u, cant, multiplicador=1):
        total = cant * multiplicador
        u["mano"]["euros"] += total
        return f" ¡Enhorabuena! Has conseguido \x0312{self.eco.formatear_dinero(total)}\x0F Euros."

    def quitar_dinero(self, u, pct, multiplicador=1):
        saldo = u["mano"]["euros"]
        # El amuleto multiplicador tambien multiplica las perdidas (Regla mIRC)
        perder = int(saldo * pct * multiplicador)
        u["mano"]["euros"] -= perder
        self.eco.sumar_al_bote("euros", int(perder * 0.30))
        return f" -{int(pct*100*multiplicador)}% !!! Has perdido \x0304{self.eco.formatear_dinero(perder)}\x0F Euros."

    def aplicar_maldicion(self, u, nick, multiplicador=1):
        u["maldicion_hasta"] = time.time() + 28800 # 8 horas
        u["maldiciones"] += 1
        return f" \x0304LA MALDICIÓN DEL BOTIJO!!!\x0F \x02{nick}\x02 no podrá jugar durante las próximas 8 Horas."

    def add_tiradas(self, u, cant, multiplicador=1):
        total = cant * multiplicador
        u["mano"]["tiradas"] += total
        return f" ¡Premio! Has ganado \x0312{self.eco.formatear_dinero(total)}\x0F tiradas extra."

    def add_obj(self, u, obj, cant, multiplicador=1):
        total = cant * multiplicador
        u["mano"][obj] += total
        return f" ¡Premio! Has ganado \x0312{total}\x0F {obj.capitalize()}."

    def ganar_bote(self, u, nick):
        b = self.eco.bote
        g_euros = b['euros']
        g_tickets = b['tickets']
        g_lingotes = b['lingotes']
        g_diamantes = b['diamantes']
        g_esmeraldas = b.get('esmeraldas', 0)
        g_llaves = b.get('llaves', 0)
        g_tiradas = b.get('tiradas', 0)
        g_fichas = b.get('fichas', 0)
        
        u["mano"]["euros"] += g_euros + g_fichas
        u["mano"]["tickets"] += g_tickets
        u["mano"]["lingotes"] += g_lingotes
        u["mano"]["diamantes"] += g_diamantes
        u["mano"]["esmeraldas"] += g_esmeraldas
        u["mano"]["llaves"] += g_llaves
        u["mano"]["tiradas"] += g_tiradas
        
        u["botes_ganados"] += 1
        
        # Reiniciar Bote
        b["ultimo_ganador"] = nick
        b["ultimo_tiempo"] = time.time()
        b["euros"] = 100000000
        b["tickets"] = 20
        b["lingotes"] = 10
        b["diamantes"] = 5
        b["esmeraldas"] = 2
        b["llaves"] = 3
        b["tiradas"] = 1000
        b["fichas"] = 5000
        
        self.eco._guardar_bote()
        return f" \x0313\x02BOTE!!!\x0F \x02{nick}\x02 se lleva \x0312{self.eco.formatear_dinero(g_euros)}€\x0F y todo el cargamento de objetos!"
