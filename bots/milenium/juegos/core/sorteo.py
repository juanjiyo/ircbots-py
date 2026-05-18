import random

class Sorteo:
    def __init__(self, economia):
        self.eco = economia
        self.objetos = ["un Lingote de Oro", "un Diamante", "un Ticket Dorado", "una Llave Magica", "1.000.000 de Euros", "500 Tiradas"]
        self.premios_frase = ["un pack de iconos IRC", "una suscripcion VIP", "el respeto eterno del bot", "un abrazo virtual", "una insignia de campeon"]

    def ejecutar(self, channel, user, channel_users):
        # Filtrar solo usuarios registrados en la economía
        registrados = [u for u in channel_users if u.lower() in self.eco.datos]
        
        if not registrados or len(registrados) < 2:
            return ["\x0304[Error]\x0F No hay suficientes usuarios registrados en el bot para realizar un sorteo. (Los participantes deben haber usado algún comando como !saldo o !premio antes)"]

        objeto = random.choice(self.objetos)
        numero = random.randint(1, 50)
        ganador = random.choice(registrados)
        frase_premio = random.choice(self.premios_frase)

        # Entregar el premio real al ganador si es un objeto cuantificable
        u_ganador = self.eco.get_user(ganador)
        if "Lingote" in objeto: u_ganador["mano"]["lingotes"] += 1
        elif "Diamante" in objeto: u_ganador["mano"]["diamantes"] += 1
        elif "Ticket" in objeto: u_ganador["mano"]["tickets"] += 1
        elif "Llave" in objeto: u_ganador["mano"]["llaves"] += 1
        elif "1.000.000" in objeto: u_ganador["mano"]["euros"] += 1000000
        elif "500 Tiradas" in objeto: u_ganador["mano"]["tiradas"] += 500
        
        self.eco._guardar_datos()

        return [
            f"\x0307[Premio]\x0F Bueno gente de \x0312{channel}\x0F .... voy a sortear \x02{objeto}\x02.",
            f"\x0308[Dado]\x0F El numero seleccionado es... \x02{numero}\x02. ¡Toma \x02{ganador}\x02! Esto... \x02{frase_premio}\x02 te pertenece.",
            f"\x0303[Fiesta]\x0F FELICITACIONES!!!! FELICITACIONES!!! FELICITACIONES!!!!\x0F"
        ]
