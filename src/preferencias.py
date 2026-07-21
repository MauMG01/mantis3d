"""Preferencias persistentes de la aplicación."""

from __future__ import annotations

import json
from pathlib import Path

from .i18n import IDIOMA_DEFECTO, Idioma

_ARCHIVO = Path.home() / ".mantis3d" / "preferences.json"


def _ruta_preferencias() -> Path:
    return _ARCHIVO


def cargar_idioma() -> Idioma:
    """Devuelve el idioma guardado o el idioma por defecto."""
    ruta = _ruta_preferencias()
    if not ruta.is_file():
        return IDIOMA_DEFECTO
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        return Idioma(datos.get("idioma", IDIOMA_DEFECTO.value))
    except (OSError, json.JSONDecodeError, ValueError):
        return IDIOMA_DEFECTO


def guardar_idioma(idioma: Idioma) -> None:
    """Guarda el idioma seleccionado para la próxima sesión."""
    ruta = _ruta_preferencias()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    datos: dict[str, str] = {}
    if ruta.is_file():
        try:
            datos = json.loads(ruta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            datos = {}
    datos["idioma"] = Idioma(idioma).value
    ruta.write_text(json.dumps(datos, indent=2) + "\n", encoding="utf-8")
