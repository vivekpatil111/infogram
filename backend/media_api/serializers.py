from rest_framework import serializers


ALLOWED_CONTENT_TYPES = {
    "image/jpeg": "image",
    "image/png": "image",
    "image/webp": "image",
    "video/mp4": "video",
    "video/webm": "video",
}
MAX_UPLOAD_SIZE_BYTES = 100 * 1024 * 1024


class PresignUploadSerializer(serializers.Serializer):
    filename = serializers.CharField(max_length=180)
    content_type = serializers.ChoiceField(choices=tuple(ALLOWED_CONTENT_TYPES))
    size_bytes = serializers.IntegerField(min_value=1, max_value=MAX_UPLOAD_SIZE_BYTES)

    def validate_filename(self, filename):
        clean_name = filename.replace("\\", "/").split("/")[-1].strip()
        if not clean_name or clean_name in {".", ".."}:
            raise serializers.ValidationError("A valid filename is required.")
        return clean_name
