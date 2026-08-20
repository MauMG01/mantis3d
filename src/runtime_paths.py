"""Rutas de recursos compatibles con desarrollo y app empaquetada (PyInstaller)."""

from __future__ import annotations

import sys
from pathlib import Path


def app_root() -> Path:
    """
    Raíz de recursos de la aplicación.

    - Desarrollo: carpeta del proyecto (padre de ``src/``).
    - Empaquetado PyInstaller: carpeta temporal ``_MEIPASS``.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[1]


def resource_path(*parts: str | Path) -> Path:
    """Une ``parts`` a la raíz de recursos."""
    return app_root().joinpath(*parts)
