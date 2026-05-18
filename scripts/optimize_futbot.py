#!/usr/bin/env python3
"""Aplica optimizaciones al scraper de futbot.py en la VPS."""
import paramiko
import json
import os

def main():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')
    with open(config_path) as f:
        cfg = json.load(f)['vps']

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    key = paramiko.Ed25519Key.from_private_key_file(cfg['key_path'])
    ssh.connect(cfg['host'], username=cfg['user'], pkey=key, timeout=10)

    # Leer el archivo actual
    sftp = ssh.open_sftp()
    with sftp.file("/home/irc/futbot/futbot.py", "r") as f:
        content = f.read().decode('utf-8')

    original = content  # backup in memory

    # ====================================================================
    # CAMBIO 1: html.parser → lxml (6 ocurrencias)
    # ====================================================================
    count1 = content.count("'html.parser'")
    content = content.replace("'html.parser'", "'lxml'")
    print(f"[1] html.parser -> lxml: {count1} reemplazos")

    # ====================================================================
    # CAMBIO 2: Connection pooling + retries en la sesión HTTP
    # ====================================================================
    # Buscar la línea donde se crea la sesión y añadir el adapter
    old_session = """        self.session = requests.Session()
        self.session.headers.update({'User-Agent': Config.USER_AGENT})"""

    new_session = """        self.session = requests.Session()
        self.session.headers.update({'User-Agent': Config.USER_AGENT})
        # Connection pooling: reutilizar conexiones TCP
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        _retry = Retry(total=2, backoff_factor=0.5, status_forcelist=[500, 502, 503])
        _adapter = HTTPAdapter(pool_connections=2, pool_maxsize=10, max_retries=_retry)
        self.session.mount('https://', _adapter)
        self.session.mount('http://', _adapter)"""

    if old_session in content:
        content = content.replace(old_session, new_session)
        print("[2] Connection pooling + retries: OK")
    else:
        print("[2] Connection pooling: NO ENCONTRADO (buscar manualmente)")

    # ====================================================================
    # CAMBIO 3: Reutilizar soups entre _buscar_partidos y _anunciar_partidos_proximos
    # ====================================================================
    # 3a. Hacer que _buscar_partidos retorne los soups
    # Buscar el final de _buscar_partidos donde tiene el return implícito
    old_buscar_final = """        logging.info(f"🔍 Scraper: {partidos_encontrados} partidos encontrados, {partidos_en_vivo} en vivo")"""
    
    new_buscar_final = """        logging.info(f"🔍 Scraper: {partidos_encontrados} partidos encontrados, {partidos_en_vivo} en vivo")
        return livescore_soups"""

    if old_buscar_final in content:
        content = content.replace(old_buscar_final, new_buscar_final, 1)
        print("[3a] _buscar_partidos return soups: OK")
    else:
        print("[3a] _buscar_partidos return: NO ENCONTRADO")

    # 3b. Almacenar soups al inicio de _buscar_partidos
    old_buscar_inicio = """        partidos_encontrados = 0
        partidos_en_vivo = 0"""

    new_buscar_inicio = """        partidos_encontrados = 0
        partidos_en_vivo = 0
        livescore_soups = {}  # {url: soup} para reutilizar en _anunciar_partidos_proximos"""

    if old_buscar_inicio in content:
        content = content.replace(old_buscar_inicio, new_buscar_inicio, 1)
        print("[3b] livescore_soups init: OK")
    else:
        print("[3b] livescore_soups init: NO ENCONTRADO")

    # 3c. Guardar el soup después de parsearlo en _buscar_partidos
    old_soup_buscar = """                soup = BeautifulSoup(response.content, 'lxml')
                
                # Buscar ligas (div con class="liga")"""

    new_soup_buscar = """                soup = BeautifulSoup(response.content, 'lxml')
                livescore_soups[url] = soup  # guardar para reutilizar
                
                # Buscar ligas (div con class="liga")"""

    if old_soup_buscar in content:
        content = content.replace(old_soup_buscar, new_soup_buscar, 1)
        print("[3c] Guardar soup en _buscar_partidos: OK")
    else:
        print("[3c] Guardar soup: NO ENCONTRADO")

    # 3d. En _run_scraper, pasar soups a _anunciar_partidos_proximos
    old_run = """                self._buscar_partidos()
                self._anunciar_partidos_proximos()"""

    new_run = """                _soups = self._buscar_partidos() or {}
                self._anunciar_partidos_proximos(_soups)"""

    if old_run in content:
        content = content.replace(old_run, new_run, 1)
        print("[3d] _run_scraper pasar soups: OK")
    else:
        print("[3d] _run_scraper: NO ENCONTRADO")

    # 3e. Modificar firma de _anunciar_partidos_proximos para aceptar soups
    old_anunciar_firma = """    def _anunciar_partidos_proximos(self):"""

    new_anunciar_firma = """    def _anunciar_partidos_proximos(self, livescore_soups=None):"""

    if old_anunciar_firma in content:
        content = content.replace(old_anunciar_firma, new_anunciar_firma, 1)
        print("[3e] Firma _anunciar_partidos_proximos: OK")
    else:
        print("[3e] Firma: NO ENCONTRADO")

    # 3f. Dentro de _anunciar_partidos_proximos, reutilizar soup si está disponible
    # Buscar donde descarga las URLs del livescore
    old_anunciar_fetch = """            for url in Config.SCRAPER_LIVESCORE_URLS:
                try:
                    response = self.session.get(url, timeout=10)
                    response.encoding = 'utf-8'
                    soup = BeautifulSoup(response.content, 'lxml')
                except Exception as e:
                    logging.error(f"Error descargando {url}: {e}")
                    continue"""

    new_anunciar_fetch = """            if livescore_soups is None:
                livescore_soups = {}
            for url in Config.SCRAPER_LIVESCORE_URLS:
                try:
                    if url in livescore_soups:
                        soup = livescore_soups[url]
                    else:
                        response = self.session.get(url, timeout=10)
                        response.encoding = 'utf-8'
                        soup = BeautifulSoup(response.content, 'lxml')
                except Exception as e:
                    logging.error(f"Error descargando {url}: {e}")
                    continue"""

    if old_anunciar_fetch in content:
        content = content.replace(old_anunciar_fetch, new_anunciar_fetch, 1)
        print("[3f] Reutilizar soup en _anunciar: OK")
    else:
        # Podría ser que ya se cambió html.parser → lxml antes
        # Intentar con la versión original
        old_anunciar_fetch2 = old_anunciar_fetch.replace("'lxml'", "'html.parser'")
        if old_anunciar_fetch2 in content:
            content = content.replace(old_anunciar_fetch2, new_anunciar_fetch, 1)
            print("[3f] Reutilizar soup en _anunciar (variant): OK")
        else:
            print("[3f] Reutilizar soup: NO ENCONTRADO")

    # ====================================================================
    # Verificar que no se rompió nada
    # ====================================================================
    if content == original:
        print("\n⚠️ NO SE HICIERON CAMBIOS")
        ssh.close()
        return

    # Escribir el archivo modificado
    with sftp.file("/home/irc/futbot/futbot.py", "w") as f:
        f.write(content)
    sftp.close()

    # Verificar sintaxis
    stdin, stdout, stderr = ssh.exec_command("python3 -c \"import py_compile; py_compile.compile('/home/irc/futbot/futbot.py', doraise=True)\" 2>&1")
    result = stdout.read().decode()
    if result.strip():
        print(f"\n❌ ERROR DE SINTAXIS:\n{result}")
    else:
        print("\n✅ Sintaxis OK — futbot.py modificado correctamente")

    # Contar líneas finales
    stdin, stdout, stderr = ssh.exec_command("wc -l /home/irc/futbot/futbot.py")
    print(f"Líneas: {stdout.read().decode().strip()}")

    ssh.close()

if __name__ == "__main__":
    main()
