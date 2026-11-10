from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from media_api.storage import get_storage_client, storage_configured


class Command(BaseCommand):
    help = "Apply the bucket CORS policy so browsers can PUT uploads directly and play media."

    def handle(self, *args, **options):
        if not storage_configured():
            raise CommandError("Object storage credentials are not configured (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY).")
        origins = settings.CORS_ALLOWED_ORIGINS
        if not origins:
            raise CommandError("CORS_ALLOWED_ORIGINS is empty.")
        client = get_storage_client()
        bucket = settings.AWS_STORAGE_BUCKET_NAME
        client.put_bucket_cors(
            Bucket=bucket,
            CORSConfiguration={
                "CORSRules": [
                    {
                        "AllowedOrigins": origins,
                        "AllowedMethods": ["PUT", "GET", "HEAD"],
                        "AllowedHeaders": ["Content-Type", "Content-Length", "Range"],
                        "ExposeHeaders": ["ETag", "Content-Length", "Content-Range", "Accept-Ranges"],
                        "MaxAgeSeconds": 3600,
                    }
                ]
            },
        )
        rules = client.get_bucket_cors(Bucket=bucket)["CORSRules"]
        self.stdout.write(self.style.SUCCESS(f"CORS on '{bucket}' allows {rules[0]['AllowedOrigins']}"))
