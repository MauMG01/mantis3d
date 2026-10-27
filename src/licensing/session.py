"""Sesión de licencia: tokens, plan actual y contador de uso."""

from __future__ import annotations

import json
from pathlib import Path

from .api_client import EstadoSuscripcion, LicensingAPIError, LicensingClient
from .policy import Plan

_SERVICE = "mantis3d"
_KEY_REFRESH = "refresh_token"
_KEY_ACCESS = "access_token"
_DIR_MANTIS = Path.home() / ".mantis3d"
_ARCHIVO_USO = _DIR_MANTIS / "usage.json"
_ARCHIVO_TOKENS = _DIR_MANTIS / "tokens.json"


def _cargar_uso_local() -> dict:
    if not _ARCHIVO_USO.is_file():
        return {"conversiones_demo": 0, "plan_override": None}
    try:
        return json.loads(_ARCHIVO_USO.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"conversiones_demo": 0, "plan_override": None}


def _guardar_uso_local(datos: dict) -> None:
    _DIR_MANTIS.mkdir(parents=True, exist_ok=True)
    _ARCHIVO_USO.write_text(json.dumps(datos, indent=2) + "\n", encoding="utf-8")


def _cargar_tokens_archivo() -> dict[str, str]:
    if not _ARCHIVO_TOKENS.is_file():
        return {}
    try:
        datos = json.loads(_ARCHIVO_TOKENS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(datos, dict):
        return {}
    return {str(k): str(v) for k, v in datos.items() if v}


def _guardar_tokens_archivo(access_token: str, refresh_token: str | None = None) -> None:
    _DIR_MANTIS.mkdir(parents=True, exist_ok=True)
    datos = _cargar_tokens_archivo()
    datos[_KEY_ACCESS] = access_token
    if refresh_token:
        datos[_KEY_REFRESH] = refresh_token
    _ARCHIVO_TOKENS.write_text(json.dumps(datos, indent=2) + "\n", encoding="utf-8")


def _borrar_tokens_archivo() -> None:
    try:
        if _ARCHIVO_TOKENS.is_file():
            _ARCHIVO_TOKENS.unlink()
    except OSError:
        pass


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


def _usar_keyring() -> bool:
    """Por defecto no usamos Keychain: en Mac sin firmar pide contraseña en bucle."""
    import os

    return os.environ.get("MANTIS_USE_KEYRING", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def guardar_tokens(access_token: str, refresh_token: str | None = None) -> None:
    """Guarda tokens en Keychain (dev) o ~/.mantis3d/tokens.json (app empaquetada)."""
    if _usar_keyring():
        try:
            import keyring

            keyring.set_password(_SERVICE, _KEY_ACCESS, access_token)
            if refresh_token:
                keyring.set_password(_SERVICE, _KEY_REFRESH, refresh_token)
            return
        except Exception:
            pass
    _guardar_tokens_archivo(access_token, refresh_token)


def cargar_access_token() -> str | None:
    if _usar_keyring():
        try:
            import keyring

            token = keyring.get_password(_SERVICE, _KEY_ACCESS)
            if token:
                return token
        except Exception:
            pass
    return _cargar_tokens_archivo().get(_KEY_ACCESS)


def borrar_tokens() -> None:
    if _usar_keyring():
        try:
            import keyring

            for clave in (_KEY_ACCESS, _KEY_REFRESH):
                try:
                    keyring.delete_password(_SERVICE, clave)
                except Exception:
                    pass
        except Exception:
            pass
    _borrar_tokens_archivo()


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
        except LicensingAPIError as error:
            detalle = str(error).lower()
            if "401" in detalle or "unauthorized" in detalle or "not authenticated" in detalle:
                borrar_tokens()
        except Exception:
            # Timeout / red: no tumbar la GUI al arrancar
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
