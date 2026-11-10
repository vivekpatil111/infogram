"""Minimal Razorpay client: create an order, verify signatures.

Keys come from the environment (RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET, plus
RAZORPAY_WEBHOOK_SECRET for webhooks). Use rzp_test_ keys until you go live.
"""

import hashlib
import hmac

import requests
from django.conf import settings

API = "https://api.razorpay.com/v1"


class RazorpayError(Exception):
    pass


def configured():
    return bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)


def create_order(*, amount_paise, receipt, notes):
    try:
        response = requests.post(
            f"{API}/orders",
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET),
            json={"amount": amount_paise, "currency": "INR", "receipt": receipt, "notes": notes},
            timeout=15,
        )
    except requests.RequestException as error:
        raise RazorpayError("Couldn't reach Razorpay. Try again.") from error
    if response.status_code >= 400:
        raise RazorpayError(response.json().get("error", {}).get("description", "Razorpay refused the order."))
    return response.json()


def _matches(message, signature, secret):
    expected = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return bool(signature) and hmac.compare_digest(expected, str(signature))


def payment_signature_ok(order_id, payment_id, signature):
    """Checkout handler signature: HMAC-SHA256(order_id|payment_id, key secret)."""

    return _matches(f"{order_id}|{payment_id}".encode(), signature, settings.RAZORPAY_KEY_SECRET)


def webhook_signature_ok(raw_body, signature):
    secret = settings.RAZORPAY_WEBHOOK_SECRET
    return bool(secret) and _matches(raw_body, signature, secret)
