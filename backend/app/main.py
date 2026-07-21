"""API de licencias MANTIS (auth + Stripe + límites Demo/Pro)."""

from __future__ import annotations

from fastapi import FastAPI

from .config import settings
from .database import Base, engine
from .routers import auth, billing, subscription

Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.app_name, version="0.1.0")
app.include_router(auth.router)
app.include_router(subscription.router)
app.include_router(billing.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "mantis-licensing"}
