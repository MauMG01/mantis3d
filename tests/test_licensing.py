"""Tests de políticas Demo / Pro."""

from __future__ import annotations

import unittest

from src.licensing.policy import (
    DEMO_MAX_CONVERSIONES,
    DEMO_MAX_SEGUNDOS,
    LicenciaError,
    Plan,
    resoluciones_para_plan,
    validar_conversion,
)
from src.procesador import ResolucionSalida


class TestLicensingPolicy(unittest.TestCase):
    def test_demo_solo_1080(self) -> None:
        self.assertEqual(
            resoluciones_para_plan(Plan.DEMO),
            [ResolucionSalida.SBS_1080],
        )

    def test_pro_todas_resoluciones_comerciales(self) -> None:
        self.assertEqual(
            resoluciones_para_plan(Plan.PRO),
            [
                ResolucionSalida.SBS_1080,
                ResolucionSalida.SBS_4K,
                ResolucionSalida.SBS_6K,
                ResolucionSalida.SBS_8K,
            ],
        )

    def test_demo_bloquea_4k(self) -> None:
        with self.assertRaises(LicenciaError):
            validar_conversion(
                plan=Plan.DEMO,
                resolucion=ResolucionSalida.SBS_4K,
                conversiones_usadas=0,
            )

    def test_demo_bloquea_tras_limite(self) -> None:
        with self.assertRaises(LicenciaError):
            validar_conversion(
                plan=Plan.DEMO,
                resolucion=ResolucionSalida.SBS_1080,
                conversiones_usadas=DEMO_MAX_CONVERSIONES,
            )

    def test_demo_permite_1080(self) -> None:
        politica = validar_conversion(
            plan=Plan.DEMO,
            resolucion=ResolucionSalida.SBS_1080,
            conversiones_usadas=0,
        )
        self.assertEqual(politica.max_segundos, DEMO_MAX_SEGUNDOS)

    def test_pro_sin_limites(self) -> None:
        politica = validar_conversion(
            plan=Plan.PRO,
            resolucion=ResolucionSalida.SBS_8K,
            conversiones_usadas=99,
        )
        self.assertIsNone(politica.max_segundos)
        self.assertIsNone(politica.max_conversiones)


if __name__ == "__main__":
    unittest.main()
