from pathlib import Path, PurePosixPath

from django.conf import settings
from django.urls import reverse
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import ALLOWED_CONTENT_TYPES, MAX_UPLOAD_SIZE_BYTES, PresignUploadSerializer
from .storage import build_object_key, build_public_media_url, create_upload_url, storage_configured


class PresignUploadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PresignUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        object_key = build_object_key(request.user.id, data["filename"])
        if not storage_configured():
            upload_url = request.build_absolute_uri(
                reverse("media-local-upload", kwargs={"object_key": object_key})
            )
            media_url = request.build_absolute_uri(f"{settings.MEDIA_URL}{object_key}")
            return Response(
                {
                    "upload_url": upload_url,
                    "method": "PUT",
                    "headers": {"Content-Type": data["content_type"]},
                    "object_key": object_key,
                    "media_url": media_url,
                    "media_type": ALLOWED_CONTENT_TYPES[data["content_type"]],
                    "expires_in": 900,
                    "local_upload": True,
                },
                status=status.HTTP_201_CREATED,
            )

        try:
            upload_url = create_upload_url(object_key, data["content_type"], data["size_bytes"])
        except RuntimeError as error:
            return Response({"detail": str(error)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response(
            {
                "upload_url": upload_url,
                "method": "PUT",
                "headers": {"Content-Type": data["content_type"]},
                "object_key": object_key,
                "media_url": build_public_media_url(object_key),
                "media_type": ALLOWED_CONTENT_TYPES[data["content_type"]],
                "expires_in": settings.MEDIA_UPLOAD_URL_EXPIRY_SECONDS,
            },
            status=status.HTTP_201_CREATED,
        )


class LocalUploadView(APIView):
    """Development-only authenticated PUT upload used when object storage is unset."""

    permission_classes = [permissions.IsAuthenticated]

    def put(self, request, object_key):
        clean_key = PurePosixPath(object_key)
        expected_prefix = PurePosixPath(f"users/{request.user.id}")
        if clean_key.is_absolute() or ".." in clean_key.parts or clean_key.parent != expected_prefix:
            return Response({"detail": "Invalid media object key."}, status=status.HTTP_403_FORBIDDEN)

        content_type = request.headers.get("Content-Type", "").split(";", 1)[0].strip()
        if content_type not in ALLOWED_CONTENT_TYPES:
            return Response({"detail": "Unsupported media type."}, status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)
        if len(request.body) > MAX_UPLOAD_SIZE_BYTES:
            return Response({"detail": "The media file is too large."}, status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)

        target = Path(settings.MEDIA_ROOT) / Path(*clean_key.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(request.body)
        return Response(
            {
                "object_key": str(clean_key),
                "media_url": request.build_absolute_uri(f"{settings.MEDIA_URL}{clean_key}"),
                "media_type": ALLOWED_CONTENT_TYPES[content_type],
            },
            status=status.HTTP_200_OK,
        )
