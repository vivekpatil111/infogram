from django.conf import settings
from django.db import models


class Block(models.Model):
    """`blocker` blocked `blocked`. Hides both accounts' content from each
    other and stops follows, messages, comments and notifications between them."""

    blocker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="blocks_made")
    blocked = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="blocks_received")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["blocker", "blocked"], name="unique_block")]
        ordering = ["-created_at", "-id"]


class Mute(models.Model):
    """Silently hide someone's posts and/or stories from your feeds. They aren't told."""

    muter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mutes_made")
    muted = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mutes_received")
    posts = models.BooleanField(default=True)
    stories = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["muter", "muted"], name="unique_mute")]


class Report(models.Model):
    class TargetType(models.TextChoices):
        POST = "post", "Post"
        COMMENT = "comment", "Comment"
        STORY = "story", "Story"
        USER = "user", "Account"

    class Reason(models.TextChoices):
        SPAM = "spam", "It's spam"
        FALSE_INFORMATION = "false_information", "False or misleading information"
        SCAM = "scam", "Scam or fraud"
        HARASSMENT = "harassment", "Bullying or harassment"
        HATE = "hate", "Hate speech or symbols"
        VIOLENCE = "violence", "Violence or dangerous organisations"
        NUDITY = "nudity", "Nudity or sexual activity"
        SELF_HARM = "self_harm", "Suicide or self-injury"
        INTELLECTUAL_PROPERTY = "intellectual_property", "Intellectual property violation"
        IMPERSONATION = "impersonation", "Pretending to be someone else"
        OTHER = "other", "Something else"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ACTIONED = "actioned", "Actioned (content removed)"
        DISMISSED = "dismissed", "Dismissed (no violation)"

    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reports_made")
    target_type = models.CharField(max_length=10, choices=TargetType.choices)
    # Exactly one target is set, matching target_type. SET_NULL keeps the
    # report (and its audit trail) after the content itself is deleted.
    post = models.ForeignKey("posts.Post", on_delete=models.SET_NULL, null=True, blank=True, related_name="reports")
    comment = models.ForeignKey("posts.Comment", on_delete=models.SET_NULL, null=True, blank=True, related_name="reports")
    story = models.ForeignKey("stories.Story", on_delete=models.SET_NULL, null=True, blank=True, related_name="reports")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="reports_received"
    )
    # Who owns the reported content, for the moderation queue and repeat-offender checks.
    target_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="reports_against"
    )
    reason = models.CharField(max_length=30, choices=Reason.choices)
    details = models.TextField(blank=True, max_length=1000)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="reports_reviewed"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["status", "-created_at"]), models.Index(fields=["target_type", "status"])]

    def __str__(self):
        return f"{self.get_target_type_display()} report #{self.pk} ({self.reason})"
