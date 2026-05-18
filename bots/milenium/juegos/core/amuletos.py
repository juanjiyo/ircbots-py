import random

class Amuletos:
    def __init__(self, economia):
        self.eco = economia
        # Tipo: (Nombre, Multiplicador, Precio_Objeto, Cantidad_Objeto)
        self.TIPOS = {
            "x2": ("Multiplicador x2", 2, "lingotes", 2),
            "x3": ("Multiplicador x3", 3, "lingotes", 3),
            "x5": ("Multiplicador x5", 5, "lingotes", 5),
            "x10": ("Multiplicador x10", 10, "diamantes", 2),
            "reduccion": ("Protección de Pérdidas", 1, "lingotes", 3),
            "maldicion": ("Protección de Maldición", 1, "diamantes", 1)
        }

    def comando_amuleto(self, user, args):
        partes = args.split()
        if not partes:
            return ["Uso: !amuleto <info/comprar/borrar/puesto>"]
        
        sub = partes[0].lower()
        u = self.eco.get_user(user)
        
        if sub == "info":
            if len(partes) < 2: return ["Uso: !amuleto info <x2/x3/x5/x10/Reduccion/Maldicion>"]
            tipo = partes[1].lower()
            if tipo not in self.TIPOS: return ["Amuleto no válido."]
            nombre, mult, obj, cant = self.TIPOS[tipo]
            if "Multiplicador" in nombre:
                return [f"\x0303[Hecho]\x0F El amuleto \x02{tipo}\x02 multiplica por {mult} la cantidad recibida en la \x02!ruleta.suerte\x02. Precio: {cant} {obj.capitalize()}."]
            elif tipo == "reduccion":
                return [f"\x0303[Escudo]\x0F El amuleto \x02reduccion\x02 te salva de las pérdidas en la \x02!ruleta.suerte\x02. Precio: {cant} {obj.capitalize()}."]
            else:
                return [f"\x0305[Amuleto]\x0F El amuleto \x02maldicion\x02 te salva de la Maldición del Botijo. Precio: {cant} {obj.capitalize()}."]

        elif sub == "comprar":
            if len(partes) < 2: return ["Uso: !amuleto comprar <tipo>"]
            tipo = partes[1].lower()
            if tipo not in self.TIPOS: return ["Amuleto no válido."]
            
            if u.get("amuleto"):
                return [f"\x0304[Error]\x0F Ya tienes un amuleto (\x02{u['amuleto']}\x02) puesto. Solo puedes llevar uno. Usa \x02!amuleto borrar\x02 primero."]
            
            nombre, mult, obj, cant = self.TIPOS[tipo]
            if u["mano"][obj] < cant:
                return [f"\x0304[Error]\x0F No tienes suficientes {obj.capitalize()} para comprar este amuleto."]
            
            # Pagar amuleto
            u["mano"][obj] -= cant
            # 25% de que sea FALSO (Regla original mIRC)
            es_falso = (random.randint(1, 4) == 1)
            u["amuleto"] = tipo
            u["amuleto_falso"] = es_falso
            
            self.eco._guardar_datos()
            return [f"\x0303[Hecho]\x0F ¡Estupendo! \x02{user}\x02 has comprado un amuleto \x02{tipo}\x02 con éxito."]

        elif sub == "borrar":
            if not u.get("amuleto"): return ["No tienes ningún amuleto puesto."]
            tipo_borrado = u["amuleto"]
            u["amuleto"] = None
            u["amuleto_falso"] = False
            self.eco._guardar_datos()
            return [f"\x0304[Basura]\x0F Has eliminado tu amuleto \x02{tipo_borrado}\x02. Ya puedes comprar otro."]

        elif sub == "puesto":
            if not u.get("amuleto"): return ["No tienes ningún amuleto activo."]
            return [f"\x0305[Amuleto]\x0F Actualmente llevas puesto el amuleto: \x02{u['amuleto']}\x02."]
            
        return ["Opción no reconocida."]
