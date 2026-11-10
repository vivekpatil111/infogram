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
