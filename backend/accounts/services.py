"""Follow / follow-request state transitions.

  public account:  follow -> accepted immediately   (notify "follow")
  private account: follow -> pending               (notify "follow_request")
                   accept -> accepted              (notify requester "follow_accept")
                   decline / cancel -> deleted     (request notification removed)
  switching private -> public approves every pending request.
"""

from django.db import transaction

from notifications.services import create_notification, remove_notification

from .models import Follow


def follow_state(viewer, target):
    """'self' | 'following' | 'requested' | 'none'."""

    if viewer.pk == target.pk:
        return "self"
    status = Follow.objects.filter(follower=viewer, following=target).values_list("status", flat=True).first()
    return {Follow.Status.ACCEPTED: "following", Follow.Status.PENDING: "requested"}.get(status, "none")


def can_view_content(viewer, target):
    return not target.is_private or follow_state(viewer, target) in {"self", "following"}


@transaction.atomic
def request_follow(follower, target):
    """Follow `target`, or send a request if the account is private. Idempotent."""

    from safety.querysets import is_blocked_between

    if is_blocked_between(follower, target):
        raise PermissionError("You can't follow this account.")
    status = Follow.Status.PENDING if target.is_private else Follow.Status.ACCEPTED
    follow, created = Follow.objects.get_or_create(follower=follower, following=target, defaults={"status": status})
    if created:
        notification_type = "follow_request" if status == Follow.Status.PENDING else "follow"
        create_notification(recipient=target, actor=follower, notification_type=notification_type)
    return follow, created


@transaction.atomic
def remove_follow(follower, target):
    """Unfollow, or cancel a pending request. Returns the removed status or None."""

    follow = Follow.objects.filter(follower=follower, following=target).first()
    if follow is None:
        return None
    follow.delete()
    remove_notification(recipient=target, actor=follower, notification_type="follow")
    remove_notification(recipient=target, actor=follower, notification_type="follow_request")
    return follow.status


@transaction.atomic
def accept_request(follow):
    follow.status = Follow.Status.ACCEPTED
    follow.save(update_fields=["status"])
    _convert_request_notification(follow)
    create_notification(recipient=follow.follower, actor=follow.following, notification_type="follow_accept")


@transaction.atomic
def decline_request(follow):
    remove_notification(recipient=follow.following, actor=follow.follower, notification_type="follow_request")
    follow.delete()


@transaction.atomic
def approve_all_pending(user):
    """Called when a private account goes public."""

    for follow in Follow.objects.pending().filter(following=user).select_related("follower", "following"):
        follow.status = Follow.Status.ACCEPTED
        follow.save(update_fields=["status"])
        _convert_request_notification(follow)


def _convert_request_notification(follow):
    """The 'requested to follow you' item becomes 'started following you'."""

    from notifications.models import Notification

    Notification.objects.filter(
        recipient=follow.following, actor=follow.follower, notification_type="follow_request"
    ).update(notification_type="follow")
