from django.shortcuts import get_object_or_404
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import CursorPagination
from rest_framework.response import Response

from notifications.services import create_notification, remove_notification
from safety.querysets import blocked_by_me, not_blocked_q

from .models import Comment, CommentLike, PostLike, PostSave, PostView
from .pagination import PostCursorPagination
from .querysets import comments_with_stats, posts_for_user
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
        if self.action in {"like", "save", "comments", "delete_comment", "like_comment", "likers", "seen", "open_resource"}:
            return [permissions.IsAuthenticated()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = posts_for_user(self.request.user)
        if self.action == "list":
            queryset = queryset.filter(is_published=True)
        return queryset

    def perform_create(self, serializer):
        from media_api.transcode import queue_transcode

        queue_transcode(serializer.save(author=self.request.user))

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

    @action(detail=True, methods=["post"], url_path=r"resources/(?P<resource_id>\d+)/open")
    def open_resource(self, request, pk=None, resource_id=None):
        """Count a Resource Drawer open (creator stats)."""

        from django.db.models import F

        post = self.get_object()
        updated = post.resources.filter(pk=resource_id).update(open_count=F("open_count") + 1)
        if not updated:
            return Response({"detail": "Resource not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response({"opened": True})

    @action(detail=False, methods=["post"], url_path="seen")
    def seen(self, request):
        """POST {ids: [...]} - posts that were on screen; first view only."""

        ids = request.data.get("ids")
        if not isinstance(ids, list) or not all(isinstance(i, int) for i in ids) or len(ids) > 100:
            return Response({"ids": ["Send up to 100 post ids."]}, status=status.HTTP_400_BAD_REQUEST)
        visible = list(posts_for_user(request.user).filter(id__in=ids, is_published=True).values_list("id", flat=True))
        PostView.objects.bulk_create([PostView(post_id=pid, user=request.user) for pid in visible], ignore_conflicts=True)
        return Response({"recorded": len(visible)})

    @action(detail=True, methods=["get"], url_path="likers")
    def likers(self, request, pk=None):
        """People who liked the post, most recent first ("Liked by" dialog)."""

        from accounts.querysets import users_with_stats
        from accounts.serializers import PublicUserSerializer
        from accounts.views import UserCursorPagination

        post = self.get_object()
        people = users_with_stats(request.user).filter(post_likes__post=post).exclude(id__in=blocked_by_me(request.user))
        paginator = UserCursorPagination()
        page = paginator.paginate_queryset(people, request, view=self)
        data = PublicUserSerializer(page, many=True, context={"request": request}).data
        return paginator.get_paginated_response(data)

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
        """GET: top-level comments, or ?parent=<id> for that comment's replies.
        POST: {text, parent_id?}. Replying to a reply attaches to its parent."""

        post = self.get_object()
        if request.method == "GET":
            paginator = CommentCursorPagination()
            comments = comments_with_stats(request.user).filter(post=post)
            parent = request.query_params.get("parent")
            comments = comments.filter(parent_id=int(parent)) if parent and parent.isdigit() else comments.filter(parent__isnull=True)
            page = paginator.paginate_queryset(comments, request, view=self)
            return paginator.get_paginated_response(CommentSerializer(page, many=True).data)
        serializer = CommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        parent = None
        parent_id = request.data.get("parent_id")
        if parent_id not in (None, ""):
            parent = Comment.objects.filter(pk=parent_id, post=post).select_related("parent", "author").first()
            if parent is None:
                return Response({"parent_id": ["That comment doesn't exist on this post."]}, status=status.HTTP_400_BAD_REQUEST)
            parent = parent.parent or parent
        comment = serializer.save(post=post, author=request.user, parent=parent)
        create_notification(recipient=post.author, actor=request.user, notification_type="comment", post=post, comment=comment)
        if parent and parent.author_id != post.author_id:
            create_notification(recipient=parent.author, actor=request.user, notification_type="reply", post=post, comment=comment)
        return Response(CommentSerializer(comments_with_stats(request.user).get(pk=comment.pk)).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post", "delete"], url_path=r"comments/(?P<comment_id>\d+)/like")
    def like_comment(self, request, pk=None, comment_id=None):
        post = self.get_object()
        comment = get_object_or_404(Comment.objects.filter(not_blocked_q(request.user)), pk=comment_id, post=post)
        if request.method == "POST":
            _, created = CommentLike.objects.get_or_create(comment=comment, user=request.user)
            if created:
                create_notification(recipient=comment.author, actor=request.user, notification_type="comment_like", post=post, comment=comment)
        else:
            if CommentLike.objects.filter(comment=comment, user=request.user).delete()[0]:
                remove_notification(recipient=comment.author, actor=request.user, notification_type="comment_like", post=post, comment=comment)
        return Response({"liked": request.method == "POST", "like_count": comment.likes.count()})

    @action(detail=True, methods=["delete"], url_path=r"comments/(?P<comment_id>\d+)")
    def delete_comment(self, request, pk=None, comment_id=None):
        post = self.get_object()
        comment = get_object_or_404(Comment, pk=comment_id, post=post)
        # The comment's author or the post's owner may delete it.
        if request.user.id not in {comment.author_id, post.author_id}:
            return Response({"detail": "You can't delete this comment."}, status=status.HTTP_403_FORBIDDEN)
        comment.delete()  # Its notification cascades.
        return Response(status=status.HTTP_204_NO_CONTENT)
