# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec para MANTIS 3D (macOS .app y Windows onedir)."""

from __future__ import annotations

import sys
from pathlib import Path

from PyInstaller.building.api import COLLECT, EXE, PYZ
from PyInstaller.building.build_main import Analysis
from PyInstaller.utils.hooks import collect_all, collect_data_files

ROOT = Path(SPECPATH).resolve().parent
BLOCK_CIPHER = None
IS_DARWIN = sys.platform == "darwin"
APP_NAME = "MANTIS 3D" if IS_DARWIN else "MANTIS3D"

datas = [
    (str(ROOT / "mantis.png"), "."),
]
_icon_png = ROOT / "packaging" / "mantis_icon.png"
if _icon_png.is_file():
    datas.append((str(_icon_png), "."))
for _api_url in (
    ROOT / "mantis_api_url.txt",
    ROOT / "packaging" / "mantis_api_url.txt",
):
    if _api_url.is_file():
        datas.append((str(_api_url), "."))
        break
binaries = []
hiddenimports = [
    "PIL",
    "PIL.Image",
    "PIL.ImageTk",
    "keyring.backends",
    "keyring.backends.macOS",
    "keyring.backends.Windows",
    "keyring.backends.SecretService",
    "imageio_ffmpeg",
    "cv2",
    "numpy",
    "src",
    "src.main",
    "src.gui",
    "src.procesador",
    "src.profundidad",
    "src.i18n",
    "src.preferencias",
    "src.licensing",
    "src.runtime_paths",
]

datas += collect_data_files("imageio_ffmpeg")

for pkg in ("torch", "torchvision", "transformers", "timm", "accelerate"):
    try:
        pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
        datas += pkg_datas
        binaries += pkg_binaries
        hiddenimports += pkg_hidden
    except Exception as exc:  # noqa: BLE001
        print(f"[mantis.spec] Aviso: no se pudo coleccionar {pkg}: {exc}")

icon_path = ROOT / "packaging" / "mantis.ico"
icon = str(icon_path) if icon_path.is_file() else None
icns_path = ROOT / "packaging" / "mantis.icns"
bundle_icon = str(icns_path) if icns_path.is_file() else None

a = Analysis(
    [str(ROOT / "packaging" / "run_mantis.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter.test",
        "matplotlib",
        "scipy",
        "IPython",
        "jupyter",
        "notebook",
    ],
    cipher=BLOCK_CIPHER,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=BLOCK_CIPHER)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)

if IS_DARWIN:
    from PyInstaller.building.osx import BUNDLE

    app = BUNDLE(
        coll,
        name="MANTIS 3D.app",
        icon=bundle_icon,
        bundle_identifier="com.mantis3d.app",
        info_plist={
            "CFBundleName": "MANTIS 3D",
            "CFBundleDisplayName": "MANTIS 3D",
            "CFBundleShortVersionString": "0.1.0",
            "CFBundleVersion": "0.1.0",
            "NSHighResolutionCapable": True,
            "LSRequiresAquaSystemAppearance": False,
        },
    )
