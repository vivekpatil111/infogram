from datetime import timedelta

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import Follow
from posts.hashtags import sync_hashtags
from posts.models import Post
from stories.models import Story


User = get_user_model()


DEMO_USERS = [
    {
        "username": "startup.school",
        "email": "startup.school@demo.infogram.local",
        "bio": "Clear startup, registration and founder basics.",
        "avatar_url": "https://i.pravatar.cc/200?img=41",
    },
    {
        "username": "arjun.codes",
        "email": "arjun.codes@demo.infogram.local",
        "bio": "Practical software engineering lessons.",
        "avatar_url": "https://i.pravatar.cc/200?img=11",
    },
    {
        "username": "finance.with.riya",
        "email": "finance.with.riya@demo.infogram.local",
        "bio": "Beginner-friendly personal finance explainers.",
        "avatar_url": "https://i.pravatar.cc/200?img=45",
    },
    {
        "username": "earth.minute",
        "email": "earth.minute@demo.infogram.local",
        "bio": "Short science and climate explainers.",
        "avatar_url": "https://i.pravatar.cc/200?img=5",
    },
]


DEMO_POSTS = [
    {
        "username": "startup.school",
        "media_type": Post.MediaType.IMAGE,
        "media_url": "https://images.unsplash.com/photo-1556761175-b413da4baf72?auto=format&fit=crop&w=1200&q=85",
        "topic": "Startup registration",
        "caption": "Startup register karne se pehle founders, business structure aur required documents ki checklist ready rakho. #startup #founders",
    },
    {
        "username": "arjun.codes",
        "media_type": Post.MediaType.VIDEO,
        "media_url": "https://assets.mixkit.co/videos/preview/mixkit-young-woman-talking-to-camera-in-a-modern-office-41543-large.mp4",
        "thumbnail_url": "https://images.unsplash.com/photo-1498050108023-c5249f4df085?auto=format&fit=crop&w=1200&q=85",
        "topic": "Coding basics",
        "caption": "Clean code tip: ek function ko ek clear responsibility do. Small functions are easier to test and reuse. #coding #cleancode",
    },
    {
        "username": "finance.with.riya",
        "media_type": Post.MediaType.IMAGE,
        "media_url": "https://images.unsplash.com/photo-1554224155-6726b3ff858f?auto=format&fit=crop&w=1200&q=85",
        "topic": "Personal finance",
        "caption": "50-30-20 rule se monthly budget start karo, phir apni real needs ke hisaab se categories adjust karo. #finance #budgeting",
    },
    {
        "username": "earth.minute",
        "media_type": Post.MediaType.IMAGE,
        "media_url": "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?auto=format&fit=crop&w=1200&q=85",
        "topic": "Climate science",
        "caption": "Biodiversity ko samajhne ka simple rule: healthy ecosystems me species, soil, water aur climate ek system ki tarah connected hote hain. #climate #science",
    },
]


DEMO_STORIES = [
    ("startup.school", "3 documents before incorporation"),
    ("arjun.codes", "One function, one responsibility"),
    ("finance.with.riya", "Budgeting for beginners"),
    ("earth.minute", "Why biodiversity matters"),
]


class Command(BaseCommand):
    help = "Create or update a small, informative Infogram demo dataset."

    def handle(self, *args, **options):
        users = {}
        for item in DEMO_USERS:
            user, created = User.objects.get_or_create(
                username=item["username"],
                defaults={"email": item["email"]},
            )
            changed = []
            if not user.email:
                user.email = item["email"]
                changed.append("email")
            if user.bio != item["bio"]:
                user.bio = item["bio"]
                changed.append("bio")
            if user.avatar_url != item["avatar_url"]:
                user.avatar_url = item["avatar_url"]
                changed.append("avatar_url")
            if created:
                user.set_unusable_password()
                changed.append("password")
            if changed:
                user.save(update_fields=changed)
            users[user.username] = user

        # Give demo creators a small social graph so Following mode is
        # testable without creating relationships manually.
        for follower in users.values():
            for following in users.values():
                if follower.pk != following.pk:
                    Follow.objects.get_or_create(follower=follower, following=following)

        post_count = 0
        for item in DEMO_POSTS:
            author = users[item["username"]]
            post, _ = Post.objects.update_or_create(
                author=author,
                topic=item["topic"],
                defaults={
                    "media_type": item["media_type"],
                    "media_url": item["media_url"],
                    "thumbnail_url": item.get("thumbnail_url", ""),
                    "caption": item["caption"],
                    "is_published": True,
                },
            )
            sync_hashtags(post)
            post_count += 1

        story_expiry = timezone.now() + timedelta(hours=24)
        story_count = 0
        for username, caption in DEMO_STORIES:
            Story.objects.update_or_create(
                author=users[username],
                caption=caption,
                defaults={
                    "media_type": Story.MediaType.IMAGE,
                    "media_url": users[username].avatar_url,
                    "expires_at": story_expiry,
                },
            )
            story_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(users)} demo creators, {post_count} posts and {story_count} stories."
            )
        )

