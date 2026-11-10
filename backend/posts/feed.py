from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .feed_snapshot import paginate_ranked
from .ranking import home_feed
from .serializers import PostSerializer


class FeedView(APIView):
    """GET /feed/?mode=for_you|following&topic=&limit=&cursor=

    for_you: followed creators + your own posts first, then suggested posts
    (each flagged `is_suggested: true`), mirroring the observed Instagram home.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        mode = request.query_params.get("mode", "for_you")
        if mode not in {"for_you", "following"}:
            return Response({"detail": "mode must be for_you or following."}, status=status.HTTP_400_BAD_REQUEST)
        topic = request.query_params.get("topic", "").strip()
        return paginate_ranked(
            request,
            lambda: home_feed(request.user, mode=mode, topic=topic),
            scope=f"home:{mode}",
            serializer_class=PostSerializer,
        )
