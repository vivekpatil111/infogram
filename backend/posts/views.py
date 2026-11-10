from django.shortcuts import get_object_or_404
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import CursorPagination
from rest_framework.response import Response

from notifications.services import create_notification, remove_notification
from safety.querysets import not_blocked_q

from .models import Comment, PostLike, PostSave
from .pagination import PostCursorPagination
from .querysets import posts_for_user
from .serializers import CommentSerializer, PostSerializer


class IsPostOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, post):
        if request.method in permissions.SAFE_METHODS:
            return True
        return post.author_id == request.user.id


class CommentCursorPagination(CursorPagination):
    page_size = 30
    page_size_query_param = "limit"
    max_page_size = 100
    ordering = ("created_at", "id")


class PostViewSet(viewsets.ModelViewSet):
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticated, IsPostOwnerOrReadOnly]
    pagination_class = PostCursorPagination

    def get_permissions(self):
        # Engagement endpoints are allowed on anyone's post.
        if self.action in {"like", "save", "comments", "delete_comment"}:
            return [permissions.IsAuthenticated()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = posts_for_user(self.request.user)
        if self.action == "list":
            queryset = queryset.filter(is_published=True)
        return queryset

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(detail=True, methods=["post", "delete"], url_path="like")
    def like(self, request, pk=None):
        post = self.get_object()
        if request.method == "POST":
            _, created = PostLike.objects.get_or_create(post=post, user=request.user)
            if created:
                create_notification(recipient=post.author, actor=request.user, notification_type="like", post=post)
            return Response({"liked": True, "created": created}, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
        deleted, _ = PostLike.objects.filter(post=post, user=request.user).delete()
        if deleted:
            remove_notification(recipient=post.author, actor=request.user, notification_type="like", post=post)
        return Response({"liked": False})

    @action(detail=True, methods=["post", "delete"], url_path="save")
    def save(self, request, pk=None):
        post = self.get_object()
        if request.method == "POST":
            _, created = PostSave.objects.get_or_create(post=post, user=request.user)
            if created:
                create_notification(recipient=post.author, actor=request.user, notification_type="save", post=post)
            return Response({"saved": True, "created": created}, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
        deleted, _ = PostSave.objects.filter(post=post, user=request.user).delete()
        if deleted:
            remove_notification(recipient=post.author, actor=request.user, notification_type="save", post=post)
        return Response({"saved": False})

    @action(detail=True, methods=["get", "post"], url_path="comments")
    def comments(self, request, pk=None):
        post = self.get_object()
        if request.method == "GET":
            paginator = CommentCursorPagination()
            comments = Comment.objects.filter(post=post).filter(not_blocked_q(request.user)).select_related("author")
            page = paginator.paginate_queryset(comments, request, view=self)
            return paginator.get_paginated_response(CommentSerializer(page, many=True).data)
        serializer = CommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        comment = serializer.save(post=post, author=request.user)
        create_notification(recipient=post.author, actor=request.user, notification_type="comment", post=post, comment=comment)
        return Response(CommentSerializer(comment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path=r"comments/(?P<comment_id>\d+)")
    def delete_comment(self, request, pk=None, comment_id=None):
        post = self.get_object()
        comment = get_object_or_404(Comment, pk=comment_id, post=post)
        # The comment's author or the post's owner may delete it.
        if request.user.id not in {comment.author_id, post.author_id}:
            return Response({"detail": "You can't delete this comment."}, status=status.HTTP_403_FORBIDDEN)
        comment.delete()  # Its notification cascades.
        return Response(status=status.HTTP_204_NO_CONTENT)
