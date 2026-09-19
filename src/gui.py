"""Interfaz gráfica para la conversión de video 2D a 3D SBS."""

from __future__ import annotations

import threading
import time
import webbrowser
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .i18n import (
    Idioma,
    etiqueta_modelo,
    modo_interno,
    modo_mostrar,
    modos_visibles,
    t,
)
from .licensing import (
    DEMO_MAX_CONVERSIONES,
    LicenciaError,
    LicensingAPIError,
    LicensingClient,
    Plan,
    borrar_tokens,
    cargar_access_token,
    estado_suscripcion_actual,
    guardar_tokens,
    registrar_conversion_exitosa,
    resoluciones_para_plan,
    validar_conversion,
)
from .preferencias import cargar_idioma, guardar_idioma
from .runtime_paths import resource_path
from .procesador import (
    ConversionCancelada,
    ModoEstereo,
    ResolucionSalida,
    convertir_video_a_sbs,
    ruta_salida_por_defecto,
)
from .profundidad import (
    INTENSIDAD_PROFUNDIDAD_DEFECTO,
    MODELO_PROFUNDIDAD_DEFECTO,
    OFFSET_PROFUNDIDAD_DEFECTO,
    ModeloProfundidad,
    modelo_profundidad_desde_etiqueta,
)


class ConversorGUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("MANTIS 3D")
        self.geometry("520x640")
        self.minsize(520, 640)
        self.resizable(False, False)

        self._idioma = cargar_idioma()
        self._modo_interno = ModoEstereo.PROFUNDIDAD.value
        self._modelo_interno = MODELO_PROFUNDIDAD_DEFECTO
        self._auth_busy = False
        self._licensing = LicensingClient()

        self.input_path: Path | None = None
        self.output_path: Path | None = None
        self.offset_value = tk.IntVar(value=OFFSET_PROFUNDIDAD_DEFECTO)
        self.offset_manual = tk.BooleanVar(value=True)
        self.codificar_final = tk.BooleanVar(value=True)
        self.resolution = tk.StringVar(value=ResolucionSalida.SBS_1080.value)
        self.stereo_mode = tk.StringVar(
            value=modo_mostrar(self._modo_interno, self._idioma)
        )
        self.intensity = tk.DoubleVar(value=INTENSIDAD_PROFUNDIDAD_DEFECTO)
        self.depth_model = tk.StringVar(
            value=etiqueta_modelo(self._modelo_interno, self._idioma)
        )
        self.device = tk.StringVar(value="auto")
        self.progress_value = tk.DoubleVar(value=0.0)
        self.progress_label_text = tk.StringVar(value="")
        self.plan_label_text = tk.StringVar(value="")
        self.start_time: float | None = None
        self._recoding_start_time: float | None = None
        self.total_frames: int = 0
        self._cancel_event = threading.Event()
        self._conversion_thread: threading.Thread | None = None
        self._estado_licencia = estado_suscripcion_actual()

        self._build_interface()
        self._apply_language()
        self._refresh_plan_ui()

    def _build_interface(self) -> None:
        padding = {"padx": 12, "pady": 8}

        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, **padding)
        frame.columnconfigure(0, weight=1)

        logo_path = resource_path("mantis.png")
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
                    # Ancho útil ≈ ventana 520 − padding horizontal
                    target_width = 496
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
                    max_width = 496
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

        self._label_input = ttk.Label(frame, text="")
        self._label_input.grid(row=1, column=0, columnspan=2, sticky="w")

        input_row = ttk.Frame(frame)
        input_row.grid(row=2, column=0, columnspan=2, sticky="ew")
        self._browse_button = ttk.Button(input_row, text="", command=self._choose_input)
        self._browse_button.pack(side="right")
        self.input_entry = ttk.Entry(input_row)
        self.input_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self._label_resolution = ttk.Label(frame, text="")
        self._label_resolution.grid(row=4, column=0, sticky="w")
        self.resolution_combo = ttk.Combobox(
            frame,
            textvariable=self.resolution,
            values=[],
            state="readonly",
            width=14,
        )
        self.resolution_combo.grid(row=5, column=0, sticky="w")

        self._label_plan = ttk.Label(
            frame,
            textvariable=self.plan_label_text,
            foreground="#555555",
        )
        self._label_plan.grid(row=5, column=1, sticky="e", padx=(8, 0))

        account = ttk.Frame(frame)
        account.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        account.columnconfigure(0, weight=1)
        account.columnconfigure(1, weight=1)

        self.login_button = ttk.Button(
            account,
            text="",
            command=self._on_login,
        )
        self.login_button.grid(row=0, column=0, sticky="ew", padx=(0, 3), pady=(0, 3))

        self.upgrade_button = ttk.Button(
            account,
            text="",
            command=self._on_upgrade,
        )
        self.upgrade_button.grid(row=0, column=1, sticky="ew", padx=(3, 0), pady=(0, 3))

        self.logout_button = ttk.Button(
            account,
            text="",
            command=self._on_logout,
        )
        self.logout_button.grid(row=1, column=0, sticky="ew", padx=(0, 3))

        self.refresh_plan_button = ttk.Button(
            account,
            text="",
            command=self._on_refresh_plan,
        )
        self.refresh_plan_button.grid(row=1, column=1, sticky="ew", padx=(3, 0))

        self.advanced_button = ttk.Button(
            frame,
            text="",
            command=self._toggle_advanced,
        )
        self.advanced_button.grid(row=7, column=0, sticky="w", pady=(12, 0))

        self.advanced_frame = ttk.Frame(frame, relief="groove", borderwidth=1)
        self.advanced_frame.grid(
            row=8, column=0, columnspan=2, sticky="ew", pady=(8, 0)
        )
        self.advanced_frame.grid_remove()

        self.advanced_canvas = tk.Canvas(
            self.advanced_frame,
            height=140,
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
        self.bind("<Button-1>", self._on_global_click, add="+")

        botones_frame = ttk.Frame(frame)
        botones_frame.grid(row=9, column=0, columnspan=2, pady=(16, 0))

        self.convert_button = ttk.Button(
            botones_frame,
            text="",
            command=self._on_convert,
            width=18,
        )
        self.convert_button.pack(side="left", padx=(0, 8))

        self.cancel_button = ttk.Button(
            botones_frame,
            text="",
            command=self._on_cancel,
            width=12,
            state="disabled",
        )
        self.cancel_button.pack(side="left")

        self._label_progress = ttk.Label(frame, text="")
        self._label_progress.grid(row=10, column=0, sticky="w", pady=(16, 0))
        self.progress_bar = ttk.Progressbar(
            frame,
            variable=self.progress_value,
            maximum=100.0,
            mode="determinate",
            length=360,
        )
        self.progress_bar.grid(row=11, column=0, columnspan=2, sticky="ew", pady=(4, 0))

        self.progress_label = ttk.Label(
            frame,
            textvariable=self.progress_label_text,
            foreground="gray",
        )
        self.progress_label.grid(
            row=12, column=0, columnspan=2, sticky="w", pady=(4, 0)
        )

        footer = ttk.Frame(frame)
        footer.grid(row=13, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        footer.columnconfigure(0, weight=1)

        self.language_button = ttk.Button(
            footer,
            text="",
            command=self._toggle_language,
            width=18,
        )
        self.language_button.grid(row=0, column=1, sticky="e")

    def _build_advanced_options(self, parent: ttk.Frame) -> None:
        self._chk_offset_manual = ttk.Checkbutton(
            parent,
            text="",
            variable=self.offset_manual,
            command=self._on_offset_toggle,
        )
        self._chk_offset_manual.grid(row=0, column=0, sticky="w", padx=8, pady=8)

        self._label_offset_px = ttk.Label(parent, text="")
        self._label_offset_px.grid(row=1, column=0, sticky="w", padx=8)
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

        self.offset_label = ttk.Label(parent, text="")
        self.offset_label.grid(row=3, column=0, sticky="w", padx=8, pady=(0, 8))

        self._label_intensity = ttk.Label(parent, text="")
        self._label_intensity.grid(row=4, column=0, sticky="w", padx=8)
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
        self.intensity_label = ttk.Label(parent, text="")
        self.intensity_label.grid(row=6, column=0, sticky="w", padx=8, pady=(0, 8))

        self._label_depth_model = ttk.Label(parent, text="")
        self._label_depth_model.grid(row=7, column=0, sticky="w", padx=8)
        self.model_combo = ttk.Combobox(
            parent,
            textvariable=self.depth_model,
            values=[],
            state="readonly",
            width=42,
        )
        self.model_combo.grid(row=8, column=0, sticky="w", padx=8, pady=(0, 10))
        self.model_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._sync_modelo_interno(),
        )

        self._label_inference = ttk.Label(parent, text="")
        self._label_inference.grid(row=9, column=0, sticky="w", padx=8)
        self.device_combo = ttk.Combobox(
            parent,
            textvariable=self.device,
            values=["auto", "cpu", "cuda", "mps"],
            state="readonly",
            width=14,
        )
        self.device_combo.grid(row=10, column=0, sticky="w", padx=8, pady=(0, 10))

        self._label_stereo_mode = ttk.Label(parent, text="")
        self._label_stereo_mode.grid(row=11, column=0, sticky="w", padx=8)
        self.mode_combo = ttk.Combobox(
            parent,
            textvariable=self.stereo_mode,
            values=[],
            state="readonly",
            width=14,
        )
        self.mode_combo.grid(row=12, column=0, sticky="w", padx=8, pady=(0, 10))
        self.mode_combo.bind("<<ComboboxSelected>>", self._on_mode_selected)

        self._chk_h264 = ttk.Checkbutton(
            parent,
            text="",
            variable=self.codificar_final,
        )
        self._chk_h264.grid(row=13, column=0, sticky="w", padx=8, pady=(0, 10))

        self._on_offset_toggle()

    def _lang(self) -> Idioma:
        return self._idioma

    def _apply_language(self) -> None:
        lang = self._lang()
        advanced_expanded = self.advanced_frame.winfo_ismapped()

        self._label_input.config(text=t("input_video", lang))
        self._browse_button.config(text=t("browse", lang))
        self._label_resolution.config(text=t("output_resolution", lang))
        if advanced_expanded:
            self.advanced_button.config(text=t("advanced_hide", lang))
        else:
            self.advanced_button.config(text=t("advanced_ai_show", lang))
        self.convert_button.config(text=t("convert", lang))
        self.cancel_button.config(text=t("cancel", lang))
        self._label_progress.config(text=t("progress", lang))
        self.login_button.config(text=t("login", lang))
        self.upgrade_button.config(text=t("upgrade_pro", lang))
        self.refresh_plan_button.config(text=t("refresh_plan", lang))
        self.logout_button.config(text=t("logout", lang))
        self.language_button.config(
            text=t("switch_to_es", lang)
            if lang is Idioma.EN
            else t("switch_to_en", lang)
        )

        self._chk_offset_manual.config(text=t("manual_offset", lang))
        self._label_offset_px.config(text=t("offset_px", lang))
        self._label_intensity.config(text=t("intensity_depth", lang))
        self._label_depth_model.config(text=t("depth_model", lang))
        self._label_inference.config(text=t("inference", lang))
        self._label_stereo_mode.config(text=t("stereo_mode", lang))
        self._chk_h264.config(text=t("h264_encode", lang))

        self.model_combo.configure(
            values=[etiqueta_modelo(m, lang) for m in ModeloProfundidad]
        )
        self.depth_model.set(etiqueta_modelo(self._modelo_interno, lang))

        self.mode_combo.configure(values=modos_visibles(lang))
        self.stereo_mode.set(modo_mostrar(self._modo_interno, lang))

        self._on_offset_toggle()
        self._update_intensity_label()
        self._refresh_plan_ui()

    def _refresh_plan_ui(self) -> None:
        lang = self._lang()
        estado = self._estado_licencia
        permitidas = [r.value for r in resoluciones_para_plan(estado.plan)]
        self.resolution_combo.configure(values=permitidas)
        if self.resolution.get() not in permitidas and permitidas:
            self.resolution.set(permitidas[0])

        if estado.plan is Plan.PRO:
            plan_txt = t("plan_pro", lang)
        else:
            plan_txt = t(
                "plan_demo",
                lang,
                used=estado.conversiones_usadas,
                max=DEMO_MAX_CONVERSIONES,
            )
        if estado.email:
            self.plan_label_text.set(
                t("plan_signed_in", lang, plan=plan_txt, email=estado.email)
            )
        else:
            self.plan_label_text.set(plan_txt)

        token = cargar_access_token()
        # Solo contar sesión si el token sigue siendo usable (API o email conocido).
        logged_in = bool(token) and (
            estado.fuente == "api" or bool(estado.email)
        )
        api_ok = self._licensing.disponible
        busy = "disabled" if self._auth_busy else "normal"

        self.login_button.configure(
            state="disabled" if (logged_in or not api_ok or self._auth_busy) else busy
        )
        self.logout_button.configure(
            state="disabled" if (not logged_in or self._auth_busy) else busy
        )
        if estado.plan is Plan.PRO:
            # En Pro no hay upgrade: solo gestión de facturación si hay sesión.
            if logged_in:
                self.upgrade_button.configure(
                    text=t("manage_billing", lang),
                    state=busy,
                )
                self.upgrade_button.grid()
            else:
                self.upgrade_button.grid_remove()
        else:
            self.upgrade_button.grid()
            self.upgrade_button.configure(
                text=t("upgrade_pro", lang),
                state="disabled" if (not api_ok or self._auth_busy) else busy,
            )
        self.refresh_plan_button.configure(
            state="disabled" if (not logged_in or self._auth_busy) else busy
        )

    def _set_auth_busy(self, busy: bool) -> None:
        self._auth_busy = busy
        self._refresh_plan_ui()

    def _on_login(self) -> None:
        lang = self._lang()
        if not self._licensing.disponible:
            messagebox.showwarning(
                t("license_title", lang), t("api_unavailable", lang)
            )
            return
        self._show_auth_dialog()

    def _show_auth_dialog(self) -> None:
        lang = self._lang()
        dialog = tk.Toplevel(self)
        dialog.title(t("account_title", lang))
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=16)
        frame.grid(row=0, column=0)

        ttk.Label(frame, text=t("email", lang)).grid(row=0, column=0, sticky="w")
        email_var = tk.StringVar()
        email_entry = ttk.Entry(frame, textvariable=email_var, width=36)
        email_entry.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(2, 8))

        ttk.Label(frame, text=t("password", lang)).grid(row=2, column=0, sticky="w")
        password_var = tk.StringVar()
        password_entry = ttk.Entry(frame, textvariable=password_var, show="*", width=36)
        password_entry.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(2, 12))

        status_var = tk.StringVar(value="")
        status = ttk.Label(frame, textvariable=status_var, foreground="#555555")
        status.grid(row=5, column=0, columnspan=2, sticky="w", pady=(8, 0))

        def _cerrar() -> None:
            dialog.grab_release()
            dialog.destroy()

        def _run_auth(accion: str) -> None:
            email = email_var.get().strip()
            password = password_var.get()
            if not email or not password:
                status_var.set(t("auth_error", lang, error="Email / password required"))
                return
            status_var.set(t("auth_busy", lang))
            self._set_auth_busy(True)

            def worker() -> None:
                try:
                    if accion == "login":
                        datos = self._licensing.login(email, password)
                        mensaje = t("login_success", lang, email=email)
                    else:
                        datos = self._licensing.register(email, password)
                        mensaje = t("register_success", lang)
                    guardar_tokens(
                        str(datos["access_token"]),
                        datos.get("refresh_token"),
                    )
                    estado = estado_suscripcion_actual(self._licensing)

                    def ok() -> None:
                        self._estado_licencia = estado
                        self._set_auth_busy(False)
                        _cerrar()
                        messagebox.showinfo(t("account_title", lang), mensaje)
                        self._refresh_plan_ui()

                    self.after(0, ok)
                except Exception as error:  # noqa: BLE001
                    detalle = str(error)[:200]

                    def fail() -> None:
                        self._set_auth_busy(False)
                        status_var.set(
                            t("auth_error", lang, error=detalle)
                        )

                    self.after(0, fail)

            threading.Thread(target=worker, daemon=True).start()

        botones = ttk.Frame(frame)
        botones.grid(row=4, column=0, columnspan=2, sticky="ew")
        ttk.Button(
            botones,
            text=t("login", lang),
            command=lambda: _run_auth("login"),
            width=14,
        ).pack(side="left")
        ttk.Button(
            botones,
            text=t("register", lang),
            command=lambda: _run_auth("register"),
            width=16,
        ).pack(side="left", padx=(8, 0))

        email_entry.focus_set()
        dialog.protocol("WM_DELETE_WINDOW", _cerrar)
        dialog.bind("<Return>", lambda _e: _run_auth("login"))

    def _on_logout(self) -> None:
        lang = self._lang()
        borrar_tokens()
        self._estado_licencia = estado_suscripcion_actual(self._licensing)
        self._refresh_plan_ui()
        messagebox.showinfo(t("account_title", lang), t("logout_success", lang))

    def _on_refresh_plan(self) -> None:
        lang = self._lang()
        if not cargar_access_token():
            messagebox.showwarning(
                t("license_title", lang), t("login_required_upgrade", lang)
            )
            return
        self._set_auth_busy(True)

        def worker() -> None:
            try:
                estado = estado_suscripcion_actual(self._licensing)

                def ok() -> None:
                    self._estado_licencia = estado
                    self._set_auth_busy(False)
                    self._refresh_plan_ui()

                self.after(0, ok)
            except Exception as error:  # noqa: BLE001
                detalle = str(error)

                def fail() -> None:
                    self._set_auth_busy(False)
                    messagebox.showerror(
                        t("error_title", lang),
                        t("auth_error", lang, error=detalle),
                    )

                self.after(0, fail)

        threading.Thread(target=worker, daemon=True).start()

    def _on_upgrade(self) -> None:
        lang = self._lang()
        if not self._licensing.disponible:
            messagebox.showwarning(
                t("license_title", lang), t("api_unavailable", lang)
            )
            return
        token = cargar_access_token()
        if not token:
            messagebox.showwarning(
                t("license_title", lang), t("login_required_upgrade", lang)
            )
            self._show_auth_dialog()
            return

        self._set_auth_busy(True)
        es_pro = self._estado_licencia.plan is Plan.PRO

        def worker() -> None:
            try:
                if es_pro:
                    url = self._licensing.crear_portal(token)
                    mensaje = t("portal_opened", lang)
                else:
                    url = self._licensing.crear_checkout(token)
                    mensaje = t("upgrade_opened", lang)
                webbrowser.open(url)

                def ok() -> None:
                    self._set_auth_busy(False)
                    messagebox.showinfo(t("license_title", lang), mensaje)

                self.after(0, ok)
            except LicensingAPIError as error:
                detalle_api = str(error)

                def fail_api() -> None:
                    self._set_auth_busy(False)
                    if "401" in detalle_api or "Not authenticated" in detalle_api:
                        borrar_tokens()
                        self._estado_licencia = estado_suscripcion_actual(
                            self._licensing
                        )
                        self._refresh_plan_ui()
                        messagebox.showwarning(
                            t("license_title", lang),
                            t("login_required_upgrade", lang),
                        )
                        self._show_auth_dialog()
                        return
                    messagebox.showerror(
                        t("error_title", lang),
                        t("auth_error", lang, error=detalle_api),
                    )

                self.after(0, fail_api)
            except Exception as error:  # noqa: BLE001
                detalle = str(error)

                def fail() -> None:
                    self._set_auth_busy(False)
                    messagebox.showerror(
                        t("error_title", lang),
                        t("auth_error", lang, error=detalle),
                    )

                self.after(0, fail)

        threading.Thread(target=worker, daemon=True).start()

    def _toggle_language(self) -> None:
        try:
            self._idioma = Idioma.ES if self._idioma is Idioma.EN else Idioma.EN
            guardar_idioma(self._idioma)
            self._apply_language()
        except Exception as error:
            messagebox.showerror(t("error_title", self._lang()), str(error))

    def _sync_modelo_interno(self) -> None:
        self._modelo_interno = modelo_profundidad_desde_etiqueta(
            self.depth_model.get()
        )

    def _on_mode_selected(self, _event: tk.Event | None = None) -> None:
        self._modo_interno = modo_interno(self.stereo_mode.get(), self._lang())
        self._set_default_output()

    def _choose_input(self) -> None:
        lang = self._lang()
        ruta = filedialog.askopenfilename(
            title=t("dialog_input_title", lang),
            filetypes=[
                (t("filetype_video", lang), "*.mp4 *.mov *.avi *.mkv"),
                (t("filetype_all", lang), "*"),
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
            self._modo_interno,
        )

    def _choose_output(self) -> bool:
        lang = self._lang()
        initialfile = None
        if self.input_path is not None:
            initialfile = ruta_salida_por_defecto(
                self.input_path,
                self._modo_interno,
            ).name
        ruta = filedialog.asksaveasfilename(
            title=t("dialog_output_title", lang),
            defaultextension=".mp4",
            initialfile=initialfile,
            filetypes=[
                (t("filetype_mp4", lang), "*.mp4"),
                (t("filetype_all", lang), "*"),
            ],
        )
        if not ruta:
            return False
        self.output_path = Path(ruta)
        return True

    def _toggle_advanced(self) -> None:
        if self.advanced_frame.winfo_ismapped():
            self._collapse_advanced_options()
            self.geometry("520x640")
        else:
            self.advanced_frame.grid()
            self.advanced_button.config(text=t("advanced_hide", self._lang()))
            self.geometry("520x780")

    def _collapse_advanced_options(self) -> None:
        if self.advanced_frame.winfo_ismapped():
            self.advanced_frame.grid_remove()
            self.advanced_button.config(text=t("advanced_ai_show", self._lang()))
            self.geometry("520x640")

    def _widget_is_in_advanced_area(self, widget: tk.Widget) -> bool:
        while widget is not None:
            if widget in {
                self.advanced_frame,
                self.advanced_canvas,
                self.advanced_scrollbar,
                self.advanced_options_frame,
                self.advanced_button,
            }:
                return True
            widget = getattr(widget, "master", None)
        return False

    def _on_global_click(self, event: tk.Event) -> None:
        if not self.advanced_frame.winfo_ismapped():
            return
        widget = event.widget
        # No interferir con botones principales.
        if widget in {
            self.convert_button,
            self.cancel_button,
            self.language_button,
            self._browse_button,
            self.login_button,
            self.upgrade_button,
            self.refresh_plan_button,
            self.logout_button,
        }:
            return
        if self._widget_is_in_advanced_area(widget):
            return
        self._collapse_advanced_options()

    def _on_offset_toggle(self) -> None:
        lang = self._lang()
        estado = "!disabled" if self.offset_manual.get() else "disabled"
        self.offset_slider.state([estado])
        if self.offset_manual.get():
            self.offset_label.configure(
                text=t("offset_current", lang, value=self.offset_value.get())
            )
        else:
            self.offset_value.set(0)
            self.offset_label.configure(text=t("offset_auto", lang))

    def _update_offset_label(self) -> None:
        self.offset_label.configure(
            text=t("offset_current", self._lang(), value=self.offset_value.get())
        )

    def _update_intensity_label(self) -> None:
        self.intensity_label.configure(
            text=t("intensity_current", self._lang(), value=self.intensity.get())
        )

    def _on_convert(self) -> None:
        if self.convert_button.instate(["disabled"]):
            return

        lang = self._lang()
        try:
            entrada = self.input_entry.get().strip()
            if not entrada:
                messagebox.showwarning(t("warn_title", lang), t("warn_no_input", lang))
                return

            self.input_path = Path(entrada)
            if not self.input_path.is_file():
                messagebox.showerror(
                    t("error_title", lang),
                    t("error_input_missing", lang),
                )
                return

            self._sync_modelo_interno()
            self._on_mode_selected()

            self._estado_licencia = estado_suscripcion_actual()
            try:
                politica = validar_conversion(
                    plan=self._estado_licencia.plan,
                    resolucion=self.resolution.get(),
                    conversiones_usadas=self._estado_licencia.conversiones_usadas,
                )
            except LicenciaError as error:
                messagebox.showerror(t("license_title", lang), str(error))
                self._refresh_plan_ui()
                return

            self._collapse_advanced_options()
            if not self._choose_output():
                return

            self.convert_button.state(["disabled"])
            self.cancel_button.state(["!disabled"])
            self._cancel_event.clear()
            self.progress_value.set(0.0)
            self.progress_label_text.set(t("starting", lang))
            self.start_time = time.time()
            self.total_frames = 0
            self._politica_activa = politica
            self._conversion_thread = threading.Thread(
                target=self._run_conversion,
                daemon=True,
            )
            self._conversion_thread.start()
        except Exception as error:
            messagebox.showerror(t("error_title", lang), str(error))
            self.convert_button.state(["!disabled"])
            self.cancel_button.state(["disabled"])

    def _on_cancel(self) -> None:
        if self._conversion_thread is not None and self._conversion_thread.is_alive():
            self._cancel_event.set()
            self.progress_label_text.set(t("cancelling", self._lang()))

    def _run_conversion(self) -> None:
        lang = self._lang()
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
                modo=self._modo_interno,
                modelo_profundidad=self._modelo_interno.value,
                intensidad_profundidad=self.intensity.get(),
                dispositivo_profundidad=dispositivo,
                codificar_final=self.codificar_final.get(),
                mostrar_progreso=False,
                callback_progreso=progress_callback,
                cancelar=self._cancel_event.is_set,
                max_segundos=self._politica_activa.max_segundos,
            )
            if self._cancel_event.is_set():
                raise ConversionCancelada()
            self.total_frames = info["fotogramas"]
            self._estado_licencia = registrar_conversion_exitosa(self._estado_licencia)
            self.after(0, self._refresh_plan_ui)
            self.after(0, self._update_progress, 100, 0, "finalizado")
            self.after(
                0,
                messagebox.showinfo,
                t("success_title", lang),
                t("success_message", lang, path=self.output_path),
            )
        except ConversionCancelada:
            self.after(0, self._log, t("cancelled", lang))
            self.after(
                0,
                messagebox.showinfo,
                t("cancelled_title", lang),
                t("cancelled_message", lang),
            )
        except Exception as error:
            self.after(0, self._log, f"Error: {error}")
            self.after(
                0,
                messagebox.showerror,
                t("error_title", lang),
                t("error_message", lang, error=error),
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
        lang = self._lang()
        self.progress_value.set(min(percentage, 100.0))
        if percentage >= 100 or etapa == "finalizado":
            self.progress_label_text.set(t("done", lang))
        else:
            mins, secs = divmod(remaining_seconds, 60)
            clave = "progress_encoding" if etapa == "codificacion" else "progress_frames"
            self.progress_label_text.set(
                t(clave, lang, pct=percentage, mins=mins, secs=secs)
            )

    def _log(self, texto: str) -> None:
        self.progress_label_text.set(texto)


def main() -> None:
    app = ConversorGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
