"""Stripe Checkout, Customer Portal y webhooks."""

from __future__ import annotations

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..config import settings
from ..database import get_db
from ..models import User
from ..schemas import CheckoutResponse

router = APIRouter(prefix="/billing", tags=["billing"])


def _as_dict(obj: object) -> dict:
    if isinstance(obj, dict):
        return obj
    to_dict = getattr(obj, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    return {}


def _stripe_ready() -> None:
    if not settings.stripe_secret_key or not settings.stripe_price_id_pro:
        raise HTTPException(
            status_code=503,
            detail="Stripe is not configured. Set STRIPE_SECRET_KEY and STRIPE_PRICE_ID_PRO.",
        )
    stripe.api_key = settings.stripe_secret_key


@router.post("/checkout", response_model=CheckoutResponse)
def create_checkout(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CheckoutResponse:
    _stripe_ready()
    if not user.stripe_customer_id:
        customer = stripe.Customer.create(email=user.email)
        user.stripe_customer_id = customer["id"]
        db.add(user)
        db.commit()

    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=user.stripe_customer_id,
        line_items=[{"price": settings.stripe_price_id_pro, "quantity": 1}],
        success_url=settings.frontend_success_url,
        cancel_url=settings.frontend_cancel_url,
        metadata={"user_email": user.email},
    )
    return CheckoutResponse(url=session["url"])


@router.post("/portal", response_model=CheckoutResponse)
def create_portal(user: User = Depends(get_current_user)) -> CheckoutResponse:
    _stripe_ready()
    if not user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No Stripe customer on file")
    session = stripe.billing_portal.Session.create(
        customer=user.stripe_customer_id,
        return_url=settings.frontend_success_url,
    )
    return CheckoutResponse(url=session["url"])


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    if not settings.stripe_webhook_secret or not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Stripe webhook not configured")

    stripe.api_key = settings.stripe_secret_key
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.stripe_webhook_secret,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Webhook error: {exc}") from exc

    event_type = event["type"]
    data = _as_dict(event["data"]["object"])

    if event_type == "checkout.session.completed":
        metadata = data.get("metadata") or {}
        email = metadata.get("user_email") if isinstance(metadata, dict) else None
        customer_id = data.get("customer")
        subscription_id = data.get("subscription")
        user = None
        if email:
            user = db.query(User).filter(User.email == email).first()
        if user is None and customer_id:
            user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
        if user is not None:
            user.plan = "pro"
            user.stripe_customer_id = customer_id or user.stripe_customer_id
            user.stripe_subscription_id = subscription_id
            db.add(user)
            db.commit()

    elif event_type in {
        "customer.subscription.created",
        "customer.subscription.deleted",
        "customer.subscription.updated",
    }:
        customer_id = data.get("customer")
        status = data.get("status")
        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
        if user is not None:
            if event_type == "customer.subscription.deleted" or status in {
                "canceled",
                "unpaid",
                "incomplete_expired",
            }:
                user.plan = "demo"
                user.stripe_subscription_id = None
            elif status in {"active", "trialing"}:
                user.plan = "pro"
                user.stripe_subscription_id = data.get("id")
            db.add(user)
            db.commit()

    return {"received": True}
