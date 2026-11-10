from django.conf import settings
from django.db import models


class Story(models.Model):
    class MediaType(models.TextChoices):
        IMAGE = "image", "Image"
        VIDEO = "video", "Video"

    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="stories")
    media_type = models.CharField(max_length=10, choices=MediaType.choices)
    media_url = models.URLField(max_length=2048)
    thumbnail_url = models.URLField(max_length=2048, blank=True)
    caption = models.CharField(max_length=180, blank=True)
    # Up to 3 stickers placed on the story: mention / link / poll, each with
    # x, y as percentages of the frame. See StorySerializer.validate_stickers.
    stickers = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["author", "-expires_at"]),
            models.Index(fields=["-expires_at", "-created_at"]),
        ]


class StoryView(models.Model):
    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name="views")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="story_views")
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["story", "user"], name="unique_story_view")]


class StoryPollVote(models.Model):
    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name="poll_votes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="story_poll_votes")
    option = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["story", "user"], name="unique_story_poll_vote")]
