import uuid
from functools import lru_cache
from pathlib import PurePath

import boto3
from botocore.config import Config
from django.conf import settings


def storage_configured():
    return bool(settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY)


def build_object_key(user_id, filename):
    suffix = PurePath(filename).suffix.lower()
    return f"users/{user_id}/{uuid.uuid4().hex}{suffix}"


@lru_cache(maxsize=1)
def _client(endpoint, region, key_id, secret, addressing_style):
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=region,
        aws_access_key_id=key_id,
        aws_secret_access_key=secret,
        config=Config(signature_version="s3v4", s3={"addressing_style": addressing_style}),
    )


def get_storage_client():
    if not storage_configured():
        raise RuntimeError("Object storage credentials are not configured.")
    return _client(
        settings.AWS_S3_ENDPOINT_URL,
        settings.AWS_S3_REGION_NAME,
        settings.AWS_ACCESS_KEY_ID,
        settings.AWS_SECRET_ACCESS_KEY,
        settings.AWS_S3_ADDRESSING_STYLE,
    )


def create_upload_url(object_key, content_type, size_bytes):
    """Presigned PUT. Content-Type and Content-Length are part of the
    signature, so the browser must upload exactly the file it declared:
    a different type or size fails with 403 instead of being stored."""

    return get_storage_client().generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
            "Key": object_key,
            "ContentType": content_type,
            "ContentLength": size_bytes,
        },
        ExpiresIn=settings.MEDIA_UPLOAD_URL_EXPIRY_SECONDS,
        HttpMethod="PUT",
    )


def build_public_media_url(object_key):
    if settings.MEDIA_PUBLIC_BASE_URL:
        return f"{settings.MEDIA_PUBLIC_BASE_URL.rstrip('/')}/{object_key}"
    if settings.AWS_S3_ENDPOINT_URL:
        # Path-style public URL (public_read bucket on Neon / MinIO).
        return f"{settings.AWS_S3_ENDPOINT_URL.rstrip('/')}/{settings.AWS_STORAGE_BUCKET_NAME}/{object_key}"
    return f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.{settings.AWS_S3_REGION_NAME}.amazonaws.com/{object_key}"


def uploaded_object_key(url):
    """Object key if `url` points into our bucket, else None (external URL)."""

    prefix = build_public_media_url("")
    if url and url.startswith(prefix):
        return url[len(prefix):]
    return None


def object_exists(object_key):
    from botocore.exceptions import ClientError

    try:
        get_storage_client().head_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=object_key)
        return True
    except ClientError:
        return False
