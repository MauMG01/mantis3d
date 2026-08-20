#!/usr/bin/env bash
# Empaqueta MANTIS 3D como .app/.dmg para Mac Intel (x86_64), macOS Monterey 12+.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export MACOSX_DEPLOYMENT_TARGET="${MACOSX_DEPLOYMENT_TARGET:-12.0}"
MAX_MINOS_MAJOR="${MAX_MINOS_MAJOR:-12}"
VENV="${ROOT}/.venv-intel"

if [[ ! -d "$VENV" ]]; then
  echo "No existe .venv-intel."
  exit 1
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"

ARCH="$(python -c 'import platform; print(platform.machine())')"
if [[ "$ARCH" != "x86_64" ]]; then
  echo "El venv no es x86_64 (es $ARCH). Reactívalo bajo Rosetta."
  exit 1
fi

echo "==> Arquitectura: $ARCH"
echo "==> macOS deployment target: $MACOSX_DEPLOYMENT_TARGET"
pip install -q "opencv-python>=4.8.0,<4.11" "numpy==1.26.4"
pip install -q "pyinstaller>=6.0"

rm -rf build/MANTIS\ 3D build/mantis dist/MANTIS\ 3D-intel dist/MANTIS\ 3D-intel.app dist/MANTIS3D-intel.dmg
rm -rf dist/MANTIS\ 3D dist/MANTIS\ 3D.app

echo "==> Generando MANTIS 3D.app (x86_64)..."
arch -x86_64 pyinstaller packaging/mantis.spec --noconfirm --clean \
  --distpath dist \
  --workpath build

APP_PATH="$ROOT/dist/MANTIS 3D.app"
if [[ ! -d "$APP_PATH" ]]; then
  echo "Error: no se generó $APP_PATH"
  exit 1
fi

MAIN_BIN="$APP_PATH/Contents/MacOS/MANTIS 3D"
if [[ -f "$MAIN_BIN" ]]; then
  file "$MAIN_BIN"
  if ! file "$MAIN_BIN" | grep -q "x86_64"; then
    echo "ERROR: el binario no es x86_64"
    exit 1
  fi
fi

if [[ -f "$ROOT/scripts/verify_macos_minos.py" ]]; then
  python "$ROOT/scripts/verify_macos_minos.py" "$APP_PATH" --max-major "$MAX_MINOS_MAJOR"
fi

INTEL_APP="$ROOT/dist/MANTIS 3D-intel.app"
INTEL_DMG="$ROOT/dist/MANTIS3D-intel.dmg"
rm -rf "$INTEL_APP"
mv "$APP_PATH" "$INTEL_APP"
rm -rf "$ROOT/dist/MANTIS 3D"

hdiutil create \
  -volname "MANTIS 3D (Intel)" \
  -srcfolder "$INTEL_APP" \
  -ov \
  -format UDZO \
  "$INTEL_DMG"

echo "Listo (Intel / Monterey): $INTEL_APP"
echo "  DMG: $INTEL_DMG"
