"""Procesamiento de video 2D a formato Side-by-Side (SBS)."""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Callable, NamedTuple

import cv2
import numpy as np

from .profundidad import INTENSIDAD_PROFUNDIDAD_DEFECTO

if TYPE_CHECKING:
    from .profundidad import EstimadorProfundidad, ModeloProfundidad

INTERPOLACION_ESCALADO = cv2.INTER_CUBIC

# Disparidad horizontal ~2 % del ancho por ojo: 3D visible sin ser agresivo en VR.
PORCENTAJE_OFFSET_DEFECTO = 2.0
PORCENTAJE_OFFSET_MAXIMO = 3.0
OFFSET_MINIMO_PX = 8


class ResolucionSalida(str, Enum):
    ORIGINAL = "original"
    SBS_1080 = "1080"
    SBS_4K = "4k"
    SBS_6K = "6k"
    SBS_8K = "8k"


class ModoEstereo(str, Enum):
    FIJO = "fijo"
    PROFUNDIDAD = "profundidad"


class ConversionCancelada(Exception):
    """La conversión fue interrumpida por el usuario."""


def ruta_salida_por_defecto(entrada: Path, modo: ModoEstereo | str) -> Path:
    """Nombre de salida sugerido según el modo estéreo."""
    modo = ModoEstereo(modo)
    sufijo = "_sbs_depth" if modo is ModoEstereo.PROFUNDIDAD else "_sbs"
    return entrada.with_name(f"{entrada.stem}{sufijo}{entrada.suffix}")


class DimensionesSBS(NamedTuple):
    ancho_sbs: int
    alto_sbs: int
    ancho_ojo: int
    alto_ojo: int


# Ancho total SBS x alto del fotograma completo (cada ojo = mitad del ancho).
_PRESETS_SBS: dict[ResolucionSalida, tuple[int, int]] = {
    ResolucionSalida.SBS_1080: (3840, 1080),
    ResolucionSalida.SBS_4K: (7680, 2160),
    ResolucionSalida.SBS_6K: (6144, 3072),
    ResolucionSalida.SBS_8K: (7680, 4320),
}


def dimensiones_por_resolucion(
    resolucion: ResolucionSalida | str,
    ancho_entrada: int,
    alto_entrada: int,
) -> DimensionesSBS:
    """Calcula el tamaño del fotograma SBS y de cada vista monocular."""
    resolucion = ResolucionSalida(resolucion)

    if resolucion is ResolucionSalida.ORIGINAL:
        return DimensionesSBS(
            ancho_sbs=ancho_entrada * 2,
            alto_sbs=alto_entrada,
            ancho_ojo=ancho_entrada,
            alto_ojo=alto_entrada,
        )

    ancho_sbs, alto_sbs = _PRESETS_SBS[resolucion]
    return DimensionesSBS(
        ancho_sbs=ancho_sbs,
        alto_sbs=alto_sbs,
        ancho_ojo=ancho_sbs // 2,
        alto_ojo=alto_sbs,
    )


def escalar_fotograma_2d(
    frame: np.ndarray,
    ancho_ojo: int,
    alto_ojo: int,
) -> np.ndarray:
    """Escala el video 2D al tamaño de un ojo antes de generar el par estéreo."""
    alto, ancho = frame.shape[:2]
    if ancho == ancho_ojo and alto == alto_ojo:
        return frame

    return cv2.resize(
        frame,
        (ancho_ojo, alto_ojo),
        interpolation=INTERPOLACION_ESCALADO,
    )


def _offset_escalado(offset: int, ancho_entrada: int, ancho_ojo: int) -> int:
    if ancho_entrada <= 0 or ancho_ojo == ancho_entrada:
        return offset
    return round(offset * ancho_ojo / ancho_entrada)


def calcular_offset_recomendado(
    ancho_entrada: int,
    *,
    porcentaje: float = PORCENTAJE_OFFSET_DEFECTO,
) -> int:
    """
    Offset en píxeles del video de entrada para un paralaje ~cómodo en VR.

    Al escalar a 6K/8K, ``_offset_escalado`` mantiene el mismo porcentaje sobre
    el ancho de cada ojo (p. ej. 2 % en 1920 px de entrada ≈ 2 % en 3072 px/ojo).
    """
    if ancho_entrada <= 0:
        return OFFSET_MINIMO_PX

    pct = min(max(porcentaje, 0.0), PORCENTAJE_OFFSET_MAXIMO)
    return max(OFFSET_MINIMO_PX, round(ancho_entrada * pct / 100.0))


def porcentaje_disparidad(offset_px: int, ancho_referencia: int) -> float:
    """Porcentaje de separación respecto al ancho de referencia (ojo o entrada)."""
    if ancho_referencia <= 0:
        return 0.0
    return 100.0 * offset_px / ancho_referencia


def procesar_fotograma_sbs(
    frame: np.ndarray,
    offset: int,
    dimensiones: DimensionesSBS,
    ancho_entrada: int,
) -> np.ndarray:
    """Escala el fotograma 2D y aplica la separación estéreo en formato SBS."""
    vista_2d = escalar_fotograma_2d(frame, dimensiones.ancho_ojo, dimensiones.alto_ojo)
    offset_ojo = _offset_escalado(offset, ancho_entrada, dimensiones.ancho_ojo)
    return frame_a_sbs(vista_2d, offset_ojo)


def _vista_desplazada(frame: np.ndarray, offset: int) -> np.ndarray:
    """
    Desplaza la imagen en X recortando píxeles en el borde opuesto.

    El hueco que queda se rellena en negro en lugar de replicar el borde,
    evitando la banda estirada que produce ``BORDER_REPLICATE`` con warpAffine.
    """
    if offset == 0:
        return frame.copy()

    alto, ancho = frame.shape[:2]
    desplazado = np.zeros_like(frame)

    if offset > 0:
        if offset >= ancho:
            return desplazado
        desplazado[:, offset:] = frame[:, :-offset]
    else:
        margen = -offset
        if margen >= ancho:
            return desplazado
        desplazado[:, : ancho - margen] = frame[:, margen:]

    return desplazado


def _mapas_remap_disparidad(
    disparidad: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Mapas para cv2.remap: ojo derecho muestrea la vista hacia la izquierda."""
    alto, ancho = disparidad.shape[:2]
    grid_x = np.arange(ancho, dtype=np.float32)
    grid_y = np.arange(alto, dtype=np.float32)
    map_x = grid_x[np.newaxis, :] - disparidad
    map_y = np.broadcast_to(grid_y[:, np.newaxis], (alto, ancho))
    return map_x, map_y


def generar_ojo_derecho_por_profundidad(
    frame: np.ndarray,
    mapa_proximidad: np.ndarray,
    max_disparidad: float,
    *,
    intensidad: float = 1.0,
) -> np.ndarray:
    """Ojo derecho con desplazamiento horizontal variable según proximidad."""
    factor = max(0.0, float(intensidad))
    disparidad = mapa_proximidad.astype(np.float32) * max_disparidad * factor
    map_x, map_y = _mapas_remap_disparidad(disparidad)
    return cv2.remap(
        frame,
        map_x,
        map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )


def frame_a_sbs_por_profundidad(
    frame: np.ndarray,
    mapa_proximidad: np.ndarray,
    max_disparidad: float,
    *,
    intensidad: float = 1.0,
) -> np.ndarray:
    """Par SBS con disparidad espacial según mapa de proximidad (1=cerca)."""
    ojo_derecho = generar_ojo_derecho_por_profundidad(
        frame,
        mapa_proximidad,
        max_disparidad,
        intensidad=intensidad,
    )
    return np.hstack((frame, ojo_derecho))


def procesar_fotograma_sbs_profundidad(
    frame: np.ndarray,
    estimador: EstimadorProfundidad,
    max_disparidad: float,
    dimensiones: DimensionesSBS,
    *,
    intensidad: float = 1.0,
) -> np.ndarray:
    """Escala el fotograma, estima profundidad y genera SBS con disparidad variable."""
    vista_2d = escalar_fotograma_2d(frame, dimensiones.ancho_ojo, dimensiones.alto_ojo)
    proximidad = estimador.estimar_proximidad(
        frame,
        dimensiones.ancho_ojo,
        dimensiones.alto_ojo,
    )
    return frame_a_sbs_por_profundidad(
        vista_2d,
        proximidad,
        max_disparidad,
        intensidad=intensidad,
    )


def frame_a_sbs(frame: np.ndarray, offset: int = 0) -> np.ndarray:
    """
    Construye un fotograma Side-by-Side con disparidad horizontal.

    Mitad izquierda: imagen original (ojo izquierdo).
    Mitad derecha: misma imagen desplazada ``offset`` píxeles en X (ojo derecho).
    La zona vacía del desplazamiento queda en negro (sin estirar el borde).

    ``offset`` positivo mueve el contenido del ojo derecho hacia la derecha;
    valores negativos lo mueven hacia la izquierda.
    """
    ojo_izquierdo = frame
    ojo_derecho = _vista_desplazada(frame, offset)
    return np.hstack((ojo_izquierdo, ojo_derecho))


def _ffmpeg_exe() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def _invoke_progreso_callback(
    callback_progreso: callable[[int, int, str], None] | None,
    current: int,
    total: int,
    etapa: str,
) -> None:
    if callback_progreso is None:
        return
    try:
        callback_progreso(current, total, etapa)
    except TypeError:
        callback_progreso(current, total)


def _cancelacion_solicitada(cancelar: Callable[[], bool] | None) -> bool:
    return cancelar is not None and cancelar()


def _eliminar_archivo(ruta: Path, intentos: int = 5, espera_s: float = 0.5) -> None:
    """Elimina un archivo temporal; en Windows FFmpeg puede retener el handle un momento."""
    for intento in range(intentos):
        try:
            ruta.unlink(missing_ok=True)
            return
        except PermissionError:
            if intento == intentos - 1:
                raise
            time.sleep(espera_s)


def _ffmpeg_tiene_pista_audio(ruta: Path) -> bool:
    """Comprueba si el contenedor incluye al menos una pista de audio."""
    resultado = subprocess.run(
        [_ffmpeg_exe(), "-hide_banner", "-i", str(ruta)],
        capture_output=True,
        text=True,
        check=False,
    )
    texto = (resultado.stderr or "") + (resultado.stdout or "")
    return "Audio:" in texto


def codificar_h264_compatible(
    ruta_video: Path,
    ruta_salida: Path,
    *,
    ruta_audio_origen: Path | None = None,
    duracion_s: float | None = None,
    callback_progreso: callable[[int, int, str], None] | None = None,
    cancelar: Callable[[], bool] | None = None,
) -> bool:
    """
    Re-codifica a H.264 (yuv420p) para compatibilidad con Windows y reproductores VR.

    Si ``ruta_audio_origen`` tiene audio, lo mezcla como AAC estéreo (2 canales).
    Devuelve ``True`` si se incluyó audio en la salida.
    """
    incluir_audio = (
        ruta_audio_origen is not None and _ffmpeg_tiene_pista_audio(ruta_audio_origen)
    )

    comando: list[str] = [
        _ffmpeg_exe(),
        "-y",
        "-i",
        str(ruta_video),
    ]
    if incluir_audio:
        comando.extend(["-i", str(ruta_audio_origen)])

    comando.extend(
        [
            "-map",
            "0:v:0",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
        ]
    )

    if incluir_audio:
        comando.extend(
            [
                "-map",
                "1:a:0",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-ac",
                "2",
                "-shortest",
            ]
        )
    else:
        comando.append("-an")

    comando.extend(["-progress", "pipe:1", "-nostats", str(ruta_salida)])

    proceso = subprocess.Popen(
        comando,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    if callback_progreso is not None:
        _invoke_progreso_callback(callback_progreso, 0, 100, "codificacion")

    out_time_ms = 0
    while True:
        if _cancelacion_solicitada(cancelar):
            proceso.terminate()
            proceso.wait()
            raise ConversionCancelada()

        if proceso.stdout is None:
            break
        linea = proceso.stdout.readline()
        if linea == "" and proceso.poll() is not None:
            break
        if not linea:
            continue
        linea = linea.strip()
        if "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        if clave == "out_time_ms":
            try:
                out_time_ms = int(valor)
            except ValueError:
                continue
            if duracion_s and duracion_s > 0:
                progreso = min(1.0, out_time_ms / 1_000_000.0 / duracion_s)
                _invoke_progreso_callback(
                    callback_progreso,
                    int(round(progreso * 100)),
                    100,
                    "codificacion",
                )
        elif clave == "progress" and valor == "end":
            _invoke_progreso_callback(callback_progreso, 100, 100, "finalizado")

    stderr = proceso.stderr.read() if proceso.stderr is not None else ""
    resultado = proceso.wait()
    if resultado != 0:
        detalle = (stderr or "").strip()
        raise RuntimeError(f"FFmpeg no pudo codificar el video: {detalle}")

    return incluir_audio


def abrir_video(ruta: str | Path) -> cv2.VideoCapture:
    """Abre un archivo de video 2D para lectura."""
    captura = cv2.VideoCapture(str(ruta))
    if not captura.isOpened():
        raise FileNotFoundError(f"No se pudo abrir el video: {ruta}")
    return captura


def convertir_video_a_sbs(
    ruta_entrada: str | Path,
    ruta_salida: str | Path,
    *,
    offset: int | None = None,
    resolucion: ResolucionSalida | str = ResolucionSalida.ORIGINAL,
    modo: ModoEstereo | str = ModoEstereo.FIJO,
    modelo_profundidad: ModeloProfundidad | str | None = None,
    intensidad_profundidad: float = INTENSIDAD_PROFUNDIDAD_DEFECTO,
    dispositivo_profundidad: str | None = None,
    codec: str = "mp4v",
    codificar_final: bool = True,
    mostrar_progreso: bool = True,
    callback_progreso: callable[[int, int, str], None] | None = None,
    cancelar: Callable[[], bool] | None = None,
    max_segundos: float | None = None,
) -> dict[str, int | float | str | bool]:
    """
    Lee un video 2D y escribe uno SBS.

    Si ``codificar_final`` es ``False``, se omite la recodificación final por FFmpeg
    y el video de salida se escribe directamente con OpenCV.

    Modo ``fijo``: offset horizontal constante. Modo ``profundidad``: mapa de
    profundidad por fotograma (Depth Anything / MiDaS) y disparidad variable.

    Si ``offset`` es ``None``, se calcula uno recomendado (~2 % del ancho);
    en modo profundidad define la disparidad máxima en el plano cercano.

    Si ``max_segundos`` se indica (p. ej. Demo = 60), se procesan como máximo
    esos segundos de video.
    
    Si ``callback_progreso`` se proporciona, se llama con (fotograma_actual, total_fotogramas)
    cada vez que se procesa un fotograma.
    """
    from .profundidad import EstimadorProfundidad, MODELO_PROFUNDIDAD_DEFECTO, ModeloProfundidad

    modo = ModoEstereo(modo)
    ruta_entrada = Path(ruta_entrada)
    ruta_salida = Path(ruta_salida)
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)

    # OpenCV escribe un contenedor intermedio; FFmpeg genera H.264 compatible.
    ruta_temporal: Path | None = None
    if codificar_final and ruta_salida.suffix.lower() in {".mp4", ".m4v", ".mov"}:
        fd, nombre_temporal = tempfile.mkstemp(
            suffix=".mp4",
            dir=ruta_salida.parent,
        )
        os.close(fd)
        ruta_temporal = Path(nombre_temporal)
        ruta_escritura = ruta_temporal
    else:
        ruta_escritura = ruta_salida

    captura = abrir_video(ruta_entrada)

    ancho = int(captura.get(cv2.CAP_PROP_FRAME_WIDTH))
    alto = int(captura.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = captura.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(captura.get(cv2.CAP_PROP_FRAME_COUNT))
    if max_segundos is not None and max_segundos > 0 and fps > 0:
        limite_fotogramas = max(1, int(max_segundos * fps))
        if total <= 0:
            total = limite_fotogramas
        else:
            total = min(total, limite_fotogramas)
    resolucion = ResolucionSalida(resolucion)
    dimensiones = dimensiones_por_resolucion(resolucion, ancho, alto)

    offset_automatico = offset is None
    if offset is None:
        offset = calcular_offset_recomendado(ancho)
    offset_ojo = _offset_escalado(offset, ancho, dimensiones.ancho_ojo)

    if mostrar_progreso:
        pct_entrada = porcentaje_disparidad(offset, ancho)
        pct_ojo = porcentaje_disparidad(offset_ojo, dimensiones.ancho_ojo)
        origen = "automático" if offset_automatico else "manual"
        print(
            f"Offset ({origen}): {offset} px entrada "
            f"({pct_entrada:.1f} %) -> {offset_ojo} px/ojo ({pct_ojo:.1f} %)"
        )

    estimador: EstimadorProfundidad | None = None
    if modo is ModoEstereo.PROFUNDIDAD:
        modelo = modelo_profundidad or MODELO_PROFUNDIDAD_DEFECTO
        if mostrar_progreso:
            dispositivo_txt = dispositivo_profundidad or "auto"
            print(f"Modo profundidad: {modelo.value} (dispositivo: {dispositivo_txt})")
            print("Cargando modelo de profundidad (primera vez puede tardar)...")
            print(
                "Estabilización activa: rango global, suavizado temporal "
                "y filtro bilateral anti-fantasma."
            )
        estimador = EstimadorProfundidad(
            modelo,
            dispositivo=dispositivo_profundidad,
        )
        estimador.cargar()
        if mostrar_progreso:
            print(f"Modelo listo en {estimador.dispositivo}.")

    escritor = cv2.VideoWriter(
        str(ruta_escritura),
        cv2.VideoWriter_fourcc(*codec),
        fps,
        (dimensiones.ancho_sbs, dimensiones.alto_sbs),
    )
    if not escritor.isOpened():
        captura.release()
        if ruta_temporal is not None:
            _eliminar_archivo(ruta_temporal)
        raise RuntimeError(f"No se pudo crear el video de salida: {ruta_escritura}")

    fotograma_idx = 0
    try:
        while True:
            if _cancelacion_solicitada(cancelar):
                raise ConversionCancelada()

            if total > 0 and fotograma_idx >= total:
                break

            ok, frame = captura.read()
            if not ok:
                break

            if modo is ModoEstereo.PROFUNDIDAD and estimador is not None:
                sbs = procesar_fotograma_sbs_profundidad(
                    frame,
                    estimador,
                    float(offset_ojo),
                    dimensiones,
                    intensidad=intensidad_profundidad,
                )
            else:
                sbs = procesar_fotograma_sbs(frame, offset, dimensiones, ancho)
            escritor.write(sbs)
            fotograma_idx += 1

            if total > 0:
                _invoke_progreso_callback(
                    callback_progreso,
                    fotograma_idx,
                    total,
                    "procesando",
                )

            if mostrar_progreso and total > 0 and fotograma_idx % 30 == 0:
                porcentaje = 100.0 * fotograma_idx / total
                print(f"Progreso: {fotograma_idx}/{total} ({porcentaje:.1f}%)")
    except ConversionCancelada:
        if ruta_temporal is not None:
            _eliminar_archivo(ruta_temporal)
        else:
            _eliminar_archivo(ruta_salida)
        raise
    finally:
        captura.release()
        escritor.release()

    audio_incluido = False
    if ruta_temporal is not None:
        if mostrar_progreso:
            print("Codificando H.264 compatible (puede tardar un poco)...")
        try:
            audio_incluido = codificar_h264_compatible(
                ruta_escritura,
                ruta_salida,
                ruta_audio_origen=ruta_entrada,
                duracion_s=(total / fps if fps > 0 else None),
                callback_progreso=callback_progreso,
                cancelar=cancelar,
            )
        except ConversionCancelada:
            _eliminar_archivo(ruta_salida)
            raise
        finally:
            _eliminar_archivo(ruta_escritura)
    elif callback_progreso is not None:
        _invoke_progreso_callback(callback_progreso, 100, 100, "finalizado")

    if mostrar_progreso:
        detalle_audio = (
            "con audio estéreo (AAC)" if audio_incluido else "sin audio"
        )
        detalle_final = (
            "codificación final H.264 aplicada"
            if ruta_temporal is not None
            else "sin codificación final"
        )
        print(
            f"Listo: {fotograma_idx} fotogramas -> {ruta_salida} "
            f"({detalle_audio}, {detalle_final})"
        )

    return {
        "codificacion_final": ruta_temporal is not None,
        "fotogramas": fotograma_idx,
        "fps": fps,
        "ancho_entrada": ancho,
        "alto_entrada": alto,
        "ancho_salida": dimensiones.ancho_sbs,
        "alto_salida": dimensiones.alto_sbs,
        "offset": offset,
        "offset_ojo": offset_ojo,
        "offset_automatico": offset_automatico,
        "offset_porcentaje_ojo": round(
            porcentaje_disparidad(offset_ojo, dimensiones.ancho_ojo),
            2,
        ),
        "resolucion": resolucion.value,
        "modo": modo.value,
        "modelo_profundidad": (
            estimador.modelo.value if estimador is not None else None
        ),
        "intensidad_profundidad": intensidad_profundidad,
        "audio": audio_incluido,
    }
