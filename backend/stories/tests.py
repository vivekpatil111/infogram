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


class StoryStickerTests(InfogramAPITestCase):
    def test_stickers_validate_mentions_notify_and_polls_count(self):
        from accounts.models import Follow
        from notifications.models import Notification

        author, friend, voter = self.make_user("storyteller"), self.make_user("friend"), self.make_user("voter")
        Follow.objects.create(follower=voter, following=author)
        body = {"media_type": "image", "media_url": "https://cdn.example.com/s.jpg", "stickers": [
            {"type": "mention", "username": "@Friend", "x": 20, "y": 30},
            {"type": "link", "url": "example.com/guide", "label": "Read the guide", "x": 50, "y": 80},
            {"type": "poll", "question": "Did this help?", "options": ["Yes", "Not yet"], "x": 140, "y": -5},
        ]}
        created = self.as_user(author).post("/api/v1/stories/", body, format="json")
        self.assertEqual(created.status_code, 201, created.data)
        stickers = created.data["stickers"]
        self.assertEqual(stickers[0]["username"], "friend")
        self.assertEqual(stickers[1]["url"], "https://example.com/guide")
        self.assertEqual((stickers[2]["x"], stickers[2]["y"]), (100.0, 0.0))
        self.assertTrue(Notification.objects.filter(recipient=friend, notification_type="story_mention").exists())

        story_id = created.data["id"]
        tray = self.as_user(voter).get("/api/v1/stories/").data["results"][0]["stories"][0]
        self.assertNotIn("counts", tray["stickers"][2])  # results hidden until you vote
        voted = self.as_user(voter).post(f"/api/v1/stories/{story_id}/vote/", {"option": 1}, format="json").data
        poll = voted["stickers"][2]
        self.assertEqual((poll["my_vote"], poll["counts"]), (1, [0, 1]))
        self.as_user(voter).post(f"/api/v1/stories/{story_id}/vote/", {"option": 0}, format="json")  # can't change
        mine = self.as_user(author).get("/api/v1/stories/").data["results"][0]["stories"][0]["stickers"][2]
        self.assertEqual(mine["counts"], [0, 1])

        bad = [
            [{"type": "mention", "username": "nobody_here"}],
            [{"type": "link", "url": "javascript:alert(1)"}],
            [{"type": "poll", "question": "Q", "options": ["only one"]}],
            [{"type": "poll", "question": "A", "options": ["1", "2"]}, {"type": "poll", "question": "B", "options": ["1", "2"]}],
            [{"type": "link", "url": "e.com"}] * 4,
        ]
        for stickers in bad:
            self.assertEqual(self.as_user(author).post("/api/v1/stories/", {**body, "stickers": stickers}, format="json").status_code, 400, stickers)


class ProblemReportTests(InfogramAPITestCase):
    def test_problem_reports_are_stored(self):
        from safety.models import ProblemReport

        me = self.make_user("reporter")
        self.assertEqual(self.as_user(me).post("/api/v1/support/problems/", {"message": "bad"}, format="json").status_code, 400)
        ok = self.as_user(me).post("/api/v1/support/problems/", {"message": "Upload button does nothing", "page": "/explore"}, format="json")
        self.assertEqual(ok.status_code, 201)
        self.assertEqual(ProblemReport.objects.get().page, "/explore")
