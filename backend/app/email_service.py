"""Envío de correos (Resend)."""

from __future__ import annotations

import logging

import httpx

from .config import settings

logger = logging.getLogger(__name__)


def send_password_reset_code(email: str, code: str) -> None:
    """
    Envía el código de recuperación.

    Si no hay ``RESEND_API_KEY``, registra el código en logs (solo para desarrollo).
    """
    subject = "MANTIS 3D — código de recuperación"
    body_text = (
        f"Tu código para restablecer la contraseña es: {code}\n\n"
        f"Caduca en {settings.reset_code_expire_minutes} minutos.\n"
        "Si no pediste este cambio, ignora este correo.\n"
    )
    body_html = (
        f"<p>Tu código para restablecer la contraseña es:</p>"
        f"<p style='font-size:24px;font-weight:bold;letter-spacing:4px'>{code}</p>"
        f"<p>Caduca en {settings.reset_code_expire_minutes} minutos.</p>"
        f"<p>Si no pediste este cambio, ignora este correo.</p>"
    )

    api_key = (settings.resend_api_key or "").strip()
    if not api_key:
        logger.warning(
            "RESEND_API_KEY no configurada. Código de reset para %s: %s",
            email,
            code,
        )
        return

    from_addr = (settings.email_from or "").strip() or "MANTIS 3D <onboarding@resend.dev>"
    respuesta = httpx.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "from": from_addr,
            "to": [email],
            "subject": subject,
            "text": body_text,
            "html": body_html,
        },
        timeout=30.0,
    )
    if respuesta.status_code >= 400:
        logger.error("Resend error %s: %s", respuesta.status_code, respuesta.text)
        raise RuntimeError(f"No se pudo enviar el correo ({respuesta.status_code})")
