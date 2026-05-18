import random

class CajaFuerte:
    def __init__(self, economia):
        self.eco = economia
        self.intentos = {} # {user_que_ataca: {target: count}}

    def _get_codigo(self, user):
        u = self.eco.get_user(user)
        if "caja_codigo" not in u:
            u["caja_codigo"] = f"{random.randint(1000, 9999)}"
            self.eco._guardar_datos()
        return u["caja_codigo"]

    def _reset_codigo(self, user):
        u = self.eco.get_user(user)
        u["caja_codigo"] = f"{random.randint(1000, 9999)}"
        self.eco._guardar_datos()

    def robar(self, user, args):
        partes = args.split()
        if len(partes) < 2:
            return ["Uso: !robar <Nick> <Código 4 dígitos> (Ej: !robar Pedro 1234)"]
        
        target = partes[0]
        intento = partes[1]
        
        if len(intento) != 4 or not intento.isdigit():
            return ["\x0304[Error]\x0F El código debe ser de 4 dígitos exactos (1000-9999)."]
            
        u_target = self.eco.get_user(target)
        if target.lower() not in self.eco.datos:
            return [f"\x0304[Error]\x0F {target} no esta registrado en el bot."]
            
        if target.lower() == user.lower():
            return ["\x0304[Error]\x0F ¿Intentas robarte a ti mismo? El bot te mira con cara rara."]

        # Lógica de Intentos
        if user not in self.intentos: self.intentos[user] = {}
        self.intentos[user][target] = self.intentos[user].get(target, 0) + 1
        
        count = self.intentos[user][target]
        codigo_real = self._get_codigo(target)
        
        if intento == codigo_real:
            # ¡ÉXITO! Saqueo de un compartimento al azar (Regla mIRC)
            del self.intentos[user][target]
            self._reset_codigo(target)
            
            suerte = random.randint(1, 15)
            if suerte == 10: 
                obj, label = "diamantes", "Diamantes"
            elif suerte in [5, 15]: 
                obj, label = "lingotes", "Lingotes de Oro"
            elif suerte == 1:
                obj, label = "esmeraldas", "Esmeraldas" # Añadido por mi como extra raro
            else: 
                obj, label = "euros", "Euros"
            
            cantidad_victima = u_target["mano"].get(obj, 0)
            botin = int(cantidad_victima * 0.25)
            
            u_target["mano"][obj] -= botin
            
            if obj == "euros":
                self.eco.cobrar_embargo(user, botin)
                msg_botin = f"\x0312{self.eco.formatear_dinero(botin)}€\x0F"
            else:
                u_ataca = self.eco.get_user(user)
                u_ataca["mano"][obj] += botin
                msg_botin = f"\x0312{botin}\x0F {label}"
            
            self.eco._guardar_datos()
            
            return [
                f"\x0304[Alarma]\x0F \x02¡¡ACERTASTE!!\x02\x0F \x02{user}\x02 ha abierto la caja fuerte de \x02{target}\x02.",
                f"\x0307[Oro]\x0F Ha robado de su interior un \x0225%\x02 de sus {label} ({msg_botin}).",
                f"\x0312[Candado]\x0F El usuario \x02{target}\x02 ha cambiado el código de seguridad de su caja fuerte."
            ]
        else:
            # FALLO - Dar pistas Mastermind
            pistas = []
            for i in range(4):
                digit = intento[i]
                if digit == codigo_real[i]:
                    pistas.append(f"\x0303{digit}\x0F") # Verde: Correcto
                elif digit in codigo_real:
                    pistas.append(f"\x0307{digit}\x0F") # Naranja: Existe pero mal sitio
                else:
                    pistas.append(f"\x0304{digit}\x0F") # Rojo: No existe
            
            msg_pistas = "".join(pistas)
            res = [f"\x0308[Ladron]\x0F \x02{user}\x02 está intentando robar la caja fuerte de \x02{target}\x02 con la combinación {msg_pistas}"]
            
            if count >= 5:
                del self.intentos[user][target]
                self._reset_codigo(target)
                res.append(f"\x0312[Candado]\x0F El usuario \x02{target}\x02 ha cambiado el código de seguridad de su caja fuerte.")
            
            return res
