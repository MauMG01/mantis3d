"""Rutas de autenticación."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import create_access_token, create_refresh_token, hash_password, verify_password
from ..config import settings
from ..database import get_db
from ..email_service import send_password_reset_code
from ..models import PasswordResetCode, User
from ..schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])

_GENERIC_FORGOT_MSG = (
    "Si el correo está registrado, recibirás un código para restablecer la contraseña."
)


@router.post("/register", response_model=TokenResponse)
def register(body: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=body.email.lower(),
        hashed_password=hash_password(body.password),
        plan="demo",
        conversiones_usadas=0,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenResponse(
        access_token=create_access_token(user.email),
        refresh_token=create_refresh_token(user.email),
    )


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.email == body.email.lower()).first()
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    return TokenResponse(
        access_token=create_access_token(user.email),
        refresh_token=create_refresh_token(user.email),
    )


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(
    body: ForgotPasswordRequest,
    db: Session = Depends(get_db),
) -> MessageResponse:
    """
    Genera un código de 6 dígitos y lo envía por correo.

    Respuesta genérica para no revelar si el email existe.
    """
    email = body.email.lower().strip()
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        return MessageResponse(message=_GENERIC_FORGOT_MSG)

    code = f"{secrets.randbelow(1_000_000):06d}"
    expires = datetime.now(timezone.utc) + timedelta(
        minutes=settings.reset_code_expire_minutes
    )
    # Invalidar códigos previos no usados.
    previos = (
        db.query(PasswordResetCode)
        .filter(
            PasswordResetCode.email == email,
            PasswordResetCode.used.is_(False),
        )
        .all()
    )
    for row in previos:
        row.used = True

    db.add(
        PasswordResetCode(
            email=email,
            code_hash=hash_password(code),
            expires_at=expires.replace(tzinfo=None),
            used=False,
        )
    )
    db.commit()

    try:
        send_password_reset_code(email, code)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=503,
            detail="No se pudo enviar el correo. Inténtalo más tarde.",
        ) from exc

    return MessageResponse(message=_GENERIC_FORGOT_MSG)


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(
    body: ResetPasswordRequest,
    db: Session = Depends(get_db),
) -> MessageResponse:
    email = body.email.lower().strip()
    code = body.code.strip()
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise HTTPException(status_code=400, detail="Código inválido o caducado")

    ahora = datetime.utcnow()
    candidatos = (
        db.query(PasswordResetCode)
        .filter(
            PasswordResetCode.email == email,
            PasswordResetCode.used.is_(False),
            PasswordResetCode.expires_at >= ahora,
        )
        .order_by(PasswordResetCode.created_at.desc())
        .all()
    )
    matched: PasswordResetCode | None = None
    for row in candidatos:
        if verify_password(code, row.code_hash):
            matched = row
            break

    if matched is None:
        raise HTTPException(status_code=400, detail="Código inválido o caducado")

    matched.used = True
    user.hashed_password = hash_password(body.new_password)
    db.commit()
    return MessageResponse(message="Contraseña actualizada. Ya puedes iniciar sesión.")
