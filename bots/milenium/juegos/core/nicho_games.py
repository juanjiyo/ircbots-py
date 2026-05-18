import random
import time

class NichoGames:
    def __init__(self, economia):
        self.eco = economia
        self.premios_cuerdas = [
            "50.000 Euros", "100.000 Euros", "1 Ticket", "5 Tickets",
            "un Lingote de Oro", "nada (estaba vacía)", "un zapato viejo",
            "una Llave Magica", "10.000 Euros", "500.000 Euros"
        ]
        self.sorpresas = [
            "¡Has encontrado un billete de 500€ en el suelo!",
            "¡Un duende te regala 5 Tickets!",
            "¡Has ganado una Llave Magica por tu cara bonita!",
            "¡El bot se siente generoso y te da 1.000.000€!",
            "¡Has tropezado y perdido 1.000€!",
            "¡Te ha tocado un pack de 100 tiradas extra!"
        ]

    def cuerdas(self, user, lado):
        u = self.eco.get_user(user)
        # 10k de entrada para jugar
        if u["mano"]["euros"] < 10000:
            return ["❌ Necesitas 10.000€ para tirar de la cuerda."]
        
        u["mano"]["euros"] -= 10000
        premio = random.choice(self.premios_cuerdas)
        
        res = [f"🪢 \x02{user}\x02 coges la cuerda {lado} suavemente, estiras y ......"]
        
        # Procesar premio real
        if "50.000" in premio: u["mano"]["euros"] += 50000
        elif "100.000" in premio: u["mano"]["euros"] += 100000
        elif "500.000" in premio: u["mano"]["euros"] += 500000
        elif "10.000" in premio: u["mano"]["euros"] += 10000
        elif "1.000.000" in premio: u["mano"]["euros"] += 1000000
        elif "1 Ticket" in premio: u["mano"]["tickets"] += 1
        elif "5 Tickets" in premio: u["mano"]["tickets"] += 5
        elif "Lingote" in premio: u["mano"]["lingotes"] += 1
        elif "Llave" in premio: u["mano"]["llaves"] += 1
        
        res.append(f"🎁 Te ha tocado: \x0312{premio}\x0F!")
        self.eco._guardar_datos()
        return res

    def sorpresa(self, user):
        u = self.eco.get_user(user)
        msg = random.choice(self.sorpresas)
        
        if "500€" in msg: u["mano"]["euros"] += 500
        elif "5 Tickets" in msg: u["mano"]["tickets"] += 5
        elif "Llave" in msg: u["mano"]["llaves"] += 1
        elif "1.000.000€" in msg: u["mano"]["euros"] += 1000000
        elif "perdido 1.000€" in msg: u["mano"]["euros"] = max(0, u["mano"]["euros"] - 1000)
        elif "100 tiradas" in msg: u["mano"]["tiradas"] += 100
        
        self.eco._guardar_datos()
        return [f"🎁 \x02{user}\x02: {msg}"]
