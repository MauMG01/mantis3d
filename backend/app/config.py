"""Configuración del backend MANTIS (variables de entorno)."""

from __future__ import annotations

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _normalize_database_url(url: str) -> str:
    # Render/Heroku entregan postgres://; SQLAlchemy 2 prefiere postgresql://
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
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
