"""Estimación de profundidad monocular (Depth Anything / MiDaS)."""

from __future__ import annotations

from enum import Enum
from typing import Any

import cv2
import numpy as np

# Ancho máximo para inferir profundidad (se escala el mapa al tamaño del ojo después).
ANCHO_INFERENCIA_DEFECTO = 518

# Estabilización anti-fantasma (suavizado temporal + rango global + filtro bilateral).
INTENSIDAD_PROFUNDIDAD_DEFECTO = 0.5
FRAMES_CALIBRACION_GLOBAL = 24
SUAVIZADO_TEMPORAL_DEFECTO = 0.35
BILATERAL_DIAMETRO = 5
BILATERAL_SIGMA_COLOR = 0.08
BILATERAL_SIGMA_SPACE = 5.0


class ModeloProfundidad(str, Enum):
    DEPTH_ANYTHING_SMALL = "depth-anything-small"
    DEPTH_ANYTHING_BASE = "depth-anything-base"
    MIDAS_SMALL = "midas-small"


ETIQUETAS_MODELO_PROFUNDIDAD: dict[ModeloProfundidad, str] = {
    ModeloProfundidad.DEPTH_ANYTHING_SMALL: "Depth Anything Small (rápido)",
    ModeloProfundidad.DEPTH_ANYTHING_BASE: "Depth Anything Base (mejor calidad, lento)",
    ModeloProfundidad.MIDAS_SMALL: "MiDaS Small (ligero, pruebas)",
}


def etiqueta_modelo_profundidad(modelo: ModeloProfundidad | str) -> str:
    return ETIQUETAS_MODELO_PROFUNDIDAD[ModeloProfundidad(modelo)]


def modelo_profundidad_desde_etiqueta(texto: str) -> ModeloProfundidad:
    """Resuelve la etiqueta amigable de la GUI (o el valor CLI) al enum."""
    for modelo, etiqueta in ETIQUETAS_MODELO_PROFUNDIDAD.items():
        if texto == etiqueta:
            return modelo
    return ModeloProfundidad(texto)


_HF_MODELOS: dict[ModeloProfundidad, str] = {
    ModeloProfundidad.DEPTH_ANYTHING_SMALL: "depth-anything/Depth-Anything-V2-Small-hf",
    ModeloProfundidad.DEPTH_ANYTHING_BASE: "depth-anything/Depth-Anything-V2-Base-hf",
}

# Si True, proximidad = 1 - norma (mapa crudo con valores altos = lejos).
_INVERTIR_PROXIMIDAD: dict[ModeloProfundidad, bool] = {
    ModeloProfundidad.DEPTH_ANYTHING_SMALL: True,
    ModeloProfundidad.DEPTH_ANYTHING_BASE: True,
    ModeloProfundidad.MIDAS_SMALL: False,
}


def _dispositivo_torch(solicitado: str | None) -> str:
    import torch

    if solicitado and solicitado != "auto":
        return solicitado
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _falta_dependencias_profundidad() -> str | None:
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
    except ImportError:
        return (
            "Faltan dependencias de profundidad. Instala con:\n"
            "  pip install -r requirements-depth.txt"
        )
    return None


class EstimadorProfundidad:
    """Carga el modelo una vez y estima mapas de proximidad (1=cerca, 0=lejos)."""

    def __init__(
        self,
        modelo: ModeloProfundidad | str = ModeloProfundidad.DEPTH_ANYTHING_SMALL,
        *,
        dispositivo: str | None = None,
        ancho_inferencia: int = ANCHO_INFERENCIA_DEFECTO,
        suavizado_temporal: float = SUAVIZADO_TEMPORAL_DEFECTO,
        filtro_bilateral: bool = True,
        calibracion_global: bool = True,
        frames_calibracion: int = FRAMES_CALIBRACION_GLOBAL,
    ) -> None:
        mensaje = _falta_dependencias_profundidad()
        if mensaje:
            raise RuntimeError(mensaje)

        self.modelo = ModeloProfundidad(modelo)
        self.dispositivo = _dispositivo_torch(dispositivo)
        self.ancho_inferencia = max(64, ancho_inferencia)
        self.suavizado_temporal = min(max(float(suavizado_temporal), 0.05), 1.0)
        self.filtro_bilateral = filtro_bilateral
        self.calibracion_global = calibracion_global
        self.frames_calibracion = max(1, frames_calibracion)
        self._backend: str | None = None
        self._pipe: Any = None
        self._midas: Any = None
        self._midas_transform: Any = None
        self._prox_anterior: np.ndarray | None = None
        self._lo_global: float | None = None
        self._hi_global: float | None = None
        self._muestras_calibracion: list[tuple[float, float]] = []

    def cargar(self) -> None:
        """Carga pesos del modelo en memoria (idempotente)."""
        self._cargar()

    def _cargar(self) -> None:
        if self._backend is not None:
            return

        if self.modelo is ModeloProfundidad.MIDAS_SMALL:
            self._cargar_midas()
        else:
            self._cargar_depth_anything()

    def _cargar_depth_anything(self) -> None:
        from transformers import pipeline

        model_id = _HF_MODELOS[self.modelo]
        if self.dispositivo == "cpu":
            device: int | str = -1
        elif self.dispositivo == "mps":
            device = "mps"
        else:
            device = 0
        self._pipe = pipeline(
            task="depth-estimation",
            model=model_id,
            device=device,
        )
        self._backend = "depth-anything"

    def _cargar_midas(self) -> None:
        import torch

        self._midas = torch.hub.load("intel-isl/MiDaS", "MiDaS_small")
        self._midas_transform = torch.hub.load("intel-isl/MiDaS", "transforms").small_transform
        self._midas.to(self.dispositivo)
        self._midas.eval()
        self._backend = "midas"

    def _reducir_para_inferencia(self, frame_bgr: np.ndarray) -> tuple[np.ndarray, float]:
        alto, ancho = frame_bgr.shape[:2]
        if ancho <= self.ancho_inferencia:
            return frame_bgr, 1.0
        escala = self.ancho_inferencia / ancho
        nuevo_ancho = self.ancho_inferencia
        nuevo_alto = max(1, int(round(alto * escala)))
        reducido = cv2.resize(
            frame_bgr,
            (nuevo_ancho, nuevo_alto),
            interpolation=cv2.INTER_AREA,
        )
        return reducido, escala

    def _profundidad_cruda(self, frame_bgr: np.ndarray) -> np.ndarray:
        from PIL import Image

        self._cargar()
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        imagen = Image.fromarray(rgb)

        if self._backend == "depth-anything":
            salida = self._pipe(imagen)
            profundidad = np.array(salida["depth"], dtype=np.float32)
            return profundidad

        import torch

        entrada = self._midas_transform(rgb).to(self.dispositivo)
        with torch.no_grad():
            prediccion = self._midas(entrada)
            prediccion = torch.nn.functional.interpolate(
                prediccion.unsqueeze(1),
                size=rgb.shape[:2],
                mode="bicubic",
                align_corners=False,
            ).squeeze()
        return prediccion.cpu().numpy().astype(np.float32)

    @staticmethod
    def _percentiles_profundidad(profundidad: np.ndarray) -> tuple[float, float]:
        lo = float(np.percentile(profundidad, 2))
        hi = float(np.percentile(profundidad, 98))
        return lo, hi

    def _actualizar_calibracion_global(self, lo: float, hi: float) -> None:
        if not self.calibracion_global or self._lo_global is not None:
            return
        self._muestras_calibracion.append((lo, hi))
        if len(self._muestras_calibracion) >= self.frames_calibracion:
            muestras = self._muestras_calibracion
            self._lo_global = float(np.mean([m[0] for m in muestras]))
            self._hi_global = float(np.mean([m[1] for m in muestras]))

    def _a_proximidad(
        self,
        profundidad: np.ndarray,
        invertir: bool,
    ) -> np.ndarray:
        lo, hi = self._percentiles_profundidad(profundidad)
        self._actualizar_calibracion_global(lo, hi)

        if (
            self.calibracion_global
            and self._lo_global is not None
            and self._hi_global is not None
        ):
            lo, hi = self._lo_global, self._hi_global

        if hi - lo < 1e-6:
            return np.zeros_like(profundidad, dtype=np.float32)
        norm = np.clip((profundidad - lo) / (hi - lo), 0.0, 1.0)
        if invertir:
            norm = 1.0 - norm
        return norm.astype(np.float32)

    def _filtro_bilateral_proximidad(self, prox: np.ndarray) -> np.ndarray:
        if not self.filtro_bilateral:
            return prox
        return cv2.bilateralFilter(
            prox,
            d=BILATERAL_DIAMETRO,
            sigmaColor=BILATERAL_SIGMA_COLOR,
            sigmaSpace=BILATERAL_SIGMA_SPACE,
        )

    def _suavizar_temporal(self, prox: np.ndarray) -> np.ndarray:
        if self._prox_anterior is None or self._prox_anterior.shape != prox.shape:
            return prox
        alpha = self.suavizado_temporal
        return (alpha * prox + (1.0 - alpha) * self._prox_anterior).astype(np.float32)

    def estimar_proximidad(
        self,
        frame_bgr: np.ndarray,
        ancho_destino: int,
        alto_destino: int,
    ) -> np.ndarray:
        """
        Mapa 0..1 del tamaño del ojo (1 = primer plano, más disparidad estéreo).

        Aplica normalización global (calibrada al inicio), filtro bilateral y
        suavizado temporal para reducir fantasmas en objetos en movimiento.
        """
        reducido, _ = self._reducir_para_inferencia(frame_bgr)
        cruda = self._profundidad_cruda(reducido)
        prox = self._a_proximidad(cruda, _INVERTIR_PROXIMIDAD[self.modelo])
        prox = self._filtro_bilateral_proximidad(prox)
        if prox.shape[:2] != (alto_destino, ancho_destino):
            prox = cv2.resize(
                prox,
                (ancho_destino, alto_destino),
                interpolation=cv2.INTER_LINEAR,
            )
        prox = self._suavizar_temporal(prox)
        self._prox_anterior = prox.copy()
        return prox
