import random
import time
import os
import json

class Robar:
    def __init__(self, economia):
        self.eco = economia
        # Guardamos los PINs de las cajas fuertes
        self.archivo_cajas = os.path.join(os.path.dirname(__file__), "..", "datos", "cajasfuertes.json")
        self.cajas = self._cargar_cajas()

    def _cargar_cajas(self):
        if os.path.exists(self.archivo_cajas):
            try:
                with open(self.archivo_cajas, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[Robar] Error cargando cajas: {e}")
        return {}

    def _guardar_cajas(self):
        try:
            with open(self.archivo_cajas, 'w', encoding='utf-8') as f:
                json.dump(self.cajas, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[Robar] Error guardando cajas: {e}")

    def get_caja(self, nick):
        nick = nick.lower()
        if nick not in self.cajas:
            # PIN aleatorio de 4 dígitos
            self.cajas[nick] = {"pin": f"{random.randint(0, 9999):04d}", "intentos": {}}
            self._guardar_cajas()
        return self.cajas[nick]

    def ejecutar(self, user, args):
        partes = args.split()
        if len(partes) < 2:
            return ["Uso: !robar <nick> <código de 4 dígitos>"]

        target = partes[0].lower()
        pin_intento = partes[1]
        
        if len(pin_intento) != 4 or not pin_intento.isdigit():
            return ["El código debe ser de 4 dígitos."]

        u = self.eco.get_user(user)
        t = self.eco.get_user(target)
        caja = self.get_caja(target)

        if user.lower() == target:
            return ["No puedes robarte a ti mismo... búscate un trabajo honrado."]

        if u["mano"]["tiradas"] < 1:
            return ["Necesitas al menos 1 tirada para intentar un robo."]

        u["mano"]["tiradas"] -= 1
        
        if pin_intento == caja["pin"]:
            # ¡EXITO! Robo del 25% del saldo del banco
            # MuLTiGaMe robaba del banco (habitualmente donde está el dinero gordo)
            botin_euros = int(t["banco"]["euros"] * 0.25)
            t["banco"]["euros"] -= botin_euros
            u["mano"]["euros"] += botin_euros
            
            # Cambiar el PIN después de un robo exitoso
            caja["pin"] = f"{random.randint(0, 9999):04d}"
            self._guardar_cajas()
            self.eco._guardar_datos()
            
            return [f"\x0307[Robo]\x0F \x0304\x02¡¡ACERTASTE!!\x0F \x02{user}\x02 ha abierto la caja fuerte de \x02{target}\x02 y ha robado \x0312{self.eco.formatear_dinero(botin_euros)}\x0F Euros (un 25% del banco)."]
        else:
            # Fallo, dar pistas (como el original)
            pista = []
            real_pin = caja["pin"]
            for i in range(4):
                if pin_intento[i] == real_pin[i]:
                    pista.append(f"\x0303{pin_intento[i]}\x0F")
                else:
                    pista.append("\x0314X\x0F")
            
            self.eco._guardar_datos()
            return [f"\x0304[Error]\x0F El código \x02{pin_intento}\x02 es incorrecto. Pista: [\x02{' '.join(pista)}\x02]. Te queda una tirada menos."]
