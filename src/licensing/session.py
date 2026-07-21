"""Sesión de licencia: tokens, plan actual y contador de uso."""

from __future__ import annotations

import json
from pathlib import Path

import keyring

from .api_client import EstadoSuscripcion, LicensingAPIError, LicensingClient
from .policy import Plan

_SERVICE = "mantis3d"
_KEY_REFRESH = "refresh_token"
_KEY_ACCESS = "access_token"
_ARCHIVO_USO = Path.home() / ".mantis3d" / "usage.json"


def _cargar_uso_local() -> dict:
    if not _ARCHIVO_USO.is_file():
        return {"conversiones_demo": 0, "plan_override": None}
    try:
        return json.loads(_ARCHIVO_USO.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"conversiones_demo": 0, "plan_override": None}


def _guardar_uso_local(datos: dict) -> None:
    _ARCHIVO_USO.parent.mkdir(parents=True, exist_ok=True)
    _ARCHIVO_USO.write_text(json.dumps(datos, indent=2) + "\n", encoding="utf-8")


def conversiones_demo_usadas() -> int:
    return int(_cargar_uso_local().get("conversiones_demo", 0))


def incrementar_conversion_demo() -> int:
    datos = _cargar_uso_local()
    datos["conversiones_demo"] = int(datos.get("conversiones_demo", 0)) + 1
    _guardar_uso_local(datos)
    return int(datos["conversiones_demo"])


def plan_override_local() -> Plan | None:
    """Solo para desarrollo: MANTIS_PLAN=pro|demo."""
    import os

    valor = os.environ.get("MANTIS_PLAN", "").strip().lower()
    if valor in {Plan.DEMO.value, Plan.PRO.value}:
        return Plan(valor)
    override = _cargar_uso_local().get("plan_override")
    if override in {Plan.DEMO.value, Plan.PRO.value}:
        return Plan(override)
    return None


def guardar_tokens(access_token: str, refresh_token: str | None = None) -> None:
    keyring.set_password(_SERVICE, _KEY_ACCESS, access_token)
    if refresh_token:
        keyring.set_password(_SERVICE, _KEY_REFRESH, refresh_token)


def cargar_access_token() -> str | None:
    try:
        return keyring.get_password(_SERVICE, _KEY_ACCESS)
    except Exception:
        return None


def borrar_tokens() -> None:
    for clave in (_KEY_ACCESS, _KEY_REFRESH):
        try:
            keyring.delete_password(_SERVICE, clave)
        except Exception:
            pass


def estado_suscripcion_actual(client: LicensingClient | None = None) -> EstadoSuscripcion:
    """
    Obtiene el plan vigente.

    Orden de prioridad:
    1. Override de desarrollo (MANTIS_PLAN)
    2. API remota (si hay token y MANTIS_API_URL)
    3. Demo local con contador de uso
    """
    override = plan_override_local()
    if override is not None:
        usadas = conversiones_demo_usadas() if override is Plan.DEMO else 0
        return EstadoSuscripcion(
            plan=override,
            conversiones_usadas=usadas,
            fuente="local",
        )

    # Sin API configurada: no tocar keychain (evita bloqueos en macOS).
    client = client or LicensingClient()
    if not client.disponible:
        return EstadoSuscripcion(
            plan=Plan.DEMO,
            conversiones_usadas=conversiones_demo_usadas(),
            fuente="local",
        )

    token = cargar_access_token()
    if token:
        try:
            return client.obtener_suscripcion(token)
        except LicensingAPIError:
            pass

    return EstadoSuscripcion(
        plan=Plan.DEMO,
        conversiones_usadas=conversiones_demo_usadas(),
        fuente="local",
    )


def registrar_conversion_exitosa(
    estado: EstadoSuscripcion,
    client: LicensingClient | None = None,
) -> EstadoSuscripcion:
    """Incrementa el contador tras una conversión exitosa (Demo)."""
    if estado.plan is Plan.PRO:
        return estado

    client = client or LicensingClient()
    token = cargar_access_token()
    if client.disponible and token and estado.fuente == "api":
        try:
            return client.registrar_conversion(token)
        except LicensingAPIError:
            pass

    usadas = incrementar_conversion_demo()
    return EstadoSuscripcion(
        plan=Plan.DEMO,
        conversiones_usadas=usadas,
        email=estado.email,
        fuente="local",
    )
