#!/usr/bin/env python3
"""Punto de entrada para la app empaquetada (abre la GUI por defecto)."""

from __future__ import annotations

import multiprocessing
import sys
import traceback
from datetime import datetime
from pathlib import Path


def _log_dir() -> Path:
    ruta = Path.home() / ".mantis3d"
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


def _escribir_log(nombre: str, texto: str) -> None:
    try:
        ruta = _log_dir() / nombre
        with ruta.open("a", encoding="utf-8") as fh:
            fh.write(texto)
            if not texto.endswith("\n"):
                fh.write("\n")
    except OSError:
        pass


def _instalar_excepthook() -> None:
    def _hook(exc_type, exc, tb) -> None:  # noqa: ANN001
        marca = datetime.now().isoformat(timespec="seconds")
        _escribir_log(
            "crash.log",
            f"\n===== {marca} =====\n"
            + "".join(traceback.format_exception(exc_type, exc, tb)),
        )
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _hook


def main() -> int:
    multiprocessing.freeze_support()
    _instalar_excepthook()
    _escribir_log(
        "startup.log",
        f"{datetime.now().isoformat(timespec='seconds')} argv={sys.argv!r} frozen={getattr(sys, 'frozen', False)}",
    )

    # Si no hay argumentos, abrir la interfaz gráfica.
    if len(sys.argv) == 1:
        sys.argv.append("--gui")
    from src.main import main as app_main

    return app_main()


if __name__ == "__main__":
    raise SystemExit(main())
