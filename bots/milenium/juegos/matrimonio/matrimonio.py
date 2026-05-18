import random
import string
import time
import json
import os

class Matrimonio:
    def __init__(self):
        self.cooldowns = {}
        self.cooldown_time = 10
        self.propuestas_pendientes = {} # clave: codigo, valor: {'de': nick1, 'para': nick2, 'tiempo': timestamp}
        self.divorcios_pendientes = {} # clave: codigo, valor: {'de': nick, 'para': target, 'tiempo': timestamp}
        # Ruta persistente en la carpeta datos/ del bot
        self.archivo_datos = os.path.join(os.path.dirname(__file__), "..", "datos", "matrimonios.json")
        self.matrimonios = self._cargar_matrimonios()
        self.tiempo_expiracion = 60 # 60 segundos para responder (1 minuto)

    def _cargar_matrimonios(self):
        if os.path.exists(self.archivo_datos):
            try:
                with open(self.archivo_datos, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[Matrimonio] Error cargando JSON: {e}")
        return {}

    def _guardar_matrimonios(self):
        try:
            # Asegurar que el directorio existe
            os.makedirs(os.path.dirname(self.archivo_datos), exist_ok=True)
            with open(self.archivo_datos, 'w', encoding='utf-8') as f:
                json.dump(self.matrimonios, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[Matrimonio] Error guardando JSON: {e}")

    def check_cooldown(self, user):
        current_time = time.time()
        if user in self.cooldowns:
            if current_time - self.cooldowns[user] < self.cooldown_time:
                return False
        self.cooldowns[user] = current_time
        return True

    def generar_codigo(self):
        # Genera un código aleatorio tipo "-1rvQPzeOL"
        caracteres = string.ascii_letters + string.digits
        codigo = '-' + ''.join(random.choice(caracteres) for _ in range(9))
        return codigo

    def _limpiar_expirados(self):
        """Elimina las propuestas y divorcios que han superado el tiempo de expiración."""
        current_time = time.time()
        self.propuestas_pendientes = {k: v for k, v in self.propuestas_pendientes.items() if current_time - v['tiempo'] <= self.tiempo_expiracion}
        self.divorcios_pendientes = {k: v for k, v in self.divorcios_pendientes.items() if current_time - v['tiempo'] <= self.tiempo_expiracion}

    def comando_casarme(self, user, args):
        if not self.check_cooldown(user):
            return []

        partes = args.split()
        if len(partes) < 1:
            return ["Sintaxis incorrecta: !casarme Nombre"]

        # Si el usuario pone "!casarme MiNick SuNick", cogemos el último nick como target.
        # Si solo pone "!casarme SuNick", cogemos el primero.
        if len(partes) >= 2 and partes[0].lower() == user.lower():
            target = partes[1]
        else:
            target = partes[0]
        
        if target.lower() == user.lower():
            return ["\x0304\x02¡Aquí el único ser con suficiente ego para casarse con uno mismo soy YO!\x02\x0F"]
            
        # Comprobar si ya están casados (y no divorciados)
        if user.lower() in self.matrimonios and not self.matrimonios[user.lower()].startswith("!DIVORCIADO:"):
            return [f"Ya estás casad@ con \x02{self.matrimonios[user.lower()]}\x02. ¡No seas infiel!"]
        
        if target.lower() in self.matrimonios and not self.matrimonios[target.lower()].startswith("!DIVORCIADO:"):
            return [f"\x02{target}\x02 ya está casad@ con \x02{self.matrimonios[target.lower()]}\x02."]

        self._limpiar_expirados()
        codigo = self.generar_codigo()
        self.propuestas_pendientes[codigo] = {
            'de': user,
            'para': target,
            'tiempo': time.time()
        }

        respuestas = [
            f"\x02{target}\x02 ¿Quieres recibir a \x02{user}\x02, como espos@ y prometerle serle fiel, sin chatear a escondidas, en las noches de soledad o canales.. \"ejem\".. en la prosperidad y adversidad, en la salud y en la enfermedad y de ese modo amarl@ y respetarl@ todos los días hasta que se os expiren los nicks?",
            f"!Si.quiero {codigo} o !No.quiero {codigo}"
        ]
        return respuestas

    def comando_siquiero(self, user, args):
        partes = args.split()
        if len(partes) < 1:
            return ["Sintaxis incorrecta: !Si.quiero CODIGO"]
        
        codigo = partes[0]
        self._limpiar_expirados()
        
        if codigo in self.propuestas_pendientes:
            propuesta = self.propuestas_pendientes[codigo]
            if propuesta['para'].lower() == user.lower():
                # Aceptó
                del self.propuestas_pendientes[codigo]
                
                # Guardar matrimonio (bidireccional)
                de_nick = propuesta['de']
                para_nick = user
                
                self.matrimonios[de_nick.lower()] = para_nick
                self.matrimonios[para_nick.lower()] = de_nick
                self._guardar_matrimonios()
                
                return [f"¡Felicidades! \x02{de_nick}\x02 y \x02{para_nick}\x02 ahora están casados virtualmente. 🎉💍"]
            else:
                return ["Este código es erróneo, ha expirado o no te pidieron matrimonio."]
        return ["Este código es erróneo, ha expirado o no te pidieron matrimonio."]

    def comando_noquiero(self, user, args):
        partes = args.split()
        if len(partes) < 1:
            return ["Sintaxis incorrecta: !No.quiero CODIGO"]
        
        codigo = partes[0]
        self._limpiar_expirados()

        if codigo in self.propuestas_pendientes:
            propuesta = self.propuestas_pendientes[codigo]
            if propuesta['para'].lower() == user.lower():
                # Rechazó
                del self.propuestas_pendientes[codigo]
                return [f"\x02{user}\x02 ha rechazado la propuesta de \x02{propuesta['de']}\x02. 💔 Ouch, directo en la friendzone."]
            else:
                return ["Este código es erróneo, ha expirado o no te pidieron matrimonio."]
        return ["Este código es erróneo, ha expirado o no te pidieron matrimonio."]
    
    def comando_divorciarme(self, user, args):
        if not self.check_cooldown(user):
            return []

        if user.lower() not in self.matrimonios or self.matrimonios[user.lower()].startswith("!DIVORCIADO:"):
            return ["No estás casad@ con nadie."]

        # El target es automáticamente la pareja actual
        target = self.matrimonios[user.lower()]

        self._limpiar_expirados()
        codigo = self.generar_codigo()
        self.divorcios_pendientes[codigo] = {
            'de': user,
            'para': target,
            'tiempo': time.time()
        }

        respuestas = [
            f"\x02{user}\x02 ha iniciado los trámites de divorcio con \x02{target}\x02. ¿Estás seguro de querer romper el vínculo para siempre?",
            f"Para firmar los papeles definitivamente, escribe: !Si.divorcio {codigo}"
        ]
        return respuestas

    def comando_sidivorcio(self, user, args):
        partes = args.split()
        if len(partes) < 1:
            return ["Sintaxis incorrecta: !Si.divorcio CODIGO"]
        
        codigo = partes[0]
        self._limpiar_expirados()

        if codigo in self.divorcios_pendientes:
            divorcio = self.divorcios_pendientes[codigo]
            # Validamos que el que confirme sea el mismo que lo pidió
            if divorcio['de'].lower() == user.lower():
                target = divorcio['para']
                del self.divorcios_pendientes[codigo]
                
                # Marcar como divorciados en lugar de borrarlos
                self.matrimonios[user.lower()] = f"!DIVORCIADO:{target}"
                self.matrimonios[target.lower()] = f"!DIVORCIADO:{user}"
                
                self._guardar_matrimonios()
                
                return [f"\x02{user}\x02 ha firmado los papeles de divorcio con \x02{target}\x02. ¡Se acabó el amor! 📄💔"]
            else:
                return ["Este código de divorcio es erróneo, ha expirado o no es tuyo."]
        return ["Este código de divorcio es erróneo, ha expirado o no es tuyo."]

    def comando_estadocivil(self, user, args):
        partes = args.split()
        target = partes[0] if len(partes) > 0 else user
        
        if target.lower() in self.matrimonios:
            pareja = self.matrimonios[target.lower()]
            if pareja.startswith("!DIVORCIADO:"):
                ex_pareja = pareja.split(":", 1)[1]
                return [f"El estado civil de \x02{target}\x02 actualmente es: \x02Divorciad@ de {ex_pareja}\x02. 💔 (Cuidado con este/a)"]
            else:
                return [f"El estado civil de \x02{target}\x02 actualmente es: \x02Casad@ con {pareja}\x02. ❤️"]
        else:
            return [f"El estado civil de \x02{target}\x02 actualmente es: \x02Soltero/a\x02."]
