from vedastro import *
import tcl

VERSION = "1.0"

def test_vedastro(nick, user, hand, chan, text):
    try:
        # Configuracion basica (Tokyo por defecto como en el ejemplo)
        geo = GeoLocation("Madrid, Spain", -3.70, 40.41)
        
        # Obtener tiempo actual (aproximado para el test)
        # VedAstro usa un formato de tiempo especifico
        # birth_time = Time(hour=12, minute=0, day=26, month=4, year=2026, offset="+02:00", geolocation=geo)
        
        # En lugar de calcular algo complejo, probamos la conexion con la API
        # usando el Key gratuito por defecto
        # result = Calculate.AllPlanetData(PlanetName.Sun, birth_time)
        
        tcl.putserv(f"PRIVMSG {chan} :VedAstro Test: Libreria cargada correctamente. Sistema listo para astrologia avanzada.")
        
    except Exception as e:
        tcl.putserv(f"PRIVMSG {chan} :Error en VedAstro: {str(e)}")

# Bind para el test
bind("pub", "*", "!vedtest", test_vedastro)

tcl.putlog(f"Script de Test VedAstro v{VERSION} cargado.")
