from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from messaging.models import Message

from .models import Notification
from .serializers import NotificationSerializer


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    MAX_LIST = 200

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user).select_related("actor", "post", "comment")

    def list(self, request, *args, **kwargs):
        # Plain array (the frontend accepts `results || response`), newest first.
        items = self.get_queryset()[: self.MAX_LIST]
        return Response(self.get_serializer(items, many=True).data)

    @action(detail=True, methods=["post"], url_path="read")
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=["read_at"])
        return Response({"read": True})

    @action(detail=False, methods=["post"], url_path="read-all")
    def mark_all_read(self, request):
        updated = (
            Notification.objects.filter(recipient=request.user, read_at__isnull=True).update(read_at=timezone.now())
        )
        return Response({"read": True, "updated": updated}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        """Badge counts (the observed "Messages - 3 new notifications" badge)."""

        activity = Notification.objects.filter(recipient=request.user, read_at__isnull=True).count()
        threads = (
            Message.objects.filter(conversation__members__user=request.user, read_at__isnull=True)
            .exclude(sender=request.user)
            .values("conversation_id")
            .distinct()
            .count()
        )
        return Response({"notifications": activity, "messages": threads})


class PushSubscriptionView(APIView):
    """GET    /notifications/push/   {enabled, public_key, subscribed_devices}
    POST   /notifications/push/   {endpoint, keys: {p256dh, auth}}   subscribe this device
    DELETE /notifications/push/   {endpoint}                         unsubscribe it"""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from django.conf import settings

        from .push import push_configured

        return Response({
            "enabled": push_configured(),
            "public_key": settings.VAPID_PUBLIC_KEY if push_configured() else "",
            "subscribed_devices": request.user.push_subscriptions.count(),
        })

    def post(self, request):
        from .models import PushSubscription
        from .push import push_configured

        if not push_configured():
            return Response({"detail": "Push notifications aren't set up on this server."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        endpoint = str(request.data.get("endpoint", ""))
        keys = request.data.get("keys") or {}
        if not endpoint.startswith("https://") or len(endpoint) > 1000 or not keys.get("p256dh") or not keys.get("auth"):
            return Response({"detail": "Invalid push subscription."}, status=status.HTTP_400_BAD_REQUEST)
        PushSubscription.objects.update_or_create(
            endpoint=endpoint,
            defaults={"user": request.user, "p256dh": str(keys["p256dh"])[:200], "auth": str(keys["auth"])[:100],
                      "user_agent": request.headers.get("User-Agent", "")[:300]},
        )
        return Response({"subscribed": True}, status=status.HTTP_201_CREATED)

    def delete(self, request):
        request.user.push_subscriptions.filter(endpoint=str(request.data.get("endpoint", ""))).delete()
        return Response({"subscribed": False})
