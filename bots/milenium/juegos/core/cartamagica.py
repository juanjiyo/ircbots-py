import random
import time
import os
import json

class CartaMagica:
    def __init__(self, economia):
        self.eco = economia
        self.archivo_datos = os.path.join(os.path.dirname(__file__), "..", "datos", "cartamagica.json")
        self.datos = self._cargar_datos()

    def _cargar_datos(self):
        if os.path.exists(self.archivo_datos):
            try:
                with open(self.archivo_datos, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[CartaMagica] Error cargando datos: {e}")
        return {"ultima_gema": "Nadie", "pendientes": {}}

    def _guardar_datos(self):
        try:
            os.makedirs(os.path.dirname(self.archivo_datos), exist_ok=True)
            with open(self.archivo_datos, 'w', encoding='utf-8') as f:
                json.dump(self.datos, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[CartaMagica] Error guardando datos: {e}")

    def ejecutar(self, user, args):
        u = self.eco.get_user(user)
        
        if u["mano"]["tickets"] < 1:
            return [" \x0304Error:\x0F No tienes ningun Ticket. Necesitas 1 para pedir una Carta Magica."]
        
        if u["mano"]["euros"] < 100000:
            return [" \x0304Error:\x0F Necesitas un minimo de \x02100.000€\x02 en mano."]

        # Consumir recursos
        u["mano"]["tickets"] -= 1
        u["mano"]["euros"] -= 100000
        self.eco.sumar_al_bote("euros", 100000)
        
        # Tirada 1 entre 34 (mismo que original)
        carta = random.randint(1, 34)
        
        if carta == 34:
            # ¡GEMA MAGICA!
            self.datos["ultima_gema"] = user
            self.datos["pendientes"][user.lower()] = True
            u["mano"]["euros"] += 10000000
            
            self._guardar_datos()
            self.eco._guardar_datos()
            
            return [
                f" \x02{user}\x02 recibe su Carta Magica, ¡y es la \x0306Gema Magica\x0F!",
                f" \x0303¡¡PREMIO!!\x0F Ganas \x031210.000.000€\x0F y una \x02Carta Sorpresa\x02. Escribe \x02!carta.sorpresa\x02 para abrirla."
            ]
        else:
            num_visual = random.randint(0, 9)
            self.eco._guardar_datos()
            return [f" \x02{user}\x02 recibe su Carta Magica y es un \x02{num_visual}\x02. .Sin Premio, el ultimo en encontrar la Gema fue [\x0306{self.datos['ultima_gema']}\x0F]. Pierdes 100.000€."]

    def abrir_sorpresa(self, user):
        nick_l = user.lower()
        if nick_l not in self.datos["pendientes"]:
            return [" No tienes ninguna Carta Sorpresa pendiente. ¡A buscar gemas!"]
        
        del self.datos["pendientes"][nick_l]
        u = self.eco.get_user(user)
        
        suerte = random.randint(1, 4)
        if suerte == 1:
            premio = 10000000
            u["mano"]["euros"] += premio
            msg = f" \x02Carta Sorpresa:\x02 Contiene un Premio de \x030310.000.000€\x0F."
        elif suerte == 2:
            premio = 100000000
            u["mano"]["euros"] += premio
            msg = f" \x02Carta Sorpresa:\x02 ¡¡BRUTAL!! Contiene un Premio de \x0303100.000.000€\x0F."
        elif suerte == 3:
            euros = 10000000
            tickets = random.randint(100, 200)
            u["mano"]["euros"] += euros
            u["mano"]["tickets"] += tickets
            msg = f" \x02Carta Sorpresa:\x02 Contiene \x030310.000.000€\x0F y \x0312{tickets} Tickets\x0F!"
        else:
            tickets = random.randint(100, 200)
            u["mano"]["tickets"] += tickets
            msg = f" \x02Carta Sorpresa:\x02 Contiene \x0312{tickets} Tickets\x0F!"

        self._guardar_datos()
        self.eco._guardar_datos()
        return [msg]
