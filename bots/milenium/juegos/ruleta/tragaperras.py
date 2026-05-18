import random

class Tragaperras:
    def __init__(self, economia):
        self.eco = economia
        # Símbolos originales del mIRC (estilizados)
        self.simbolos = ["", "", "", "", "", ""]

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
            return [f" \x02{user}\x02 no tienes suficientes tiradas. Te quedan \x02{u['mano']['tiradas']}\x02. (Aviso {u['intentos_sin_tiradas']}/5 antes de la Maldición)"]

        # Resetear contador si tiene tiradas y juega
        u["intentos_sin_tiradas"] = 0
        # Consumir tiradas
        u["mano"]["tiradas"] -= tiradas_a_usar
        
        # Tirar tragaperras
        s1 = random.choice(self.simbolos)
        s2 = random.choice(self.simbolos)
        s3 = random.choice(self.simbolos)
        
        resultado_visual = f"\x02[\x0F {s1} \x02|\x0F {s2} \x02|\x0F {s3} \x02]\x0F"
        msg_base = f"El usuario \x0312{user}\x0F juega a la máquina tragaperras: {resultado_visual}"
        
        premio = 0
        if s1 == s2 == s3:
            # Triple coincidencia (Premios recalibrados)
            if s1 == "": premio = 80000
            elif s1 == "": premio = 40000
            elif s1 == "": premio = 20000
            else: premio = 10000
            
            premio_total = premio * tiradas_a_usar
            recibe, emb, e_msg = self.eco.cobrar_embargo(user, premio_total)
            msg_final = f"{msg_base} \x0303¡JACKPOT! \x0F Has ganado \x0312{self.eco.formatear_dinero(recibe)}\x0F Euros.{e_msg}"
        elif s1 == s2 or s2 == s3 or s1 == s3:
            # Doble coincidencia
            premio = 1500 * tiradas_a_usar
            recibe, emb, e_msg = self.eco.cobrar_embargo(user, premio)
            msg_final = f"{msg_base} \x0310¡Doble! \x0F Has ganado \x0312{self.eco.formatear_dinero(recibe)}\x0F Euros.{e_msg}"
        else:
            msg_final = f"{msg_base} ¡Mala suerte! No has ganado nada."

        self.eco._guardar_datos()
        return [msg_final]
