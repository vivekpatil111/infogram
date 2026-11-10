import tempfile
from unittest import mock
from urllib.parse import parse_qs, urlparse

from django.test import override_settings

from config.testutils import InfogramAPITestCase

STORAGE = dict(
    AWS_ACCESS_KEY_ID="test-key",
    AWS_SECRET_ACCESS_KEY="test-secret",
    AWS_S3_ENDPOINT_URL="https://br-test.storage.example.neon.tech",
    AWS_S3_REGION_NAME="ap-southeast-1",
    AWS_S3_ADDRESSING_STYLE="path",
    AWS_STORAGE_BUCKET_NAME="infogram-media",
    MEDIA_PUBLIC_BASE_URL="",
)
BASE = "https://br-test.storage.example.neon.tech/infogram-media/"


@override_settings(**STORAGE)
class PresignTests(InfogramAPITestCase):
    def setUp(self):
        super().setUp()
        self.user = self.make_user("uploader")
        self.client = self.as_user(self.user)

    def test_presign_signs_type_and_size_with_path_style_url(self):
        response = self.client.post(
            "/api/v1/media/presign/",
            {"filename": "../../guide.MP4", "content_type": "video/mp4", "size_bytes": 1234},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["media_type"], "video")
        self.assertRegex(response.data["object_key"], rf"^users/{self.user.id}/[0-9a-f]{{32}}\.mp4$")
        self.assertEqual(response.data["media_url"], BASE + response.data["object_key"])
        upload = urlparse(response.data["upload_url"])
        self.assertEqual(upload.path, "/infogram-media/" + response.data["object_key"])  # path-style
        signed = parse_qs(upload.query)["X-Amz-SignedHeaders"][0].split(";")
        self.assertIn("content-type", signed)
        self.assertIn("content-length", signed)
        self.assertEqual(response.data["headers"], {"Content-Type": "video/mp4"})

    def test_presign_rejects_bad_type_and_size(self):
        for payload in (
            {"filename": "x.exe", "content_type": "application/octet-stream", "size_bytes": 10},
            {"filename": "x.mp4", "content_type": "video/mp4", "size_bytes": 101 * 1024 * 1024},
            {"filename": "x.mp4", "content_type": "video/mp4", "size_bytes": 0},
        ):
            self.assertEqual(self.client.post("/api/v1/media/presign/", payload, format="json").status_code, 400)

    def test_post_with_uploaded_media_must_exist_and_be_own(self):
        own = f"{BASE}users/{self.user.id}/abc.jpg"
        with mock.patch("media_api.storage.object_exists", return_value=False):
            missing = self.client.post("/api/v1/posts/", {"media_type": "image", "media_url": own}, format="json")
        self.assertEqual(missing.status_code, 400)
        self.assertIn("upload", missing.data["media_url"][0])

        with mock.patch("media_api.storage.object_exists", return_value=True):
            created = self.client.post("/api/v1/posts/", {"media_type": "image", "media_url": own}, format="json")
            someone_else = self.client.post(
                "/api/v1/posts/", {"media_type": "image", "media_url": f"{BASE}users/999/x.jpg"}, format="json"
            )
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(someone_else.status_code, 400)

    def test_external_urls_skip_storage_check(self):
        with mock.patch("media_api.storage.object_exists") as exists:
            response = self.client.post(
                "/api/v1/posts/", {"media_type": "image", "media_url": "https://images.example.com/a.jpg"}, format="json"
            )
        self.assertEqual(response.status_code, 201)
        exists.assert_not_called()


@override_settings(AWS_ACCESS_KEY_ID="", AWS_SECRET_ACCESS_KEY="", AWS_S3_ENDPOINT_URL=None)
class LocalUploadFallbackTests(InfogramAPITestCase):
    def test_local_upload_round_trip(self):
        user = self.make_user("local.dev")
        client = self.as_user(user)
        with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            presign = client.post(
                "/api/v1/media/presign/", {"filename": "a.png", "content_type": "image/png", "size_bytes": 4}, format="json"
            ).data
            self.assertTrue(presign["local_upload"])
            path = urlparse(presign["upload_url"]).path
            uploaded = client.put(path, b"\x89PNG", content_type="image/png")
            self.assertEqual(uploaded.status_code, 200, uploaded.data)

            other = self.as_user(self.make_user("intruder"))
            self.assertEqual(other.put(path, b"\x89PNG", content_type="image/png").status_code, 403)


class HlsTranscodeTests(InfogramAPITestCase):
    def test_transcode_writes_renditions_and_marks_ready_or_failed(self):
        import subprocess
        from pathlib import Path
        from unittest import mock

        from media_api import transcode
        from posts.models import Post

        author = self.make_user("filmmaker")
        post = self.make_post(author, media_type="video", media_url="https://cdn.example.com/clip.mp4")

        def fake_download(url, target):
            subprocess.run([transcode.ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=24:duration=3",
                            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-f", "mp4", str(target)], check=True)

        uploaded = {}

        def fake_upload(out_dir, prefix):
            uploaded["files"] = sorted(p.relative_to(out_dir).as_posix() for p in Path(out_dir).rglob("*") if p.is_file())
            uploaded["prefix"] = prefix
            return f"https://media.example.com/{prefix}/master.m3u8"

        with mock.patch.object(transcode, "_download", fake_download), mock.patch.object(transcode, "_upload_tree", fake_upload):
            url = transcode.transcode_post(post.id)
        post.refresh_from_db()
        self.assertEqual((post.hls_status, post.hls_url), ("ready", url))
        self.assertEqual(uploaded["prefix"], f"users/{author.id}/hls/{post.id}")
        self.assertIn("master.m3u8", uploaded["files"])
        self.assertIn("v1/index.m3u8", uploaded["files"])  # 480p rendition too
        self.assertEqual(self.as_user(author).get(f"/api/v1/posts/{post.id}/").data["hls_url"], url)

        with mock.patch.object(transcode, "_download", side_effect=OSError("network down")):
            self.assertIsNone(transcode.transcode_post(post.id))
        post.refresh_from_db()
        self.assertEqual(post.hls_status, "failed")

    def test_new_video_posts_are_queued_when_enabled(self):
        from unittest import mock

        author = self.make_user("reeler")
        with mock.patch("media_api.transcode.hls_enabled", return_value=True), \
                mock.patch("media_api.transcode._run_in_thread") as run, self.captureOnCommitCallbacks(execute=True):
            response = self.as_user(author).post("/api/v1/posts/", {"media_type": "video", "media_url": "https://cdn.example.com/v.mp4"}, format="json")
            image = self.as_user(author).post("/api/v1/posts/", {"media_type": "image", "media_url": "https://cdn.example.com/i.jpg"}, format="json")
        from posts.models import Post
        import time
        time.sleep(0.2)
        self.assertEqual(Post.objects.get(pk=response.data["id"]).hls_status, "pending")
        self.assertEqual(Post.objects.get(pk=image.data["id"]).hls_status, "")
        run.assert_called_once_with(response.data["id"])
