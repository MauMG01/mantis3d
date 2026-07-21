"""Licencias comerciales: planes Demo / Pro."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..procesador import ResolucionSalida


class Plan(str, Enum):
    DEMO = "demo"
    PRO = "pro"


DEMO_MAX_SEGUNDOS = 60
DEMO_MAX_CONVERSIONES = 2
DEMO_RESOLUCIONES: frozenset[ResolucionSalida] = frozenset(
    {ResolucionSalida.SBS_1080}
)
PRO_RESOLUCIONES: frozenset[ResolucionSalida] = frozenset(
    {
        ResolucionSalida.SBS_1080,
        ResolucionSalida.SBS_4K,
        ResolucionSalida.SBS_6K,
        ResolucionSalida.SBS_8K,
    }
)


@dataclass(frozen=True)
class PoliticaPlan:
    plan: Plan
    resoluciones_permitidas: frozenset[ResolucionSalida]
    max_segundos: int | None  # None = ilimitado
    max_conversiones: int | None  # None = ilimitado


POLITICAS: dict[Plan, PoliticaPlan] = {
    Plan.DEMO: PoliticaPlan(
        plan=Plan.DEMO,
        resoluciones_permitidas=DEMO_RESOLUCIONES,
        max_segundos=DEMO_MAX_SEGUNDOS,
        max_conversiones=DEMO_MAX_CONVERSIONES,
    ),
    Plan.PRO: PoliticaPlan(
        plan=Plan.PRO,
        resoluciones_permitidas=PRO_RESOLUCIONES,
        max_segundos=None,
        max_conversiones=None,
    ),
}


class LicenciaError(Exception):
    """La conversión no está permitida por el plan actual."""


def politica_para(plan: Plan | str) -> PoliticaPlan:
    return POLITICAS[Plan(plan)]


def resoluciones_para_plan(plan: Plan | str) -> list[ResolucionSalida]:
    politica = politica_para(plan)
    orden = [
        ResolucionSalida.SBS_1080,
        ResolucionSalida.SBS_4K,
        ResolucionSalida.SBS_6K,
        ResolucionSalida.SBS_8K,
    ]
    return [r for r in orden if r in politica.resoluciones_permitidas]


def validar_conversion(
    *,
    plan: Plan | str,
    resolucion: ResolucionSalida | str,
    conversiones_usadas: int,
    duracion_entrada_s: float | None = None,
) -> PoliticaPlan:
    """
    Valida si se puede iniciar una conversión.

    Lanza ``LicenciaError`` si el plan no lo permite.
    """
    politica = politica_para(plan)
    resolucion = ResolucionSalida(resolucion)

    if (
        politica.max_conversiones is not None
        and conversiones_usadas >= politica.max_conversiones
    ):
        raise LicenciaError(
            f"Demo limit reached: maximum {politica.max_conversiones} conversions. "
            "Upgrade to Pro for unlimited conversions."
        )

    if resolucion not in politica.resoluciones_permitidas:
        permitidas = ", ".join(r.value for r in sorted(politica.resoluciones_permitidas, key=lambda x: x.value))
        raise LicenciaError(
            f"Resolution '{resolucion.value}' is not available on the {politica.plan.value} plan. "
            f"Allowed: {permitidas}."
        )

    if (
        politica.max_segundos is not None
        and duracion_entrada_s is not None
        and duracion_entrada_s > politica.max_segundos
    ):
        # Se permite convertir, pero el motor truncará a max_segundos.
        # Solo avisamos si queremos bloquear videos largos; aquí no bloqueamos.
        pass

    return politica
