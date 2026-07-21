"""Suscripción y uso de conversiones."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import User
from ..schemas import SubscriptionResponse

router = APIRouter(tags=["subscription"])

DEMO_MAX_CONVERSIONES = 2


@router.get("/me/subscription", response_model=SubscriptionResponse)
def me_subscription(user: User = Depends(get_current_user)) -> SubscriptionResponse:
    return SubscriptionResponse(
        email=user.email,
        plan=user.plan,
        conversiones_usadas=user.conversiones_usadas,
        activo=True,
    )


@router.post("/usage/conversion", response_model=SubscriptionResponse)
def usage_conversion(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubscriptionResponse:
    if user.plan == "demo" and user.conversiones_usadas >= DEMO_MAX_CONVERSIONES:
        raise HTTPException(
            status_code=403,
            detail="Demo conversion limit reached. Upgrade to Pro.",
        )
    if user.plan == "demo":
        user.conversiones_usadas += 1
        db.add(user)
        db.commit()
        db.refresh(user)
    return SubscriptionResponse(
        email=user.email,
        plan=user.plan,
        conversiones_usadas=user.conversiones_usadas,
        activo=True,
    )
