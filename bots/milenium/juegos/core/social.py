import random

class Social:
    def __init__(self):
        self.respuestas_bola8 = [
            "SI.", "No.", "Puede Ser.", "Lo Siento Pero No Lo Puedo Predecir En Estos Instantes.",
            "Le Gustaria Que Le Respondiese A Eso?", "Puede Volver A Preguntarlo Mas Tarde.",
            "Decididamente, Si.", "Decididamente, No.", "Puedes Confiar En Ello.",
            "Todo Apunta... A Que Si.", "Probablemente.", "Sin Duda Alguna.",
            "No Cuentes Con Ello.", "Mis Fuentes Dicen, Que No.", "Mis Fuentes Dicen, Que Si.",
            "Mi Respuesta Es, No.", "Mi Respuesta Es, Si.", "Como Yo Lo Veo, Si.",
            "Como Yo Lo Veo, No.", "Concentrate Y Formula La Pregunta De Nuevo.",
            "Eso, Es Cierto.", "Eso, No Es Cierto.", "Creo... Que Si.", "Creo... Que No.",
            "Posiblemente.", "Tal Vez.", "Lo Siento Pero Es Mejor Que No Te Lo Diga Ahora."
        ]

    def bola8(self, user, args):
        if not args:
            return ["12Bola ( 8 ) -> " + user + " Formula Tu Pregunta tipeando: !bola8 pregunta"]
        
        res = random.choice(self.respuestas_bola8)
        return [
            f"12Bola ( 8 ) -> {user}, La Respuesta es..",
            f"12Bola ( 8 ) -> {user}, {res}"
        ]

    def beso(self, user, args):
        partes = args.split()
        target = partes[0] if partes else "el aire"
        return [f"13{user} le da un gran beso a 13{target}. ¡Que romántico!"]

    def abrazo(self, user, args):
        partes = args.split()
        target = partes[0] if partes else "el aire"
        return [f"10{user} le da un fuerte abrazo a 10{target}. ¡Se siente el cariño!"]

    def sexo(self, user, args):
        partes = args.split()
        target = partes[0] if partes else "el aire"
        frases = [
            f"04{user} le susurra cosas al oído a 04{target}... y {target} se sonroja.",
            f"07{user} se acerca lentamente a 07{target} y le muerde el labio inferior.",
            f"13{user} desliza su mano por la espalda de 13{target} provocando un escalofrío.",
            f"05{user} muerde suavemente el cuello de 05{target} mientras susurra su nombre.",
            f"12{user} y 12{target} se pierden juntos en la noche... lo que pase después es cosa suya.",
            f"07{user} le da una nalgada juguetona a 07{target} y sale corriendo entre risas.",
            f"04{user} mira a 04{target} de arriba abajo con una sonrisa pícara. {target} no sabe dónde meterse.",
            f"13{user} se quita la chaqueta y se sienta en el regazo de 13{target}. La temperatura sube.",
            f"07{user} provoca a 07{target} con un baile sugerente. {target} se queda sin aliento.",
            f"05{user} besa el cuello de 05{target} mientras sus manos recorren su cuerpo.",
        ]
        return [random.choice(frases)]

    def _barra(self, pct):
        total = 25
        llenos = max(1, int(pct / (100 / total)))
        if pct < 25: clr = "04"; txtclr = "00"
        elif pct < 50: clr = "08"; txtclr = "01"
        elif pct < 75: clr = "12"; txtclr = "00"
        else: clr = "03"; txtclr = "01"
        fmt = f"{clr},{clr}"
        texto = f"{pct}%"
        if llenos >= 3:
            antes = (llenos - 1) // 2
            despues = llenos - antes - 1
            return "".join([f"{fmt} " for _ in range(antes)]) + \
                   f"{txtclr},{clr}{texto}" + \
                   "".join([f"{fmt} " for _ in range(max(0, despues))]) + \
                   "".join(["01,01 " for _ in range(total - llenos)]) + ""
        return "".join([f"{fmt} " for _ in range(llenos)]) + \
               "".join(["01,01 " for _ in range(total - llenos)]) + f" {texto}"

    def _rand_range(self, pct):
        if pct < 20: return random.randint(1, 20)
        elif pct < 40: return random.randint(20, 40)
        elif pct < 60: return random.randint(40, 60)
        elif pct < 80: return random.randint(60, 80)
        else: return random.randint(80, 100)

    def sexom(self, user, args):
        partes = args.split()
        if len(partes) < 2:
            return ["Uso: .sexom <Nick1> <Nick2>"]
        
        n1, n2 = partes[0], partes[1]
        sexo = random.randint(1, 100)
        kama = random.randint(1, 100)
        sado = random.randint(1, 100)
        azotes = random.randint(1, 100)
        
        posturas = self._rand_range(kama)
        dolorosas = self._rand_range(sado)
        azotes_num = self._rand_range(azotes)
        
        return [
            f"04SexoMetro Compatibilidad entre 12{n1} y 12{n2} :",
            f"04Sexo: {self._barra(sexo)}",
            f"13Kamasutra: {self._barra(kama)} 10→ {posturas} posturas",
            f"07Sado: {self._barra(sado)} 10→ {dolorosas} posturas dolorosas",
            f"12Azotes: {self._barra(azotes)} 10→ {azotes_num} azotes",
        ]