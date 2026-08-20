#!/usr/bin/env python3
"""Verifica que ningún binario del .app exija un macOS más nuevo que el permitido."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path


def minos_of(path: Path) -> str | None:
    try:
        out = subprocess.check_output(
            ["otool", "-l", str(path)],
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    match = re.search(r"minos\s+([0-9.]+)", out)
    return match.group(1) if match else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("app_path", type=Path)
    parser.add_argument("--max-major", type=int, default=12)
    args = parser.parse_args()

    app = args.app_path
    if not app.is_dir():
        print(f"No existe: {app}", file=sys.stderr)
        return 1

    too_new: list[tuple[str, str]] = []
    checked = 0
    for path in app.rglob("*"):
        if not path.is_file():
            continue
        is_lib = path.suffix in {".dylib", ".so"}
        is_ffmpeg = "ffmpeg" in path.name.lower()
        is_exec = os.access(path, os.X_OK) and path.suffix == ""
        if not (is_lib or is_ffmpeg or is_exec):
            continue
        minos = minos_of(path)
        if not minos:
            continue
        checked += 1
        major = int(minos.split(".", 1)[0])
        if major > args.max_major:
            too_new.append((minos, str(path.relative_to(app))))

    print(f"Binarios con minos revisados: {checked}")
    if too_new:
        print(
            f"ERROR: {len(too_new)} archivo(s) requieren macOS > {args.max_major}.x:",
            file=sys.stderr,
        )
        for minos, rel in sorted(too_new)[:40]:
            print(f"  minos {minos}: {rel}", file=sys.stderr)
        if len(too_new) > 40:
            print(f"  ... +{len(too_new) - 40} más", file=sys.stderr)
        return 1

    print(f"OK: ningún binario exige macOS > {args.max_major}.x")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
