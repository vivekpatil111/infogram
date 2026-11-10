"""Candidate retrieval + scoring for Infogram's home, reels and explore feeds.

What the REA capture of a signed-in Instagram session verified (product level):
  * the home feed shows posts from accounts you follow first, and then a
    separate "Suggested posts" section from accounts you don't follow;
  * Reels and Explore are separate surfaces that recommend unconnected content.

What it could NOT verify: Instagram's server-side ranking model and weights
are never sent to the browser. The score below is Infogram's own explainable
heuristic, biased toward useful content (saves/comments > likes).
"""

from datetime import timedelta

from django.db.models import Case, Exists, F, FloatField, IntegerField, OuterRef, Q, Value, When
from django.db.models.functions import Cast
from django.utils import timezone

from accounts.models import Follow
from accounts.querysets import followed_ids
from safety.querysets import muted_posts

from .querysets import posts_for_user


# Tier ordering for the home feed: 0 = your network, 1 = suggested.
IN_NETWORK = 0
SUGGESTED = 1


def network_filter(user):
    """Posts authored by the user or by accounts they follow (no JOIN fan-out)."""

    return Q(author=user) | Q(author_id__in=followed_ids(user))


def ranked_posts_for_user(user, *, scope="all", media_type=None, topic=""):
    """Return published posts annotated with `ranking_score` and `feed_tier`.

    scope:
      "network"  - only your own and followed creators' posts
      "all"      - every published post (network posts still get a bonus)
      "discover" - exclude your own and followed creators' posts (Explore)
    """

    now = timezone.now()
    # Muted accounts drop out of every ranked feed (their profile stays reachable).
    queryset = posts_for_user(user).filter(is_published=True).exclude(author_id__in=muted_posts(user))

    if scope == "network":
        queryset = queryset.filter(network_filter(user))
    elif scope == "discover":
        queryset = queryset.exclude(network_filter(user))

    if media_type:
        queryset = queryset.filter(media_type=media_type)
    if topic:
        tag = topic.lstrip("#").lower()
        queryset = queryset.filter(
            Q(topic__icontains=topic) | Q(caption__icontains=topic) | Q(hashtags__name=tag)
        ).distinct()

    followed_author = Exists(
        Follow.objects.accepted().filter(follower=user, following=OuterRef("author_id"))
    )
    queryset = queryset.annotate(followed_author=followed_author)

    engagement = (
        Cast(F("like_count"), FloatField()) * 1.0
        + Cast(F("comment_count"), FloatField()) * 3.0
        + Cast(F("save_count"), FloatField()) * 5.0
    )
    relationship = Case(
        When(author=user, then=Value(25.0)),
        When(followed_author=True, then=Value(30.0)),
        default=Value(0.0),
        output_field=FloatField(),
    )
    freshness = Case(
        When(created_at__gte=now - timedelta(days=1), then=Value(20.0)),
        When(created_at__gte=now - timedelta(days=7), then=Value(8.0)),
        default=Value(0.0),
        output_field=FloatField(),
    )
    quality = Case(When(topic__gt="", then=Value(15.0)), default=Value(0.0), output_field=FloatField())
    format_bonus = Case(
        When(media_type="video", then=Value(4.0)),
        When(media_type="carousel", then=Value(2.0)),
        default=Value(0.0),
        output_field=FloatField(),
    )
    tier = Case(
        When(author=user, then=Value(IN_NETWORK)),
        When(followed_author=True, then=Value(IN_NETWORK)),
        default=Value(SUGGESTED),
        output_field=IntegerField(),
    )

    return queryset.annotate(
        ranking_score=engagement + relationship + freshness + quality + format_bonus,
        feed_tier=tier,
    )


def home_feed(user, *, mode="for_you", topic=""):
    """Following-first home feed: network posts, then suggested posts."""

    if mode == "following":
        return ranked_posts_for_user(user, scope="network", topic=topic).order_by(
            "-ranking_score", "-created_at", "-id"
        )
    return ranked_posts_for_user(user, scope="all", topic=topic).order_by(
        "feed_tier", "-ranking_score", "-created_at", "-id"
    )


def reels_feed(user, *, mode="for_you", topic=""):
    """Reels recommend across the whole catalogue; following mode is network only."""

    scope = "network" if mode == "following" else "all"
    return ranked_posts_for_user(user, scope=scope, media_type="video", topic=topic).order_by(
        "-ranking_score", "-created_at", "-id"
    )


def explore_feed(user, *, topic=""):
    return ranked_posts_for_user(user, scope="discover", topic=topic).order_by(
        "-ranking_score", "-created_at", "-id"
    )
