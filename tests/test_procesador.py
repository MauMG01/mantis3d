"""Tests del pipeline SBS (sin modelos de IA)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from src.procesador import (
    ModoEstereo,
    calcular_offset_recomendado,
    convertir_video_a_sbs,
    frame_a_sbs,
    ruta_salida_por_defecto,
)

ROOT = Path(__file__).resolve().parents[1]
VIDEO_PRUEBA = ROOT / "_codec_test" / "test_mp4v.mp4"


class TestProcesadorBasico(unittest.TestCase):
    def test_calcular_offset_recomendado(self) -> None:
        self.assertGreaterEqual(calcular_offset_recomendado(1920), 8)
        self.assertEqual(calcular_offset_recomendado(0), 8)

    def test_frame_a_sbs_duplica_ancho(self) -> None:
        frame = np.zeros((100, 200, 3), dtype=np.uint8)
        sbs = frame_a_sbs(frame, offset=10)
        self.assertEqual(sbs.shape, (100, 400, 3))

    def test_ruta_salida_por_defecto(self) -> None:
        entrada = Path("/tmp/demo.mp4")
        self.assertEqual(
            ruta_salida_por_defecto(entrada, ModoEstereo.FIJO).name,
            "demo_sbs.mp4",
        )
        self.assertEqual(
            ruta_salida_por_defecto(entrada, ModoEstereo.PROFUNDIDAD).name,
            "demo_sbs_depth.mp4",
        )

    def test_dimensiones_1080_y_4k(self) -> None:
        from src.procesador import ResolucionSalida, dimensiones_por_resolucion

        dims_1080 = dimensiones_por_resolucion(ResolucionSalida.SBS_1080, 1280, 720)
        self.assertEqual(dims_1080.ancho_sbs, 3840)
        self.assertEqual(dims_1080.alto_sbs, 1080)
        self.assertEqual(dims_1080.ancho_ojo, 1920)
        self.assertEqual(dims_1080.alto_ojo, 1080)

        dims_4k = dimensiones_por_resolucion(ResolucionSalida.SBS_4K, 1280, 720)
        self.assertEqual(dims_4k.ancho_sbs, 7680)
        self.assertEqual(dims_4k.alto_sbs, 2160)
        self.assertEqual(dims_4k.ancho_ojo, 3840)
        self.assertEqual(dims_4k.alto_ojo, 2160)


class TestConversionFijo(unittest.TestCase):
    def test_convertir_video_modo_fijo(self) -> None:
        if not VIDEO_PRUEBA.is_file():
            self.skipTest(f"No existe video de prueba: {VIDEO_PRUEBA}")

        with tempfile.TemporaryDirectory() as tmp:
            salida = Path(tmp) / "salida_sbs.mp4"
            info = convertir_video_a_sbs(
                VIDEO_PRUEBA,
                salida,
                modo=ModoEstereo.FIJO,
                codificar_final=False,
                mostrar_progreso=False,
            )
            self.assertTrue(salida.is_file())
            self.assertEqual(info["fotogramas"], 5)
            self.assertEqual(info["ancho_salida"], info["ancho_entrada"] * 2)
            self.assertEqual(info["modo"], "fijo")


if __name__ == "__main__":
    unittest.main()
