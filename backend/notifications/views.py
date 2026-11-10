from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

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
