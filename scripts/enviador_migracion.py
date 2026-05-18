#!/usr/bin/env python3
"""
Enviador de Migración — Empaqueta y envía directorios entre nodos via vps_bridge.

Empaqueta un directorio local en un .tar.gz temporal y lo sube al nodo destino
usando vps_bridge.py (SFTP). Luego envía un comando de desempaquetado remoto.

Uso:
  python enviador_migracion.py <nodo_destino> <carpeta_local> <ruta_destino>

Ejemplos:
  python enviador_migracion.py pcb ./bots/milenium /home/juanjo/ircbots_backup/bots/milenium
  python enviador_migracion.py panel ./scripts /home/irc/ircbots/scripts
"""

import os
import sys
import subprocess
import tarfile
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
BRIDGE     = SCRIPT_DIR / "vps_bridge.py"


def empaquetar(carpeta: str) -> str:
    """Empaqueta una carpeta en un .tar.gz temporal. Devuelve la ruta del archivo."""
    carpeta = Path(carpeta).resolve()
    if not carpeta.is_dir():
        print(f"❌ La carpeta '{carpeta}' no existe.")
        sys.exit(1)

    tmp = tempfile.mktemp(suffix=".tar.gz", prefix="migracion_")
    print(f"📦 Empaquetando {carpeta.name}...")
    with tarfile.open(tmp, "w:gz") as tar:
        tar.add(str(carpeta), arcname=carpeta.name)
    size_mb = os.path.getsize(tmp) / (1024 * 1024)
    print(f"   ✅ Paquete: {tmp} ({size_mb:.1f} MB)")
    return tmp


def subir(nodo: str, archivo_local: str, ruta_remota: str) -> bool:
    """Sube un archivo al nodo destino via vps_bridge."""
    archivo_remoto = f"{ruta_remota}/{Path(archivo_local).name}"
    cmd = [sys.executable, str(BRIDGE), nodo, "upload", archivo_local, archivo_remoto]
    print(f"📤 Subiendo a {nodo}:{archivo_remoto}...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"   ✅ Subida completada.")
        return True
    else:
        print(f"   ❌ Error: {result.stderr or result.stdout}")
        return False


def desempaquetar_remoto(nodo: str, ruta_remota: str, nombre_archivo: str) -> bool:
    """Ejecuta tar en el nodo remoto para desempaquetar."""
    cmd_remoto = f"cd {ruta_remota} && tar xzf {nombre_archivo} --strip-components=1 && rm -f {nombre_archivo}"
    cmd = [sys.executable, str(BRIDGE), nodo, cmd_remoto]
    print(f"📂 Desempaquetando en {nodo}:{ruta_remota}...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if "error" not in result.stdout.lower():
        print(f"   ✅ Desempaquetado y limpieza completados.")
        return True
    else:
        print(f"   ⚠️  Revisar salida: {result.stdout}")
        return False


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)

    nodo         = sys.argv[1]
    carpeta      = sys.argv[2]
    ruta_destino = sys.argv[3]

    # 1. Empaquetar
    archivo = empaquetar(carpeta)

    try:
        # 2. Subir
        if not subir(nodo, archivo, ruta_destino):
            sys.exit(1)

        # 3. Desempaquetar en remoto
        nombre = Path(archivo).name
        desempaquetar_remoto(nodo, ruta_destino, nombre)

        print(f"\n🎉 Migración completada: {carpeta} → {nodo}:{ruta_destino}")
    finally:
        # Limpiar temporal local
        if os.path.exists(archivo):
            os.remove(archivo)


if __name__ == "__main__":
    main()
