"""Stripe billing integration."""

import os

import stripe

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

PRICE_IDS = {
    "pro_monthly": os.getenv("STRIPE_PRICE_PRO_MONTHLY", ""),
    "studio_monthly": os.getenv("STRIPE_PRICE_STUDIO_MONTHLY", ""),
    "credits_5": os.getenv("STRIPE_PRICE_CREDITS_5", ""),
    "credits_20": os.getenv("STRIPE_PRICE_CREDITS_20", ""),
}

PLAN_FROM_PRICE = {
    PRICE_IDS["pro_monthly"]: "pro",
    PRICE_IDS["studio_monthly"]: "studio",
}

CREDIT_PACKS = {
    PRICE_IDS["credits_5"]: 5,
    PRICE_IDS["credits_20"]: 20,
}


def stripe_configured() -> bool:
    return bool(stripe.api_key)


def create_checkout_session(user, price_key: str) -> str | None:
    price_id = PRICE_IDS.get(price_key)
    if not price_id or not stripe_configured():
        return None

    mode = "subscription" if "monthly" in price_key else "payment"
    session = stripe.checkout.Session.create(
        mode=mode,
        customer_email=user.email or None,
        client_reference_id=user.id,
        metadata={"user_id": user.id, "price_key": price_key},
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{FRONTEND_URL}/checkout/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{FRONTEND_URL}/checkout/cancel",
    )
    return session.url


def create_portal_session(customer_id: str) -> str | None:
    if not stripe_configured() or not customer_id:
        return None
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=f"{FRONTEND_URL}/dashboard",
    )
    return session.url


def retrieve_checkout_session(session_id: str) -> dict | None:
    if not stripe_configured() or not session_id:
        return None
    try:
        return stripe.checkout.Session.retrieve(session_id)
    except stripe.error.StripeError:
        return None


def session_belongs_to_user(session: dict, user_id: str) -> bool:
    ref = session.get("client_reference_id") or session.get("metadata", {}).get("user_id")
    return ref == user_id


def describe_checkout_session(session: dict) -> dict:
    price_key = session.get("metadata", {}).get("price_key", "")
    credits_map = {"credits_5": 5, "credits_20": 20}
    plan = None
    if session.get("mode") == "subscription":
        plan = "studio" if "studio" in price_key else "pro"
    return {
        "status": session.get("status"),
        "payment_status": session.get("payment_status"),
        "plan": plan,
        "credits_added": credits_map.get(price_key, 0),
        "price_key": price_key,
    }


def handle_webhook_event(payload: bytes, sig_header: str):
    secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    if not secret:
        raise ValueError("STRIPE_WEBHOOK_SECRET not configured")
    return stripe.Webhook.construct_event(payload, sig_header, secret)
