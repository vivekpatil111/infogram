from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    email = models.EmailField(unique=True)
    bio = models.TextField(blank=True)
    avatar_url = models.URLField(blank=True)
    # Private accounts: new followers must be approved, and posts/stories/
    # reels are visible only to the owner and approved followers.
    is_private = models.BooleanField(default=False)
    # Up to MAX_PROFILE_LINKS [{"title": str, "url": "https://..."}], shown on the profile.
    links = models.JSONField(default=list, blank=True)

    REQUIRED_FIELDS = ["email"]


class FollowQuerySet(models.QuerySet):
    def accepted(self):
        return self.filter(status=Follow.Status.ACCEPTED)

    def pending(self):
        return self.filter(status=Follow.Status.PENDING)


class Follow(models.Model):
    class Status(models.TextChoices):
        ACCEPTED = "accepted", "Accepted"
        PENDING = "pending", "Pending"  # a follow request to a private account

    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name="following")
    following = models.ForeignKey(User, on_delete=models.CASCADE, related_name="followers")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACCEPTED)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = FollowQuerySet.as_manager()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["follower", "following"], name="unique_follow")]
        indexes = [models.Index(fields=["following", "status", "-created_at"])]
        ordering = ["-created_at", "-id"]
