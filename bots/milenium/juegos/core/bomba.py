import random

class Bomba:
    def __init__(self, economia):
        self.eco = economia
        self.colores = ["rojo", "azul", "amarillo", "verde"]
        self.activo = False
        self.cable_correcto = None
        self.usuario_objetivo = None

    def iniciar(self, user):
        if self.activo:
            return ["\x0304[Aviso]\x0F Ya hay una bomba activa en el canal. ¡Alguien tiene que cortarla!"]
        
        self.activo = True
        self.usuario_objetivo = user
        self.cable_correcto = random.choice(self.colores)
        
        return [
            f"\x0304[Bomba]\x0F \x02¡HAY UNA BOMBA EN EL CANAL!\x02\x0F Necesitamos que alguien la desactive...",
            f"\x0308[Corte]\x0F \x02{user}\x02, debes cortar uno de estos cables: \x0304rojo\x0F, \x0312azul\x0F, \x0308amarillo\x0F, \x0303verde\x0F.",
            f"Uso: !cortar <color>"
        ]

    def cortar(self, user, color):
        if not self.activo:
            return ["No hay ninguna bomba que desactivar ahora mismo."]
        
        color = color.lower()
        if color not in self.colores:
            return [f"Ese color no existe. Elige entre: {', '.join(self.colores)}"]

        self.activo = False
        if color == self.cable_correcto:
            premio = random.randint(5000, 25000)
            u = self.eco.get_user(user)
            u["mano"]["euros"] += premio
            self.eco._guardar_datos()
            return [
                f"\x0308[Corte]\x0F Cortar el cable \x02{color}\x02 ha sido una buena idea! Has salvado el canal desactivando la bomba.",
                f"\x0303[Fiesta]\x0F ¡Hurra por \x02{user}\x02! Has ganado \x0312{self.eco.formatear_dinero(premio)}€\x0F de recompensa."
            ]
        else:
            # Fallo: El bot intentará hacer un KICK (manejado en iabot.py)
            return ["BOOM"] # Señal para iabot de que debe kickear
