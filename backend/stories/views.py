from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from accounts.querysets import followed_ids
from safety.querysets import muted_stories, not_blocked_q

from .models import Story, StoryPollVote, StoryView
from .serializers import StorySerializer


STORY_LIFETIME = timedelta(hours=24)
User = get_user_model()


def visible_stories(user):
    """Active stories from yourself and accounts you follow, minus blocks and mutes."""

    return (
        Story.objects.filter(expires_at__gt=timezone.now())
        .filter(Q(author=user) | Q(author_id__in=followed_ids(user)))
        .filter(not_blocked_q(user))
        .exclude(author_id__in=muted_stories(user))
        .select_related("author")
        .annotate(viewed_by_me=Exists(StoryView.objects.filter(story=OuterRef("pk"), user=user)))
        .order_by("created_at", "id")
    )


class StoryViewSet(viewsets.ModelViewSet):
    serializer_class = StorySerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        return visible_stories(self.request.user)

    def list(self, request, *args, **kwargs):
        """Story tray, one ring per creator.

        Order matches the observed Instagram tray: your own ring first, then
        creators with unseen stories ("Story by X, not seen"), then fully
        seen ones; most recent activity first inside each group.
        `resume_index` is the first unseen story, where the viewer opens.
        """

        user = request.user
        groups = {}
        for story in self.get_queryset():
            group = groups.setdefault(
                story.author_id,
                {
                    "author": {
                        "id": story.author_id,
                        "username": story.author.username,
                        "avatar_url": story.author.avatar_url,
                    },
                    "is_own": story.author_id == user.id,
                    "has_unseen": False,
                    "resume_index": None,
                    "latest_at": story.created_at,
                    "stories": [],
                },
            )
            if not story.viewed_by_me and group["resume_index"] is None:
                group["resume_index"] = len(group["stories"])
                group["has_unseen"] = True
            group["stories"].append(StorySerializer(story, context={"request": request}).data)
            group["latest_at"] = story.created_at

        ordered = sorted(
            groups.values(),
            key=lambda g: (not g["is_own"], not g["has_unseen"], -g["latest_at"].timestamp()),
        )
        for group in ordered:
            group["resume_index"] = group["resume_index"] or 0
            group["latest_at"] = group["latest_at"].isoformat()
        return Response({"results": ordered})

    def perform_create(self, serializer):
        from notifications.services import create_notification

        story = serializer.save(author=self.request.user, expires_at=timezone.now() + STORY_LIFETIME)
        mentioned = {sticker["user_id"] for sticker in story.stickers if sticker["type"] == "mention"}
        for user in User.objects.filter(id__in=mentioned):
            create_notification(recipient=user, actor=story.author, notification_type="story_mention")

    @action(detail=True, methods=["post"], url_path="vote")
    def vote(self, request, pk=None):
        """POST {option: 0|1} - answer the story's poll once."""

        story = self.get_object()
        if not any(sticker["type"] == "poll" for sticker in story.stickers):
            return Response({"detail": "This story has no poll."}, status=status.HTTP_400_BAD_REQUEST)
        option = request.data.get("option")
        if option not in (0, 1):
            return Response({"option": ["Choose 0 or 1."]}, status=status.HTTP_400_BAD_REQUEST)
        StoryPollVote.objects.get_or_create(story=story, user=request.user, defaults={"option": option})
        return Response(StorySerializer(story, context={"request": request}).data)

    def perform_destroy(self, instance):
        if instance.author_id != self.request.user.id:
            raise PermissionDenied("You can only delete your own stories.")
        instance.delete()

    @action(detail=True, methods=["post"], url_path="view")
    def view(self, request, pk=None):
        story = self.get_object()
        _, created = StoryView.objects.get_or_create(story=story, user=request.user)
        return Response({"viewed": True, "created": created}, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="viewers")
    def viewers(self, request, pk=None):
        """'Seen by' list - only the story's author can read it."""

        story = self.get_object()
        if story.author_id != request.user.id:
            raise PermissionDenied("Only the author can see who viewed this story.")
        views = story.views.exclude(user=request.user).select_related("user").order_by("-viewed_at")
        return Response(
            {
                "count": views.count(),
                "results": [
                    {
                        "id": view.user_id,
                        "username": view.user.username,
                        "avatar_url": view.user.avatar_url,
                        "viewed_at": view.viewed_at,
                    }
                    for view in views
                ],
            }
        )
