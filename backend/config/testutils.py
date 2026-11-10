from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APITestCase


User = get_user_model()
PASSWORD = "Kn0wledge-Stream!"


class InfogramAPITestCase(APITestCase):
    def setUp(self):
        cache.clear()  # Feed snapshots and throttle buckets.

    def make_user(self, username, **extra):
        return User.objects.create_user(
            username=username, email=f"{username.replace('.', '_')}@example.com", password=PASSWORD, **extra
        )

    def as_user(self, user):
        self.client.force_authenticate(user)
        return self.client

    def make_post(self, author, **fields):
        from posts.models import Post

        defaults = {"media_type": "image", "media_url": "https://cdn.example.com/a.jpg", "topic": "Learning"}
        defaults.update(fields)
        return Post.objects.create(author=author, **defaults)
