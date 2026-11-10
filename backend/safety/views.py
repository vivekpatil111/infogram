from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from posts.models import Comment
from posts.querysets import posts_for_user
from stories.views import visible_stories

from .models import Block, Report
from .serializers import ReportCreateSerializer


User = get_user_model()


class BlockListViewSet(viewsets.ViewSet):
    """GET /blocks/ - accounts you've blocked (to manage / unblock)."""

    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        blocks = Block.objects.filter(blocker=request.user).select_related("blocked")
        return Response(
            {
                "count": blocks.count(),
                "results": [
                    {"id": b.blocked_id, "username": b.blocked.username, "avatar_url": b.blocked.avatar_url, "blocked_at": b.created_at}
                    for b in blocks[:500]
                ],
            }
        )


class ReportViewSet(viewsets.ViewSet):
    """POST /reports/ {target_type, target_id, reason, details?}

    You can only report things you can see. Reporting the same target again
    while your earlier report is still open returns that report (200)."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "reports"  # tight limit: mass reporting is an abuse vector

    @action(detail=False, methods=["get"])
    def reasons(self, request):
        return Response([{"value": value, "label": label} for value, label in Report.Reason.choices])

    def create(self, request):
        serializer = ReportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        target_type, raw_id = data["target_type"], data["target_id"]
        fields, owner = self._resolve_target(request.user, target_type, raw_id)
        if fields is None:
            return Response({"detail": "That content isn't available to report."}, status=status.HTTP_404_NOT_FOUND)
        if owner is not None and owner.pk == request.user.pk:
            return Response({"detail": "You can't report your own content."}, status=status.HTTP_400_BAD_REQUEST)

        existing = Report.objects.filter(
            reporter=request.user, target_type=target_type, status=Report.Status.OPEN, **fields
        ).first()
        if existing:
            return Response({"id": existing.id, "status": existing.status, "created": False}, status=status.HTTP_200_OK)
        report = Report.objects.create(
            reporter=request.user,
            target_type=target_type,
            target_owner=owner,
            reason=data["reason"],
            details=data["details"],
            **fields,
        )
        return Response({"id": report.id, "status": report.status, "created": True}, status=status.HTTP_201_CREATED)

    def _resolve_target(self, user, target_type, raw_id):
        if target_type == Report.TargetType.USER:
            target = User.objects.filter(Q(username__iexact=raw_id) | Q(pk=raw_id if raw_id.isdigit() else -1)).first()
            return ({"user": target}, target) if target else (None, None)
        if not raw_id.isdigit():
            return None, None
        pk = int(raw_id)
        if target_type == Report.TargetType.POST:
            post = posts_for_user(user).filter(pk=pk).first()
            return ({"post": post}, post.author) if post else (None, None)
        if target_type == Report.TargetType.COMMENT:
            comment = Comment.objects.filter(pk=pk, post__in=posts_for_user(user)).select_related("author").first()
            return ({"comment": comment}, comment.author) if comment else (None, None)
        story = visible_stories(user).filter(pk=pk).first()
        return ({"story": story}, story.author) if story else (None, None)


class ProblemReportView(APIView):
    """POST /support/problems/ {message, page?} - "Report a problem"."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "reports"

    def post(self, request):
        from .models import ProblemReport

        message = str(request.data.get("message", "")).strip()
        if len(message) < 5:
            return Response({"message": ["Tell us a little more about what went wrong."]}, status=status.HTTP_400_BAD_REQUEST)
        report = ProblemReport.objects.create(
            user=request.user,
            message=message[:2000],
            page=str(request.data.get("page", ""))[:300],
            user_agent=request.headers.get("User-Agent", "")[:300],
        )
        return Response({"id": report.id, "received": True}, status=status.HTTP_201_CREATED)
