import re

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db.models import Q
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


User = get_user_model()

# Instagram-style handles: letters, digits, periods and underscores, at most
# 30 characters, no leading/trailing or doubled period. Stored lowercase and
# unique case-insensitively, so "Vasu.Py" and "vasu.py" are the same account.
USERNAME_PATTERN = re.compile(r"^(?!\.)(?!.*\.\.)(?!.*\.$)[a-z0-9._]{1,30}$")
RESERVED_USERNAMES = {"me", "admin", "api", "explore", "reels", "stories", "infogram", "suggested"}


def clean_username(value, *, instance=None):
    username = (value or "").strip().lower()
    if not USERNAME_PATTERN.match(username):
        raise serializers.ValidationError(
            "Usernames can use up to 30 letters, numbers, underscores and periods, "
            "and can't start or end with a period."
        )
    if username in RESERVED_USERNAMES:
        raise serializers.ValidationError("This username isn't available.")
    taken = User.objects.filter(username__iexact=username)
    if instance is not None:
        taken = taken.exclude(pk=instance.pk)
    if taken.exists():
        raise serializers.ValidationError("A user with that username already exists.")
    return username


def clean_email(value, *, instance=None):
    email = (value or "").strip().lower()
    taken = User.objects.filter(email__iexact=email)
    if instance is not None:
        taken = taken.exclude(pk=instance.pk)
    if taken.exists():
        raise serializers.ValidationError("A user with that email already exists.")
    return email


MAX_PROFILE_LINKS = 5


def clean_links(value):
    """[{title?, url}] -> normalised list; only http(s) URLs, at most 5."""

    from urllib.parse import urlparse

    if not isinstance(value, list):
        raise serializers.ValidationError("Send a list of links.")
    if len(value) > MAX_PROFILE_LINKS:
        raise serializers.ValidationError(f"You can add up to {MAX_PROFILE_LINKS} links.")
    cleaned = []
    for item in value:
        if not isinstance(item, dict):
            raise serializers.ValidationError("Each link needs a url.")
        url = str(item.get("url", "")).strip()
        title = " ".join(str(item.get("title", "")).split())[:40]
        if url and "://" not in url:
            url = f"https://{url}"
        parts = urlparse(url)
        if parts.scheme not in {"http", "https"} or not parts.netloc or "." not in parts.netloc or len(url) > 500:
            raise serializers.ValidationError(f"\"{item.get('url', '')}\" isn't a valid web link.")
        cleaned.append({"title": title, "url": url})
    return cleaned


class UserSerializer(serializers.ModelSerializer):
    """The signed-in user's own account (GET/PATCH /auth/me/)."""

    class Meta:
        model = User
        fields = ["id", "username", "email", "bio", "avatar_url", "is_private", "links", "date_joined"]
        read_only_fields = ["id", "date_joined"]
        extra_kwargs = {"bio": {"max_length": 500}}

    def update(self, instance, validated_data):
        from .services import approve_all_pending

        was_private = instance.is_private
        user = super().update(instance, validated_data)
        if was_private and not user.is_private:
            approve_all_pending(user)  # Going public approves waiting requests.
        return user

    def validate_username(self, value):
        return clean_username(value, instance=self.instance)

    def validate_email(self, value):
        return clean_email(value, instance=self.instance)

    def validate_links(self, value):
        return clean_links(value)


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8, style={"input_type": "password"})

    class Meta:
        model = User
        fields = ["id", "username", "email", "password"]
        read_only_fields = ["id"]
        # Model-level unique validators are case-sensitive; ours replace them.
        extra_kwargs = {"username": {"validators": []}, "email": {"validators": []}}

    def validate_username(self, value):
        return clean_username(value)

    def validate_email(self, value):
        return clean_email(value)

    def validate(self, attrs):
        candidate = User(username=attrs.get("username"), email=attrs.get("email"))
        try:
            validate_password(attrs["password"], user=candidate)
        except Exception as error:  # django ValidationError -> DRF field error
            raise serializers.ValidationError({"password": list(getattr(error, "messages", [str(error)]))})
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


def _password_errors(password, user):
    try:
        validate_password(password, user=user)
    except Exception as error:
        raise serializers.ValidationError({"new_password": list(getattr(error, "messages", [str(error)]))})


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)


class LoginSerializer(TokenObtainPairSerializer):
    """Accept a username *or* email in the `username` field, case-insensitively."""

    def validate(self, attrs):
        identifier = (attrs.get(self.username_field) or "").strip()
        user = (
            User.objects.filter(Q(username__iexact=identifier) | Q(email__iexact=identifier))
            .only("username")
            .first()
        )
        if user is not None:
            attrs[self.username_field] = user.username
        return super().validate(attrs)


class PublicUserSerializer(serializers.ModelSerializer):
    followers_count = serializers.IntegerField(read_only=True, default=0)
    following_count = serializers.IntegerField(read_only=True, default=0)
    is_following = serializers.BooleanField(read_only=True, default=False)
    is_requested = serializers.BooleanField(read_only=True, default=False)
    follow_status = serializers.SerializerMethodField()
    can_view_content = serializers.SerializerMethodField()
    follows_me = serializers.BooleanField(read_only=True, default=False)
    is_blocked = serializers.BooleanField(read_only=True, default=False)
    posts_muted = serializers.BooleanField(read_only=True, default=False)
    stories_muted = serializers.BooleanField(read_only=True, default=False)
    posts_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "bio",
            "avatar_url",
            "is_private",
            "followers_count",
            "following_count",
            "is_following",
            "is_requested",
            "follow_status",
            "can_view_content",
            "follows_me",
            "is_blocked",
            "posts_muted",
            "stories_muted",
            "posts_count",
            "date_joined",
            "links",
        ]

    def _viewer_id(self):
        request = self.context.get("request")
        return getattr(getattr(request, "user", None), "id", None)

    def get_follow_status(self, user):
        """'self' | 'following' | 'requested' | 'none' for the viewer."""

        if user.id == self._viewer_id():
            return "self"
        if getattr(user, "is_following", False):
            return "following"
        if getattr(user, "is_requested", False):
            return "requested"
        return "none"

    def get_can_view_content(self, user):
        if getattr(user, "is_blocked", False):
            return False
        return not user.is_private or self.get_follow_status(user) in {"self", "following"}
