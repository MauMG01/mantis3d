"""Configuración del backend MANTIS (variables de entorno)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

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


settings = Settings()
