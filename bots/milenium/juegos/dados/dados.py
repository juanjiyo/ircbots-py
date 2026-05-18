import random

class Dados:
    def __init__(self, economia):
        self.eco = economia

    def ejecutar(self, user, args):
        u = self.eco.get_user(user)
        partes = args.split()
        
        try:
            tiradas_a_usar = int(partes[0]) if partes else 1
        except Exception:
            return ["La cantidad de tiradas debe ser un número."]

        if tiradas_a_usar <= 0:
            return ["Debes usar al menos 1 tirada."]

        if u["mano"]["tiradas"] < tiradas_a_usar:
            u["intentos_sin_tiradas"] = u.get("intentos_sin_tiradas", 0) + 1
            if u["intentos_sin_tiradas"] >= 5:
                return self.eco.trigger_maldicion(user)
            return [f"❌ \x02{user}\x02 no tienes suficientes tiradas. Te quedan \x02{u['mano']['tiradas']}\x02. (Aviso {u['intentos_sin_tiradas']}/5 antes de la Maldición)"]

        # Resetear contador
        u["intentos_sin_tiradas"] = 0
        # Consumir tiradas
        u["mano"]["tiradas"] -= tiradas_a_usar
        
        # Tirar 3 dados
        d1 = random.randint(1, 6)
        d2 = random.randint(1, 6)
        d3 = random.randint(1, 6)
        total = d1 + d2 + d3
        
        resultado_msg = f"El usuario \x0312{user}\x0F lanza los dados: \x0312{d1}\x0F + \x0312{d2}\x0F + \x0312{d3}\x0F = \x0304{total}\x0F"
        
        premio = 0
        if total == 10:
            premio = 2500 * tiradas_a_usar
            recibe, emb, e_msg = self.eco.cobrar_embargo(user, premio)
            msg_final = f"{resultado_msg} ¡Enhorabuena! Has conseguido \x0312{self.eco.formatear_dinero(recibe)}\x0F Euros.{e_msg}"
        elif total == 5 or total == 15:
            premio = 1000 * tiradas_a_usar
            recibe, emb, e_msg = self.eco.cobrar_embargo(user, premio)
            msg_final = f"{resultado_msg} ¡Enhorabuena! Has conseguido \x0312{self.eco.formatear_dinero(recibe)}\x0F Euros.{e_msg}"
        else:
            msg_final = f"{resultado_msg} ¡Mala suerte! No has ganado nada esta vez."

        self.eco._guardar_datos()
        return [msg_final]
