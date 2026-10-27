#!/usr/bin/env bash
# Empaqueta MANTIS 3D como .app (y opcionalmente .dmg) en macOS.
# Compatible con macOS Monterey (12) y posteriores (Apple Silicon).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export MACOSX_DEPLOYMENT_TARGET="${MACOSX_DEPLOYMENT_TARGET:-12.0}"
MAX_MINOS_MAJOR="${MAX_MINOS_MAJOR:-12}"

if [[ ! -d .venv ]]; then
  echo "No existe .venv. Crea el entorno e instala dependencias primero."
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> macOS deployment target: $MACOSX_DEPLOYMENT_TARGET"
echo "==> Asegurando OpenCV compatible con Monterey (<4.11)..."
pip install -q "opencv-python>=4.8.0,<4.11"

echo "==> Instalando PyInstaller..."
pip install -q "pyinstaller>=6.0"

echo "==> Generando icono de app (cara MANTIS → PNG/ICO/ICNS)..."
python scripts/make_app_icon.py

echo "==> Limpiando builds anteriores..."
rm -rf build dist/MANTIS\ 3D dist/MANTIS\ 3D.app dist/MANTIS3D.dmg

echo "==> Generando MANTIS 3D.app (puede tardar varios minutos)..."
pyinstaller packaging/mantis.spec --noconfirm --clean

APP_PATH="$ROOT/dist/MANTIS 3D.app"
if [[ ! -d "$APP_PATH" ]]; then
  echo "Error: no se generó $APP_PATH"
  exit 1
fi

if [[ -f "$ROOT/scripts/verify_macos_minos.py" ]]; then
  echo "==> Verificando compatibilidad macOS (minos <= $MAX_MINOS_MAJOR)..."
  python "$ROOT/scripts/verify_macos_minos.py" "$APP_PATH" --max-major "$MAX_MINOS_MAJOR"
fi

echo "==> Creando DMG..."
hdiutil create \
  -volname "MANTIS 3D" \
  -srcfolder "$APP_PATH" \
  -ov \
  -format UDZO \
  "$ROOT/dist/MANTIS3D.dmg"

echo ""
echo "Listo:"
echo "  App: $APP_PATH"
echo "  DMG: $ROOT/dist/MANTIS3D.dmg"
echo "  Mínimo: macOS ${MACOSX_DEPLOYMENT_TARGET}+ (Monterey), Apple Silicon (arm64)"
echo ""
echo "Primera apertura en macOS: clic derecho en la app → Abrir"
echo "(Gatekeeper bloquea apps sin firmar la primera vez)."
