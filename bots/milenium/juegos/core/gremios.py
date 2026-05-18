import random
import os
import json

class Gremios:
    def __init__(self, economia):
        self.eco = economia
        self.archivo_datos = os.path.join(os.path.dirname(__file__), "..", "datos", "gremios.json")
        self.gremios = self._cargar_datos()
        
        # Estructura base de gremios clásicos mIRC + Nuevos
        self.LISTA_GREMIOS = {
            "Red Lizard": {"tipo": "Legal", "maestro": "Nadie"},
            "Tartaros": {"tipo": "Oscuro", "maestro": "Nadie"},
            "Crime Sorciere": {"tipo": "Oscuro", "maestro": "Nadie"},
            "Phantom Lord": {"tipo": "Oscuro", "maestro": "Nadie"},
            "Blue Pegasus": {"tipo": "Legitimo", "maestro": "Nadie"},
            "Olympos": {"tipo": "Divino", "maestro": "Nadie"},
            "Fairy Tail": {"tipo": "Heroico", "maestro": "Nadie"},
            "Sabertooth": {"tipo": "Competitivo", "maestro": "Nadie"},
            "Grimoire Heart": {"tipo": "Oscuro", "maestro": "Nadie"},
            "Lamia Scale": {"tipo": "Legal", "maestro": "Nadie"}
        }

    def _cargar_datos(self):
        if os.path.exists(self.archivo_datos):
            try:
                with open(self.archivo_datos, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[Gremios] Error cargando datos: {e}")
        return {} # {gremio_name: [miembros]}

    def _guardar_datos(self):
        try:
            os.makedirs(os.path.dirname(self.archivo_datos), exist_ok=True)
            with open(self.archivo_datos, 'w', encoding='utf-8') as f:
                json.dump(self.gremios, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[Gremios] Error guardando datos: {e}")

    def comando_gremios(self):
        res = ["\x0307[Pergamino]\x0F \x02Lista de Gremios:\x02"]
        for g, info in self.LISTA_GREMIOS.items():
            maestro = info["maestro"]
            res.append(f"\x0312[-]\x0F \x02{g}\x02 ({info['tipo']}) - Maestro: \x02{maestro}\x02")
        return res

    def comando_gremio_info(self, name):
        g_name = self._find_gremio(name)
        if not g_name: return ["\x0304[Error]\x0F Gremio no encontrado."]
        
        info = self.LISTA_GREMIOS[g_name]
        miembros = self.gremios.get(g_name, [])
        return [
            f"\x0307[Gremio]\x0F \x0312Gremio:\x03 \x02{g_name}\x02 ({info['tipo']})",
            f"\x0303[Jefe]\x0F Maestro: \x02{info['maestro']}\x02 | Miembros: \x02{len(miembros)}\x02"
        ]

    def comando_entrar(self, user, gremio_name, gestor_p):
        g_name = self._find_gremio(gremio_name)
        if not g_name: return ["\x0304[Error]\x0F Ese gremio no existe."]
        
        # En mIRC se requiere autorización
        if not gestor_p.es_oper("", user):
             return [f"\x0304[Error]\x0F {user}, necesitas autorización de un Oper para entrar en un gremio."]

        return self._add_to_guild(user, g_name)

    def comando_add_miembro(self, executor, args, gestor_p):
        """Comando administrativo para añadir a X a un gremio manual"""
        if not gestor_p.es_root("", executor):
            return ["\x0304[Error]\x0F Acceso denegado. Solo Roots pueden gestionar gremios."]
            
        partes = args.split()
        if len(partes) < 2: return ["Uso: !miembro <Gremio> <Nick>"]
        
        gremio_name = partes[0]
        target = partes[1]
        
        g_name = self._find_gremio(gremio_name)
        if not g_name: return [f"\x0304[Error]\x0F El gremio \x02{gremio_name}\x02 no existe."]
        
        return self._add_to_guild(target, g_name)

    def _add_to_guild(self, user, g_name):
        # Eliminar de gremio anterior
        for g in list(self.gremios.keys()):
            self.gremios[g] = [m for m in self.gremios[g] if m.lower() != user.lower()]
        
        if g_name not in self.gremios: self.gremios[g_name] = []
        self.gremios[g_name].append(user)
        self._guardar_datos()
        return [f"\x0303[OK]\x0F \x02{user}\x02 ha sido asignado al gremio \x0312{g_name}\x0F."]

    def _find_gremio(self, name):
        for g in self.LISTA_GREMIOS:
            if name.lower() in g.lower(): return g
        return None
