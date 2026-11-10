import json

from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from notifications.services import create_notification
from posts.querysets import posts_for_user
from safety.querysets import is_blocked_between

from . import razorpay
from .models import Tip

PRESETS = [20, 50, 100, 200]
MIN_RUPEES, MAX_RUPEES = 10, 5000


def tip_row(tip, *, viewer):
    other = tip.sender if tip.creator_id == viewer.id else tip.creator
    return {
        "id": tip.id,
        "amount": tip.amount_paise / 100,
        "message": tip.message,
        "status": tip.status,
        "post_id": tip.post_id,
        "person": {"id": other.id, "username": other.username, "avatar_url": other.avatar_url} if other else None,
        "created_at": tip.created_at.isoformat(),
    }


@transaction.atomic
def mark_paid(tip, payment_id):
    """Idempotent: the checkout callback and the webhook may both arrive."""

    tip = Tip.objects.select_for_update().get(pk=tip.pk)
    if tip.status == Tip.Status.PAID:
        return tip
    tip.status, tip.razorpay_payment_id, tip.paid_at = Tip.Status.PAID, payment_id, timezone.now()
    tip.save(update_fields=["status", "razorpay_payment_id", "paid_at"])
    if tip.sender:
        create_notification(recipient=tip.creator, actor=tip.sender, notification_type="tip", post=tip.post)
    return tip


class TipConfigView(APIView):
    """GET /tips/config/ - whether tipping is on, the public key and amounts."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from django.conf import settings

        return Response({
            "enabled": razorpay.configured(),
            "key_id": settings.RAZORPAY_KEY_ID if razorpay.configured() else "",
            "presets": PRESETS, "min": MIN_RUPEES, "max": MAX_RUPEES, "currency": "INR",
        })


class TipCreateView(APIView):
    """POST /tips/ {creator, amount (rupees), post_id?, message?} -> a Razorpay order for Checkout."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "reports"

    def post(self, request):
        from django.conf import settings

        if not razorpay.configured():
            return Response({"detail": "Tipping isn't available yet."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        creator = get_object_or_404(User, username__iexact=str(request.data.get("creator", "")), is_active=True)
        if creator.id == request.user.id:
            return Response({"detail": "You can't tip yourself."}, status=status.HTTP_400_BAD_REQUEST)
        if is_blocked_between(request.user, creator):
            return Response({"detail": "You can't tip this account."}, status=status.HTTP_403_FORBIDDEN)
        try:
            rupees = int(request.data.get("amount"))
        except (TypeError, ValueError):
            rupees = 0
        if not MIN_RUPEES <= rupees <= MAX_RUPEES:
            return Response({"amount": [f"Tips are ₹{MIN_RUPEES}-₹{MAX_RUPEES}."]}, status=status.HTTP_400_BAD_REQUEST)
        post = None
        if request.data.get("post_id"):
            post = posts_for_user(request.user).filter(pk=request.data["post_id"], author=creator).first()
        message = " ".join(str(request.data.get("message", "")).split())[:200]
        try:
            order = razorpay.create_order(
                amount_paise=rupees * 100,
                receipt=f"tip-{request.user.id}-{timezone.now():%Y%m%d%H%M%S}",
                notes={"creator": creator.username, "sender": request.user.username, "post": str(post.id if post else "")},
            )
        except razorpay.RazorpayError as error:
            return Response({"detail": str(error)}, status=status.HTTP_502_BAD_GATEWAY)
        tip = Tip.objects.create(sender=request.user, creator=creator, post=post, amount_paise=rupees * 100,
                                 message=message, razorpay_order_id=order["id"])
        return Response({
            "tip_id": tip.id, "order_id": order["id"], "amount_paise": tip.amount_paise, "currency": "INR",
            "key_id": settings.RAZORPAY_KEY_ID, "creator": creator.username,
        }, status=status.HTTP_201_CREATED)


class TipVerifyView(APIView):
    """POST /tips/verify/ {razorpay_order_id, razorpay_payment_id, razorpay_signature} after Checkout."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        order_id = str(request.data.get("razorpay_order_id", ""))
        payment_id = str(request.data.get("razorpay_payment_id", ""))
        tip = get_object_or_404(Tip, razorpay_order_id=order_id, sender=request.user)
        if not razorpay.payment_signature_ok(order_id, payment_id, request.data.get("razorpay_signature", "")):
            Tip.objects.filter(pk=tip.pk, status=Tip.Status.CREATED).update(status=Tip.Status.FAILED)
            return Response({"detail": "Payment couldn't be verified."}, status=status.HTTP_400_BAD_REQUEST)
        tip = mark_paid(tip, payment_id)
        return Response({"status": tip.status, "amount": tip.amount_paise / 100, "creator": tip.creator.username})


class TipWebhookView(APIView):
    """POST /tips/webhook/ - Razorpay server-to-server events (order.paid / payment.captured)."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        if not razorpay.webhook_signature_ok(request.body, request.headers.get("X-Razorpay-Signature", "")):
            return Response(status=status.HTTP_400_BAD_REQUEST)
        event = json.loads(request.body or b"{}")
        payment = event.get("payload", {}).get("payment", {}).get("entity", {})
        order_id = payment.get("order_id") or event.get("payload", {}).get("order", {}).get("entity", {}).get("id")
        if event.get("event") in {"payment.captured", "order.paid"} and order_id:
            tip = Tip.objects.filter(razorpay_order_id=order_id).first()
            if tip:
                mark_paid(tip, payment.get("id", ""))
        return Response({"ok": True})


class TipListView(APIView):
    """GET /tips/received/ or /tips/sent/ - paid tips, newest first, with totals."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, direction):
        field = "creator" if direction == "received" else "sender"
        tips = Tip.objects.filter(**{field: request.user}, status=Tip.Status.PAID).select_related("sender", "creator")
        total = tips.aggregate(total=Sum("amount_paise"))["total"] or 0
        return Response({"total": total / 100, "count": tips.count(), "results": [tip_row(tip, viewer=request.user) for tip in tips[:100]]})
