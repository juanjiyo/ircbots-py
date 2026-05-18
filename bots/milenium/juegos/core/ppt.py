import random

class PiedraPapelTijera:
    def __init__(self, economia):
        self.eco = economia
        self.opciones = ["piedra", "papel", "tijeras"]

    def ejecutar(self, user, eleccion_user):
        eleccion_user = eleccion_user.lower()
        if eleccion_user not in self.opciones:
            return ["Uso: !piedra, !papel o !tijeras"]
        
        u = self.eco.get_user(user)
        # Coste de 1.000€ para jugar
        if u["mano"]["euros"] < 1000:
            return ["❌ Necesitas 1.000€ para jugar."]
        
        u["mano"]["euros"] -= 1000
        eleccion_bot = random.choice(self.opciones)
        
        msg_base = f"👊 \x02{user}\x02 elige \x02{eleccion_user.upper()}\x02 y el bot responde con \x02{eleccion_bot.upper()}\x02."
        
        if eleccion_user == eleccion_bot:
            # Empate
            u["mano"]["euros"] += 1000 # Devolver dinero
            return [f"{msg_base} 🤝 ¡Empate! Se te devuelve el dinero."]
        
        ganaste = False
        if eleccion_user == "piedra" and eleccion_bot == "tijeras": ganaste = True
        elif eleccion_user == "papel" and eleccion_bot == "piedra": ganaste = True
        elif eleccion_user == "tijeras" and eleccion_bot == "papel": ganaste = True
        
        if ganaste:
            premio = 2500
            self.eco.cobrar_embargo(user, premio)
            return [f"{msg_base} 🏆 ¡HAS GANADO! Te llevas \x0312{self.eco.formatear_dinero(premio)}€\x0F."]
        else:
            self.eco.sumar_al_bote("euros", 1000)
            return [f"{msg_base} 💀 ¡HAS PERDIDO! El bot se queda con tus 1.000€ para el Bote."]
