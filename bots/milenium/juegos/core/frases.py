import random
import os

class Frases:
    def __init__(self):
        self.base_dir = os.path.dirname(__file__)
        self.categorias = {
            "chiste": "chistes.txt",
            "piropo": "piropos.txt",
            "refran": "refranes.txt",
            "murphy": "murphy.txt"
        }
        self.datos = {}
        self._cargar_frases()

    def _cargar_frases(self):
        for cat, filename in self.categorias.items():
            path = os.path.join(self.base_dir, filename)
            if os.path.exists(path):
                try:
                    # Muchos archivos mIRC estan en latin-1/windows-1252
                    with open(path, 'r', encoding='latin-1') as f:
                        # Filtrar lineas vacias y quitar saltos de linea
                        self.datos[cat] = [line.strip() for line in f if line.strip()]
                except Exception:
                    self.datos[cat] = []
            else:
                self.datos[cat] = []

    def get_frase(self, categoria):
        if categoria in self.datos and self.datos[categoria]:
            return [random.choice(self.datos[categoria])]
        return [f"❌ No hay contenido cargado para la categoría: \x02{categoria}\x02."]

    def comando_chiste(self): return self.get_frase("chiste")
    def comando_piropo(self): return self.get_frase("piropo")
    def comando_refran(self): return self.get_frase("refran")
    def comando_murphy(self): return self.get_frase("murphy")
