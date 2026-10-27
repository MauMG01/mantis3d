"""MANTIS IMAGE 3D: galería de imágenes 2D → SBS 3D al vuelo."""

from __future__ import annotations

import re
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

import cv2
from PIL import Image, ImageTk

from .image_sbs import (
    EXTENSIONES,
    INTENSIDAD_IMAGEN_PROFUNDIDAD_DEFECTO,
    PORCENTAJE_OFFSET_IMAGEN,
    cargar_bgr,
    exportar_carpeta_quest,
    guardar_bgr,
    imagen_a_sbs,
    listar_imagenes,
)
from .procesador import ModoEstereo, ResolucionSalida, calcular_offset_recomendado
from .profundidad import (
    MODELO_PROFUNDIDAD_DEFECTO,
    ModeloProfundidad,
)

# Etiqueta UI → valor ResolucionSalida
RESOLUCIONES_UI: dict[str, ResolucionSalida] = {
    "Original": ResolucionSalida.ORIGINAL,
    "SBS 1080 (3840×1080)": ResolucionSalida.SBS_1080,
    "SBS 4K (7680×2160)": ResolucionSalida.SBS_4K,
}


class ImageSbsApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("MANTIS IMAGE 3D")
        self.root.geometry("1100x720")
        self.root.minsize(800, 560)

        self.imagenes: list[Path] = []
        self.carpeta_origen: Path | None = None
        self.indice = 0
        self.sbs_actual = None
        self.foto_tk = None
        self.estimador = None
        self._gen = 0
        self._busy = False
        self._export_cancel = False

        self.modo = tk.StringVar(value=ModoEstereo.PROFUNDIDAD.value)
        self.modelo = tk.StringVar(value=MODELO_PROFUNDIDAD_DEFECTO.value)
        self.offset = tk.IntVar(value=24)
        self.intensidad = tk.DoubleVar(value=INTENSIDAD_IMAGEN_PROFUNDIDAD_DEFECTO)
        self.conservar_proporcion = tk.BooleanVar(value=True)
        self.resolucion_ui = tk.StringVar(value="SBS 1080 (3840×1080)")
        self.estado = tk.StringVar(value="Abre una carpeta con fotos para empezar.")

        self._build()
        self.root.bind("<Left>", lambda _e: self._navegar(-1))
        self.root.bind("<Right>", lambda _e: self._navegar(1))

    def _build(self) -> None:
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill="x")

        ttk.Button(top, text="Abrir carpeta…", command=self._abrir_carpeta).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(top, text="◀ Anterior", command=lambda: self._navegar(-1)).pack(
            side="left", padx=2
        )
        ttk.Button(top, text="Siguiente ▶", command=lambda: self._navegar(1)).pack(
            side="left", padx=2
        )
        ttk.Button(top, text="Guardar SBS…", command=self._guardar).pack(
            side="left", padx=(12, 0)
        )
        ttk.Button(
            top,
            text="Exportar carpeta a 3D (Quest)…",
            command=self._exportar_quest,
        ).pack(side="left", padx=(12, 0))

        opts = ttk.LabelFrame(self.root, text="Conversión al vuelo", padding=10)
        opts.pack(fill="x", padx=10, pady=(0, 8))

        row1 = ttk.Frame(opts)
        row1.pack(fill="x", pady=2)
        ttk.Label(row1, text="Modo:").pack(side="left")
        ttk.Radiobutton(
            row1,
            text="Fijo (instantáneo)",
            value=ModoEstereo.FIJO.value,
            variable=self.modo,
            command=self._reconvertir,
        ).pack(side="left", padx=(6, 12))
        ttk.Radiobutton(
            row1,
            text="Profundidad IA",
            value=ModoEstereo.PROFUNDIDAD.value,
            variable=self.modo,
            command=self._on_modo_ia,
        ).pack(side="left")
        ttk.Checkbutton(
            row1,
            text="Conservar proporciones",
            variable=self.conservar_proporcion,
            command=self._reconvertir,
        ).pack(side="left", padx=(16, 0))
        ttk.Label(row1, text="Salida:").pack(side="left", padx=(16, 4))
        ttk.Combobox(
            row1,
            textvariable=self.resolucion_ui,
            values=list(RESOLUCIONES_UI.keys()),
            width=22,
            state="readonly",
        ).pack(side="left")
        ttk.Button(row1, text="Aplicar salida", command=self._reconvertir).pack(
            side="left", padx=(6, 0)
        )

        row2 = ttk.Frame(opts)
        row2.pack(fill="x", pady=6)
        ttk.Label(row2, text="Offset px:").pack(side="left")
        scale_off = ttk.Scale(
            row2,
            from_=0,
            to=120,
            orient="horizontal",
            variable=self.offset,
            command=lambda _v: self._reconvertir_debounce(),
        )
        scale_off.pack(side="left", fill="x", expand=True, padx=8)
        self.lbl_offset = ttk.Label(row2, text="24", width=4)
        self.lbl_offset.pack(side="left")

        row3 = ttk.Frame(opts)
        row3.pack(fill="x", pady=2)
        ttk.Label(row3, text="Intensidad IA:").pack(side="left")
        ttk.Scale(
            row3,
            from_=0.0,
            to=2.0,
            orient="horizontal",
            variable=self.intensidad,
            command=lambda _v: self._reconvertir_debounce(),
        ).pack(side="left", fill="x", expand=True, padx=8)
        self.lbl_intensidad = ttk.Label(row3, text="45%", width=5)
        self.lbl_intensidad.pack(side="left")
        ttk.Label(row3, text="Modelo:").pack(side="left", padx=(8, 4))
        ttk.Combobox(
            row3,
            textvariable=self.modelo,
            values=[m.value for m in ModeloProfundidad],
            width=28,
            state="readonly",
        ).pack(side="left")
        ttk.Button(row3, text="Aplicar", command=self._reconvertir).pack(
            side="left", padx=(8, 0)
        )

        self.canvas = tk.Label(self.root, background="#0b0f12", foreground="#9aada2")
        self.canvas.pack(fill="both", expand=True, padx=10, pady=(0, 4))
        self.canvas.bind("<Configure>", lambda _e: self._mostrar_preview())

        ttk.Label(self.root, textvariable=self.estado, padding=(10, 4)).pack(fill="x")

        self._debounce_id = None

    def _resolucion_actual(self) -> ResolucionSalida:
        return RESOLUCIONES_UI.get(
            self.resolucion_ui.get(),
            ResolucionSalida.SBS_1080,
        )

    def _etiqueta_resolucion(self) -> str:
        return self.resolucion_ui.get() or "SBS 1080 (3840×1080)"

    def _offset_para_imagen(self, ancho: int) -> int:
        return calcular_offset_recomendado(
            ancho,
            porcentaje=PORCENTAJE_OFFSET_IMAGEN,
        )

    def _on_modo_ia(self) -> None:
        if self.modo.get() == ModoEstereo.PROFUNDIDAD.value and self.imagenes:
            frame = cargar_bgr(self.imagenes[self.indice])
            self.offset.set(self._offset_para_imagen(frame.shape[1]))
        self._reconvertir()

    def _abrir_carpeta(self) -> None:
        ruta = filedialog.askdirectory(title="Carpeta de imágenes")
        if not ruta:
            return
        try:
            self.imagenes = listar_imagenes(Path(ruta))
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Error", str(exc))
            return
        if not self.imagenes:
            messagebox.showinfo(
                "Sin imágenes",
                f"No hay archivos {', '.join(sorted(EXTENSIONES))} en esa carpeta.",
            )
            return
        self.carpeta_origen = Path(ruta).expanduser().resolve()
        self.indice = 0
        frame = cargar_bgr(self.imagenes[0])
        self.offset.set(self._offset_para_imagen(frame.shape[1]))
        self._reconvertir()

    def _navegar(self, delta: int) -> None:
        if not self.imagenes or self._busy:
            return
        self.indice = (self.indice + delta) % len(self.imagenes)
        self._reconvertir()

    def _actualizar_lbl_intensidad(self) -> None:
        pct = int(round(float(self.intensidad.get()) * 100))
        self.lbl_intensidad.config(text=f"{pct}%")

    def _reconvertir_debounce(self) -> None:
        self.lbl_offset.config(text=str(int(self.offset.get())))
        self._actualizar_lbl_intensidad()
        if self._debounce_id is not None:
            self.root.after_cancel(self._debounce_id)
        self._debounce_id = self.root.after(180, self._reconvertir)

    def _reconvertir(self) -> None:
        if not self.imagenes:
            return
        if self._busy and self.modo.get() == ModoEstereo.PROFUNDIDAD.value:
            return

        self._gen += 1
        gen = self._gen
        ruta = self.imagenes[self.indice]
        modo = self.modo.get()
        offset = int(self.offset.get())
        intensidad = float(self.intensidad.get())
        modelo = self.modelo.get()
        conservar = bool(self.conservar_proporcion.get())
        resolucion = self._resolucion_actual()
        self.lbl_offset.config(text=str(offset))
        self.estado.set(f"Convirtiendo {ruta.name}…")

        def worker() -> None:
            t0 = time.perf_counter()
            try:
                frame = cargar_bgr(ruta)
                sbs, estimador = imagen_a_sbs(
                    frame,
                    modo=modo,
                    resolucion=resolucion,
                    offset=offset,
                    intensidad=intensidad,
                    estimador=self.estimador,
                    modelo=modelo,
                    dispositivo="auto",
                    conservar_proporcion=conservar,
                )
                ms = (time.perf_counter() - t0) * 1000.0
                err = None
            except Exception as exc:  # noqa: BLE001
                sbs, estimador, ms, err = None, self.estimador, 0.0, exc

            def done() -> None:
                if gen != self._gen:
                    return
                self._busy = False
                if err is not None:
                    self.estado.set(f"Error: {err}")
                    messagebox.showerror("Conversión", str(err))
                    return
                self.estimador = estimador
                self.sbs_actual = sbs
                h, w = sbs.shape[:2]
                self.estado.set(
                    f"{self.indice + 1}/{len(self.imagenes)}  ·  {ruta.name}  ·  "
                    f"{modo}  ·  {w}×{h}  ·  {ms:.0f} ms"
                )
                self._mostrar_preview()

            self.root.after(0, done)

        self._busy = True
        threading.Thread(target=worker, daemon=True).start()

    def _mostrar_preview(self) -> None:
        if self.sbs_actual is None:
            self.canvas.config(image="", text="SBS preview (L | R)")
            return
        rgb = cv2.cvtColor(self.sbs_actual, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb)
        cw = max(self.canvas.winfo_width(), 100)
        ch = max(self.canvas.winfo_height(), 100)
        img.thumbnail((cw - 8, ch - 8), Image.Resampling.LANCZOS)
        self.foto_tk = ImageTk.PhotoImage(img)
        self.canvas.config(image=self.foto_tk, text="")

    def _guardar(self) -> None:
        if self.sbs_actual is None or not self.imagenes:
            messagebox.showinfo("Guardar", "No hay imagen SBS para guardar.")
            return
        origen = self.imagenes[self.indice]
        sugerido = origen.with_name(f"{origen.stem}_sbs.jpg")
        destino = filedialog.asksaveasfilename(
            title="Guardar SBS",
            defaultextension=".jpg",
            initialfile=sugerido.name,
            filetypes=[("JPEG", "*.jpg"), ("PNG", "*.png"), ("Todos", "*.*")],
        )
        if not destino:
            return
        try:
            guardar_bgr(Path(destino), self.sbs_actual)
            self.estado.set(f"Guardado: {destino}")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Guardar", str(exc))

    @staticmethod
    def _nombre_carpeta_seguro(nombre: str) -> str:
        nombre = nombre.strip()
        nombre = re.sub(r'[<>:"/\\|?*]+', "_", nombre)
        nombre = nombre.strip(" .")
        return nombre or "Quest_SBS_3D"

    def _exportar_quest(self) -> None:
        if self._busy:
            messagebox.showinfo("Exportar", "Espera a que termine la conversión actual.")
            return

        origen = self.carpeta_origen
        if origen is None or not self.imagenes:
            ruta = filedialog.askdirectory(title="Carpeta de imágenes a exportar")
            if not ruta:
                return
            origen = Path(ruta).expanduser().resolve()
            try:
                imagenes = listar_imagenes(origen)
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("Exportar", str(exc))
                return
            if not imagenes:
                messagebox.showinfo(
                    "Sin imágenes",
                    f"No hay archivos {', '.join(sorted(EXTENSIONES))} en esa carpeta.",
                )
                return
        else:
            imagenes = self.imagenes

        ubicacion = filedialog.askdirectory(
            title="¿Dónde guardar la carpeta 3D para Quest?"
        )
        if not ubicacion:
            return

        sugerido = f"{origen.name}_SBS_Quest"
        nombre = simpledialog.askstring(
            "Nombre de la carpeta",
            f"Nombre de la carpeta de salida ({self._etiqueta_resolucion()}):",
            initialvalue=sugerido,
            parent=self.root,
        )
        if nombre is None:
            return
        nombre = self._nombre_carpeta_seguro(nombre)
        destino = Path(ubicacion).expanduser().resolve() / nombre

        if destino.exists() and any(destino.iterdir()):
            if not messagebox.askyesno(
                "Carpeta existente",
                f"«{destino}» ya existe y tiene archivos.\n"
                "¿Continuar y añadir/sobrescribir las SBS?",
            ):
                return

        modo = self.modo.get()
        offset = int(self.offset.get())
        intensidad = float(self.intensidad.get())
        modelo = self.modelo.get()
        conservar = bool(self.conservar_proporcion.get())
        resolucion = self._resolucion_actual()
        etiqueta_res = self._etiqueta_resolucion()
        total = len(imagenes)
        self._export_cancel = False
        self._busy = True
        self.estado.set(f"Exportando 0/{total} para Quest…")

        def progreso(i: int, n: int, name: str) -> None:
            self.root.after(
                0,
                lambda: self.estado.set(f"Exportando {i}/{n} · {name}"),
            )

        def worker() -> None:
            try:
                resultado = exportar_carpeta_quest(
                    origen,
                    destino,
                    modo=modo,
                    resolucion=resolucion,
                    offset=offset,
                    intensidad=intensidad,
                    estimador=self.estimador,
                    modelo=modelo,
                    dispositivo="auto",
                    conservar_proporcion=conservar,
                    progreso=progreso,
                    cancelar=lambda: self._export_cancel,
                )
                err = None
            except Exception as exc:  # noqa: BLE001
                resultado, err = None, exc

            def done() -> None:
                self._busy = False
                if err is not None:
                    self.estado.set(f"Error al exportar: {err}")
                    messagebox.showerror("Exportar Quest", str(err))
                    return
                self.estimador = resultado.get("estimador") or self.estimador
                ok = resultado["ok"]
                errores = resultado["errores"]
                msg = (
                    f"Listo para Quest: {ok}/{resultado['total']} imágenes\n"
                    f"Carpeta: {resultado['destino']}\n"
                    f"Formato: {etiqueta_res} JPEG\n\n"
                    "Copia esa carpeta al Quest y ábrela en un visor SBS "
                    "(DeoVR, Skybox, etc.)."
                )
                if errores:
                    msg += "\n\nErrores:\n" + "\n".join(errores[:8])
                    if len(errores) > 8:
                        msg += f"\n… y {len(errores) - 8} más"
                self.estado.set(
                    f"Exportado Quest: {ok}/{resultado['total']} → {resultado['destino']}"
                )
                messagebox.showinfo("Exportar Quest", msg)

            self.root.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    ImageSbsApp().run()


if __name__ == "__main__":
    main()
