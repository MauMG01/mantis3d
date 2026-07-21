"""Tests de preferencias persistentes."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.i18n import Idioma
from src import preferencias as pref


class TestPreferencias(unittest.TestCase):
    def test_guardar_y_cargar_idioma(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "preferences.json"
            with patch.object(pref, "_ARCHIVO", ruta):
                pref.guardar_idioma(Idioma.ES)
                self.assertEqual(pref.cargar_idioma(), Idioma.ES)
                pref.guardar_idioma(Idioma.EN)
                self.assertEqual(pref.cargar_idioma(), Idioma.EN)

    def test_cargar_idioma_inexistente_usa_defecto(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "no_existe.json"
            with patch.object(pref, "_ARCHIVO", ruta):
                self.assertEqual(pref.cargar_idioma(), Idioma.EN)

    def test_cargar_idioma_invalido_usa_defecto(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "preferences.json"
            ruta.write_text(json.dumps({"idioma": "fr"}), encoding="utf-8")
            with patch.object(pref, "_ARCHIVO", ruta):
                self.assertEqual(pref.cargar_idioma(), Idioma.EN)


if __name__ == "__main__":
    unittest.main()
