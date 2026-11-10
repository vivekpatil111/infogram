from django.db import transaction
from rest_framework import serializers

from .hashtags import sync_hashtags
from .models import Comment, Post, PostMedia


MAX_CAROUSEL_ITEMS = 10


def author_summary(user):
    return {"id": user.id, "username": user.username, "avatar_url": user.avatar_url}


class PostMediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostMedia
        fields = ["position", "media_type", "media_url", "thumbnail_url"]
        read_only_fields = ["position"]


class PostSerializer(serializers.ModelSerializer):
    """Post read/write contract.

    Single media: send `media_type` ("image"|"video") + `media_url`.
    Carousel: send `media` = [{media_type, media_url, thumbnail_url?}, ...]
    (2-10 slides); the post's own media fields are derived from slide 1.
    """

    author = serializers.SerializerMethodField()
    media = PostMediaSerializer(many=True, required=False, source="media_items")
    hashtags = serializers.SlugRelatedField(many=True, read_only=True, slug_field="name")
    like_count = serializers.IntegerField(read_only=True, default=0)
    comment_count = serializers.IntegerField(read_only=True, default=0)
    save_count = serializers.IntegerField(read_only=True, default=0)
    liked_by_me = serializers.BooleanField(read_only=True, default=False)
    saved_by_me = serializers.BooleanField(read_only=True, default=False)
    is_suggested = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            "id",
            "author",
            "media_type",
            "media_url",
            "thumbnail_url",
            "media",
            "topic",
            "caption",
            "hashtags",
            "is_published",
            "created_at",
            "updated_at",
            "like_count",
            "comment_count",
            "save_count",
            "liked_by_me",
            "saved_by_me",
            "is_suggested",
        ]
        read_only_fields = ["id", "author", "created_at", "updated_at"]
        extra_kwargs = {
            "media_type": {"required": False},
            "media_url": {"required": False},
        }

    def get_author(self, post):
        summary = author_summary(post.author)
        # 'self' | 'following' | 'requested' | 'none' for the viewer (feed Follow buttons).
        request = self.context.get("request")
        if request is not None and post.author_id == getattr(request.user, "id", None):
            summary["follow_status"] = "self"
        else:
            status = getattr(post, "author_follow_status", None)
            summary["follow_status"] = {"accepted": "following", "pending": "requested"}.get(status, "none")
        return summary

    def get_is_suggested(self, post):
        return bool(getattr(post, "is_suggested", False))

    def _check_uploaded_media(self, attrs):
        """URLs into our bucket must be the caller's own, finished uploads."""

        from media_api.storage import object_exists, storage_configured, uploaded_object_key

        if not storage_configured():
            return
        request = self.context.get("request")
        user_id = getattr(getattr(request, "user", None), "id", None)
        urls = [attrs.get("media_url"), attrs.get("thumbnail_url")]
        urls += [u for slide in attrs.get("media_items") or [] for u in (slide.get("media_url"), slide.get("thumbnail_url"))]
        for url in filter(None, urls):
            key = uploaded_object_key(url)
            if key is None:
                continue
            if user_id is not None and not key.startswith(f"users/{user_id}/"):
                raise serializers.ValidationError({"media_url": "You can only post media you uploaded."})
            if not object_exists(key):
                raise serializers.ValidationError({"media_url": "The upload didn't finish. Please upload the file again."})

    def validate(self, attrs):
        attrs = self._validate_media_shape(attrs)
        self._check_uploaded_media(attrs)
        return attrs

    def _validate_media_shape(self, attrs):
        slides = attrs.get("media_items")
        if slides is not None:
            if not 2 <= len(slides) <= MAX_CAROUSEL_ITEMS:
                raise serializers.ValidationError(
                    {"media": f"A carousel needs between 2 and {MAX_CAROUSEL_ITEMS} items."}
                )
            attrs["media_type"] = Post.MediaType.CAROUSEL
            attrs["media_url"] = slides[0]["media_url"]
            attrs["thumbnail_url"] = slides[0].get("thumbnail_url") or (
                slides[0]["media_url"] if slides[0]["media_type"] == "image" else ""
            )
            return attrs

        media_type = attrs.get("media_type", getattr(self.instance, "media_type", None))
        if self.instance is None or "media_type" in attrs or "media_url" in attrs:
            if self.instance is None and not attrs.get("media_url"):
                raise serializers.ValidationError({"media_url": "This field is required."})
            if media_type not in {Post.MediaType.IMAGE, Post.MediaType.VIDEO}:
                if not (self.instance and media_type == Post.MediaType.CAROUSEL):
                    raise serializers.ValidationError(
                        {"media_type": "Use image or video, or send `media` for a carousel."}
                    )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        slides = validated_data.pop("media_items", None)
        post = Post.objects.create(**validated_data)
        if slides:
            PostMedia.objects.bulk_create(
                [PostMedia(post=post, position=index, **slide) for index, slide in enumerate(slides)]
            )
        sync_hashtags(post)
        return post

    @transaction.atomic
    def update(self, instance, validated_data):
        slides = validated_data.pop("media_items", None)
        post = super().update(instance, validated_data)
        if slides is not None:
            post.media_items.all().delete()
            PostMedia.objects.bulk_create(
                [PostMedia(post=post, position=index, **slide) for index, slide in enumerate(slides)]
            )
        if "caption" in validated_data:
            sync_hashtags(post)
        return post


class CommentSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    parent_id = serializers.IntegerField(read_only=True, allow_null=True)
    like_count = serializers.IntegerField(read_only=True, default=0)
    reply_count = serializers.IntegerField(read_only=True, default=0)
    liked_by_me = serializers.BooleanField(read_only=True, default=False)

    class Meta:
        model = Comment
        fields = ["id", "author", "text", "created_at", "parent_id", "like_count", "reply_count", "liked_by_me"]
        read_only_fields = ["id", "author", "created_at", "parent_id", "like_count", "reply_count", "liked_by_me"]

    def get_author(self, comment):
        return author_summary(comment.author)

    def validate_text(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Comment can't be empty.")
        return value
