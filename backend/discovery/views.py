from django.db.models import Case, Count, IntegerField, OuterRef, Q, Value, When
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.querysets import count_subquery, users_with_stats
from posts.feed_snapshot import paginate_ranked
from posts.models import Hashtag, Location, Post
from posts.pagination import PostCursorPagination
from posts.querysets import posts_for_user
from posts.ranking import explore_feed
from posts.serializers import PostSerializer
from safety.querysets import blocked_by_me

from .serializers import SearchUserSerializer


SEARCH_TYPES = {"all", "users", "posts", "hashtags", "locations"}
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

        payload = {"query": query, "users": [], "posts": [], "hashtags": [], "locations": []}
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

        if result_type in {"all", "locations"} and not is_tag_query:
            places = locations_with_counts().filter(name__icontains=term).filter(post_count__gt=0)
            payload["locations"] = [location_payload(place) for place in places.order_by("-post_count", "name")[:SEARCH_LIMIT]]

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
        vertical = request.query_params.get("vertical", "").strip()
        return paginate_ranked(
            request,
            lambda: explore_feed(request.user, topic=topic, vertical=vertical),
            scope=f"explore:{vertical}",
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


def locations_with_counts():
    return Location.objects.annotate(
        post_count=count_subquery(Post.objects.filter(location=OuterRef("pk"), is_published=True), "location")
    )


def location_payload(location):
    return {"name": location.name, "slug": location.slug, "post_count": location.post_count}


class LocationListView(APIView):
    """GET /locations/?q= - places to tag a post with, most used first."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        places = locations_with_counts()
        query = request.query_params.get("q", "").strip()
        if query:
            places = places.filter(name__icontains=query)
        places = places.order_by("-post_count", "name")[:10]
        return Response({"results": [location_payload(place) for place in places]})


class LocationDetailView(APIView):
    """GET /locations/{slug}/ - the place plus its posts, newest first (cursor)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, slug):
        location = locations_with_counts().filter(slug=slug).first()
        if location is None:
            return Response({"detail": "Location not found."}, status=status.HTTP_404_NOT_FOUND)
        posts = posts_for_user(request.user).filter(location=location, is_published=True)
        paginator = PostCursorPagination()
        page = paginator.paginate_queryset(posts, request, view=self)
        response = paginator.get_paginated_response(PostSerializer(page, many=True, context={"request": request}).data)
        response.data["location"] = location_payload(location)
        return response


class VerticalListView(APIView):
    """GET /verticals/ - the Knowledge Verticals with post and expert counts."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from django.contrib.auth import get_user_model

        from posts.verticals import VERTICALS

        posts = dict(Post.objects.filter(is_published=True).exclude(vertical="").values_list("vertical").annotate(n=Count("id")))
        experts = dict(
            get_user_model().objects.filter(verified_at__isnull=False).exclude(expert_vertical="")
            .values_list("expert_vertical").annotate(n=Count("id"))
        )
        return Response({"results": [
            {"slug": slug, "name": name, "emoji": emoji, "description": description,
             "post_count": posts.get(slug, 0), "expert_count": experts.get(slug, 0)}
            for slug, name, emoji, description in VERTICALS
        ]})
