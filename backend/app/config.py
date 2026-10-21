"""Configuración del backend MANTIS (variables de entorno)."""

from __future__ import annotations

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _normalize_database_url(url: str) -> str:
    """
    Normaliza la URL de Postgres para el driver que instalamos (psycopg2-binary).

    Render/Heroku entregan ``postgres://`` o ``postgresql://``. SQLAlchemy reciente
    puede resolver ``postgresql://`` a ``psycopg`` (v3) y fallar con
    ``ModuleNotFoundError: No module named 'psycopg'``.
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]

    if url.startswith("postgresql+psycopg2://"):
        return url
    if url.startswith("postgresql+psycopg://"):
        return "postgresql+psycopg2://" + url[len("postgresql+psycopg://") :]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg2://" + url[len("postgresql://") :]
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "MANTIS Licensing API"
    secret_key: str = "cambia-esta-clave-en-produccion"
    access_token_expire_minutes: int = 30
    database_url: str = "sqlite:///./mantis_licensing.db"

    # Stripe
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id_pro: str = ""
    frontend_success_url: str = "https://example.com/success"
    frontend_cancel_url: str = "https://example.com/cancel"

    # Email (Resend) — recuperación de contraseña
    resend_api_key: str = ""
    email_from: str = "MANTIS 3D <onboarding@resend.dev>"
    reset_code_expire_minutes: int = 15

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_db_url(cls, value: str) -> str:
        if isinstance(value, str):
            return _normalize_database_url(value)
        return value


settings = Settings()
