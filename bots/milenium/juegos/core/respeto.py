import random
import time

class Respeto:
    def __init__(self, economia):
        self.eco = economia

    def ejecutar(self, user, args):
        u = self.eco.get_user(user)
        
        # El Respeto original: Todo o Nada.
        # Ajuste de Trilero: Si pierdes, quiebra + Deuda masiva.
        
        balance_mano = u["mano"]["euros"]
        if balance_mano < 1000000:
            return [f"❌ \x02{user}\x02, necesitas al menos \x03121.000.000€\x0F para que el Trilero te mire a la cara."]

        # El bot lanza el guante
        respuestas = [f"🎲 \x0312{user}\x0F, te juegas el \x02TODO POR EL TODO\x02 ante el Trilero... Los vasos se mueven rápido."]
        
        # Probabilidad de la Casa: 20% (La banca nunca pierde)
        victoria = (random.randint(1, 5) == 1)
        dado = random.randint(1, 6)
        b = self.eco.bote

        # Definir apuesta: 10M o el total de la mano si tiene menos de 10M
        apuesta = min(balance_mano, 10000000)

        if victoria:
            # GANASTE: Te llevas x2 de lo que apostaste
            premio_neto = apuesta * 2
            
            u["mano"]["euros"] += premio_neto
            u["respeto"] = min(100, u.get("respeto", 0) + 5)
            
            respuestas.append(f"🏆 \x0303\x02¡INCREÍBLE!\x02\x0F Has ganado el asalto. El Trilero te suelta \x0312{self.eco.formatear_dinero(premio_neto)}€\x0F.")
            respuestas.append(f"📈 Tu \x02Respeto\x02 sube a \x0303{u['respeto']}\x0F. Los cobradores te miran con otros ojos.")
        else:
            # PERDISTE: Quiebra + Deuda
            # Pierdes lo apostado y se genera deuda = apuesta * dado
            deuda_gen = apuesta * dado
            
            u["mano"]["euros"] -= apuesta
            u["deuda"] += deuda_gen
            u["respeto"] = max(-100, u.get("respeto", 0) - 10)
            
            # El 50% de lo perdido va al bote
            self.eco.sumar_al_bote("euros", int(apuesta * 0.5))
            
            respuestas.append(f"👊 \x0304\x02¡DESPLUMADO!\x02\x0F El Trilero te ha limpiado los bolsillos.")
            respuestas.append(f"💀 Pierdes \x0312{self.eco.formatear_dinero(apuesta)}€\x0F y te quedas con una \x02DEUDA\x02 de \x0304{self.eco.formatear_dinero(deuda_gen)}€\x0F.")
            respuestas.append(f"📉 Tu \x02Respeto\x02 cae a \x0304{u['respeto']}\x0F. El embargo será implacable.")

        self.eco._guardar_datos()
        return respuestas
