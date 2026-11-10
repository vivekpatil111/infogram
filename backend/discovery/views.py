from django.db.models import Case, Count, IntegerField, OuterRef, Q, Value, When
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.querysets import count_subquery, users_with_stats
from posts.feed_snapshot import paginate_ranked
from posts.models import Hashtag, Post
from posts.querysets import posts_for_user
from posts.ranking import explore_feed
from posts.serializers import PostSerializer
from safety.querysets import blocked_by_me

from .serializers import SearchUserSerializer


SEARCH_TYPES = {"all", "users", "posts", "hashtags"}
SEARCH_LIMIT = 20


class SearchView(APIView):
    """GET /search/?q=&type=all|users|posts|hashtags

    Users rank exact handle > handle prefix > handle/bio substring, then by
    follower count. A leading '#' searches hashtags.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        query = request.query_params.get("q", "").strip()
        result_type = request.query_params.get("type", "all")
        if result_type not in SEARCH_TYPES:
            return Response({"detail": f"type must be one of {sorted(SEARCH_TYPES)}."}, status=status.HTTP_400_BAD_REQUEST)
        term = query.lstrip("#@")
        if len(term) < 2:
            return Response({"detail": "q must contain at least 2 characters."}, status=status.HTTP_400_BAD_REQUEST)
        is_tag_query = query.startswith("#")

        payload = {"query": query, "users": [], "posts": [], "hashtags": []}
        if result_type in {"all", "users"} and not is_tag_query:
            users = (
                users_with_stats(request.user)
                .filter(Q(username__icontains=term) | Q(bio__icontains=term))
                .exclude(pk__in=blocked_by_me(request.user))
                .annotate(
                    match_rank=Case(
                        When(username__iexact=term, then=Value(0)),
                        When(username__istartswith=term, then=Value(1)),
                        When(username__icontains=term, then=Value(2)),
                        default=Value(3),
                        output_field=IntegerField(),
                    )
                )
                .order_by("match_rank", "-followers_count", "username")[:SEARCH_LIMIT]
            )
            payload["users"] = SearchUserSerializer(users, many=True).data

        if result_type in {"all", "hashtags"}:
            tags = (
                Hashtag.objects.filter(name__istartswith=term.lower())
                .annotate(
                    post_count=count_subquery(
                        Post.hashtags.through.objects.filter(hashtag=OuterRef("pk"), post__is_published=True),
                        "hashtag",
                    )
                )
                .filter(post_count__gt=0)
                .order_by("-post_count", "name")[:SEARCH_LIMIT]
            )
            payload["hashtags"] = [{"name": tag.name, "post_count": tag.post_count} for tag in tags]

        if result_type in {"all", "posts"}:
            matches = Q(hashtags__name=term.lower())
            if not is_tag_query:
                matches |= Q(topic__icontains=term) | Q(caption__icontains=term)
            post_ids = (
                Post.objects.filter(is_published=True).filter(matches).order_by("-created_at", "-id")
                .values_list("id", flat=True).distinct()[:SEARCH_LIMIT]
            )
            posts = posts_for_user(request.user).filter(id__in=list(post_ids)).order_by("-created_at", "-id")
            payload["posts"] = PostSerializer(posts, many=True, context={"request": request}).data
        return Response(payload)


class ExploreView(APIView):
    """GET /explore/?topic=&limit=&cursor= - creators you don't follow yet."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        topic = request.query_params.get("topic", "").strip()
        return paginate_ranked(
            request,
            lambda: explore_feed(request.user, topic=topic),
            scope="explore",
            serializer_class=PostSerializer,
            page_size=24,
        )


class TopicView(APIView):
    """GET /topics/ - knowledge topics ordered by how many posts use them."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        rows = list(
            Post.objects.filter(is_published=True)
            .exclude(topic="")
            .values("topic")
            .annotate(post_count=Count("id"))
            .order_by("-post_count", "topic")[:50]
        )
        return Response({"topics": [row["topic"] for row in rows], "counts": rows})
