# Empaqueta MANTIS 3D para Windows 64-bit (onedir + zip).
# Ejecutar en PowerShell:  .\scripts\build_windows.ps1
$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python no esta en PATH. Instala Python 3.12 (64-bit) desde python.org y marca 'Add python.exe to PATH'."
}

if (-not (Test-Path (Join-Path $Root ".venv"))) {
    Write-Host "==> Creando .venv..."
    python -m venv .venv
}

$Activate = Join-Path $Root ".venv\Scripts\Activate.ps1"
. $Activate

Write-Host "==> Instalando dependencias..."
python -m pip install -U pip
pip install -r requirements.txt
pip install -r requirements-licensing.txt
pip install -r requirements-depth.txt
pip install "pyinstaller>=6.0" "Pillow>=10.0.0"

$HasNvidia = $false
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    nvidia-smi | Select-Object -First 8
    $HasNvidia = $true
}
if ($HasNvidia) {
    Write-Host "==> NVIDIA detectada: instalando PyTorch con CUDA 12.4..."
    pip install --upgrade torch torchvision --index-url https://download.pytorch.org/whl/cu124
    python -c "import torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"
} else {
    Write-Host "==> Sin NVIDIA en PATH: el build usara PyTorch CPU."
}

Write-Host "==> Generando icono de app (cara MANTIS → PNG/ICO)..."
python scripts/make_app_icon.py

Write-Host "==> Limpiando builds anteriores..."
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist\MANTIS3D") { Remove-Item -Recurse -Force "dist\MANTIS3D" }
if (Test-Path "dist\MANTIS3D-windows.zip") { Remove-Item -Force "dist\MANTIS3D-windows.zip" }

Write-Host "==> PyInstaller (puede tardar varios minutos)..."
pyinstaller packaging/mantis.spec --noconfirm --clean

$Exe = Join-Path $Root "dist\MANTIS3D\MANTIS3D.exe"
if (-not (Test-Path $Exe)) {
    throw "No se genero $Exe"
}

Copy-Item (Join-Path $Root "packaging\windows\LEEME.txt") (Join-Path $Root "dist\MANTIS3D\LEEME.txt")

Write-Host "==> Creando ZIP..."
Compress-Archive -Path (Join-Path $Root "dist\MANTIS3D") -DestinationPath (Join-Path $Root "dist\MANTIS3D-windows.zip") -Force

Write-Host ""
Write-Host "Listo:"
Write-Host "  App: $Exe"
Write-Host "  ZIP: $Root\dist\MANTIS3D-windows.zip"
Write-Host "Windows puede avisar SmartScreen (app sin firma). Usar 'Mas informacion' -> 'Ejecutar de todas formas'."
