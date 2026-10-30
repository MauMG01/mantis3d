# MANTIS 3D

Conversor de video **2D a Side-by-Side (SBS)** para ver contenido en **Meta Quest** y otros visores VR.

Genera un par estéreo (ojo izquierdo + ojo derecho) a partir de un video plano, con modo fijo o con mapa de profundidad por IA.

## Requisitos

- Python 3.10 o superior
- macOS, Windows o Linux
- Para modo **profundidad**: varios GB de espacio (PyTorch + modelos)

## Instalación

```bash
cd conversor3D
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-licensing.txt   # auth cliente (httpx, keyring, JWT)
pip install -r requirements-depth.txt       # solo para modo profundidad (IA)
```

## Descargas oficiales (v0.2.0)

| Plataforma | URL |
|------------|-----|
| macOS Apple Silicon | https://github.com/MauMG01/mantis3d/releases/download/v0.2.0/MANTIS3D.dmg |
| macOS Intel | https://github.com/MauMG01/mantis3d/releases/download/v0.2.0/MANTIS3D-intel.dmg |
| Windows 64-bit | https://pub-707e69a2701543ab9d2c32bc3098047a.r2.dev/MANTIS3D-windows.zip |

Mac = **GitHub Releases** · Windows = **Cloudflare R2** (público). Ya no usamos Google Drive.

Sitio: https://frolicking-babka-669c54.netlify.app · Release: https://github.com/MauMG01/mantis3d/releases/tag/v0.2.0

## Generar instaladores (desarrollo)

| Plataforma | Cómo generar | Resultado |
|------------|--------------|-----------|
| macOS Apple Silicon | `./scripts/build_mac.sh` | `dist/MANTIS3D.dmg` |
| macOS Intel (Monterey) | `./scripts/build_mac_intel.sh` | `dist/MANTIS3D-intel.dmg` |
| Windows 64-bit | En un PC Windows: `.\scripts\build_windows.ps1` | `dist/MANTIS3D-windows.zip` |

PyInstaller no cruza de Mac a Windows: el `.exe` hay que compilarlo **en Windows** (o con el workflow `.github/workflows/build-windows.yml`).

En Windows, descomprime el ZIP y ejecuta `MANTIS3D.exe`. SmartScreen puede avisar la primera vez (app sin firma).

Backend de suscripciones (opcional, para Stripe):

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # configura Stripe
uvicorn app.main:app --reload --port 8000
```

## Planes comerciales

| | **Demo** | **Pro** |
|---|----------|---------|
| Resoluciones | solo `1080` | `1080`, `4k`, `6k`, `8k` |
| Duración | máx. **1 minuto** | ilimitada |
| Conversiones | **2 videos** | ilimitadas |

Sin API configurada, la app opera en **Demo local** (contador en `~/.mantis3d/usage.json`).

Para pruebas de desarrollo:

```bash
export MANTIS_PLAN=demo   # o pro
export MANTIS_API_URL=http://127.0.0.1:8000   # cuando el backend esté activo
```

Detalles del backend: ver [`backend/README.md`](backend/README.md).

## Uso rápido

### Interfaz gráfica

```bash
python -m src.main --gui
```

1. Selecciona el video de entrada.
2. Elige resolución de salida (según tu plan).
3. (Opcional) Abre **Advanced AI options** para modelo, intensidad, modo estéreo, etc.
4. Pulsa **Convert to 3D** / **Convertir a 3D** y elige dónde guardar.
5. Usa **Cancel** para detener una conversión en curso.

### Línea de comandos

Modo fijo (rápido):

```bash
python -m src.main -i video.mp4 -o video_3d.mp4 --modo fijo -r 1080
```

Modo profundidad (mejor 3D, más lento):

```bash
python -m src.main -i video.mp4 -o video_3d.mp4 \
  --modo profundidad \
  --modelo depth-anything-base \
  --intensidad 0.5 \
  --dispositivo mps \
  -r 1080
```

### Opciones principales

| Opción | Descripción |
|--------|-------------|
| `--modo fijo` | Desplazamiento horizontal constante |
| `--modo profundidad` | Mapa de profundidad por fotograma (IA) |
| `--modelo` | `depth-anything-small`, `depth-anything-base`, `midas-small` |
| `--intensidad` | Escala de disparidad 0–2 (por defecto `0.45`) |
| `--dispositivo` | `auto`, `cpu`, `cuda`, `mps` |
| `-r` / `--resolucion` | `1080`, `4k`, `6k`, `8k` (Demo: solo `1080`) |
| `--offset` | Separación máx. en px (por defecto `24`) |
| `--modelo` | Por defecto `depth-anything-base` |

Los archivos de salida usan por defecto el sufijo `_sbs` (modo fijo) o `_sbs_depth` (modo profundidad).

## Arquitectura de licencias

```
App desktop  --JWT-->  FastAPI backend  --webhooks-->  Stripe
                |              |
                v              v
         límites Demo/Pro   PostgreSQL/SQLite
```

Librerías clave:

- **Cliente:** `httpx`, `keyring`, `PyJWT`
- **Backend:** `fastapi`, `stripe`, `python-jose`, `passlib`, `sqlalchemy`, `pydantic-settings`

## Reproducir en Meta Quest

Copia el MP4 resultante al visor (USB, Skybox, DeoVR, etc.). El video SBS debe mostrarse en modo **Side-by-Side 3D**.

## Pruebas

```bash
python prueba.py
```

## Estructura del proyecto

```
conversor3D/
├── src/
│   ├── main.py
│   ├── gui.py
│   ├── procesador.py
│   ├── profundidad.py
│   ├── i18n.py
│   └── licensing/      # Demo/Pro + cliente API
├── backend/            # FastAPI + Stripe
├── packaging/          # PyInstaller (Mac + Windows)
├── scripts/            # build_mac.sh, build_mac_intel.sh, build_windows.ps1
├── tests/
├── requirements.txt
├── requirements-licensing.txt
└── requirements-depth.txt
```

## Consejos para reducir fantasmas en VR

- Usa **modo profundidad** con **Depth Anything Base**.
- Mantén **intensidad** en 0.4–0.5 en escenas con mucho movimiento.
- Prueba **modo fijo** si la escena tiene acción continua.
