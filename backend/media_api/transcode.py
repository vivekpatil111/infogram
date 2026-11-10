"""HLS transcoding: turn an uploaded video into adaptive streams.

For each video post we write a master playlist with up to two renditions
(720p and 480p on the short side, never upscaled) in 4-second segments to
users/{author}/hls/{post}/ in the bucket, then set Post.hls_url. Players pick
the rendition that fits the connection; the original MP4 stays as fallback.

ffmpeg comes from the imageio-ffmpeg wheel (a static binary), so it runs on a
plain Render Python service. One transcode runs at a time per process.
"""

import logging
import mimetypes
import re
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

import requests
from django.conf import settings
from django.db import transaction

logger = logging.getLogger(__name__)
_one_at_a_time = threading.Semaphore(1)
TARGETS = [720, 480]  # short-side heights
MAX_SOURCE_BYTES = 300 * 1024 * 1024


def hls_enabled():
    from .storage import storage_configured

    return settings.HLS_ENABLED and storage_configured()


def ffmpeg_path():
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def queue_transcode(post):
    """Mark a video post pending and transcode it in the background after commit."""

    from posts.models import Post

    if post.media_type != Post.MediaType.VIDEO or not hls_enabled():
        return
    Post.objects.filter(pk=post.pk).update(hls_status="pending")
    transaction.on_commit(lambda: threading.Thread(target=_run_in_thread, args=(post.pk,), daemon=True).start())


def _run_in_thread(post_id):
    from django.db import connection

    try:
        transcode_post(post_id)
    finally:
        connection.close()


def probe(ffmpeg, source):
    """(width, height, has_audio) from ffmpeg's stream summary."""

    result = subprocess.run([ffmpeg, "-hide_banner", "-i", str(source)], capture_output=True, text=True)
    info = result.stderr
    size = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", info)
    if not size:
        raise ValueError("No video stream found.")
    width, height = int(size.group(1)), int(size.group(2))
    rotate = re.search(r"rotate\s*:\s*-?(90|270)", info) or re.search(r"rotation of -?(90|270)", info)
    if rotate:
        width, height = height, width
    return width, height, "Audio:" in info


def build_command(ffmpeg, source, out_dir, width, height, has_audio):
    short = min(width, height)
    targets = [t for t in TARGETS if t <= short] or [short - short % 2]
    portrait = height > width
    count = len(targets)
    scales = "".join(
        f"[v{i}]scale={f'{t}:-2' if portrait else f'-2:{t}'}[v{i}o];" for i, t in enumerate(targets)
    )
    command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
               "-filter_complex", f"[0:v]split={count}" + "".join(f"[v{i}]" for i in range(count)) + ";" + scales.rstrip(";")]
    stream_map = []
    for i, target in enumerate(targets):
        command += ["-map", f"[v{i}o]"]
        if has_audio:
            command += ["-map", "0:a:0"]
        command += [f"-b:v:{i}", "2800k" if target >= 720 else "1200k", f"-maxrate:v:{i}", "3000k" if target >= 720 else "1400k",
                    f"-bufsize:v:{i}", "5000k" if target >= 720 else "2400k"]
        stream_map.append(f"v:{i},a:{i}" if has_audio else f"v:{i}")
    command += ["-c:v", "libx264", "-preset", "veryfast", "-profile:v", "main", "-pix_fmt", "yuv420p",
                "-g", "48", "-keyint_min", "48", "-sc_threshold", "0", "-threads", "2"]
    if has_audio:
        command += ["-c:a", "aac", "-b:a", "128k", "-ac", "2"]
    command += ["-f", "hls", "-hls_time", "4", "-hls_playlist_type", "vod", "-hls_flags", "independent_segments",
                "-hls_segment_filename", str(out_dir / "v%v" / "seg_%03d.ts"), "-master_pl_name", "master.m3u8",
                "-var_stream_map", " ".join(stream_map), str(out_dir / "v%v" / "index.m3u8")]
    return command


def _download(url, target):
    from .storage import get_storage_client, uploaded_object_key

    key = uploaded_object_key(url)
    if key:
        get_storage_client().download_file(settings.AWS_STORAGE_BUCKET_NAME, key, str(target))
        return
    with requests.get(url, stream=True, timeout=30) as response:
        response.raise_for_status()
        written = 0
        with open(target, "wb") as handle:
            for chunk in response.iter_content(1024 * 256):
                written += len(chunk)
                if written > MAX_SOURCE_BYTES:
                    raise ValueError("Source video is too large to transcode.")
                handle.write(chunk)


def _upload_tree(out_dir, prefix):
    from .storage import build_public_media_url, get_storage_client

    client = get_storage_client()
    for path in sorted(out_dir.rglob("*")):
        if not path.is_file():
            continue
        key = f"{prefix}/{path.relative_to(out_dir).as_posix()}"
        content_type = {".m3u8": "application/vnd.apple.mpegurl", ".ts": "video/mp2t"}.get(path.suffix) or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        client.upload_file(str(path), settings.AWS_STORAGE_BUCKET_NAME, key,
                           ExtraArgs={"ContentType": content_type, "CacheControl": "public, max-age=31536000, immutable"})
    return build_public_media_url(f"{prefix}/master.m3u8")


def transcode_post(post_id):
    from posts.models import Post

    with _one_at_a_time:
        post = Post.objects.filter(pk=post_id).first()
        if post is None or post.media_type != Post.MediaType.VIDEO:
            return None
        Post.objects.filter(pk=post_id).update(hls_status="processing")
        work = Path(tempfile.mkdtemp(prefix="infogram-hls-"))
        try:
            source = work / "source"
            _download(post.media_url, source)
            ffmpeg = ffmpeg_path()
            width, height, has_audio = probe(ffmpeg, source)
            out_dir = work / "out"
            out_dir.mkdir()
            subprocess.run(build_command(ffmpeg, source, out_dir, width, height, has_audio), check=True, capture_output=True, timeout=30 * 60)
            url = _upload_tree(out_dir, f"users/{post.author_id}/hls/{post.id}")
            Post.objects.filter(pk=post_id).update(hls_url=url, hls_status="ready")
            logger.info("HLS ready for post %s (%sx%s)", post_id, width, height)
            return url
        except Exception as error:  # keep the MP4; mark failed so the command can retry
            stderr = getattr(error, "stderr", b"") or b""
            logger.warning("HLS failed for post %s: %s %s", post_id, error, stderr[-500:] if isinstance(stderr, bytes) else stderr)
            Post.objects.filter(pk=post_id).update(hls_status="failed")
            return None
        finally:
            shutil.rmtree(work, ignore_errors=True)
