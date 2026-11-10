"""Cursor pagination over a frozen snapshot of a ranked feed.

Plain keyset pagination breaks for ranked feeds: `ranking_score` changes
between requests (new likes, posts crossing the 24h freshness boundary), so a
"score < cursor" filter skips or repeats posts. Instead, the first request
ranks the candidates once and stores the ordered post ids in the cache
(Redis in production). The opaque cursor carries the snapshot token and an
offset; later pages read from the same snapshot and re-hydrate fresh counts.

Response shape matches DRF cursor pagination: {"next", "previous", "results"}.
"""

import base64
import binascii
import json
import secrets

from django.conf import settings
from django.core.cache import cache
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.utils.urls import replace_query_param

from .querysets import posts_for_user
from .ranking import SUGGESTED


DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50


def _encode_cursor(token, offset):
    raw = json.dumps({"t": token, "o": offset}, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_cursor(cursor):
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded.encode()))
        token, offset = str(data["t"]), int(data["o"])
    except (binascii.Error, ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise ValidationError({"cursor": "Invalid cursor."})
    if offset < 0:
        raise ValidationError({"cursor": "Invalid cursor."})
    return token, offset


def _page_size(request, default):
    try:
        size = int(request.query_params.get("limit", default))
    except (TypeError, ValueError):
        size = default
    return max(1, min(size, MAX_PAGE_SIZE))


def paginate_ranked(request, ranked_queryset_factory, *, scope, serializer_class, page_size=DEFAULT_PAGE_SIZE):
    user = request.user
    limit = _page_size(request, page_size)
    cursor = request.query_params.get("cursor")

    if cursor:
        token, offset = _decode_cursor(cursor)
        snapshot = cache.get(f"feed:{scope}:{user.id}:{token}")
        if snapshot is None:
            raise ValidationError(
                {"cursor": "This feed session expired. Reload the feed from the first page.", "code": "cursor_expired"}
            )
    else:
        token, offset = secrets.token_urlsafe(9), 0
        rows = ranked_queryset_factory().values_list("id", "feed_tier")[: settings.FEED_SNAPSHOT_MAX_ITEMS]
        snapshot = [[post_id, tier == SUGGESTED] for post_id, tier in rows]
        cache.set(f"feed:{scope}:{user.id}:{token}", snapshot, settings.FEED_SNAPSHOT_TTL_SECONDS)

    window = snapshot[offset : offset + limit]
    suggested = {post_id: flag for post_id, flag in window}
    posts_by_id = {
        post.id: post
        for post in posts_for_user(user).filter(is_published=True, id__in=list(suggested))
    }
    page = []
    for post_id, _ in window:
        post = posts_by_id.get(post_id)  # Deleted/unpublished since the snapshot: skip.
        if post is not None:
            post.is_suggested = suggested[post_id]
            page.append(post)

    base_url = request.build_absolute_uri()
    next_offset = offset + limit
    next_url = (
        replace_query_param(base_url, "cursor", _encode_cursor(token, next_offset))
        if next_offset < len(snapshot)
        else None
    )
    # Previous pages stay inside the same snapshot (offset 0 included) so the
    # user scrolls back through exactly what they already saw.
    previous_url = (
        replace_query_param(base_url, "cursor", _encode_cursor(token, max(0, offset - limit)))
        if offset > 0
        else None
    )

    data = serializer_class(page, many=True, context={"request": request}).data
    return Response({"next": next_url, "previous": previous_url, "results": data})
