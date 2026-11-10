from django.db import transaction
from django.db.models import Q

from .models import Block, Mute


@transaction.atomic
def block(blocker, target):
    """Block `target`: cut follows both ways and clear activity between them."""

    from accounts.models import Follow
    from notifications.models import Notification

    _, created = Block.objects.get_or_create(blocker=blocker, blocked=target)
    Follow.objects.filter(Q(follower=blocker, following=target) | Q(follower=target, following=blocker)).delete()
    Notification.objects.filter(
        Q(recipient=blocker, actor=target) | Q(recipient=target, actor=blocker)
    ).delete()
    Mute.objects.filter(muter=blocker, muted=target).delete()  # redundant once blocked
    return created


def unblock(blocker, target):
    # Unblocking never restores old follows; they have to follow again.
    return Block.objects.filter(blocker=blocker, blocked=target).delete()[0] > 0


def set_mute(muter, target, *, posts, stories):
    if not posts and not stories:
        Mute.objects.filter(muter=muter, muted=target).delete()
        return None
    mute, _ = Mute.objects.update_or_create(muter=muter, muted=target, defaults={"posts": posts, "stories": stories})
    return mute
