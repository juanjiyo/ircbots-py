import random

class TicketGames:
    def __init__(self, economia):
        self.eco = economia

    def rtgp(self, user):
        u = self.eco.get_user(user)
        if u["mano"]["tickets"] < 1:
            return [" \x0304Error:\x0F No tienes ningun Ticket para jugar a la RTGP."]
        
        # Consumir ticket
        u["mano"]["tickets"] -= 1
        
        simbolos = ["Bar1", "Limon", "Diamante"]
        s1, s2, s3 = random.choice(simbolos), random.choice(simbolos), random.choice(simbolos)
        
        resultado_visual = f"[{s1}] [{s2}] [{s3}]"
        
        # 1 en 25 de Premio Oculto (no gasta ticket realmente en el original, pero aqui si para simplificar o le devolvemos uno)
        if random.randint(1, 25) == 1:
            u["mano"]["tickets"] += 1 # Devolver ticket por premio oculto
            premio = random.randint(100000, 200000)
            self.eco.cobrar_embargo(user, premio)
            return [f" \x0306\u00a1Premio Oculto!:\x0F \x02{user}\x02 obtienes un premio de \x0312{self.eco.formatear_dinero(premio)}€\x0F! Y no gastas ningun Ticket."]

        if s1 == s2 == s3:
            premio = random.randint(10000, 20000)
            recibe, emb, e_msg = self.eco.cobrar_embargo(user, premio)
            msg = f" \x02Rtgp:\x02 {resultado_visual} \x0303¡Premio!\x0F Ganas \x0312{self.eco.formatear_dinero(recibe)}€\x0F.{e_msg}"
        else:
            msg = f" \x02Rtgp:\x02 {resultado_visual} \x0314¡Pierdes!\x0F No hay premio esta vez."
            self.eco.sumar_al_bote("euros", 150) # El original sumaba 150 al bote
        
        self.eco._guardar_datos()
        return [msg]

    def rsuerte(self, user):
        u = self.eco.get_user(user)
        if u["mano"]["tickets"] < 1:
            return [" \x0304Error:\x0F No tienes ningun Ticket para la RSuerte."]

        u["mano"]["tickets"] -= 1
        suerte = random.randint(1, 14)
        
        if suerte in [1, 3, 5, 7, 9]:
            t_ganados = random.randint(5, 50)
            u["mano"]["tickets"] += t_ganados
            msg = f" \x02RSuerte:\x02 Giras la ruleta y ganas \x0312{t_ganados} Tickets\x0F!"
        elif suerte in [2, 4, 6, 8, 10, 11]:
            euros = random.randint(10000, 20000)
            recibe, emb, e_msg = self.eco.cobrar_embargo(user, euros)
            msg = f" \x02RSuerte:\x02 Giras la ruleta y ganas \x0312{self.eco.formatear_dinero(recibe)}€\x0F.{e_msg}"
        else:
            # Premio Oculto (12, 13, 14)
            u["mano"]["tickets"] += 1 # No gasta ticket
            premio = random.randint(200000, 400000)
            self.eco.cobrar_embargo(user, premio)
            msg = f" \x0306\u00a1Premio Oculto!:\x0F ¡Obtienes \x0312{self.eco.formatear_dinero(premio)}€\x0F y no gastas ticket!"
            
        self.eco._guardar_datos()
        return [msg]

    def rpremio(self, user):
        u = self.eco.get_user(user)
        if u["mano"]["tickets"] < 1:
            return [" \x0304Error:\x0F No tienes ningun Ticket para el RPremio."]

        u["mano"]["tickets"] -= 1
        suerte = random.randint(1, 18)
        
        if suerte in [1, 3, 5, 7, 9, 11, 13]:
            t_ganados = random.randint(5, 100)
            u["mano"]["tickets"] += t_ganados
            msg = f" \x02RPremio:\x02 ¡Felicidades! Tu premio contiene \x0312{t_ganados} Tickets\x0F."
        elif suerte in [2, 4, 6, 8, 10, 12]:
            euros = random.randint(10000, 20000)
            recibe, emb, e_msg = self.eco.cobrar_embargo(user, euros)
            msg = f" \x02RPremio:\x02 ¡Felicidades! Tu premio contiene \x0312{self.eco.formatear_dinero(recibe)}€\x0F.{e_msg}"
        else:
            # Premio Oculto (14-18)
            u["mano"]["tickets"] += 1
            premio = random.randint(200000, 400000)
            self.eco.cobrar_embargo(user, premio)
            msg = f" \x0306\u00a1Premio Oculto!:\x0F ¡Tu sobre contenia \x0312{self.eco.formatear_dinero(premio)}€\x0F extra!"

        self.eco._guardar_datos()
        return [msg]
