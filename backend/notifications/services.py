from .models import Notification


def create_notification(*, recipient, actor, notification_type, post=None, comment=None):
    from safety.querysets import is_blocked_between

    if recipient.id == actor.id or is_blocked_between(recipient, actor):
        return None
    notification, _ = Notification.objects.get_or_create(
        recipient=recipient,
        actor=actor,
        notification_type=notification_type,
        post=post,
        comment=comment,
    )
    return notification


def remove_notification(*, recipient, actor, notification_type, post=None):
    """Undo an activity item when its action is reversed (unlike, unfollow...)."""

    Notification.objects.filter(
        recipient=recipient,
        actor=actor,
        notification_type=notification_type,
        post=post,
    ).delete()
