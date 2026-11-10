from django.conf import settings
from django.db import models


class Hashtag(models.Model):
    """A `#tag` parsed from captions. Names are stored lowercase without '#'."""

    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"#{self.name}"


class Location(models.Model):
    """A named place a post can be tagged with. Created on first use from the
    name the author types; posts sharing a slug share a location page."""

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True, allow_unicode=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @classmethod
    def for_name(cls, name):
        from django.utils.text import slugify

        name = " ".join(name.split())[:100]
        slug = slugify(name, allow_unicode=True)[:120]
        if not slug:
            return None
        location, _ = cls.objects.get_or_create(slug=slug, defaults={"name": name})
        return location


class Post(models.Model):
    class MediaType(models.TextChoices):
        IMAGE = "image", "Image"
        VIDEO = "video", "Video"
        CAROUSEL = "carousel", "Carousel"

    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posts")
    # For carousels, media_type is "carousel" and media_url/thumbnail_url mirror
    # the first slide so clients that only read the cover keep working.
    media_type = models.CharField(max_length=10, choices=MediaType.choices)
    media_url = models.URLField(max_length=2048)
    thumbnail_url = models.URLField(max_length=2048, blank=True)
    topic = models.CharField(max_length=80, blank=True)
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True, related_name="posts")
    caption = models.TextField(blank=True, max_length=2200)
    hashtags = models.ManyToManyField(Hashtag, blank=True, related_name="posts")
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["-created_at", "-id"]),
            models.Index(fields=["author", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.author.username}: {self.topic or self.media_type}"


class PostMedia(models.Model):
    """One slide of a carousel post, ordered by `position`."""

    class MediaType(models.TextChoices):
        IMAGE = "image", "Image"
        VIDEO = "video", "Video"

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="media_items")
    position = models.PositiveSmallIntegerField()
    media_type = models.CharField(max_length=10, choices=MediaType.choices)
    media_url = models.URLField(max_length=2048)
    thumbnail_url = models.URLField(max_length=2048, blank=True)

    class Meta:
        ordering = ["position", "id"]
        constraints = [models.UniqueConstraint(fields=["post", "position"], name="unique_post_media_position")]


class PostLike(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="post_likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["post", "user"], name="unique_post_like")]


class PostSave(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="saves")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="post_saves")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["post", "user"], name="unique_post_save")]


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments")
    # One level of threading: a reply always hangs off a top-level comment
    # (replying to a reply attaches to that reply's parent).
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies")
    text = models.TextField(max_length=2200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["post", "parent", "created_at"])]


class CommentLike(models.Model):
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comment_likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["comment", "user"], name="unique_comment_like")]
