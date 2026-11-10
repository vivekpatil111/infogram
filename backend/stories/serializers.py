from rest_framework import serializers

from .models import Story


class StorySerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    viewed_by_me = serializers.BooleanField(read_only=True)

    class Meta:
        model = Story
        fields = [
            "id",
            "author",
            "media_type",
            "media_url",
            "thumbnail_url",
            "caption",
            "created_at",
            "expires_at",
            "viewed_by_me",
        ]
        read_only_fields = ["id", "author", "created_at", "expires_at", "viewed_by_me"]

    def get_author(self, story):
        return {
            "id": story.author_id,
            "username": story.author.username,
            "avatar_url": story.author.avatar_url,
        }
