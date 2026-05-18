import random
import time
import os
import json

class RuletaRusa:
    def __init__(self, economia):
        self.eco = economia
        self.archivo_record = os.path.join(os.path.dirname(__file__), "..", "datos", "ruletarusa.json")
        self.stats = self._cargar_stats()

    def _cargar_stats(self):
        if os.path.exists(self.archivo_record):
            try:
                with open(self.archivo_record, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[RuletaRusa] Error cargando stats: {e}")
        return {"record_supervivencia": 0, "campeon": "Nadie", "usuarios": {}}

    def _guardar_stats(self):
        try:
            with open(self.archivo_record, 'w', encoding='utf-8') as f:
                json.dump(self.stats, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[RuletaRusa] Error guardando stats: {e}")

    def ejecutar(self, user, args):
        u = self.eco.get_user(user)
        partes = args.split()
        
        if partes and partes[0] == "info":
            s = self.stats
            return [f"🏆 \x0312Récord de Ruleta Rusa:\x0F {s['record_supervivencia']} disparos seguidos por \x02{s['campeon']}\x02."]

        if user.lower() not in self.stats["usuarios"]:
            self.stats["usuarios"][user.lower()] = {"streak": 0, "muertes": 0}

        user_stats = self.stats["usuarios"][user.lower()]
        
        # Probabilidad 1 de 6
        bala = random.randint(1, 6)
        
        if bala == 1:
            # ¡MUERTO!
            racha_final = user_stats["streak"]
            user_stats["streak"] = 0
            user_stats["muertes"] += 1
            
            # Penalización: Pierde 5.000€ y 2 tiradas. Van al BOTE.
            u["mano"]["euros"] = max(0, u["mano"]["euros"] - 5000)
            u["mano"]["tiradas"] = max(0, u["mano"]["tiradas"] - 2)
            
            self.eco.sumar_al_bote("euros", 5000)
            self.eco.sumar_al_bote("tiradas", 2)
            
            self._guardar_stats()
            self.eco._guardar_datos()
            return [f"💥 \x0304\x02¡BOOM!\x02\x0F El tambor giró y la bala atravesó la cabeza de \x02{user}\x02. Pierdes \x03045.000€\x0F y \x03122 tiradas\x0F (que van al bote). Racha cortada en \x02{racha_final}\x02."]
        else:
            # SOBREVIVE
            user_stats["streak"] += 1
            record_msg = ""
            if user_stats["streak"] > self.stats["record_supervivencia"]:
                self.stats["record_supervivencia"] = user_stats["streak"]
                self.stats["campeon"] = user
                record_msg = " \x0303¡NUEVO RÉCORD!\x0F"
            
            # Premio: Gana 500€
            recibe, emb, e_msg = self.eco.cobrar_embargo(user, 500)
            
            self._guardar_stats()
            self.eco._guardar_datos()
            return [f"🔫 \x0310\x02*click*\x02\x0F... \x02{user}\x02 aprieta el gatillo y respira aliviado. ¡Sobrevives! Ganas \x0312{self.eco.formatear_dinero(recibe)}€\x0F.{record_msg}{e_msg} Racha actual: \x02{user_stats['streak']}\x02."]
