"""Tests básicos: verificar que los módulos clave importan sin errores."""

from pathlib import Path
import sys

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

BOTS_DIR = Path(__file__).parent.parent
if str(BOTS_DIR) not in sys.path:
    sys.path.insert(0, str(BOTS_DIR))


def test_ia_central_import():
    """AI Hub central debe importar sin errores."""
    from ia_central import hub
    assert hub is not None


def test_ia_central_methods():
    """AICentralHub debe tener métodos esenciales."""
    from ia_central import hub
    assert hasattr(hub, "call_ai")
    assert hasattr(hub, "call_ai_messages")
    assert hasattr(hub, "has_keys")


def test_requirements_exist():
    """requirements.txt debe existir y no estar vacío."""
    req = Path(__file__).parent.parent / "requirements.txt"
    assert req.exists()
    content = req.read_text().strip()
    assert len(content) > 0


def test_pyproject_toml():
    """pyproject.toml debe ser TOML válido."""
    import tomllib
    path = Path(__file__).parent.parent / "pyproject.toml"
    assert path.exists()
    data = tomllib.loads(path.read_text())
    assert "project" in data
