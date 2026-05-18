import random

class MayorMenor:
    def __init__(self, economia):
        self.eco = economia

    def ejecutar(self, user, args, cmd):
        u = self.eco.get_user(user)
        # Usamos la estructura de datos existente, añadimos campos si no existen
        if "mayor_menor" not in u:
            u["mayor_menor"] = {"ultimo_numero": random.randint(1, 9), "aciertos_seguidos": 0}
            self.eco._guardar_datos()

        game_state = u["mayor_menor"]

        if cmd == "!numero":
            return [f"El último número de \x0312{user}\x0F es el \x0304{game_state['ultimo_numero']}\x0F. Para jugar escribe \x02!mayor\x02 o \x02!menor\x02."]

        if u["mano"]["tiradas"] <= 0:
            return ["No tienes tiradas disponibles para jugar."]

        u["mano"]["tiradas"] -= 1
        nuevo_numero = random.randint(1, 9)
        # Evitar empates para que el juego sea fluido
        while nuevo_numero == game_state["ultimo_numero"]:
            nuevo_numero = random.randint(1, 9)

        acerto = False
        if cmd == "!mayor" and nuevo_numero > game_state["ultimo_numero"]:
            acerto = True
        elif cmd == "!menor" and nuevo_numero < game_state["ultimo_numero"]:
            acerto = True

        old_num = game_state["ultimo_numero"]
        game_state["ultimo_numero"] = nuevo_numero

        if acerto:
            game_state["aciertos_seguidos"] += 1
            self.eco._guardar_datos()
            return [f"\x0312{user}\x0F Tu número era el \x0304{old_num}\x0F y ha salido el número \x0304{nuevo_numero}\x0F. \x0303¡Has Acertado!\x0F Sigue jugando, escribe \x02!mayor\x02 o \x02!menor\x02."]
        else:
            recompensa = game_state["aciertos_seguidos"] * 1000
            recibe, emb, e_msg = self.eco.cobrar_embargo(user, recompensa)
            racha = game_state["aciertos_seguidos"]
            game_state["aciertos_seguidos"] = 0
            # Resetear número tras fallo
            game_state["ultimo_numero"] = random.randint(1, 9)
            self.eco._guardar_datos()
            return [f"\x0312{user}\x0F Tu número era el \x0304{old_num}\x0F y ha salido el número \x0304{nuevo_numero}\x0F. ¡Has fallado! Tu recompensa son \x0312{self.eco.formatear_dinero(recibe)}\x0F Euros por tu racha de {racha} aciertos.{e_msg}"]
