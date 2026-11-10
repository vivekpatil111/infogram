from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    actor = serializers.SerializerMethodField()
    text = serializers.SerializerMethodField()
    post_id = serializers.IntegerField(source="post.id", read_only=True, allow_null=True, default=None)
    post_thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ["id", "actor", "notification_type", "text", "post_id", "post_thumbnail_url", "created_at", "read_at"]
        read_only_fields = fields

    def get_actor(self, notification):
        return {
            "id": notification.actor_id,
            "username": notification.actor.username,
            "avatar_url": notification.actor.avatar_url,
        }

    def get_post_thumbnail_url(self, notification):
        post = notification.post
        if post is None:
            return None
        return post.thumbnail_url or (post.media_url if post.media_type != "video" else "")

    def get_text(self, notification):
        if notification.notification_type == Notification.Type.COMMENT and notification.comment:
            snippet = notification.comment.text
            if len(snippet) > 80:
                snippet = f"{snippet[:77]}..."
            return f"commented: {snippet}"
        return {
            Notification.Type.LIKE: "liked your post.",
            Notification.Type.COMMENT: "commented on your post.",
            Notification.Type.FOLLOW: "started following you.",
            Notification.Type.SAVE: "saved your post.",
            Notification.Type.FOLLOW_REQUEST: "requested to follow you.",
            Notification.Type.FOLLOW_ACCEPT: "accepted your follow request.",
        }[notification.notification_type]
