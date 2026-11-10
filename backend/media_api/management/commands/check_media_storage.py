import ssl
import urllib.error
import urllib.request

from botocore.httpsession import get_cert_path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from media_api.storage import build_public_media_url, create_upload_url, get_storage_client, storage_configured


# python.org builds ship without system root certificates; reuse the CA
# bundle botocore already uses for the S3 API itself.
_TLS = ssl.create_default_context(cafile=get_cert_path(True))


def _request(method, url, body=None, headers=None):
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=20, context=_TLS) as response:
            return response.status, response.read(), dict(response.headers)
    except urllib.error.HTTPError as error:
        return error.code, error.read(), dict(error.headers)


class Command(BaseCommand):
    help = "End-to-end check: presigned upload, anonymous public read, signature enforcement, cleanup."

    def handle(self, *args, **options):
        if not storage_configured():
            raise CommandError("Object storage credentials are not configured.")
        key = "healthchecks/check.txt"
        body = b"infogram storage check"
        results = []

        url = create_upload_url(key, "text/plain", len(body))
        status, _, _ = _request("PUT", url, body, {"Content-Type": "text/plain"})
        results.append(("presigned PUT upload", status == 200, status))

        status, data, headers = _request("GET", build_public_media_url(key))
        results.append(("anonymous public GET", status == 200 and data == body, status))
        results.append(("stored Content-Type", headers.get("Content-Type", "").startswith("text/plain"), headers.get("Content-Type")))

        status, _, _ = _request("GET", build_public_media_url(key), headers={"Range": "bytes=0-3"})
        results.append(("range request (video seeking)", status == 206, status))

        url = create_upload_url("healthchecks/wrong-type.txt", "image/png", len(body))
        status, _, _ = _request("PUT", url, body, {"Content-Type": "text/plain"})
        results.append(("wrong Content-Type rejected", status in {400, 403}, status))

        url = create_upload_url("healthchecks/wrong-size.txt", "text/plain", 5)
        status, _, _ = _request("PUT", url, body, {"Content-Type": "text/plain"})
        results.append(("wrong size rejected", status in {400, 403}, status))

        client = get_storage_client()
        for leftover in ("healthchecks/check.txt", "healthchecks/wrong-type.txt", "healthchecks/wrong-size.txt"):
            client.delete_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=leftover)

        for name, ok, detail in results:
            mark = self.style.SUCCESS("PASS") if ok else self.style.ERROR("FAIL")
            self.stdout.write(f"{mark}  {name} ({detail})")
        if not all(ok for _, ok, _ in results):
            raise CommandError("Storage check failed.")
