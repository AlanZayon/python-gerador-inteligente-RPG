"""Stripe billing routes."""

import logging

from flask import Blueprint, g, jsonify, request
from sqlalchemy.exc import IntegrityError

from database import SessionLocal
from models.entities import StripeEvent, Subscription, User
from services.auth import require_user
from services.billing import (
    CREDIT_PACKS,
    PLAN_FROM_PRICE,
    PRICE_IDS,
    create_checkout_session,
    create_portal_session,
    describe_checkout_session,
    handle_webhook_event,
    retrieve_checkout_session,
    session_belongs_to_user,
    stripe_configured,
)
from services.quota import add_credits, reset_plan_credits

logger = logging.getLogger(__name__)

billing_bp = Blueprint("billing", __name__, url_prefix="/billing")


@billing_bp.route("/checkout", methods=["POST"])
@require_user
def create_checkout():
    if not stripe_configured():
        return jsonify({"error": "Billing not configured"}), 503
    body = request.get_json(silent=True) or {}
    price_key = body.get("price_key")
    if price_key not in PRICE_IDS or not PRICE_IDS[price_key]:
        return jsonify({"error": "Invalid price_key"}), 400
    url = create_checkout_session(g.user, price_key)
    if not url:
        return jsonify({"error": "Could not create checkout session"}), 500
    return jsonify({"checkout_url": url})


@billing_bp.route("/portal", methods=["POST"])
@require_user
def customer_portal():
    if not stripe_configured():
        return jsonify({"error": "Billing not configured"}), 503
    if not g.user.stripe_customer_id:
        return jsonify({"error": "No subscription found"}), 404
    url = create_portal_session(g.user.stripe_customer_id)
    if not url:
        return jsonify({"error": "Could not open portal"}), 500
    return jsonify({"portal_url": url})


@billing_bp.route("/session/<session_id>", methods=["GET"])
@require_user
def get_checkout_session(session_id: str):
    if not stripe_configured():
        return jsonify({"error": "Billing not configured"}), 503
    session = retrieve_checkout_session(session_id)
    if not session or not session_belongs_to_user(session, g.user.id):
        return jsonify({"error": "Session not found"}), 404
    return jsonify(describe_checkout_session(session))


@billing_bp.route("/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.get_data()
    sig = request.headers.get("Stripe-Signature", "")
    try:
        event = handle_webhook_event(payload, sig)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        logger.warning("Webhook verification failed: %s", exc)
        return jsonify({"error": "Invalid signature"}), 400

    if not _record_stripe_event(event):
        logger.info("Skipping duplicate Stripe event %s", event.get("id"))
        return jsonify({"received": True, "duplicate": True})

    etype = event["type"]
    data = event["data"]["object"]

    if etype == "checkout.session.completed":
        _handle_checkout_completed(data)
    elif etype == "invoice.paid":
        _handle_invoice_paid(data)
    elif etype == "customer.subscription.deleted":
        _handle_subscription_deleted(data)

    return jsonify({"received": True})


def _record_stripe_event(event: dict) -> bool:
    """Return False if this event was already processed."""
    event_id = event.get("id")
    if not event_id:
        return True
    session_id = None
    if event.get("type") == "checkout.session.completed":
        session_id = event.get("data", {}).get("object", {}).get("id")
    db = SessionLocal()
    try:
        existing = db.query(StripeEvent).filter(StripeEvent.event_id == event_id).first()
        if existing:
            return False
        db.add(
            StripeEvent(
                event_id=event_id,
                event_type=event.get("type", ""),
                session_id=session_id,
            )
        )
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        return False
    finally:
        db.close()


def _user_from_session(session: dict) -> User | None:
    user_id = session.get("client_reference_id") or session.get("metadata", {}).get("user_id")
    if not user_id:
        return None
    db = SessionLocal()
    try:
        return db.query(User).filter(User.id == user_id).first()
    finally:
        db.close()


def _handle_checkout_completed(session: dict) -> None:
    user = _user_from_session(session)
    if not user:
        return
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.id == user.id).first()
        if not u:
            return
        if session.get("customer"):
            u.stripe_customer_id = session["customer"]
        mode = session.get("mode")
        if mode == "subscription":
            price_key = session.get("metadata", {}).get("price_key", "pro_monthly")
            plan = "studio" if "studio" in price_key else "pro"
            stripe_sub_id = session.get("subscription")
            existing = (
                db.query(Subscription)
                .filter(Subscription.stripe_subscription_id == stripe_sub_id)
                .first()
                if stripe_sub_id
                else None
            )
            if not existing:
                reset_plan_credits(u.id, plan)
                sub = Subscription(
                    user_id=u.id,
                    stripe_subscription_id=stripe_sub_id,
                    plan=plan,
                    status="active",
                )
                db.add(sub)
        elif mode == "payment":
            price_key = session.get("metadata", {}).get("price_key", "")
            credits = CREDIT_PACKS.get(PRICE_IDS.get(price_key, ""), 0)
            if not credits:
                credits_map = {"credits_5": 5, "credits_20": 20}
                credits = credits_map.get(price_key, 0)
            if credits:
                add_credits(u.id, credits, "credit_pack_purchase")
        db.commit()
    finally:
        db.close()


def _handle_invoice_paid(invoice: dict) -> None:
    customer_id = invoice.get("customer")
    if not customer_id:
        return
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
        if not user:
            return
        lines = invoice.get("lines", {}).get("data", [])
        for line in lines:
            price_id = line.get("price", {}).get("id")
            plan = PLAN_FROM_PRICE.get(price_id)
            if plan:
                reset_plan_credits(user.id, plan)
                break
    finally:
        db.close()


def _handle_subscription_deleted(subscription: dict) -> None:
    customer_id = subscription.get("customer")
    if not customer_id:
        return
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
        if user:
            reset_plan_credits(user.id, "free")
            db.query(Subscription).filter(Subscription.user_id == user.id).update(
                {"status": "cancelled"}
            )
            db.commit()
    finally:
        db.close()
