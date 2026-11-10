from django.db import transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status, viewsets
from rest_framework.response import Response

from accounts.models import User
from accounts.services import can_view_content
from posts.models import PostView
from posts.querysets import posts_for_user
from posts.serializers import PostSerializer
from safety.querysets import is_blocked_between

from .models import LearningPath, PathItem
from .serializers import LearningPathSerializer


class IsCreatorOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, path):
        return request.method in permissions.SAFE_METHODS or path.creator_id == request.user.id


class LearningPathViewSet(viewsets.ModelViewSet):
    """Learning Paths.

    GET  /paths/?creator=<username>   a creator's paths (their syllabus)
    POST /paths/                      {title, description?, vertical?, post_ids}
    GET  /paths/{id}/                 the path with its lessons and your progress
    PATCH/DELETE /paths/{id}/         creator only (post_ids replaces the order)
    """

    serializer_class = LearningPathSerializer
    permission_classes = [permissions.IsAuthenticated, IsCreatorOrReadOnly]
    pagination_class = None

    def get_queryset(self):
        queryset = LearningPath.objects.select_related("creator").prefetch_related(
            Prefetch("items", queryset=PathItem.objects.select_related("post"))
        )
        if self.action == "list":
            creator = get_object_or_404(User, username__iexact=self.request.query_params.get("creator", self.request.user.username))
            if is_blocked_between(self.request.user, creator):
                return queryset.none()
            queryset = queryset.filter(creator=creator)
        return queryset

    def list(self, request, *args, **kwargs):
        paths = list(self.get_queryset())
        own = request.query_params.get("creator", request.user.username).lower() == request.user.username.lower()
        if not own:
            paths = [path for path in paths if path.items.all()]  # others don't see empty paths
        return Response(self.get_serializer(paths, many=True).data)

    def retrieve(self, request, *args, **kwargs):
        path = self.get_object()
        creator = path.creator
        if is_blocked_between(request.user, creator):
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        data = self.get_serializer(path).data
        if not can_view_content(request.user, creator):
            data.update({"lessons": [], "locked": True, "progress": {"seen": 0, "total": data["lesson_count"]}, "next_post_id": None})
            return Response(data)
        order = [item.post_id for item in sorted(path.items.all(), key=lambda item: item.position)]
        posts = {post.id: post for post in posts_for_user(request.user).filter(id__in=order, is_published=True)}
        lessons = [posts[pid] for pid in order if pid in posts]
        seen = set(PostView.objects.filter(user=request.user, post_id__in=order).values_list("post_id", flat=True))
        data["lessons"] = PostSerializer(lessons, many=True, context={"request": request}).data
        data["locked"] = False
        data["progress"] = {"seen": len([p for p in lessons if p.id in seen]), "total": len(lessons)}
        data["next_post_id"] = next((p.id for p in lessons if p.id not in seen), None)
        return Response(data)

    @transaction.atomic
    def perform_create(self, serializer):
        post_ids = serializer.validated_data.pop("post_ids")
        path = serializer.save(creator=self.request.user)
        self._set_items(path, post_ids)

    @transaction.atomic
    def perform_update(self, serializer):
        post_ids = serializer.validated_data.pop("post_ids", None)
        path = serializer.save()
        if post_ids is not None:
            self._set_items(path, post_ids)

    @staticmethod
    def _set_items(path, post_ids):
        path.items.all().delete()
        PathItem.objects.bulk_create([PathItem(path=path, post_id=pid, position=i) for i, pid in enumerate(post_ids)])
