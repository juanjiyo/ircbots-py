import json
import os
import time
import random
from datetime import datetime

class Quotes:
    def __init__(self):
        self.archivo_datos = os.path.join(os.path.dirname(__file__), "..", "datos", "quotes.json")
        self.quotes = self._cargar_datos()

    def _cargar_datos(self):
        if os.path.exists(self.archivo_datos):
            try:
                with open(self.archivo_datos, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[Quotes] Error cargando datos: {e}")
        return {} # {canal: [{"texto": "", "autor": "", "quien": "", "fecha": ""}]}

    def _guardar_datos(self):
        try:
            os.makedirs(os.path.dirname(self.archivo_datos), exist_ok=True)
            with open(self.archivo_datos, 'w', encoding='utf-8') as f:
                json.dump(self.quotes, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[Quotes] Error guardando datos: {e}")

    def add_quote(self, channel, user, texto):
        chan = channel.lower()
        if chan not in self.quotes: self.quotes[chan] = []
        
        nueva = {
            "texto": texto,
            "quien": user,
            "fecha": datetime.now().strftime("%d/%m/%Y"),
            "hora": datetime.now().strftime("%H:%M")
        }
        self.quotes[chan].append(nueva)
        num = len(self.quotes[chan])
        self._guardar_datos()
        return [f" \x0303Quote Numero:\x0F \x02{num}\x02 Añadida Exitosamente."]

    def del_quote(self, channel, user, num_str, es_admin=False):
        chan = channel.lower()
        if chan not in self.quotes or not self.quotes[chan]:
            return [" No hay Quotes en este canal."]
        
        try: idx = int(num_str) - 1
        except Exception: return ["Uso: !delquote <numero>"]
        
        if idx < 0 or idx >= len(self.quotes[chan]):
            return [" Numero de Quote invalido."]
            
        q = self.quotes[chan][idx]
        if q["quien"].lower() != user.lower() and not es_admin:
            return [f" Solo \x02{q['quien']}\x02 o un Admin puede borrar esta Quote."]
            
        self.quotes[chan].pop(idx)
        self._guardar_datos()
        return [f" Quote Numero \x02{idx+1}\x02 borrada con exito."]

    def get_quote(self, channel, num_str=None):
        chan = channel.lower()
        if chan not in self.quotes or not self.quotes[chan]:
            return [" No hay Quotes en este canal."]
            
        total = len(self.quotes[chan])
        
        if num_str:
            try: idx = int(num_str) - 1
            except Exception: return ["Uso: !quote <numero>"]
            if idx < 0 or idx >= total: return [" Numero de Quote invalido."]
        else:
            idx = random.randint(0, total - 1)
            
        q = self.quotes[chan][idx]
        return [f" \x0312Quote [\x02{idx+1}/{total}\x02]:\x0F {q['texto']} \x0314(por {q['quien']} el {q['fecha']})\x0F"]

    def buscar_quote(self, channel, query):
        chan = channel.lower()
        if chan not in self.quotes or not self.quotes[chan]:
            return [" No hay Quotes."]
            
        encontradas = []
        for i, q in enumerate(self.quotes[chan]):
            if query.lower() in q["texto"].lower():
                encontradas.append(str(i + 1))
        
        if not encontradas:
            return [f" No se encontraron quotes con: \x02{query}\x02"]
            
        return [f" \x02Busca:\x02 Las palabras '{query}' se encontraron en las Quotes: \x0303{', '.join(encontradas)}\x0F"]

    def info_quote(self, channel, num_str):
        chan = channel.lower()
        if chan not in self.quotes or not self.quotes[chan]: return [" No hay Quotes."]
        
        try: idx = int(num_str) - 1
        except Exception: return ["Uso: !quoteinfo <numero>"]
        
        if idx < 0 or idx >= len(self.quotes[chan]): return [" Numero invalido."]
        
        q = self.quotes[chan][idx]
        return [f" \x02Quote {idx+1}:\x02 Añadida por \x02{q['quien']}\x02 el dia \x02{q['fecha']}\x02 a las \x02{q['hora']}\x02."]
