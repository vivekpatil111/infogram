"""Web Push: deliver activity and messages to subscribed browsers/phones.

Uses VAPID (no third-party push account). Keys live in the environment:
VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY (generate with `manage.py generate_vapid_keys`).
Without them push is simply off. Sending happens on a background thread after
the database commit, so a slow push service never slows down a request.
"""

import json
import logging
import threading

from django.conf import settings
from django.db import transaction

logger = logging.getLogger(__name__)


def push_configured():
    return bool(settings.VAPID_PUBLIC_KEY and settings.VAPID_PRIVATE_KEY)


def send_to_user(user_id, *, title, body, url="/", tag=None):
    """Queue a push to every device the user subscribed, after the current transaction."""

    if not push_configured() or getattr(settings, "PUSH_DISABLED", False):
        return
    payload = {"title": title, "body": body, "url": url, "tag": tag or url, "icon": "/icons/icon-192.png"}
    transaction.on_commit(lambda: threading.Thread(target=_deliver_in_thread, args=(user_id, payload), daemon=True).start())


def _deliver(user_id, payload):
    from pywebpush import WebPushException, webpush

    from .models import PushSubscription

    try:
        for subscription in PushSubscription.objects.filter(user_id=user_id):
            try:
                webpush(
                    subscription_info={"endpoint": subscription.endpoint, "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth}},
                    data=json.dumps(payload),
                    vapid_private_key=settings.VAPID_PRIVATE_KEY,
                    vapid_claims={"sub": settings.VAPID_SUBJECT},
                    ttl=24 * 3600,
                    timeout=10,
                )
            except WebPushException as error:
                status = getattr(error.response, "status_code", None)
                if status in (404, 410):  # the browser dropped this subscription
                    subscription.delete()
                else:
                    logger.warning("push to %s failed: %s", user_id, status or error)
    except Exception:  # pragma: no cover - never let a push thread crash noisily
        logger.exception("push delivery crashed")


def _deliver_in_thread(user_id, payload):
    from django.db import connection

    try:
        _deliver(user_id, payload)
    finally:
        connection.close()  # the thread's own DB connection
