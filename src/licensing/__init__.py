"""Licenciamiento comercial de MANTIS 3D."""

from .api_client import EstadoSuscripcion, LicensingAPIError, LicensingClient
from .policy import (
    DEMO_MAX_CONVERSIONES,
    DEMO_MAX_SEGUNDOS,
    LicenciaError,
    Plan,
    PoliticaPlan,
    politica_para,
    resoluciones_para_plan,
    validar_conversion,
)
from .session import (
    estado_suscripcion_actual,
    registrar_conversion_exitosa,
)

__all__ = [
    "DEMO_MAX_CONVERSIONES",
    "DEMO_MAX_SEGUNDOS",
    "EstadoSuscripcion",
    "LicenciaError",
    "LicensingAPIError",
    "LicensingClient",
    "Plan",
    "PoliticaPlan",
    "estado_suscripcion_actual",
    "politica_para",
    "registrar_conversion_exitosa",
    "resoluciones_para_plan",
    "validar_conversion",
]
