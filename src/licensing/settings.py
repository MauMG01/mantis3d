"""URL del backend de licencias (env, archivo local o recurso empaquetado)."""

from __future__ import annotations

import json
import os
from pathlib import Path

_CONFIG = Path.home() / ".mantis3d" / "config.json"


def _from_config_file() -> str | None:
    if not _CONFIG.is_file():
        return None
    try:
        data = json.loads(_CONFIG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    url = (data.get("api_url") or data.get("MANTIS_API_URL") or "").strip().rstrip("/")
    return url or None


def _from_packaged_default() -> str | None:
    try:
        from ..runtime_paths import resource_path

        path = resource_path("mantis_api_url.txt")
        if not path.is_file():
            return None
        url = path.read_text(encoding="utf-8").strip().splitlines()[0].strip().rstrip("/")
        if not url or url.startswith("#"):
            return None
        return url
    except Exception:
        return None


def licensing_api_url() -> str | None:
    """
    Orden de prioridad:
    1. Variable de entorno MANTIS_API_URL
    2. ~/.mantis3d/config.json → "api_url"
    3. mantis_api_url.txt empaquetado con la app (build de producción)
    """
    env = os.environ.get("MANTIS_API_URL", "").strip().rstrip("/")
    if env:
        return env
    return _from_config_file() or _from_packaged_default()


def config_file_path() -> Path:
    return _CONFIG
