import random

class Ahorcado:
    def __init__(self, economia):
        self.eco = economia
        self.diccionario = [
            "ORDENADOR", "BOTIJO", "ESPAÑA", "FUTBOL", "MAGIA", "DRAGON", "CASTILLO",
            "TECLADO", "PANTALLA", "SERVIDOR", "PYTHON", "PROGRAMA", "AVENTURA",
            "TESORO", "PIRATA", "COFRE", "LLAVE", "ESMERALDA", "DIAMANTE", "LINGOTE",
            "ZAPATO", "GUITARRA", "CERVEZA", "FIESTA", "VERANO", "INVIERNO", "PLAYA",
            "MONTAÑA", "ESTRELLA", "GALAXIA", "UNIVERSO", "IRC", "CHAT", "CANAL"
        ]
        self.partidas = {} # {canal: {palabra: "", descubierta: [], fallos: 0, letras_dichas: []}}

    def iniciar(self, channel):
        chan_l = channel.lower()
        if chan_l in self.partidas:
            p = self.partidas[chan_l]
            return [f"⚠️ Ya hay una partida activa en este canal. Palabra: {self._formatear_palabra(p)} (Fallos: {p['fallos']}/6)"]
        
        palabra = random.choice(self.diccionario)
        self.partidas[chan_l] = {
            "palabra": palabra,
            "descubierta": ["_" for _ in palabra],
            "fallos": 0,
            "letras_dichas": []
        }
        
        p = self.partidas[chan_l]
        return [
            f"🎮 \x0303\x02¡Comienza el Ahorcado!\x0F El bot ha pensado una palabra de \x02{len(palabra)}\x02 letras.",
            f"🔍 Palabra: \x02{self._formatear_palabra(p)}\x02",
            f"Uso: !letra <L>"
        ]

    def adivinar_letra(self, channel, user, letra):
        chan_l = channel.lower()
        if chan_l not in self.partidas:
            return ["No hay ninguna partida activa. Escribe \x02!ahorcado\x02 para empezar."]
        
        p = self.partidas[chan_l]
        letra = letra.upper()
        
        if len(letra) != 1 or not letra.isalpha():
            return ["❌ Por favor, di solo una letra."]
            
        if letra in p["letras_dichas"]:
            return [f"⚠️ La letra \x02{letra}\x02 ya se ha dicho. Intenta con otra."]
            
        p["letras_dichas"].append(letra)
        
        if letra in p["palabra"]:
            # ¡ACIERTO!
            for i, char in enumerate(p["palabra"]):
                if char == letra:
                    p["descubierta"][i] = letra
            
            if "_" not in p["descubierta"]:
                # ¡GANADOR!
                premio = 50000
                recibe, emb, e_msg = self.eco.cobrar_embargo(user, premio)
                del self.partidas[chan_l]
                return [
                    f"🎉 \x0303\x02¡ENHORABUENA!\x0F \x02{user}\x02 ha adivinado la palabra: \x0312{p['palabra']}\x0F.",
                    f"💰 Has ganado \x0312{self.eco.formatear_dinero(recibe)}€\x0F de premio.{e_msg}"
                ]
            else:
                return [f"✅ \x0303¡Bien!\x0F La letra \x02{letra}\x02 esta en la palabra. -> \x02{self._formatear_palabra(p)}\x02"]
        else:
            # FALLO
            p["fallos"] += 1
            if p["fallos"] >= 6:
                palabra_final = p["palabra"]
                del self.partidas[chan_l]
                return [
                    f"💀 \x0304\x02¡AHORCADO!\x0F Nadie adivino la palabra y el monigote ha muerto.",
                    f"🔍 La palabra era: \x0312{palabra_final}\x0F. Escribe \x02!ahorcado\x02 para la revancha."
                ]
            else:
                return [f"❌ \x0304¡Fallo!\x0F La \x02{letra}\x02 no esta. Te quedan \x02{6 - p['fallos']}\x02 vidas. -> \x02{self._formatear_palabra(p)}\x02"]

    def _formatear_palabra(self, p):
        return " ".join(p["descubierta"])
