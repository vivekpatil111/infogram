from datetime import timedelta

from django.utils import timezone

from accounts.models import Follow
from config.testutils import InfogramAPITestCase
from notifications.models import Notification
from stories.models import Story


class PrivateAccountTests(InfogramAPITestCase):
    def setUp(self):
        super().setUp()
        self.owner = self.make_user("private.creator", is_private=True)
        self.fan = self.make_user("fan")
        self.post = self.make_post(self.owner, caption="members only #secret")
        self.video = self.make_post(self.owner, media_type="video", media_url="https://cdn.example.com/v.mp4")
        Story.objects.create(
            author=self.owner, media_type="image", media_url="https://cdn.example.com/s.jpg",
            expires_at=timezone.now() + timedelta(hours=24),
        )
        self.fan_client = self.as_user(self.fan)

    def fan_get(self, url):
        self.client.force_authenticate(self.fan)
        return self.client.get(url)

    def owner_client(self):
        self.client.force_authenticate(self.owner)
        return self.client

    def assert_content_hidden(self):
        self.assertEqual(self.fan_get(f"/api/v1/posts/{self.post.id}/").status_code, 404)
        self.assertEqual(self.fan_get("/api/v1/feed/").data["results"], [])
        self.assertEqual(self.fan_get("/api/v1/reels/").data["results"], [])
        self.assertEqual(self.fan_get("/api/v1/explore/").data["results"], [])
        self.assertEqual(self.fan_get("/api/v1/stories/").data["results"], [])
        self.assertEqual(self.fan_get("/api/v1/search/?q=members&type=posts").data["posts"], [])
        self.client.force_authenticate(self.fan)
        self.assertEqual(self.client.post(f"/api/v1/posts/{self.post.id}/like/").status_code, 404)

    def test_private_content_hidden_from_non_followers(self):
        self.assert_content_hidden()
        profile = self.fan_get("/api/v1/users/private.creator/profile/")
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(profile.data["results"], [])
        self.assertTrue(profile.data["profile"]["is_private"])
        self.assertFalse(profile.data["profile"]["can_view_content"])
        self.assertEqual(profile.data["profile"]["posts_count"], 2)  # counts stay visible
        self.assertEqual(self.fan_get("/api/v1/users/private.creator/followers/").status_code, 403)
        # The account itself is still discoverable in search.
        users = self.fan_get("/api/v1/search/?q=private&type=users").data["users"]
        self.assertEqual([(u["username"], u["is_private"]) for u in users], [("private.creator", True)])

    def test_owner_sees_own_private_content(self):
        client = self.owner_client()
        profile = client.get("/api/v1/users/private.creator/profile/").data
        self.assertEqual(profile["profile"]["follow_status"], "self")
        self.assertEqual(len(profile["results"]), 2)

    def test_request_accept_flow(self):
        self.client.force_authenticate(self.fan)
        response = self.client.post("/api/v1/users/private.creator/follow/")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["follow_status"], "requested")
        self.assertFalse(response.data["following"])
        self.assertEqual(self.fan_get("/api/v1/users/private.creator/").data["follow_status"], "requested")
        self.assertEqual(self.fan_get("/api/v1/users/private.creator/").data["followers_count"], 0)
        self.assert_content_hidden()  # pending is not access

        owner = self.owner_client()
        items = owner.get("/api/v1/notifications/").data
        self.assertEqual([(i["notification_type"], i["text"]) for i in items], [("follow_request", "requested to follow you.")])
        requests = owner.get("/api/v1/follow-requests/").data
        self.assertEqual((requests["count"], requests["results"][0]["username"]), (1, "fan"))

        self.assertEqual(owner.post("/api/v1/follow-requests/FAN/accept/").status_code, 200)
        self.assertEqual(owner.get("/api/v1/follow-requests/").data["count"], 0)
        self.assertEqual([i["notification_type"] for i in owner.get("/api/v1/notifications/").data], ["follow"])
        self.assertEqual(
            Notification.objects.get(recipient=self.fan).notification_type, "follow_accept"
        )

        profile = self.fan_get("/api/v1/users/private.creator/profile/").data
        self.assertEqual(profile["profile"]["follow_status"], "following")
        self.assertEqual(len(profile["results"]), 2)
        feed = self.fan_get("/api/v1/feed/").data["results"]
        self.assertEqual({p["id"] for p in feed}, {self.post.id, self.video.id})
        self.assertEqual(len(self.fan_get("/api/v1/stories/").data["results"]), 1)

    def test_decline_and_cancel(self):
        self.client.force_authenticate(self.fan)
        self.client.post("/api/v1/users/private.creator/follow/")
        self.assertEqual(self.owner_client().post("/api/v1/follow-requests/fan/decline/").status_code, 200)
        self.assertFalse(Follow.objects.exists())
        self.assertFalse(Notification.objects.exists())
        self.assertEqual(self.owner_client().post("/api/v1/follow-requests/fan/accept/").status_code, 404)

        self.client.force_authenticate(self.fan)
        self.client.post("/api/v1/users/private.creator/follow/")
        cancel = self.client.delete("/api/v1/users/private.creator/follow/")
        self.assertEqual(cancel.data["follow_status"], "none")
        self.assertFalse(Follow.objects.exists())
        self.assertFalse(Notification.objects.exists())

    def test_going_public_approves_pending_requests(self):
        self.client.force_authenticate(self.fan)
        self.client.post("/api/v1/users/private.creator/follow/")
        owner = self.owner_client()
        response = owner.patch("/api/v1/auth/me/", {"is_private": False}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["is_private"])
        self.assertEqual(Follow.objects.get().status, "accepted")
        self.assertEqual(Notification.objects.get().notification_type, "follow")

    def test_going_private_keeps_existing_followers_and_remove_follower(self):
        public = self.make_user("public.creator")
        Follow.objects.create(follower=self.fan, following=public)
        post = self.make_post(public)
        self.client.force_authenticate(public)
        self.client.patch("/api/v1/auth/me/", {"is_private": True}, format="json")
        self.assertEqual(self.fan_get(f"/api/v1/posts/{post.id}/").status_code, 200)

        self.client.force_authenticate(public)
        self.assertEqual(self.client.delete("/api/v1/users/fan/follower/").status_code, 204)
        self.assertEqual(self.fan_get(f"/api/v1/posts/{post.id}/").status_code, 404)

    def test_public_follow_is_immediate(self):
        public = self.make_user("public.creator")
        self.client.force_authenticate(self.fan)
        response = self.client.post("/api/v1/users/public.creator/follow/")
        self.assertEqual((response.data["follow_status"], response.data["following"]), ("following", True))
        self.assertEqual(Notification.objects.get(recipient=public).notification_type, "follow")
