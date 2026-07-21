"""Textos de la interfaz gráfica (inglés / español)."""

from __future__ import annotations

from enum import Enum

from .profundidad import ModeloProfundidad


class Idioma(str, Enum):
    EN = "en"
    ES = "es"


IDIOMA_DEFECTO = Idioma.EN

_ETIQUETAS_MODELO: dict[Idioma, dict[ModeloProfundidad, str]] = {
    Idioma.EN: {
        ModeloProfundidad.DEPTH_ANYTHING_SMALL: "Depth Anything Small (fast)",
        ModeloProfundidad.DEPTH_ANYTHING_BASE: "Depth Anything Base (best quality, slow)",
        ModeloProfundidad.MIDAS_SMALL: "MiDaS Small (lightweight, testing)",
    },
    Idioma.ES: {
        ModeloProfundidad.DEPTH_ANYTHING_SMALL: "Depth Anything Small (rápido)",
        ModeloProfundidad.DEPTH_ANYTHING_BASE: "Depth Anything Base (mejor calidad, lento)",
        ModeloProfundidad.MIDAS_SMALL: "MiDaS Small (ligero, pruebas)",
    },
}

_MODO_ETIQUETAS: dict[Idioma, dict[str, str]] = {
    Idioma.EN: {"fijo": "fixed", "profundidad": "depth"},
    Idioma.ES: {"fijo": "fijo", "profundidad": "profundidad"},
}

_MODO_VALORES: dict[Idioma, dict[str, str]] = {
    Idioma.EN: {"fixed": "fijo", "depth": "profundidad"},
    Idioma.ES: {"fijo": "fijo", "profundidad": "profundidad"},
}

_TEXTOS: dict[Idioma, dict[str, str]] = {
    Idioma.EN: {
        "input_video": "Input video:",
        "browse": "Browse...",
        "output_resolution": "Output resolution:",
        "advanced_ai_show": "Advanced AI options ▼",
        "advanced_hide": "Advanced options ▲",
        "advanced_show": "Advanced options ▼",
        "convert": "Convert to 3D",
        "cancel": "Cancel",
        "progress": "Progress:",
        "manual_offset": "Manual offset",
        "offset_px": "Offset (px):",
        "offset_current": "Current offset: {value} px",
        "offset_auto": "Automatic offset",
        "intensity_depth": "Intensity (depth mode only):",
        "intensity_current": "Intensity: {value:.2f}",
        "depth_model": "Depth model:",
        "inference": "Inference:",
        "stereo_mode": "Stereo mode:",
        "h264_encode": "Final H.264 compatible encoding",
        "dialog_input_title": "Select input video",
        "dialog_output_title": "Select output file",
        "filetype_video": "Video files",
        "filetype_mp4": "MP4 video",
        "filetype_all": "All files",
        "warn_title": "Warning",
        "error_title": "Error",
        "success_title": "Conversion complete",
        "cancelled_title": "Cancelled",
        "warn_no_input": "Select an input video.",
        "error_input_missing": "The selected input file was not found.",
        "warn_no_output": "Select an output path.",
        "starting": "Starting...",
        "cancelling": "Cancelling...",
        "done": "Done",
        "cancelled": "Cancelled",
        "success_message": "Video converted successfully:\n{path}",
        "cancelled_message": "The conversion was cancelled.",
        "error_message": "Could not convert the video:\n{error}",
        "progress_encoding": "Encoding H.264: {pct:.1f}% - Time remaining: {mins}m {secs}s",
        "progress_frames": "Processing frames: {pct:.1f}% - Time remaining: {mins}m {secs}s",
        "switch_to_es": "Cambiar a Español",
        "switch_to_en": "Switch to English",
        "plan_demo": "Demo · {used}/{max} videos · 1 min · 1080",
        "plan_pro": "Pro · unlimited",
        "license_title": "License",
    },
    Idioma.ES: {
        "input_video": "Video de entrada:",
        "browse": "Buscar...",
        "output_resolution": "Resolución de salida:",
        "advanced_ai_show": "Opciones de IA avanzadas ▼",
        "advanced_hide": "Opciones avanzadas ▲",
        "advanced_show": "Opciones avanzadas ▼",
        "convert": "Convertir a 3D",
        "cancel": "Cancelar",
        "progress": "Progreso:",
        "manual_offset": "Offset manual",
        "offset_px": "Offset (px):",
        "offset_current": "Offset actual: {value} px",
        "offset_auto": "Offset automático",
        "intensity_depth": "Intensidad (solo profundidad):",
        "intensity_current": "Intensidad: {value:.2f}",
        "depth_model": "Modelo de profundidad:",
        "inference": "Inferencia:",
        "stereo_mode": "Modo estéreo:",
        "h264_encode": "Realizar codificación final H.264 compatible",
        "dialog_input_title": "Seleccionar video de entrada",
        "dialog_output_title": "Seleccionar archivo de salida",
        "filetype_video": "Archivos de video",
        "filetype_mp4": "Video MP4",
        "filetype_all": "Todos los archivos",
        "warn_title": "Advertencia",
        "error_title": "Error",
        "success_title": "Conversión completa",
        "cancelled_title": "Cancelado",
        "warn_no_input": "Selecciona un video de entrada.",
        "error_input_missing": "No se encontró el archivo de entrada seleccionado.",
        "warn_no_output": "Selecciona una ruta de salida.",
        "starting": "Iniciando...",
        "cancelling": "Cancelando...",
        "done": "Listo",
        "cancelled": "Cancelado",
        "success_message": "Video convertido correctamente:\n{path}",
        "cancelled_message": "La conversión fue cancelada.",
        "error_message": "No se pudo convertir el video:\n{error}",
        "progress_encoding": "Codificando H.264: {pct:.1f}% - Tiempo restante: {mins}m {secs}s",
        "progress_frames": "Procesando fotogramas: {pct:.1f}% - Tiempo restante: {mins}m {secs}s",
        "switch_to_es": "Cambiar a Español",
        "switch_to_en": "Switch to English",
        "plan_demo": "Demo · {used}/{max} videos · 1 min · 1080",
        "plan_pro": "Pro · ilimitado",
        "license_title": "Licencia",
    },
}


def t(clave: str, idioma: Idioma | str = IDIOMA_DEFECTO, **kwargs: object) -> str:
    lang = Idioma(idioma)
    texto = _TEXTOS[lang][clave]
    return texto.format(**kwargs) if kwargs else texto


def etiqueta_modelo(modelo: ModeloProfundidad | str, idioma: Idioma | str) -> str:
    return _ETIQUETAS_MODELO[Idioma(idioma)][ModeloProfundidad(modelo)]


def etiquetas_modelo_todas() -> list[tuple[ModeloProfundidad, str]]:
    pares: list[tuple[ModeloProfundidad, str]] = []
    for etiquetas in _ETIQUETAS_MODELO.values():
        for modelo, etiqueta in etiquetas.items():
            pares.append((modelo, etiqueta))
    return pares


def modo_mostrar(valor_interno: str, idioma: Idioma | str) -> str:
    return _MODO_ETIQUETAS[Idioma(idioma)][valor_interno]


def modo_interno(etiqueta_visible: str, idioma: Idioma | str) -> str:
    return _MODO_VALORES[Idioma(idioma)][etiqueta_visible]


def modos_visibles(idioma: Idioma | str) -> list[str]:
    lang = Idioma(idioma)
    return list(_MODO_VALORES[lang].keys())
