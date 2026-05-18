import random

class Fortaleza:
    def __init__(self, economia):
        self.eco = economia
        self.activo = False
        self.retador = None
        self.canal = None
        self.clave = None
        self.intentos = 0
        self.max_intentos = 3
        self.timestamp = 0

    def iniciar(self, canal, retador):
        if self.activo:
            return None, ["\x0304[Aviso]\x0F Ya hay un desafío de Fortaleza activo."]

        self.activo = True
        self.retador = retador
        self.canal = canal
        self.clave = str(random.randint(1000, 9999))
        self.intentos = 0

        return f"MODE {canal} +k {self.clave}", [
            f"\x0304\x02¡FORTALEZA ACTIVADA!\x02\x0F",
            f"\x0310{retador}\x0F, has sido retado. Se ha bloqueado el canal con una clave.",
            f"Te expulso. Vuelve a entrar con \x02/join {canal} <clave>\x02.",
            f"Tienes \x0304{self.max_intentos} intentos\x0F o perderás 5.000€.",
            "Escribe \x02!fortaleza stop\x02 cuando estés dentro para ganar.",
        ]

    def verificar_clave(self, nick, clave_intentada):
        if not self.activo or nick != self.retador:
            return None
        if clave_intentada == self.clave:
            return True
        self.intentos += 1
        return False

    def pista(self, nick):
        if not self.activo or nick != self.retador:
            return None
        pistas = [
            f"Pista: la clave tiene 4 dígitos.",
            f"Pista: empieza por {self.clave[0]}...",
            f"Pista: termina en {self.clave[-1]}...",
            f"Pista: la suma de sus dígitos es {sum(int(d) for d in self.clave)}.",
        ]
        idx = min(self.intentos, len(pistas) - 1)
        return pistas[idx]

    def detener(self, nick):
        if not self.activo:
            return None, ["\x0304[Aviso]\x0F No hay ningún desafío activo."]
        if nick != self.retador:
            return None, ["\x0304[Aviso]\x0F Solo el retado puede detener el desafío."]

        premio = 10000
        u = self.eco.get_user(nick)
        u["mano"]["euros"] += premio
        self.eco._guardar_datos()

        modo = f"MODE {self.canal} -k"
        self._limpiar()
        return modo, [
            f"\x0303\x02¡{nick} ha superado la Fortaleza!\x02\x0F",
            f"\x0303[Victoria]\x0F El canal ha sido liberado. Has ganado \x0312{self.eco.formatear_dinero(premio)}€\x0F.",
        ]

    def fallar(self, nick):
        if not self.activo or nick != self.retador:
            return None, []

        costo = 5000
        u = self.eco.get_user(nick)
        perdida = min(costo, u["mano"]["euros"])
        u["mano"]["euros"] -= perdida
        self.eco.sumar_al_bote("euros", perdida)
        self.eco._guardar_datos()

        modo = f"MODE {self.canal} -k"
        self._limpiar()
        return modo, [
            f"\x0304\x02¡{nick} ha fallado la Fortaleza!\x02\x0F",
            f"\x0304[Muerte]\x0F Has perdido \x0304{self.eco.formatear_dinero(perdida)}€\x0F que van al Bote.",
        ]

    def _limpiar(self):
        self.activo = False
        self.retador = None
        self.canal = None
        self.clave = None
        self.intentos = 0
