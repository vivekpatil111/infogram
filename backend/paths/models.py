from django.conf import settings
from django.db import models

from posts.verticals import VERTICAL_CHOICES


class LearningPath(models.Model):
    """An ordered series of a creator's own posts ("Mastering Startup Law", 10 reels).
    The profile's "Paths" tab is the creator's syllabus."""

    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="learning_paths")
    title = models.CharField(max_length=80)
    description = models.TextField(blank=True, max_length=500)
    vertical = models.CharField(max_length=20, blank=True, choices=VERTICAL_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]

    def __str__(self):
        return self.title


class PathItem(models.Model):
    path = models.ForeignKey(LearningPath, on_delete=models.CASCADE, related_name="items")
    post = models.ForeignKey("posts.Post", on_delete=models.CASCADE, related_name="path_items")
    position = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["position"]
        constraints = [models.UniqueConstraint(fields=["path", "post"], name="unique_path_post")]
