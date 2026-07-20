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
pip install -r requirements-depth.txt   # solo para modo profundidad (IA)
```

## Uso rápido

### Interfaz gráfica

```bash
python -m src.main --gui
```

1. Selecciona el video de entrada.
2. Elige resolución de salida.
3. (Opcional) Abre **Opciones de IA avanzadas** para modelo, intensidad, modo estéreo, etc.
4. Pulsa **Convertir a 3D** y elige dónde guardar.
5. Usa **Cancelar** para detener una conversión en curso.

### Línea de comandos

Modo fijo (rápido):

```bash
python -m src.main -i video.mp4 -o video_3d.mp4 --modo fijo
```

Modo profundidad (mejor 3D, más lento):

```bash
python -m src.main -i video.mp4 -o video_3d.mp4 \
  --modo profundidad \
  --modelo depth-anything-base \
  --intensidad 0.5 \
  --dispositivo mps
```

### Opciones principales

| Opción | Descripción |
|--------|-------------|
| `--modo fijo` | Desplazamiento horizontal constante |
| `--modo profundidad` | Mapa de profundidad por fotograma (IA) |
| `--modelo` | `depth-anything-small`, `depth-anything-base`, `midas-small` |
| `--intensidad` | Escala de disparidad 0–2 (por defecto `0.5`) |
| `--dispositivo` | `auto`, `cpu`, `cuda`, `mps` |
| `-r` / `--resolucion` | `original`, `6k`, `8k` |

Los archivos de salida usan por defecto el sufijo `_sbs` (modo fijo) o `_sbs_depth` (modo profundidad).

## Reproducir en Meta Quest

Copia el MP4 resultante al visor (USB, Skybox, DeoVR, etc.). El video SBS debe mostrarse en modo **Side-by-Side 3D**.

## Pruebas

```bash
python prueba.py
```

Ejecuta tests unitarios e integración básica (modo fijo, sin descargar modelos de IA).

## Estructura del proyecto

```
conversor3D/
├── src/
│   ├── main.py        # CLI
│   ├── gui.py         # Interfaz gráfica
│   ├── procesador.py  # Pipeline de video SBS
│   └── profundidad.py # Modelos Depth Anything / MiDaS
├── tests/
├── requirements.txt
└── requirements-depth.txt
```

## Consejos para reducir fantasmas en VR

- Usa **modo profundidad** con **Depth Anything Base**.
- Mantén **intensidad** en 0.4–0.5 en escenas con mucho movimiento.
- Prueba **modo fijo** si la escena tiene acción continua.
