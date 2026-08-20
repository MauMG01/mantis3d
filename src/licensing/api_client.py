"""Cliente HTTP hacia la API de licencias (auth + suscripción)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from .policy import Plan
from .settings import licensing_api_url


@dataclass
class EstadoSuscripcion:
    plan: Plan
    conversiones_usadas: int
    email: str | None = None
    activo: bool = True
    fuente: str = "local"  # local | api


class LicensingAPIError(Exception):
    """Error al comunicar con la API de licencias."""


def api_base_url() -> str | None:
    """URL del backend. Si no está definida, la app opera en modo local (Demo)."""
    return licensing_api_url()


class LicensingClient:
    """Cliente de la API de suscripciones."""

    def __init__(self, base_url: str | None = None, timeout_s: float = 15.0) -> None:
        self.base_url = (base_url or api_base_url() or "").rstrip("/")
        self.timeout_s = timeout_s

    @property
    def disponible(self) -> bool:
        return bool(self.base_url)

    def _headers(self, token: str | None) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def login(self, email: str, password: str) -> dict[str, Any]:
        if not self.disponible:
            raise LicensingAPIError("MANTIS_API_URL is not configured.")
        with httpx.Client(timeout=self.timeout_s) as client:
            respuesta = client.post(
                f"{self.base_url}/auth/login",
                json={"email": email, "password": password},
            )
        if respuesta.status_code >= 400:
            raise LicensingAPIError(respuesta.text)
        return respuesta.json()

    def register(self, email: str, password: str) -> dict[str, Any]:
        if not self.disponible:
            raise LicensingAPIError("MANTIS_API_URL is not configured.")
        with httpx.Client(timeout=self.timeout_s) as client:
            respuesta = client.post(
                f"{self.base_url}/auth/register",
                json={"email": email, "password": password},
            )
        if respuesta.status_code >= 400:
            raise LicensingAPIError(respuesta.text)
        return respuesta.json()

    def obtener_suscripcion(self, token: str) -> EstadoSuscripcion:
        if not self.disponible:
            raise LicensingAPIError("MANTIS_API_URL is not configured.")
        with httpx.Client(timeout=self.timeout_s) as client:
            respuesta = client.get(
                f"{self.base_url}/me/subscription",
                headers=self._headers(token),
            )
        if respuesta.status_code >= 400:
            raise LicensingAPIError(respuesta.text)
        datos = respuesta.json()
        return EstadoSuscripcion(
            plan=Plan(datos.get("plan", Plan.DEMO.value)),
            conversiones_usadas=int(datos.get("conversiones_usadas", 0)),
            email=datos.get("email"),
            activo=bool(datos.get("activo", True)),
            fuente="api",
        )

    def registrar_conversion(self, token: str) -> EstadoSuscripcion:
        if not self.disponible:
            raise LicensingAPIError("MANTIS_API_URL is not configured.")
        with httpx.Client(timeout=self.timeout_s) as client:
            respuesta = client.post(
                f"{self.base_url}/usage/conversion",
                headers=self._headers(token),
            )
        if respuesta.status_code >= 400:
            raise LicensingAPIError(respuesta.text)
        datos = respuesta.json()
        return EstadoSuscripcion(
            plan=Plan(datos.get("plan", Plan.DEMO.value)),
            conversiones_usadas=int(datos.get("conversiones_usadas", 0)),
            email=datos.get("email"),
            activo=bool(datos.get("activo", True)),
            fuente="api",
        )

    def crear_checkout(self, token: str) -> str:
        """Devuelve la URL de Stripe Checkout para upgrade a Pro."""
        if not self.disponible:
            raise LicensingAPIError("MANTIS_API_URL is not configured.")
        with httpx.Client(timeout=self.timeout_s) as client:
            respuesta = client.post(
                f"{self.base_url}/billing/checkout",
                headers=self._headers(token),
            )
        if respuesta.status_code >= 400:
            raise LicensingAPIError(respuesta.text)
        return str(respuesta.json()["url"])

    def crear_portal(self, token: str) -> str:
        """Devuelve la URL del Customer Portal de Stripe."""
        if not self.disponible:
            raise LicensingAPIError("MANTIS_API_URL is not configured.")
        with httpx.Client(timeout=self.timeout_s) as client:
            respuesta = client.post(
                f"{self.base_url}/billing/portal",
                headers=self._headers(token),
            )
        if respuesta.status_code >= 400:
            raise LicensingAPIError(respuesta.text)
        return str(respuesta.json()["url"])
