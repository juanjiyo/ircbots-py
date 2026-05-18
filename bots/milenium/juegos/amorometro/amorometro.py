import random
import time
import os
import json

class Amorometro:
    def __init__(self, admins=None):
        self.cooldowns = {}
        self.cooldown_time = 10
        self.admins = [a.lower() for a in admins] if admins else []
        self.archivo_datos = os.path.join(os.path.dirname(__file__), "..", "datos", "amorometro.json")
        self.resultados = self._cargar_resultados()

    def _cargar_resultados(self):
        if os.path.exists(self.archivo_datos):
            try:
                with open(self.archivo_datos, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[Amorometro] Error cargando JSON: {e}")
        return {}

    def _guardar_resultados(self):
        try:
            os.makedirs(os.path.dirname(self.archivo_datos), exist_ok=True)
            with open(self.archivo_datos, 'w', encoding='utf-8') as f:
                json.dump(self.resultados, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[Amorometro] Error guardando JSON: {e}")

    def check_cooldown(self, user):
        if user.lower() in self.admins:
            return True
        current_time = time.time()
        if user in self.cooldowns:
            if current_time - self.cooldowns[user] < self.cooldown_time:
                return False
        self.cooldowns[user] = current_time
        return True

    def generar_barra(self, porcentaje, color_code, texto_porc=""):
        # Estilo Win-Stats (porcentaje DENTRO de la barra)
        total_bloques = 25
        bloques_llenos = int(porcentaje / (100 / total_bloques))
        if bloques_llenos == 0 and porcentaje > 0:
            bloques_llenos = 1
        bloques_vacios = total_bloques - bloques_llenos
        
        color_fmt = f"{color_code},{color_code}"
        negro_fmt = "01,01"
        
        if texto_porc:
            # Incrustar texto dentro de la barra siempre
            if bloques_llenos < 2:
                antes = 0
                despues = 0
            else:
                antes = (bloques_llenos - 1) // 2
                despues = bloques_llenos - antes - 1
            
            barra = "".join([f"\x03{color_fmt} " for _ in range(antes)])
            barra += f"\x0301,{color_code}{texto_porc}\x0F"
            barra += "".join([f"\x03{color_fmt} " for _ in range(max(0, despues))])
            barra += "".join([f"\x03{negro_fmt} " for _ in range(bloques_vacios)])
            return barra + "\x0F"
        
        # Barra llena: Repetir \x03COLOR[espacio] evita colapso
        barra = "".join([f"\x03{color_fmt} " for _ in range(bloques_llenos)])
        # Barra vacía: Color negro (01)
        barra += "".join([f"\x03{negro_fmt} " for _ in range(bloques_vacios)])
        return barra + "\x0F"

    def ejecutar(self, user, args):
        if not self.check_cooldown(user):
            return []

        partes = args.split()
        if len(partes) < 2:
            return ["\x0304Sintaxis incorrecta:\x0F !amorometro Nombre1 Nombre2"]

        nick1 = partes[0]
        nick2 = partes[1]

        # Generar clave única para la pareja (orden alfabético para que X Y == Y X)
        pair_key = "-".join(sorted([nick1.lower(), nick2.lower()]))

        if pair_key in self.resultados:
            stats = self.resultados[pair_key]
            amor = stats['amor']
            amistad = stats['amistad']
            trabajo = stats['trabajo']
            confianza = stats['confianza']
            estabilidad = stats['estabilidad']
            # Añadidas a posteriori, usamos get con fallback
            pasion = stats.get('pasion', random.randint(0, 100))
            locura = stats.get('locura', random.randint(0, 100))
            celos = stats.get('celos', random.randint(0, 100))
            toxicidad = stats.get('toxicidad', random.randint(0, 100))
            
            # Si no existían, las guardamos para el futuro
            if 'pasion' not in stats or 'celos' not in stats:
                stats['pasion'] = pasion
                stats['locura'] = locura
                stats['celos'] = celos
                stats['toxicidad'] = toxicidad
                self._guardar_resultados()
        else:
            # Generar porcentajes si no existen
            amor = random.randint(0, 100)
            amistad = random.randint(0, 100)
            trabajo = random.randint(0, 100)
            confianza = random.randint(0, 100)
            estabilidad = random.randint(0, 100)
            pasion = random.randint(0, 100)
            locura = random.randint(0, 100)
            celos = random.randint(0, 100)
            toxicidad = random.randint(0, 100)
            
            # Guardar para futuras consultas
            self.resultados[pair_key] = {
                'amor': amor,
                'amistad': amistad,
                'trabajo': trabajo,
                'confianza': confianza,
                'estabilidad': estabilidad,
                'pasion': pasion,
                'locura': locura,
                'celos': celos,
                'toxicidad': toxicidad
            }
            self._guardar_resultados()

        # Generar veredicto cómico
        if toxicidad > 85:
            veredicto = "\x0304[Veredicto]\x0F \x02Relación más tóxica que Chernóbil. ¡Huid el uno del otro! \x02"
        elif celos > 85:
            veredicto = "\x0307[Veredicto]\x0F \x02Niveles de celos críticos. Esto acaba en el Diario de Patricia. \x02"
        elif locura > 85:
            veredicto = "\x0306[Veredicto]\x0F \x02Terminaréis los dos en el manicomio... pero juntos. \x02"
        elif amor > 90 and pasion > 80:
            veredicto = "\x0313[Veredicto]\x0F \x02¡Amor verdadero! Id buscando fecha para la boda. \x02"
        elif amistad > 90 and amor < 30:
            veredicto = "\x0312[Veredicto]\x0F \x02Friendzone nivel Dios. De ahí no salís ni con pala. \x02"
        elif estabilidad < 20:
            veredicto = "\x0305[Veredicto]\x0F \x02Montaña rusa emocional. Preparad los cascos para el impacto. \x02"
        elif (amor + confianza) / 2 > 65:
            veredicto = "\x0303[Veredicto]\x0F \x02Hacen muy buena pareja, aquí hay futuro. \x02"
        else:
            veredicto = "\x0314[Veredicto]\x0F \x02Mejor que os dediquéis al parchís, lo vuestro no tiene arreglo. \x02"

        # Win-Stats Style:
        # 1. Labels exactos de la captura 1.
        # 2. Alineación de las barras (usamos padding de espacios).
        # 3. Colores: Amor(04), Amistad(12), Trabajo(07), Confianza(03), Estabilidad(10)
        
        # El label más largo es "Estabilidad:" (12 chars). 
        
        respuestas = [
            f"El amorómetro para \x02{nick1}\x02 y \x02{nick2}\x02 :",
            f"Amor :      {self.generar_barra(amor, '04', f'{amor}%')}",
            f"Amistad:    {self.generar_barra(amistad, '12', f'{amistad}%')}",
            f"Trabajo:    {self.generar_barra(trabajo, '07', f'{trabajo}%')}",
            f"Confianza:  {self.generar_barra(confianza, '03', f'{confianza}%')}",
            f"Estabilidad:{self.generar_barra(estabilidad, '10', f'{estabilidad}%')}",
            f"Pasión:     {self.generar_barra(pasion, '13', f'{pasion}%')}",
            f"Locura:     {self.generar_barra(locura, '06', f'{locura}%')}",
            f"Celos:      {self.generar_barra(celos, '08', f'{celos}%')}",
            f"Toxicidad:  {self.generar_barra(toxicidad, '05', f'{toxicidad}%')}",
            veredicto
        ]
        
        return respuestas
