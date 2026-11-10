"""Transcode video posts to HLS.

    python manage.py transcode_videos            # pending + failed
    python manage.py transcode_videos --missing  # every video without HLS yet (backfill)
    python manage.py transcode_videos --post 42
"""

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from media_api.transcode import hls_enabled, transcode_post
from posts.models import Post


class Command(BaseCommand):
    help = "Create HLS renditions for video posts."

    def add_arguments(self, parser):
        parser.add_argument("--post", type=int)
        parser.add_argument("--missing", action="store_true")

    def handle(self, *args, post=None, missing=False, **options):
        if not hls_enabled():
            raise CommandError("HLS needs media storage configured and HLS_ENABLED=1.")
        videos = Post.objects.filter(media_type=Post.MediaType.VIDEO)
        if post:
            videos = videos.filter(pk=post)
        elif missing:
            videos = videos.filter(hls_url="")
        else:
            videos = videos.filter(Q(hls_status="pending") | Q(hls_status="failed"))
        for video in videos.order_by("id"):
            url = transcode_post(video.id)
            self.stdout.write(f"post {video.id}: {'ready' if url else 'failed'}")
