from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db.models import Count, OuterRef
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from posts.pagination import PostCursorPagination
from posts.querysets import posts_for_user
from posts.serializers import PostSerializer
from safety import services as safety_services
from safety.querysets import blocked_by_me

from . import services
from .models import Follow
from .querysets import count_subquery, followed_ids, users_with_stats
from .models import User
from .serializers import (
    LoginSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    PublicUserSerializer,
    RegisterSerializer,
    UserSerializer,
    _password_errors,
)


class RegisterView(generics.CreateAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer
    throttle_scope = "auth"


class LoginView(TokenObtainPairView):
    permission_classes = [permissions.AllowAny]
    serializer_class = LoginSerializer
    throttle_scope = "auth"


class RefreshView(TokenRefreshView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "auth"


class LogoutView(generics.GenericAPIView):
    """Blacklist the refresh token so it can't mint new access tokens."""

    permission_classes = [permissions.AllowAny]
    throttle_scope = "auth"

    def post(self, request):
        token = request.data.get("refresh")
        if not token:
            return Response({"detail": "refresh is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            RefreshToken(token).blacklist()
        except TokenError:
            pass  # Already invalid/expired: logging out is still a success.
        return Response(status=status.HTTP_205_RESET_CONTENT)


def logout_everywhere(user):
    """Blacklist every refresh token the user holds (all devices)."""

    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)


class PasswordResetRequestView(generics.GenericAPIView):
    """POST {email}. Always answers the same way, so it can't be used to find
    out which emails have accounts."""

    permission_classes = [permissions.AllowAny]
    serializer_class = PasswordResetRequestSerializer
    throttle_scope = "auth"

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(email__iexact=serializer.validated_data["email"], is_active=True).first()
        if user is not None and user.has_usable_password():
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            link = f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"
            minutes = settings.PASSWORD_RESET_TIMEOUT // 60
            send_mail(
                "Reset your Infogram password",
                f"Hi {user.username},\n\nUse this link to choose a new password:\n{link}\n\n"
                f"The link works once and expires in {minutes} minutes. If you didn't ask for this, ignore this email.\n",
                None,
                [user.email],
            )
        return Response({"detail": "If an account uses that email, we've sent a link to reset the password."})


class PasswordResetConfirmView(generics.GenericAPIView):
    """POST {uid, token, new_password}. Signs the account out everywhere."""

    permission_classes = [permissions.AllowAny]
    serializer_class = PasswordResetConfirmSerializer
    throttle_scope = "auth"

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            user = User.objects.get(pk=force_str(urlsafe_base64_decode(data["uid"])), is_active=True)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            user = None
        # The token embeds the password hash and last login, so it's single-use.
        if user is None or not default_token_generator.check_token(user, data["token"]):
            return Response({"detail": "This reset link is invalid or has expired."}, status=status.HTTP_400_BAD_REQUEST)
        _password_errors(data["new_password"], user)
        user.set_password(data["new_password"])
        user.save(update_fields=["password"])
        logout_everywhere(user)
        return Response({"detail": "Password updated. You can log in now."})


class PasswordChangeView(generics.GenericAPIView):
    """POST {current_password, new_password} while signed in."""

    serializer_class = PasswordChangeSerializer
    throttle_scope = "auth"

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if not request.user.check_password(data["current_password"]):
            return Response({"current_password": ["Your current password is incorrect."]}, status=status.HTTP_400_BAD_REQUEST)
        _password_errors(data["new_password"], request.user)
        request.user.set_password(data["new_password"])
        request.user.save(update_fields=["password"])
        logout_everywhere(request.user)
        refresh = RefreshToken.for_user(request.user)  # keep this device signed in
        return Response({"detail": "Password changed.", "access": str(refresh.access_token), "refresh": str(refresh)})


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PublicUserSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "username"
    # Usernames may contain dots; DRF's default route regex stops at a dot.
    lookup_value_regex = r"[^/]+"

    def get_queryset(self):
        return users_with_stats(self.request.user).order_by("username")

    def get_object(self):
        user = get_object_or_404(self.get_queryset(), username__iexact=self.kwargs["username"])
        self.check_object_permissions(self.request, user)
        return user

    def _private_locked(self, user):
        return not self.get_serializer(user).data["can_view_content"]

    @action(detail=True, methods=["get"], url_path="profile")
    def profile(self, request, username=None):
        user = self.get_object()
        tab = request.query_params.get("tab", "posts")
        if tab not in {"posts", "reels", "saved"}:
            return Response({"detail": "tab must be posts, reels or saved."}, status=status.HTTP_400_BAD_REQUEST)
        if tab == "saved" and user.id != request.user.id:
            return Response({"detail": "Saved posts are private."}, status=status.HTTP_403_FORBIDDEN)

        profile = self.get_serializer(user).data
        profile["top_topics"] = list(
            posts_for_user(request.user).filter(author=user, is_published=True).exclude(topic="")
            .values("topic").annotate(n=Count("id")).order_by("-n", "topic").values_list("topic", flat=True)[:5]
        ) if profile["can_view_content"] else []
        if not profile["can_view_content"]:
            # "This account is private": header and counts only, no grid.
            return Response({"next": None, "previous": None, "results": [], "profile": profile, "tab": tab})

        queryset = posts_for_user(request.user).filter(is_published=True)
        if tab == "saved":
            queryset = queryset.filter(saved_by_me=True)
        else:
            queryset = queryset.filter(author=user)
            if tab == "reels":
                queryset = queryset.filter(media_type="video")

        paginator = PostCursorPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        context = self.get_serializer_context()
        response = paginator.get_paginated_response(PostSerializer(page, many=True, context=context).data)
        response.data["profile"] = profile
        response.data["tab"] = tab
        return response

    @staticmethod
    def _limit(request, *, default, maximum):
        try:
            return max(1, min(int(request.query_params.get("limit", default)), maximum))
        except (TypeError, ValueError):
            return default

    @action(detail=False, methods=["get"], url_path="suggested")
    def suggested(self, request):
        """'Suggested for you': accounts you don't follow (or requested) yet.

        Infogram's own heuristic: people followed by accounts you follow
        rank first (mutual_count), then overall followers. Each item carries
        `followed_by` - one mutual's username - for "Followed by X" copy.
        """

        me = request.user
        mine = followed_ids(me)
        already = Follow.objects.filter(follower=me).values("following_id")
        mutual = Follow.objects.accepted().filter(following=OuterRef("pk"), follower_id__in=mine)
        candidates = (
            self.get_queryset()
            .exclude(pk=me.pk)
            .exclude(pk__in=already)
            .exclude(pk__in=blocked_by_me(me))
            .annotate(mutual_count=count_subquery(mutual, "following"))
            .order_by("-mutual_count", "-followers_count", "username")[: self._limit(request, default=10, maximum=30)]
        )
        results = []
        for user in candidates:
            data = self.get_serializer(user).data
            data["mutual_count"] = user.mutual_count
            first = Follow.objects.accepted().filter(following=user, follower_id__in=mine).select_related("follower").first()
            data["followed_by"] = first.follower.username if first else None
            results.append(data)
        return Response({"results": results})

    @action(detail=True, methods=["post", "delete"], url_path="follow")
    def follow(self, request, username=None):
        """POST follows (or requests to follow a private account); DELETE
        unfollows or cancels a pending request."""

        user = self.get_object()
        if user.id == request.user.id:
            return Response({"detail": "You cannot follow yourself."}, status=status.HTTP_400_BAD_REQUEST)
        if request.method == "POST":
            try:
                follow, created = services.request_follow(request.user, user)
            except PermissionError as error:
                return Response({"detail": str(error)}, status=status.HTTP_403_FORBIDDEN)
            accepted = follow.status == Follow.Status.ACCEPTED
            return Response(
                {
                    "following": accepted,
                    "requested": not accepted,
                    "follow_status": "following" if accepted else "requested",
                    "created": created,
                },
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            )
        services.remove_follow(request.user, user)
        return Response({"following": False, "requested": False, "follow_status": "none"})

    @action(detail=True, methods=["post", "delete"], url_path="block")
    def block(self, request, username=None):
        """POST blocks (and removes follows both ways); DELETE unblocks."""

        user = self.get_object()
        if user.id == request.user.id:
            return Response({"detail": "You cannot block yourself."}, status=status.HTTP_400_BAD_REQUEST)
        if request.method == "POST":
            created = safety_services.block(request.user, user)
            return Response({"blocked": True, "created": created}, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
        safety_services.unblock(request.user, user)
        return Response({"blocked": False})

    @action(detail=True, methods=["post", "delete"], url_path="mute")
    def mute(self, request, username=None):
        """POST {"posts": bool, "stories": bool} (both default true); DELETE unmutes."""

        user = self.get_object()
        if user.id == request.user.id:
            return Response({"detail": "You cannot mute yourself."}, status=status.HTTP_400_BAD_REQUEST)
        if request.method == "DELETE":
            safety_services.set_mute(request.user, user, posts=False, stories=False)
            return Response({"posts_muted": False, "stories_muted": False})
        # Partial update: a key you don't send keeps its current value.
        from safety.models import Mute

        current = Mute.objects.filter(muter=request.user, muted=user).first()
        posts = bool(request.data.get("posts", current.posts if current else True))
        stories = bool(request.data.get("stories", current.stories if current else True))
        safety_services.set_mute(request.user, user, posts=posts, stories=stories)
        return Response({"posts_muted": posts, "stories_muted": stories})

    @action(detail=True, methods=["delete"], url_path="follower")
    def remove_follower(self, request, username=None):
        """Remove someone who follows you (e.g. after going private)."""

        follower = self.get_object()
        services.remove_follow(follower, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _user_list(self, user, queryset):
        if self._private_locked(user):
            return Response({"detail": "This account is private."}, status=status.HTTP_403_FORBIDDEN)
        paginator = UserCursorPagination()
        page = paginator.paginate_queryset(queryset, self.request, view=self)
        return paginator.get_paginated_response(self.get_serializer(page, many=True).data)

    @action(detail=True, methods=["get"], url_path="followers")
    def followers(self, request, username=None):
        user = self.get_object()
        return self._user_list(
            user, self.get_queryset().filter(following__following=user, following__status=Follow.Status.ACCEPTED)
        )

    @action(detail=True, methods=["get"], url_path="following")
    def following(self, request, username=None):
        user = self.get_object()
        return self._user_list(
            user, self.get_queryset().filter(followers__follower=user, followers__status=Follow.Status.ACCEPTED)
        )


class UserCursorPagination(PostCursorPagination):
    ordering = ("username", "id")


class FollowRequestViewSet(viewsets.GenericViewSet):
    """Incoming follow requests for the signed-in (private) account.

    GET  /follow-requests/                     pending requests, newest first
    POST /follow-requests/{username}/accept/   approve the requester
    POST /follow-requests/{username}/decline/  delete the request
    """

    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "username"
    lookup_value_regex = r"[^/]+"

    def get_queryset(self):
        return Follow.objects.pending().filter(following=self.request.user).select_related("follower")

    def get_object(self):
        return get_object_or_404(self.get_queryset(), follower__username__iexact=self.kwargs["username"])

    def list(self, request):
        requests = self.get_queryset().order_by("-created_at", "-id")
        return Response(
            {
                "count": requests.count(),
                "results": [
                    {
                        "id": follow.follower_id,
                        "username": follow.follower.username,
                        "avatar_url": follow.follower.avatar_url,
                        "bio": follow.follower.bio,
                        "requested_at": follow.created_at,
                    }
                    for follow in requests[:200]
                ],
            }
        )

    @action(detail=True, methods=["post"])
    def accept(self, request, username=None):
        services.accept_request(self.get_object())
        return Response({"accepted": True})

    @action(detail=True, methods=["post"])
    def decline(self, request, username=None):
        services.decline_request(self.get_object())
        return Response({"declined": True})
