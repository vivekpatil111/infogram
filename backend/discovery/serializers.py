from rest_framework import serializers


class SearchUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    bio = serializers.CharField()
    avatar_url = serializers.CharField(allow_blank=True)
    followers_count = serializers.IntegerField()
    is_following = serializers.BooleanField()
    is_requested = serializers.BooleanField()
    is_private = serializers.BooleanField()
    is_verified = serializers.BooleanField()
