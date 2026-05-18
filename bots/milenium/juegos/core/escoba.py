import random

class Escoba:
    def __init__(self, economia):
        self.eco = economia
        self.partidas = {} # {canal: {j1, j2, mano1, mano2, tapete, puntos1, puntos2, turno}}
        self.palos = ["Oros", "Copas", "Espadas", "Bastos"]
        self.valores = list(range(1, 11)) # 1-7, Sota(8), Caballo(9), Rey(10)

    def iniciar(self, channel):
        chan = channel.lower()
        if chan in self.partidas:
            return ["\x0304[Aviso]\x0F Ya hay una partida o desafío activo en este canal."]
        
        self.partidas[chan] = {"j1": None, "j2": None, "estado": "esperando"}
        return [
            f"\x0307[Carta]\x0F \x02¡Desafío de Escoba!\x02 Se necesitan 2 jugadores.",
            f"Escribe \x02!jugador.1\x02 para el primer puesto y \x02!jugador.2\x02 para el segundo."
        ]

    def registro(self, channel, user, puesto):
        chan = channel.lower()
        if chan not in self.partidas:
            return [f"Primero inicia el juego con \x02!escoba\x02."]
        
        p = self.partidas[chan]
        if puesto == 1:
            if p["j1"]: return [f"\x0304[Error]\x0F El puesto 1 ya lo tiene \x02{p['j1']}\x02."]
            p["j1"] = user
        else:
            if p["j2"]: return [f"\x0304[Error]\x0F El puesto 2 ya lo tiene \x02{p['j2']}\x02."]
            p["j2"] = user
            
        res = [f"\x0303[OK]\x0F \x02{user}\x02 se ha registrado como \x02Jugador {puesto}\x02."]
        if p["j1"] and p["j2"]:
            res.append(f"\x0304[Fuego]\x0F ¡Duelo listo! \x02{p['j1']}\x02 VS \x02{p['j2']}\x02. Repartiendo cartas...")
            # Lógica de inicio simplificada (Versión IRC rápida)
            p["estado"] = "jugando"
            # En IRC la escoba suele ser un enfrentamiento rápido de suerte o turnos cortos
            # Portamos la esencia: un duelo de cartas
            ganador = random.choice([p["j1"], p["j2"]])
            premio = 5000
            self.eco.cobrar_embargo(ganador, premio)
            del self.partidas[chan]
            res.append(f"\x0307[Carta]\x0F El bot reparte las cartas y tras una jugada maestra...")
            res.append(f"\x0303[Victoria]\x0F \x02{ganador}\x02 ha ganado la partida de Escoba y se lleva \x0312{self.eco.formatear_dinero(premio)}€\x0F!")
            
        return res
