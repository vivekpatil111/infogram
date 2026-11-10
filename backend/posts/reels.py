from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .feed_snapshot import paginate_ranked
from .ranking import reels_feed
from .serializers import PostSerializer


class ReelFeedView(APIView):
    """GET /reels/?feed=for_you|following&topic=&limit=&cursor="""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        mode = request.query_params.get("feed", "for_you")
        if mode not in {"for_you", "following"}:
            return Response({"detail": "feed must be for_you or following."}, status=status.HTTP_400_BAD_REQUEST)
        topic = request.query_params.get("topic", "").strip()
        vertical = request.query_params.get("vertical", "").strip()
        return paginate_ranked(
            request,
            lambda: reels_feed(request.user, mode=mode, topic=topic, vertical=vertical),
            scope=f"reels:{mode}:{vertical}",
            serializer_class=PostSerializer,
        )
