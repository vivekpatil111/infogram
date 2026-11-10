from rest_framework import serializers

from posts.models import Post
from posts.serializers import author_summary

from .models import LearningPath

MAX_PATH_ITEMS = 30


class LearningPathSerializer(serializers.ModelSerializer):
    """Write: {title, description?, vertical?, post_ids: [own published post ids, in order]}."""

    creator = serializers.SerializerMethodField()
    post_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, allow_empty=False)
    lesson_count = serializers.SerializerMethodField()
    cover_url = serializers.SerializerMethodField()

    class Meta:
        model = LearningPath
        fields = ["id", "creator", "title", "description", "vertical", "post_ids", "lesson_count", "cover_url", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_creator(self, path):
        return author_summary(path.creator)

    def _ordered_items(self, path):
        return sorted(path.items.all(), key=lambda item: item.position)

    def get_lesson_count(self, path):
        return len(path.items.all())

    def get_cover_url(self, path):
        items = self._ordered_items(path)
        if not items:
            return ""
        post = items[0].post
        return post.thumbnail_url or (post.media_url if post.media_type != "video" else "")

    def validate_title(self, value):
        value = " ".join(value.split())
        if not value:
            raise serializers.ValidationError("Give the path a title.")
        return value

    def validate_post_ids(self, ids):
        if len(ids) > MAX_PATH_ITEMS:
            raise serializers.ValidationError(f"A path can have up to {MAX_PATH_ITEMS} lessons.")
        if len(set(ids)) != len(ids):
            raise serializers.ValidationError("Each post can appear once.")
        user = self.context["request"].user
        owned = set(Post.objects.filter(author=user, is_published=True, id__in=ids).values_list("id", flat=True))
        if owned != set(ids):
            raise serializers.ValidationError("Paths can only contain your own published posts.")
        return ids
