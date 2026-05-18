import random

class Cofres:
    def __init__(self, economia):
        self.eco = economia

    def ejecutar(self, user, args):
        u = self.eco.get_user(user)
        
        if u["mano"]["llaves"] < 1:
            return ["\x0304¡Error!\x0F Necesitas al menos 1 \x02Llave\x02 para abrir un Cofre Mágico."]

        # Consumir llave
        u["mano"]["llaves"] -= 1
        
        # Generar premios aleatorios variados
        p_euros = random.randint(100000, 5000000) # De 100k a 5M
        p_tickets = random.randint(0, 10)
        p_lingotes = random.randint(0, 5)
        p_diamantes = random.randint(0, 2)
        
        u["mano"]["tickets"] += p_tickets
        u["mano"]["lingotes"] += p_lingotes
        u["mano"]["diamantes"] += p_diamantes
        
        # El dinero va por embargo
        recibe, emb, e_msg = self.eco.cobrar_embargo(user, p_euros)
        
        self.eco._guardar_datos()
        
        premios = []
        if recibe > 0: premios.append(f"\x0312{self.eco.formatear_dinero(recibe)}\x0F Euros")
        if p_tickets > 0: premios.append(f"\x0312{p_tickets}\x0F Tickets")
        if p_lingotes > 0: premios.append(f"\x0312{p_lingotes}\x0F Lingotes")
        if p_diamantes > 0: premios.append(f"\x0312{p_diamantes}\x0F Diamantes")
        
        msg_premios = ", ".join(premios) if premios else "nada (¡qué mala suerte!)"
        if e_msg: msg_premios += e_msg
        
        return [
            f"El cofre contenía ..... \x0312{msg_premios}"
        ]
