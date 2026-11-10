from django.db.models import Exists, OuterRef, Prefetch, Q, Subquery

from accounts.models import Follow
from accounts.querysets import count_subquery, visible_author_q
from safety.querysets import not_blocked_q

from .models import Comment, CommentLike, Post, PostLike, PostMedia, PostResource, PostSave, PostView


def _path_items():
    from django.db.models import Count

    from paths.models import PathItem

    return PathItem.objects.select_related("path").annotate(path_total=Count("path__items"))


def posts_for_user(user):
    """Posts the viewer may see, annotated with engagement counts and state.

    Counts are scalar subqueries rather than JOIN + COUNT(DISTINCT): joining
    likes, comments and saves at once multiplies rows per post.
    """

    return (
        Post.objects.filter(Q(is_published=True) | Q(author=user))
        # Private accounts: only the owner and approved followers see posts.
        .filter(visible_author_q(user))
        # Blocks hide content in both directions.
        .filter(not_blocked_q(user))
        .select_related("author", "location")
        .prefetch_related(
            "hashtags",
            Prefetch("media_items", queryset=PostMedia.objects.order_by("position")),
            Prefetch("resources", queryset=PostResource.objects.select_related("post").order_by("position", "id")),
            Prefetch("path_items", queryset=_path_items()),
        )
        .annotate(
            like_count=count_subquery(PostLike.objects.filter(post=OuterRef("pk")), "post"),
            comment_count=count_subquery(Comment.objects.filter(post=OuterRef("pk")), "post"),
            save_count=count_subquery(PostSave.objects.filter(post=OuterRef("pk")), "post"),
            view_count=count_subquery(PostView.objects.filter(post=OuterRef("pk")), "post"),
            seen_by_me=Exists(PostView.objects.filter(post=OuterRef("pk"), user=user)),
            liked_by_me=Exists(PostLike.objects.filter(post=OuterRef("pk"), user=user)),
            saved_by_me=Exists(PostSave.objects.filter(post=OuterRef("pk"), user=user)),
            author_follow_status=Subquery(
                Follow.objects.filter(follower=user, following=OuterRef("author_id")).values("status")[:1]
            ),
        )
    )


def comments_with_stats(viewer):
    """Comments the viewer may see, with like/reply counts and liked_by_me."""

    return (
        Comment.objects.filter(not_blocked_q(viewer))
        .select_related("author")
        .annotate(
            like_count=count_subquery(CommentLike.objects.filter(comment=OuterRef("pk")), "comment"),
            reply_count=count_subquery(Comment.objects.filter(parent=OuterRef("pk")).filter(not_blocked_q(viewer)), "parent"),
            liked_by_me=Exists(CommentLike.objects.filter(comment=OuterRef("pk"), user=viewer)),
        )
    )
