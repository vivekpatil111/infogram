from .models import Notification


def create_notification(*, recipient, actor, notification_type, post=None, comment=None):
    from safety.querysets import is_blocked_between

    if recipient.id == actor.id or is_blocked_between(recipient, actor):
        return None
    notification, created = Notification.objects.get_or_create(
        recipient=recipient,
        actor=actor,
        notification_type=notification_type,
        post=post,
        comment=comment,
    )
    if created:
        _push(notification)
    return notification


def _push(notification):
    from .push import push_configured, send_to_user
    from .serializers import NotificationSerializer

    if not push_configured():
        return
    text = NotificationSerializer(notification).data["text"]
    url = f"/post/{notification.post_id}" if notification.post_id else f"/u/{notification.actor.username}"
    if notification.notification_type in {"follow_request"}:
        url = "/activity"
    send_to_user(notification.recipient_id, title="Infogram", body=f"{notification.actor.username} {text}", url=url, tag=f"n{notification.id}")


def remove_notification(*, recipient, actor, notification_type, post=None, comment=None):
    """Undo an activity item when its action is reversed (unlike, unfollow...)."""

    items = Notification.objects.filter(recipient=recipient, actor=actor, notification_type=notification_type, post=post)
    if comment is not None:
        items = items.filter(comment=comment)
    items.delete()
