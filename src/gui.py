"""Interfaz gráfica para la conversión de video 2D a 3D SBS."""

from __future__ import annotations

import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .procesador import (
    ConversionCancelada,
    ModoEstereo,
    ResolucionSalida,
    convertir_video_a_sbs,
    ruta_salida_por_defecto,
)
from .profundidad import (
    INTENSIDAD_PROFUNDIDAD_DEFECTO,
    ETIQUETAS_MODELO_PROFUNDIDAD,
    ModeloProfundidad,
    etiqueta_modelo_profundidad,
    modelo_profundidad_desde_etiqueta,
)


class ConversorGUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("MANTIS 3D")
        self.geometry("500x520")
        self.resizable(False, False)

        self.input_path: Path | None = None
        self.output_path: Path | None = None
        self.offset_value = tk.IntVar(value=0)
        self.offset_manual = tk.BooleanVar(value=False)
        self.codificar_final = tk.BooleanVar(value=True)
        self.resolution = tk.StringVar(value=ResolucionSalida.ORIGINAL.value)
        self.stereo_mode = tk.StringVar(value=ModoEstereo.PROFUNDIDAD.value)
        self.intensity = tk.DoubleVar(value=INTENSIDAD_PROFUNDIDAD_DEFECTO)
        self.depth_model = tk.StringVar(
            value=etiqueta_modelo_profundidad(ModeloProfundidad.DEPTH_ANYTHING_SMALL)
        )
        self.device = tk.StringVar(value="auto")
        self.progress_value = tk.DoubleVar(value=0.0)
        self.progress_label_text = tk.StringVar(value="")
        self.start_time: float | None = None
        self._recoding_start_time: float | None = None
        self.total_frames: int = 0
        self._cancel_event = threading.Event()
        self._conversion_thread: threading.Thread | None = None

        self._build_interface()

    def _build_interface(self) -> None:
        padding = {"padx": 12, "pady": 8}

        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, **padding)

        logo_path = Path(__file__).resolve().parents[1] / "mantis.png"
        logo_displayed = False
        if logo_path.is_file():
            try:
                try:
                    from PIL import Image, ImageTk
                except ImportError:
                    Image = None
                    ImageTk = None

                if Image is not None and ImageTk is not None:
                    raw_image = Image.open(logo_path)
                    target_width = 600
                    max_height = 160
                    width, height = raw_image.size
                    scale = target_width / width
                    new_width = int(width * scale)
                    new_height = int(height * scale)
                    if new_height > max_height:
                        scale = max_height / height
                        new_width = int(width * scale)
                        new_height = max_height
                    resized = raw_image.resize((new_width, new_height), Image.LANCZOS)
                    self.logo_image = ImageTk.PhotoImage(resized)
                else:
                    logo_image = tk.PhotoImage(file=str(logo_path))
                    max_width = 580
                    max_height = 140
                    if (
                        logo_image.width() > max_width
                        or logo_image.height() > max_height
                    ):
                        downscale = max(
                            max(1, logo_image.width() // max_width),
                            max(1, logo_image.height() // max_height),
                        )
                        logo_image = logo_image.subsample(downscale, downscale)
                    self.logo_image = logo_image

                ttk.Label(frame, image=self.logo_image).grid(
                    row=0,
                    column=0,
                    columnspan=2,
                    pady=(0, 12),
                    sticky="ew",
                )
                logo_displayed = True
            except (tk.TclError, OSError):
                self.logo_image = None

        if not logo_displayed:
            ttk.Label(
                frame,
                text="MANTIS 3D",
                font=("Segoe UI", 18, "bold"),
            ).grid(row=0, column=0, columnspan=2, pady=(0, 8))

        ttk.Label(frame, text="Video de entrada:").grid(row=1, column=0, sticky="w")
        self.input_entry = ttk.Entry(frame, width=56)
        self.input_entry.grid(row=2, column=0, sticky="w")
        ttk.Button(frame, text="Buscar...", command=self._choose_input).grid(
            row=2, column=1, sticky="e"
        )

        # El botón "Guardar como..." se muestra al pulsar "Convertir a 3D".

        ttk.Label(frame, text="Resolución de salida:").grid(row=4, column=0, sticky="w")
        self.resolution_combo = ttk.Combobox(
            frame,
            textvariable=self.resolution,
            values=[r.value for r in ResolucionSalida],
            state="readonly",
            width=14,
        )
        self.resolution_combo.grid(row=5, column=0, sticky="w")

        self.advanced_button = ttk.Button(
            frame,
            text="Opciones de IA avanzadas ▼",
            command=self._toggle_advanced,
        )
        self.advanced_button.grid(row=6, column=0, sticky="w", pady=(16, 0))

        self.advanced_frame = ttk.Frame(frame, relief="groove", borderwidth=1)
        self.advanced_frame.grid(
            row=7, column=0, columnspan=2, sticky="ew", pady=(8, 0)
        )
        self.advanced_frame.grid_remove()

        self.advanced_canvas = tk.Canvas(
            self.advanced_frame,
            height=220,
            highlightthickness=0,
        )
        self.advanced_scrollbar = ttk.Scrollbar(
            self.advanced_frame, orient="vertical", command=self.advanced_canvas.yview
        )

        self.advanced_canvas.configure(yscrollcommand=self.advanced_scrollbar.set)
        self.advanced_canvas.grid(row=0, column=0, sticky="nsew")
        self.advanced_scrollbar.grid(row=0, column=1, sticky="ns")

        self.advanced_frame.columnconfigure(0, weight=1)
        self.advanced_frame.rowconfigure(0, weight=1)

        self.advanced_options_frame = ttk.Frame(self.advanced_canvas)
        self.advanced_canvas_window = self.advanced_canvas.create_window(
            (0, 0), window=self.advanced_options_frame, anchor="nw"
        )

        self.advanced_options_frame.bind(
            "<Configure>",
            lambda event: self.advanced_canvas.configure(
                scrollregion=self.advanced_canvas.bbox("all")
            ),
        )
        self.advanced_canvas.bind(
            "<Configure>",
            lambda event: self.advanced_canvas.itemconfigure(
                self.advanced_canvas_window, width=event.width
            ),
        )

        self._build_advanced_options(self.advanced_options_frame)

        botones_frame = ttk.Frame(frame)
        botones_frame.grid(row=8, column=0, columnspan=2, pady=(16, 0))

        self.convert_button = ttk.Button(
            botones_frame,
            text="Convertir a 3D",
            command=self._on_convert,
            width=18,
        )
        self.convert_button.pack(side="left", padx=(0, 8))

        self.cancel_button = ttk.Button(
            botones_frame,
            text="Cancelar",
            command=self._on_cancel,
            width=12,
            state="disabled",
        )
        self.cancel_button.pack(side="left")

        ttk.Label(frame, text="Progreso:").grid(
            row=9, column=0, sticky="w", pady=(16, 0)
        )
        self.progress_bar = ttk.Progressbar(
            frame,
            variable=self.progress_value,
            maximum=100.0,
            mode="determinate",
            length=360,
        )
        self.progress_bar.grid(row=10, column=0, columnspan=2, sticky="ew", pady=(4, 0))

        self.progress_label = ttk.Label(
            frame,
            textvariable=self.progress_label_text,
            foreground="gray",
        )
        self.progress_label.grid(
            row=11, column=0, columnspan=2, sticky="w", pady=(4, 0)
        )

        frame.columnconfigure(0, weight=1)

    def _build_advanced_options(self, parent: ttk.Frame) -> None:
        ttk.Checkbutton(
            parent,
            text="Offset manual",
            variable=self.offset_manual,
            command=self._on_offset_toggle,
        ).grid(row=0, column=0, sticky="w", padx=8, pady=8)

        ttk.Label(parent, text="Offset (px):").grid(row=1, column=0, sticky="w", padx=8)
        self.offset_slider = ttk.Scale(
            parent,
            from_=0,
            to=512,
            orient="horizontal",
            variable=self.offset_value,
            command=lambda _: self._update_offset_label(),
            length=360,
        )
        self.offset_slider.grid(row=2, column=0, padx=8, pady=(0, 4), sticky="w")

        self.offset_label = ttk.Label(parent, text="Offset actual: 0 px")
        self.offset_label.grid(row=3, column=0, sticky="w", padx=8, pady=(0, 8))

        ttk.Label(parent, text="Intensidad (solo profundidad):").grid(
            row=4, column=0, sticky="w", padx=8
        )
        self.intensity_slider = ttk.Scale(
            parent,
            from_=0.0,
            to=2.0,
            orient="horizontal",
            variable=self.intensity,
            command=lambda _: self._update_intensity_label(),
            length=360,
        )
        self.intensity_slider.grid(row=5, column=0, padx=8, pady=(0, 4), sticky="w")
        self.intensity_label = ttk.Label(
            parent, text=f"Intensidad: {INTENSIDAD_PROFUNDIDAD_DEFECTO:.2f}"
        )
        self.intensity_label.grid(row=6, column=0, sticky="w", padx=8, pady=(0, 8))

        ttk.Label(parent, text="Modelo de profundidad:").grid(
            row=7, column=0, sticky="w", padx=8
        )
        self.model_combo = ttk.Combobox(
            parent,
            textvariable=self.depth_model,
            values=[ETIQUETAS_MODELO_PROFUNDIDAD[m] for m in ModeloProfundidad],
            state="readonly",
            width=42,
        )
        self.model_combo.grid(row=8, column=0, sticky="w", padx=8, pady=(0, 10))

        ttk.Label(parent, text="Inferencia:").grid(row=9, column=0, sticky="w", padx=8)
        self.device_combo = ttk.Combobox(
            parent,
            textvariable=self.device,
            values=["auto", "cpu", "cuda", "mps"],
            state="readonly",
            width=14,
        )
        self.device_combo.grid(row=10, column=0, sticky="w", padx=8, pady=(0, 10))

        ttk.Label(parent, text="Modo estéreo:").grid(
            row=11, column=0, sticky="w", padx=8
        )
        self.mode_combo = ttk.Combobox(
            parent,
            textvariable=self.stereo_mode,
            values=[m.value for m in ModoEstereo],
            state="readonly",
            width=14,
        )
        self.mode_combo.grid(row=12, column=0, sticky="w", padx=8, pady=(0, 10))
        self.mode_combo.bind("<<ComboboxSelected>>", lambda _event: self._set_default_output())

        ttk.Checkbutton(
            parent,
            text="Realizar codificación final H.264 compatible",
            variable=self.codificar_final,
        ).grid(row=13, column=0, sticky="w", padx=8, pady=(0, 10))

        self._on_offset_toggle()

    def _choose_input(self) -> None:
        ruta = filedialog.askopenfilename(
            title="Seleccionar video de entrada",
            filetypes=[
                ("Video files", "*.mp4 *.mov *.avi *.mkv"),
                ("Todos los archivos", "*"),
            ],
        )
        if not ruta:
            return
        self.input_path = Path(ruta)
        self.input_entry.delete(0, tk.END)
        self.input_entry.insert(0, ruta)
        self._set_default_output()

    def _set_default_output(self) -> None:
        if self.input_path is None:
            return
        self.output_path = ruta_salida_por_defecto(
            self.input_path,
            self.stereo_mode.get(),
        )

    def _choose_output(self) -> None:
        initialfile = None
        if self.input_path is not None:
            initialfile = ruta_salida_por_defecto(
                self.input_path,
                self.stereo_mode.get(),
            ).name
        ruta = filedialog.asksaveasfilename(
            title="Seleccionar archivo de salida",
            defaultextension=".mp4",
            initialfile=initialfile,
            filetypes=[("MP4 video", "*.mp4"), ("Todos los archivos", "*")],
        )
        if not ruta:
            return
        self.output_path = Path(ruta)

    def _toggle_advanced(self) -> None:
        if self.advanced_frame.winfo_ismapped():
            self.advanced_frame.grid_remove()
            self.advanced_button.config(text="Opciones avanzadas ▼")
        else:
            self.advanced_frame.grid()
            self.advanced_button.config(text="Opciones avanzadas ▲")

    def _on_offset_toggle(self) -> None:
        estado = "!disabled" if self.offset_manual.get() else "disabled"
        self.offset_slider.state([estado])
        self.offset_label.configure(text=f"Offset actual: {self.offset_value.get()} px")
        if not self.offset_manual.get():
            self.offset_value.set(0)
            self.offset_label.configure(text="Offset automático")

    def _update_offset_label(self) -> None:
        self.offset_label.configure(text=f"Offset actual: {self.offset_value.get()} px")

    def _update_intensity_label(self) -> None:
        self.intensity_label.configure(text=f"Intensidad: {self.intensity.get():.2f}")

    def _on_convert(self) -> None:
        if self.convert_button.instate(["disabled"]):
            return

        entrada = self.input_entry.get().strip()
        if not entrada:
            messagebox.showwarning("Advertencia", "Selecciona un video de entrada.")
            return

        self.input_path = Path(entrada)
        if not self.input_path.is_file():
            messagebox.showerror(
                "Error", "No se encontró el archivo de entrada seleccionado."
            )
            return

        # Pedir siempre la ruta de salida al usuario antes de convertir
        self._choose_output()
        if self.output_path is None:
            messagebox.showwarning("Advertencia", "Selecciona una ruta de salida.")
            return

        self.convert_button.state(["disabled"])
        self.cancel_button.state(["!disabled"])
        self._cancel_event.clear()
        self.progress_value.set(0.0)
        self.progress_label_text.set("Iniciando...")
        self.start_time = time.time()
        self.total_frames = 0
        self._conversion_thread = threading.Thread(
            target=self._run_conversion,
            daemon=True,
        )
        self._conversion_thread.start()

    def _on_cancel(self) -> None:
        if self._conversion_thread is not None and self._conversion_thread.is_alive():
            self._cancel_event.set()
            self.progress_label_text.set("Cancelando...")

    def _run_conversion(self) -> None:
        try:
            offset = (
                None if not self.offset_manual.get() else int(self.offset_value.get())
            )
            dispositivo = self.device.get()
            if dispositivo == "auto":
                dispositivo = None

            self._recoding_start_time = None

            def progress_callback(
                current: int,
                total: int,
                etapa: str = "procesando",
            ) -> None:
                if self._cancel_event.is_set():
                    return
                if self.start_time is None:
                    return

                if etapa == "codificacion":
                    percentage = 50.0 + 50.0 * current / total if total > 0 else 50.0
                    if self._recoding_start_time is None:
                        self._recoding_start_time = time.time()
                    if current > 0:
                        elapsed = time.time() - self._recoding_start_time
                        remaining_seconds = int(elapsed * (100.0 - current) / current)
                    else:
                        remaining_seconds = 0
                    self.after(
                        0,
                        self._update_progress,
                        percentage,
                        remaining_seconds,
                        etapa,
                    )
                elif etapa == "finalizado":
                    self.after(0, self._update_progress, 100, 0, etapa)
                else:
                    percentage = 50.0 * current / total if total > 0 else 0.0
                    elapsed = time.time() - self.start_time
                    if current > 0:
                        fps_actual = current / elapsed
                        remaining_frames = total - current
                        remaining_seconds = (
                            int(remaining_frames / fps_actual) if fps_actual > 0 else 0
                        )
                    else:
                        remaining_seconds = 0
                    self.after(
                        0,
                        self._update_progress,
                        percentage,
                        remaining_seconds,
                        etapa,
                    )

            info = convertir_video_a_sbs(
                self.input_path,
                self.output_path,
                offset=offset,
                resolucion=self.resolution.get(),
                modo=self.stereo_mode.get(),
                modelo_profundidad=modelo_profundidad_desde_etiqueta(
                    self.depth_model.get()
                ).value,
                intensidad_profundidad=self.intensity.get(),
                dispositivo_profundidad=dispositivo,
                codificar_final=self.codificar_final.get(),
                mostrar_progreso=False,
                callback_progreso=progress_callback,
                cancelar=self._cancel_event.is_set,
            )
            if self._cancel_event.is_set():
                raise ConversionCancelada()
            self.total_frames = info["fotogramas"]
            self.after(0, self._update_progress, 100, 0, "finalizado")
            self.after(
                0,
                messagebox.showinfo,
                "Conversión completa",
                f"Video convertido correctamente:\n{self.output_path}",
            )
        except ConversionCancelada:
            self.after(0, self._log, "Cancelado")
            self.after(
                0,
                messagebox.showinfo,
                "Cancelado",
                "La conversión fue cancelada.",
            )
        except Exception as error:
            self.after(0, self._log, f"Error: {error}")
            self.after(
                0,
                messagebox.showerror,
                "Error",
                f"No se pudo convertir el video:\n{error}",
            )
        finally:
            self.after(0, self.convert_button.state, ["!disabled"])
            self.after(0, self.cancel_button.state, ["disabled"])
            self._conversion_thread = None

    def _update_progress(
        self,
        percentage: float,
        remaining_seconds: int,
        etapa: str = "procesando",
    ) -> None:
        """Actualiza la barra de progreso y el label."""
        self.progress_value.set(min(percentage, 100.0))
        if percentage >= 100 or etapa == "finalizado":
            self.progress_label_text.set("Listo")
        else:
            mins, secs = divmod(remaining_seconds, 60)
            if etapa == "codificacion":
                texto = f"Codificando H.264: {percentage:.1f}% - Tiempo restante: {mins}m {secs}s"
            else:
                texto = f"Procesando fotogramas: {percentage:.1f}% - Tiempo restante: {mins}m {secs}s"
            self.progress_label_text.set(texto)

    def _log(self, texto: str) -> None:
        self.progress_label_text.set(texto)


def main() -> None:
    app = ConversorGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
