import random

class Trileros:
    def __init__(self, economia):
        self.eco = economia
        self.posiciones = ["izquierda", "centro", "derecha"]

    def _repartir(self):
        cartas = ["As de Picas", "Rey de Corazones", "Jota de Treboles"]
        random.shuffle(cartas)
        return dict(zip(self.posiciones, cartas))

    def ejecutar(self, user, eleccion):
        eleccion = eleccion.lower()
        if eleccion not in self.posiciones:
            return [
                "🎴 \x02Trileros\x02 — ¡Encuentra el As de Picas!",
                "   Uso: \x02!trileros <izquierda|centro|derecha>\x02",
                "   Hay 3 cartas boca abajo. Solo una es el As de Picas.",
                "   Apuesta 2.000€ y si aciertas, ¡ganas 5.000€!"
            ]

        u = self.eco.get_user(user)
        if u["mano"]["euros"] < 2000:
            return ["❌ Necesitas 2.000€ para jugar a los trileros."]

        u["mano"]["euros"] -= 2000
        mesa = self._repartir()
        carta_usuario = mesa[eleccion]

        if carta_usuario == "As de Picas":
            premio = 5000
            self.eco.cobrar_embargo(user, premio)
            return [
                f"🎴 \x02{user}\x02 levanta la carta de la \x02{eleccion}\x02... ¡ES EL \x0304AS DE PICAS\x0F!",
                f"🏆 \x0303¡HAS GANADO!\x0F Te llevas \x0312{self.eco.formatear_dinero(premio)}€\x0F."
            ]
        else:
            self.eco.sumar_al_bote("euros", 2000)
            msg_extra = ""
            if carta_usuario == "Rey de Corazones":
                msg_extra = "El \x0304Rey de Corazones\x0F te ha sido esquivo..."
            elif carta_usuario == "Jota de Treboles":
                msg_extra = "La \x0304Jota de Treboles\x0F te ha engañado..."
            return [
                f"🎴 \x02{user}\x02 levanta la carta de la \x02{eleccion}\x02... \x0304{carta_usuario}\x0F.",
                f"💀 \x0304¡HAS PERDIDO!\x0F {msg_extra} Tus 2.000€ van al Bote."
            ]
