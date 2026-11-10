from datetime import timedelta

from django.utils import timezone

from accounts.models import Follow
from config.testutils import InfogramAPITestCase
from stories.models import Story, StoryView


class StoryTests(InfogramAPITestCase):
    def setUp(self):
        super().setUp()
        self.me = self.make_user("me.user")
        self.seen_friend = self.make_user("seen.friend")
        self.fresh_friend = self.make_user("fresh.friend")
        self.stranger = self.make_user("stranger")
        for friend in (self.seen_friend, self.fresh_friend):
            Follow.objects.create(follower=self.me, following=friend)
        self.client = self.as_user(self.me)

    def story(self, author, **extra):
        return Story.objects.create(
            author=author,
            media_type="image",
            media_url="https://cdn.example.com/s.jpg",
            expires_at=extra.pop("expires_at", timezone.now() + timedelta(hours=24)),
            **extra,
        )

    def test_tray_order_own_then_unseen_then_seen(self):
        seen = self.story(self.seen_friend)
        StoryView.objects.create(story=seen, user=self.me)
        self.story(self.fresh_friend)
        self.story(self.me)
        self.story(self.stranger)  # not followed: hidden
        self.story(self.fresh_friend, expires_at=timezone.now() - timedelta(minutes=1))  # expired

        groups = self.client.get("/api/v1/stories/").data["results"]
        self.assertEqual([g["author"]["username"] for g in groups], ["me.user", "fresh.friend", "seen.friend"])
        self.assertTrue(groups[0]["is_own"])
        self.assertEqual([g["has_unseen"] for g in groups[1:]], [True, False])
        self.assertEqual(len(groups[1]["stories"]), 1)

    def test_resume_index_points_at_first_unseen(self):
        first = self.story(self.fresh_friend)
        self.story(self.fresh_friend)
        StoryView.objects.create(story=first, user=self.me)
        group = self.client.get("/api/v1/stories/").data["results"][0]
        self.assertEqual(group["resume_index"], 1)

    def test_create_view_and_viewers(self):
        response = self.client.post(
            "/api/v1/stories/", {"media_type": "image", "media_url": "https://cdn.example.com/n.jpg"}, format="json"
        )
        self.assertEqual(response.status_code, 201, response.data)
        story_id = response.data["id"]

        Follow.objects.create(follower=self.seen_friend, following=self.me)
        friend_client = self.as_user(self.seen_friend)
        self.assertEqual(friend_client.post(f"/api/v1/stories/{story_id}/view/").status_code, 201)
        self.assertEqual(friend_client.post(f"/api/v1/stories/{story_id}/view/").status_code, 200)
        self.assertEqual(friend_client.get(f"/api/v1/stories/{story_id}/viewers/").status_code, 403)
        self.assertEqual(friend_client.delete(f"/api/v1/stories/{story_id}/").status_code, 403)

        viewers = self.as_user(self.me).get(f"/api/v1/stories/{story_id}/viewers/").data
        self.assertEqual([v["username"] for v in viewers["results"]], ["seen.friend"])
