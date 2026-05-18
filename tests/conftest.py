"""Configuración global de pytest para el proyecto ircbots."""

from pathlib import Path
import sys

# Añadir scripts/ al path para que ia_central sea importable
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
