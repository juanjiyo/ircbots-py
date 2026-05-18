#!/usr/bin/env python3
"""
Receptor de Migración — Descarga y restaura directorios desde un nodo remoto.

Descarga un directorio remoto completo empaquetándolo en el nodo origen,
transfiriéndolo via vps_bridge y desempaquetándolo localmente.

Uso:
  python receptor_migracion.py <nodo_origen> <ruta_remota> <carpeta_local>

Ejemplos:
  python receptor_migracion.py pcb /home/juanjo/ircbots_backup/bots/milenium ./bots/milenium
  python receptor_migracion.py panel /home/irc/ircbots/scripts ./scripts_backup
"""

import os
import sys
import subprocess
import tarfile
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
BRIDGE     = SCRIPT_DIR / "vps_bridge.py"


def empaquetar_remoto(nodo: str, ruta_remota: str) -> str:
    """Empaqueta un directorio en el nodo remoto. Devuelve la ruta del .tar.gz remoto."""
    nombre_base = Path(ruta_remota).name
    archivo_remoto = f"/tmp/migracion_{nombre_base}.tar.gz"
    cmd_remoto = f"cd {Path(ruta_remota).parent} && tar czf {archivo_remoto} {nombre_base}"
    cmd = [sys.executable, str(BRIDGE), nodo, cmd_remoto]
    print(f"📦 Empaquetando {nodo}:{ruta_remota}...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"   ✅ Paquete creado en {nodo}:{archivo_remoto}")
        return archivo_remoto
    else:
        print(f"   ❌ Error: {result.stderr or result.stdout}")
        sys.exit(1)


def descargar(nodo: str, archivo_remoto: str) -> str:
    """Descarga un archivo del nodo via vps_bridge. Devuelve la ruta local."""
    local = tempfile.mktemp(suffix=".tar.gz", prefix="recibido_")
    cmd = [sys.executable, str(BRIDGE), nodo, "download", archivo_remoto, local]
    print(f"📥 Descargando {nodo}:{archivo_remoto}...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0 and os.path.exists(local):
        size_mb = os.path.getsize(local) / (1024 * 1024)
        print(f"   ✅ Descargado: {local} ({size_mb:.1f} MB)")
        return local
    else:
        print(f"   ❌ Error: {result.stderr or result.stdout}")
        sys.exit(1)


def desempaquetar_local(archivo: str, destino: str) -> None:
    """Desempaqueta un .tar.gz en la carpeta destino local."""
    destino = Path(destino).resolve()
    destino.mkdir(parents=True, exist_ok=True)
    print(f"📂 Desempaquetando en {destino}...")
    with tarfile.open(archivo, "r:gz") as tar:
        tar.extractall(str(destino))
    print(f"   ✅ Restaurado en {destino}")


def limpiar_remoto(nodo: str, archivo_remoto: str) -> None:
    """Elimina el archivo temporal del nodo remoto."""
    cmd = [sys.executable, str(BRIDGE), nodo, f"rm -f {archivo_remoto}"]
    subprocess.run(cmd, capture_output=True, text=True)


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)

    nodo         = sys.argv[1]
    ruta_remota  = sys.argv[2]
    carpeta_local = sys.argv[3]

    # 1. Empaquetar en remoto
    archivo_remoto = empaquetar_remoto(nodo, ruta_remota)

    # 2. Descargar
    archivo_local = descargar(nodo, archivo_remoto)

    try:
        # 3. Desempaquetar localmente
        desempaquetar_local(archivo_local, carpeta_local)
        print(f"\n🎉 Migración completada: {nodo}:{ruta_remota} → {carpeta_local}")
    finally:
        # Limpiar temporales
        if os.path.exists(archivo_local):
            os.remove(archivo_local)
        limpiar_remoto(nodo, archivo_remoto)


if __name__ == "__main__":
    main()
