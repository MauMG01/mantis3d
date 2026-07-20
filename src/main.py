"""Punto de entrada para la conversión de prueba 2D -> SBS."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .procesador import (
    ConversionCancelada,
    ModoEstereo,
    ResolucionSalida,
    convertir_video_a_sbs,
    ruta_salida_por_defecto,
)
from .profundidad import INTENSIDAD_PROFUNDIDAD_DEFECTO, ModeloProfundidad


def parsear_argumentos(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convierte video 2D a Side-by-Side (prototipo para Meta Quest 3).",
    )
    parser.add_argument(
        "-i",
        "--entrada",
        required=False,
        type=Path,
        help="Ruta del video 2D de entrada (mp4, avi, mov, etc.).",
    )
    parser.add_argument(
        "-o",
        "--salida",
        type=Path,
        default=None,
        help="Ruta del video SBS de salida. Por defecto: <nombre>_sbs o _sbs_depth.<ext>",
    )
    parser.add_argument(
        "--modo",
        type=ModoEstereo,
        choices=[m.value for m in ModoEstereo],
        default=ModoEstereo.FIJO,
        help=(
            "fijo: offset horizontal constante. "
            "profundidad: mapa de profundidad por fotograma (IA)."
        ),
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=None,
        metavar="PX",
        help=(
            "Separación máxima en píxeles (ancho del video de entrada). "
            "Si se omite, ~2 %% del ancho. En modo profundidad es la disparidad "
            "máxima en primer plano."
        ),
    )
    parser.add_argument(
        "-r",
        "--resolucion",
        type=ResolucionSalida,
        choices=[r.value for r in ResolucionSalida],
        default=ResolucionSalida.ORIGINAL,
        metavar="MODO",
        help=(
            "Resolución SBS: original (tamaño del origen), "
            "6k (6144x3072), 8k (7680x4320). Por defecto: original."
        ),
    )
    parser.add_argument(
        "--modelo",
        type=ModeloProfundidad,
        choices=[m.value for m in ModeloProfundidad],
        default=ModeloProfundidad.DEPTH_ANYTHING_SMALL,
        help="Modelo de profundidad (solo con --modo profundidad).",
    )
    parser.add_argument(
        "--intensidad",
        type=float,
        default=INTENSIDAD_PROFUNDIDAD_DEFECTO,
        metavar="FACTOR",
        help=(
            "Escala la disparidad del mapa de profundidad (0-2, por defecto "
            f"{INTENSIDAD_PROFUNDIDAD_DEFECTO}). Solo modo profundidad."
        ),
    )
    parser.add_argument(
        "--dispositivo",
        type=str,
        default="auto",
        choices=["auto", "cpu", "cuda", "mps"],
        help="Dispositivo para inferencia de profundidad (solo modo profundidad).",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Abrir la interfaz gráfica para seleccionar el video y opciones.",
    )
    parser.add_argument(
        "--sin-codificacion-final",
        action="store_false",
        dest="codificar_final",
        help="Omitir la codificación final H.264 compatible cuando se genera MP4.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parsear_argumentos(argv)
    if args.gui:
        from .gui import main as gui_main

        gui_main()
        return 0

    if args.entrada is None:
        print("Error: se requiere -i/--entrada cuando no se usa --gui.", file=sys.stderr)
        return 1

    entrada = args.entrada.resolve()
    modo = args.modo

    if not entrada.is_file():
        print(f"Error: no existe el archivo de entrada: {entrada}", file=sys.stderr)
        return 1

    if args.intensidad < 0 or args.intensidad > 2:
        print("Error: --intensidad debe estar entre 0 y 2.", file=sys.stderr)
        return 1

    salida = (args.salida or ruta_salida_por_defecto(entrada, modo)).resolve()
    dispositivo = None if args.dispositivo == "auto" else args.dispositivo

    print(f"Entrada:    {entrada}")
    print(f"Archivo:    {salida}")
    print(f"Modo:       {modo.value}")
    print(f"Resolución: {args.resolucion.value}")
    if modo is ModoEstereo.PROFUNDIDAD:
        print(f"Modelo:     {args.modelo.value}")
        print(f"Intensidad: {args.intensidad}")
    if args.offset is not None:
        print(f"Offset:     {args.offset} px (manual)")

    try:
        info = convertir_video_a_sbs(
            entrada,
            salida,
            offset=args.offset,
            resolucion=args.resolucion,
            modo=modo,
            modelo_profundidad=args.modelo,
            intensidad_profundidad=args.intensidad,
            dispositivo_profundidad=dispositivo,
            codificar_final=args.codificar_final,
        )
    except ConversionCancelada:
        print("Conversión cancelada.", file=sys.stderr)
        return 130
    except (FileNotFoundError, RuntimeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    if info.get("codificacion_final", True):
        audio = "estéreo AAC" if info.get("audio") else "sin pista de audio"
    else:
        audio = "sin pista de audio (codificación final omitida)"
    offset_txt = (
        f"{info['offset']} px entrada / {info['offset_ojo']} px por ojo "
        f"({info['offset_porcentaje_ojo']:.1f} %"
        f"{', auto' if info.get('offset_automatico') else ''})"
    )
    modo_txt = info["modo"]
    if info.get("modelo_profundidad"):
        modo_txt += f" ({info['modelo_profundidad']})"
    print(
        f"Resumen: {info['fotogramas']} fotogramas @ {info['fps']:.2f} fps, "
        f"{info['ancho_entrada']}x{info['alto_entrada']} -> "
        f"{info['ancho_salida']}x{info['alto_salida']} SBS [{info['resolucion']}] "
        f"(modo: {modo_txt}, offset máx: {offset_txt}, audio: {audio})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
