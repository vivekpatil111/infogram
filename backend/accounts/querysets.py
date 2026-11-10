from django.contrib.auth import get_user_model
from django.db.models import Count, Exists, IntegerField, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce

from .models import Follow


User = get_user_model()


def count_subquery(queryset, group_field):
    """COUNT(*) of `queryset` correlated to the outer row, as a scalar subquery.

    Subqueries avoid the row explosion of joining several reverse relations
    (followers x following x posts) and then COUNT(DISTINCT ...).
    """

    counted = queryset.order_by().values(group_field).annotate(_count=Count("pk")).values("_count")[:1]
    return Coalesce(Subquery(counted, output_field=IntegerField()), Value(0))


def followed_ids(viewer):
    """Ids of accounts the viewer follows (accepted only), as a subquery."""

    return Follow.objects.accepted().filter(follower=viewer).values("following_id")


def visible_author_q(viewer, prefix="author"):
    """Content by this author is visible: public, own, or an approved follower."""

    return (
        Q(**{f"{prefix}__is_private": False})
        | Q(**{prefix: viewer})
        | Q(**{f"{prefix}_id__in": followed_ids(viewer)})
    )


def users_with_stats(viewer):
    from posts.models import Post

    from safety.models import Block, Mute
    from safety.querysets import blocked_me

    accepted = Follow.objects.accepted()
    # Someone who blocked the viewer doesn't exist for them ("User not found").
    return User.objects.filter(is_active=True).exclude(pk__in=blocked_me(viewer)).annotate(
        followers_count=count_subquery(accepted.filter(following=OuterRef("pk")), "following"),
        following_count=count_subquery(accepted.filter(follower=OuterRef("pk")), "follower"),
        posts_count=count_subquery(
            Post.objects.filter(author=OuterRef("pk"), is_published=True), "author"
        ),
        is_following=Exists(accepted.filter(follower=viewer, following=OuterRef("pk"))),
        is_requested=Exists(Follow.objects.pending().filter(follower=viewer, following=OuterRef("pk"))),
        follows_me=Exists(accepted.filter(follower=OuterRef("pk"), following=viewer)),
        is_blocked=Exists(Block.objects.filter(blocker=viewer, blocked=OuterRef("pk"))),
        posts_muted=Exists(Mute.objects.filter(muter=viewer, muted=OuterRef("pk"), posts=True)),
        stories_muted=Exists(Mute.objects.filter(muter=viewer, muted=OuterRef("pk"), stories=True)),
    )
