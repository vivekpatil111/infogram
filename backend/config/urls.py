import time
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.db import connection
from django.http import JsonResponse
from django.urls import include, path


def healthz(request):
    """Liveness + database check for the hosting platform."""

    try:
        started = time.perf_counter()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        # db_ms shows how far the app is from its database (same region: a few ms).
        return JsonResponse({"status": "ok", "db_ms": round((time.perf_counter() - started) * 1000, 1)})
    except Exception:  # pragma: no cover - depends on the environment
        return JsonResponse({"status": "database unavailable"}, status=503)
from rest_framework.routers import DefaultRouter

from accounts.views import FollowRequestViewSet, UserViewSet
from posts.views import PostViewSet
from posts.feed import FeedView
from posts.reels import ReelFeedView
from notifications.views import NotificationViewSet
from messaging.views import ConversationViewSet
from paths.views import LearningPathViewSet
from discovery.views import ExploreView, LocationDetailView, LocationListView, SearchView, TopicView, VerticalListView
from stories.views import StoryViewSet
from safety.views import BlockListViewSet, ProblemReportView, ReportViewSet


router = DefaultRouter()
router.register("posts", PostViewSet, basename="post")
router.register("users", UserViewSet, basename="user")
router.register("follow-requests", FollowRequestViewSet, basename="follow-request")
router.register("stories", StoryViewSet, basename="story")
router.register("notifications", NotificationViewSet, basename="notification")
router.register("conversations", ConversationViewSet, basename="conversation")
router.register("reports", ReportViewSet, basename="report")
router.register("paths", LearningPathViewSet, basename="paths")
router.register("blocks", BlockListViewSet, basename="block")


urlpatterns = [
    path("healthz/", healthz, name="healthz"),
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("accounts.urls")),
    path("api/v1/", include(router.urls)),
    path("api/v1/media/", include("media_api.urls")),
    path("api/v1/feed/", FeedView.as_view(), name="feed"),
    path("api/v1/reels/", ReelFeedView.as_view(), name="reels"),
    path("api/v1/search/", SearchView.as_view(), name="search"),
    path("api/v1/explore/", ExploreView.as_view(), name="explore"),
    path("api/v1/topics/", TopicView.as_view(), name="topics"),
    path("api/v1/verticals/", VerticalListView.as_view(), name="verticals"),
    path("api/v1/support/problems/", ProblemReportView.as_view(), name="problem-report"),
    path("api/v1/locations/", LocationListView.as_view(), name="locations"),
    path("api/v1/locations/<str:slug>/", LocationDetailView.as_view(), name="location-detail"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
