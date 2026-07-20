#!/usr/bin/env python3
"""Ejecuta la suite de pruebas de MANTIS 3D."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


def main() -> int:
    print("MANTIS 3D - pruebas")
    print(f"Python: {sys.version.split()[0]}")

    raiz = Path(__file__).resolve().parent
    loader = unittest.TestLoader()
    suite = loader.discover(str(raiz / "tests"), pattern="test_*.py")
    resultado = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if resultado.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
