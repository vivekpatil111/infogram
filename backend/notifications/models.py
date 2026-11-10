from django.conf import settings
from django.db import models

from posts.models import Comment, Post


class Notification(models.Model):
    class Type(models.TextChoices):
        LIKE = "like", "Like"
        COMMENT = "comment", "Comment"
        FOLLOW = "follow", "Follow"
        SAVE = "save", "Save"
        FOLLOW_REQUEST = "follow_request", "Follow request"
        FOLLOW_ACCEPT = "follow_accept", "Follow request accepted"
        COMMENT_LIKE = "comment_like", "Comment like"
        REPLY = "reply", "Reply"

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_notifications")
    notification_type = models.CharField(max_length=20, choices=Type.choices)
    # Deleting the post/comment removes its activity items, as on Instagram.
    post = models.ForeignKey(Post, on_delete=models.CASCADE, null=True, blank=True, related_name="notifications")
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, null=True, blank=True, related_name="notifications")
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["recipient", "-created_at"]),
            models.Index(fields=["recipient", "read_at"]),
        ]
