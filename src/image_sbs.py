"""Conversión de imagen 2D a SBS (prototipo para galería / Quest)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import cv2
import numpy as np

from .procesador import (
    ModoEstereo,
    ResolucionSalida,
    _ancho_contenido_ojo,
    _offset_escalado,
    calcular_offset_recomendado,
    dimensiones_por_resolucion,
    procesar_fotograma_sbs,
    procesar_fotograma_sbs_profundidad,
)
from .profundidad import (
    MODELO_PROFUNDIDAD_DEFECTO,
    EstimadorProfundidad,
    ModeloProfundidad,
)

EXTENSIONES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}

# ~2 % de ancho de ojo × intensidad 0.45: buen 3D con menos duplicados/artefactos (pruebas reales).
PORCENTAJE_OFFSET_IMAGEN = 2.0
INTENSIDAD_IMAGEN_PROFUNDIDAD_DEFECTO = 0.45


def listar_imagenes(carpeta: Path) -> list[Path]:
    carpeta = carpeta.expanduser().resolve()
    if not carpeta.is_dir():
        raise NotADirectoryError(carpeta)
    return [
        p
        for p in sorted(carpeta.iterdir())
        if p.is_file() and p.suffix.lower() in EXTENSIONES
    ]


def cargar_bgr(ruta: Path) -> np.ndarray:
    data = np.fromfile(str(ruta), dtype=np.uint8)
    frame = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError(f"No se pudo leer la imagen: {ruta}")
    return frame


def guardar_bgr(ruta: Path, frame: np.ndarray) -> None:
    ruta = ruta.expanduser().resolve()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ext = ruta.suffix.lower() or ".jpg"
    ok, encoded = cv2.imencode(
        ext,
        frame,
        [int(cv2.IMWRITE_JPEG_QUALITY), 92],
    )
    if not ok:
        raise ValueError(f"No se pudo codificar: {ruta}")
    encoded.tofile(str(ruta))


def imagen_a_sbs(
    frame_bgr: np.ndarray,
    *,
    modo: ModoEstereo | str = ModoEstereo.PROFUNDIDAD,
    resolucion: ResolucionSalida | str = ResolucionSalida.ORIGINAL,
    offset: int | None = None,
    intensidad: float = INTENSIDAD_IMAGEN_PROFUNDIDAD_DEFECTO,
    estimador: EstimadorProfundidad | None = None,
    modelo: ModeloProfundidad | str = MODELO_PROFUNDIDAD_DEFECTO,
    dispositivo: str = "auto",
    conservar_proporcion: bool = True,
) -> tuple[np.ndarray, EstimadorProfundidad | None]:
    """
    Convierte un fotograma BGR a SBS.

    Devuelve ``(sbs, estimador)`` para reutilizar el modelo de profundidad
    entre fotos en una galería.

    Con ``conservar_proporcion=True`` (por defecto) no estira: encaja la foto
    en el tamaño del ojo con barras negras si hace falta (p. ej. SBS 1080).

    En modo profundidad el offset se interpreta respecto al ancho de la foto
    y se escala al ancho útil del ojo (importante en cuadradas con letterbox).
    """
    modo = ModoEstereo(modo)
    resolucion = ResolucionSalida(resolucion)
    alto, ancho = frame_bgr.shape[:2]
    dims = dimensiones_por_resolucion(resolucion, ancho, alto)

    if offset is None:
        offset = calcular_offset_recomendado(
            ancho,
            porcentaje=PORCENTAJE_OFFSET_IMAGEN,
        )

    if modo is ModoEstereo.FIJO:
        return (
            procesar_fotograma_sbs(
                frame_bgr,
                offset,
                dims,
                ancho,
                conservar_proporcion=conservar_proporcion,
            ),
            estimador,
        )

    if estimador is None:
        estimador = EstimadorProfundidad(modelo=modelo, dispositivo=dispositivo)

    ancho_ref = _ancho_contenido_ojo(
        ancho,
        alto,
        dims,
        conservar_proporcion=conservar_proporcion,
    )
    max_disparidad = float(_offset_escalado(int(offset), ancho, ancho_ref))

    sbs = procesar_fotograma_sbs_profundidad(
        frame_bgr,
        estimador,
        max_disparidad,
        dims,
        intensidad=intensidad,
        conservar_proporcion=conservar_proporcion,
    )
    return sbs, estimador


def exportar_carpeta_quest(
    origen: Path,
    destino: Path,
    *,
    modo: ModoEstereo | str = ModoEstereo.PROFUNDIDAD,
    resolucion: ResolucionSalida | str = ResolucionSalida.SBS_1080,
    offset: int | None = None,
    intensidad: float = INTENSIDAD_IMAGEN_PROFUNDIDAD_DEFECTO,
    estimador: EstimadorProfundidad | None = None,
    modelo: ModeloProfundidad | str = MODELO_PROFUNDIDAD_DEFECTO,
    dispositivo: str = "auto",
    conservar_proporcion: bool = True,
    progreso: Callable[[int, int, str], None] | None = None,
    cancelar: Callable[[], bool] | None = None,
) -> dict:
    """
    Convierte todas las imágenes de ``origen`` a SBS y las guarda en ``destino``.

    Pensado para Quest: por defecto SBS 1080 (3840×1080) en JPEG, sin estirar
    (letterbox) para conservar la proporción de cada foto.
    ``progreso(actual, total, nombre)`` y ``cancelar() -> bool`` son opcionales.
    """
    imagenes = listar_imagenes(origen)
    if not imagenes:
        raise ValueError(f"No hay imágenes en: {origen}")

    destino = destino.expanduser().resolve()
    destino.mkdir(parents=True, exist_ok=True)

    ok = 0
    errores: list[str] = []
    for i, ruta in enumerate(imagenes, start=1):
        if cancelar is not None and cancelar():
            break
        if progreso is not None:
            progreso(i, len(imagenes), ruta.name)
        try:
            frame = cargar_bgr(ruta)
            sbs, estimador = imagen_a_sbs(
                frame,
                modo=modo,
                resolucion=resolucion,
                offset=offset,
                intensidad=intensidad,
                estimador=estimador,
                modelo=modelo,
                dispositivo=dispositivo,
                conservar_proporcion=conservar_proporcion,
            )
            salida = destino / f"{ruta.stem}_sbs.jpg"
            guardar_bgr(salida, sbs)
            ok += 1
        except Exception as exc:  # noqa: BLE001
            errores.append(f"{ruta.name}: {exc}")

    return {
        "destino": str(destino),
        "total": len(imagenes),
        "ok": ok,
        "errores": errores,
        "estimador": estimador,
    }
