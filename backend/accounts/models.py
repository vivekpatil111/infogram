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
    # Expert verification: granted by staff (see ExpertApplication), never self-set.
    expert_vertical = models.CharField(max_length=20, blank=True)
    expert_title = models.CharField(max_length=80, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    @property
    def is_verified(self):
        return self.verified_at is not None

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


class ExpertApplication(models.Model):
    """A request to be shown as a verified expert in one Knowledge Vertical."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="expert_applications")
    vertical = models.CharField(max_length=20)
    title = models.CharField(max_length=80, help_text='Shown on the badge, e.g. "Chartered Accountant".')
    evidence_url = models.URLField(max_length=500, help_text="Licence, publication, employer page...")
    note = models.TextField(blank=True, max_length=1000)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} -> {self.vertical} ({self.status})"

    def approve(self):
        from django.utils import timezone

        now = timezone.now()
        self.status, self.reviewed_at = self.Status.APPROVED, now
        self.save(update_fields=["status", "reviewed_at"])
        self.user.expert_vertical, self.user.expert_title, self.user.verified_at = self.vertical, self.title, now
        self.user.save(update_fields=["expert_vertical", "expert_title", "verified_at"])

    def reject(self):
        from django.utils import timezone

        self.status, self.reviewed_at = self.Status.REJECTED, timezone.now()
        self.save(update_fields=["status", "reviewed_at"])
