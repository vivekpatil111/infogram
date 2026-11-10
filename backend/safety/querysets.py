"""Block / mute filters shared by every content queryset."""

from django.db.models import Q

from .models import Block, Mute


def blocked_by_me(user):
    return Block.objects.filter(blocker=user).values("blocked_id")


def blocked_me(user):
    return Block.objects.filter(blocked=user).values("blocker_id")


def not_blocked_q(user, field="author"):
    """Rows whose `field` user has no block with `user` in either direction."""

    return ~Q(**{f"{field}_id__in": blocked_by_me(user)}) & ~Q(**{f"{field}_id__in": blocked_me(user)})


def muted_posts(user):
    return Mute.objects.filter(muter=user, posts=True).values("muted_id")


def muted_stories(user):
    return Mute.objects.filter(muter=user, stories=True).values("muted_id")


def is_blocked_between(a, b):
    return Block.objects.filter(Q(blocker=a, blocked=b) | Q(blocker=b, blocked=a)).exists()
