#!/usr/bin/env python3
"""Genera el icono de app MANTIS 3D.

Prioridad de fuente:
1. ``packaging/mantis_icon_source.png`` (cuadrado preferido, p. ej. de la web)
2. Recorte de cara desde ``mantis.png`` (banner de la GUI)
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BANNER = ROOT / "mantis.png"
SOURCE = ROOT / "packaging" / "mantis_icon_source.png"
OUT_DIR = ROOT / "packaging"
MASTER = OUT_DIR / "mantis_icon.png"
ICO = OUT_DIR / "mantis.ico"
ICNS = OUT_DIR / "mantis.icns"

# Fallback si solo hay banner panorámico.
FACE_WIDTH_MUL = 2.45
CONTENT_FIT = 0.90
BG = (6, 10, 8, 255)
MASTER_SIZE = 1024
ICO_SIZES = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
ICNS_SPECS = [
    (16, "icon_16x16.png"),
    (32, "icon_16x16@2x.png"),
    (32, "icon_32x32.png"),
    (64, "icon_32x32@2x.png"),
    (128, "icon_128x128.png"),
    (256, "icon_128x128@2x.png"),
    (256, "icon_256x256.png"),
    (512, "icon_256x256@2x.png"),
    (512, "icon_512x512.png"),
    (1024, "icon_512x512@2x.png"),
]


def compose_from_square(im: Image.Image) -> Image.Image:
    """Normaliza una imagen ya cuadrada (o casi) a RGBA centrada."""
    im = im.convert("RGBA")
    w, h = im.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    return im.crop((left, top, left + side, top + side))


def compose_from_banner(im: Image.Image) -> Image.Image:
    """Recorte ancho de la cara del banner GUI sobre cuadrado oscuro."""
    im = im.convert("RGBA")
    w, h = im.size
    cw = max(1, min(w, int(round(h * FACE_WIDTH_MUL))))
    left = max(0, (w - cw) // 2)
    crop = im.crop((left, 0, left + cw, h))

    side = cw
    canvas = Image.new("RGBA", (side, side), BG)
    nw = max(1, int(round(cw * CONTENT_FIT)))
    nh = max(1, int(round(h * CONTENT_FIT)))
    resized = crop.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas.paste(resized, ((side - nw) // 2, (side - nh) // 2), resized)
    return canvas


def load_face() -> Image.Image:
    if SOURCE.is_file():
        print(f"Fuente: {SOURCE}")
        return compose_from_square(Image.open(SOURCE))
    if BANNER.is_file():
        print(f"Fuente (banner): {BANNER}")
        return compose_from_banner(Image.open(BANNER))
    raise FileNotFoundError(
        f"No hay fuente de icono. Coloca {SOURCE.name} o {BANNER.name}."
    )


def write_master(face: Image.Image) -> Image.Image:
    master = face.resize((MASTER_SIZE, MASTER_SIZE), Image.Resampling.LANCZOS)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    master.save(MASTER, format="PNG")
    print(f"PNG: {MASTER}")
    return master


def write_ico(master: Image.Image) -> None:
    master.save(ICO, format="ICO", sizes=ICO_SIZES)
    print(f"ICO: {ICO}")


def write_icns(master: Image.Image) -> None:
    if sys.platform != "darwin":
        print("ICNS: omitido (solo macOS / iconutil)")
        return
    if shutil.which("iconutil") is None:
        print("ICNS: omitido (iconutil no encontrado)")
        return

    iconset = OUT_DIR / "mantis.iconset"
    if iconset.exists():
        shutil.rmtree(iconset)
    iconset.mkdir(parents=True)
    try:
        for size, name in ICNS_SPECS:
            resized = master.resize((size, size), Image.Resampling.LANCZOS)
            resized.save(iconset / name, format="PNG")
        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset), "-o", str(ICNS)],
            check=True,
        )
    finally:
        shutil.rmtree(iconset, ignore_errors=True)
    print(f"ICNS: {ICNS}")


def main() -> int:
    try:
        face = load_face()
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 1
    master = write_master(face)
    write_ico(master)
    write_icns(master)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
