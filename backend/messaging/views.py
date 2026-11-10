import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import OuterRef, Prefetch, Q
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import CursorPagination
from rest_framework.response import Response

from accounts.querysets import count_subquery
from safety.models import Block
from safety.querysets import is_blocked_between

from .models import Conversation, ConversationMember, Message
from .serializers import ConversationSerializer, MessageSerializer


User = get_user_model()
logger = logging.getLogger(__name__)
MAX_GROUP_PARTICIPANTS = 32


def conversation_blocked(conversation, sender):
    """A direct (1:1) thread is frozen while either person blocks the other."""

    others = [m.user for m in conversation.members.select_related("user") if m.user_id != sender.id]
    return len(others) == 1 and is_blocked_between(sender, others[0])


class MessageCursorPagination(CursorPagination):
    """Newest first; the client reverses for display and loads older pages."""

    page_size = 50
    page_size_query_param = "limit"
    max_page_size = 100
    ordering = ("-created_at", "-id")


class ConversationViewSet(viewsets.ModelViewSet):
    serializer_class = ConversationSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        return (
            Conversation.objects.filter(members__user=user)
            .prefetch_related(Prefetch("members", queryset=ConversationMember.objects.select_related("user")))
            .annotate(
                unread_count=count_subquery(
                    Message.objects.filter(conversation=OuterRef("pk"), read_at__isnull=True).exclude(sender=user),
                    "conversation",
                )
            )
            .order_by("-updated_at", "-id")
        )

    def create(self, request, *args, **kwargs):
        raw_ids = request.data.get("participant_ids", [])
        if not isinstance(raw_ids, list) or not raw_ids:
            return Response({"detail": "participant_ids must contain at least one user."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            other_ids = {int(value) for value in raw_ids} - {request.user.id}
        except (TypeError, ValueError):
            return Response({"detail": "participant_ids must be user ids."}, status=status.HTTP_400_BAD_REQUEST)
        if not other_ids:
            return Response({"detail": "Add at least one other person."}, status=status.HTTP_400_BAD_REQUEST)
        if len(other_ids) + 1 > MAX_GROUP_PARTICIPANTS:
            return Response({"detail": f"Groups are limited to {MAX_GROUP_PARTICIPANTS} people."}, status=status.HTTP_400_BAD_REQUEST)
        others = list(User.objects.filter(id__in=other_ids, is_active=True))
        if len(others) != len(other_ids):
            return Response({"detail": "One or more users were not found."}, status=status.HTTP_400_BAD_REQUEST)
        if Block.objects.filter(
            Q(blocker=request.user, blocked_id__in=other_ids) | Q(blocked=request.user, blocker_id__in=other_ids)
        ).exists():
            return Response({"detail": "You can't message this account."}, status=status.HTTP_403_FORBIDDEN)

        # A direct message reuses the existing 1:1 thread instead of
        # starting a new one each time (as Instagram's inbox does).
        if len(others) == 1:
            existing = (
                self.get_queryset()
                .filter(members__user=others[0])
                .annotate(
                    member_count=count_subquery(
                        ConversationMember.objects.filter(conversation=OuterRef("pk")), "conversation"
                    )
                )
                .filter(member_count=2)
                .first()
            )
            if existing is not None:
                return Response(self.get_serializer(existing).data, status=status.HTTP_200_OK)

        with transaction.atomic():
            conversation = Conversation.objects.create()
            ConversationMember.objects.bulk_create(
                [ConversationMember(conversation=conversation, user=user) for user in [request.user, *others]]
            )
        conversation = self.get_queryset().get(pk=conversation.pk)
        return Response(self.get_serializer(conversation).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get", "post"], url_path="messages")
    def messages(self, request, pk=None):
        conversation = self.get_object()
        if request.method == "GET":
            paginator = MessageCursorPagination()
            page = paginator.paginate_queryset(conversation.messages.select_related("sender"), request, view=self)
            return paginator.get_paginated_response(MessageSerializer(page, many=True).data)

        if conversation_blocked(conversation, request.user):
            return Response({"detail": "You can't message this account."}, status=status.HTTP_403_FORBIDDEN)
        serializer = MessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = serializer.save(conversation=conversation, sender=request.user)
        Conversation.objects.filter(id=conversation.id).update(updated_at=timezone.now())
        payload = MessageSerializer(message).data
        # Persisting must not fail because the realtime transport is down.
        try:
            async_to_sync(get_channel_layer().group_send)(
                f"conversation_{conversation.id}",
                {"type": "chat.message", "message": payload},
            )
        except Exception:  # pragma: no cover - broker failures are environment-specific
            logger.warning("Realtime message broadcast failed", exc_info=True)
        return Response(payload, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="read")
    def mark_read(self, request, pk=None):
        conversation = self.get_object()
        updated = (
            conversation.messages.exclude(sender=request.user).filter(read_at__isnull=True).update(read_at=timezone.now())
        )
        return Response({"read": True, "updated": updated})
