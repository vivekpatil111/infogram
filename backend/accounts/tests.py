from accounts.models import Follow
from config.testutils import PASSWORD, InfogramAPITestCase
from notifications.models import Notification


class AuthTests(InfogramAPITestCase):
    def test_register_login_refresh_logout_flow(self):
        response = self.client.post(
            "/api/v1/auth/register/",
            {"username": "Vasu.Py", "email": "Vasu@Example.com", "password": PASSWORD},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["username"], "vasu.py")  # stored lowercase

        # Login accepts username (any case) or email.
        for identifier in ("VASU.PY", "vasu@example.com"):
            login = self.client.post("/api/v1/auth/login/", {"username": identifier, "password": PASSWORD}, format="json")
            self.assertEqual(login.status_code, 200, login.data)
            self.assertIn("access", login.data)

        refreshed = self.client.post("/api/v1/auth/refresh/", {"refresh": login.data["refresh"]}, format="json")
        self.assertEqual(refreshed.status_code, 200)
        self.assertIn("refresh", refreshed.data)  # rotated

        # The rotated-out token is blacklisted.
        reused = self.client.post("/api/v1/auth/refresh/", {"refresh": login.data["refresh"]}, format="json")
        self.assertEqual(reused.status_code, 401)

        logout = self.client.post("/api/v1/auth/logout/", {"refresh": refreshed.data["refresh"]}, format="json")
        self.assertEqual(logout.status_code, 205)
        after = self.client.post("/api/v1/auth/refresh/", {"refresh": refreshed.data["refresh"]}, format="json")
        self.assertEqual(after.status_code, 401)

    def test_register_validation(self):
        self.make_user("taken.name")
        cases = [
            ({"username": "TAKEN.NAME", "email": "x@example.com", "password": PASSWORD}, "username"),
            ({"username": "bad name!", "email": "y@example.com", "password": PASSWORD}, "username"),
            ({"username": ".dotstart", "email": "z@example.com", "password": PASSWORD}, "username"),
            ({"username": "fresh.name", "email": "taken_name@EXAMPLE.com", "password": PASSWORD}, "email"),
            ({"username": "fresh.name", "email": "w@example.com", "password": "password"}, "password"),
            ({"username": "fresh.name", "email": "w@example.com", "password": "12345678901"}, "password"),
        ]
        for payload, field in cases:
            response = self.client.post("/api/v1/auth/register/", payload, format="json")
            self.assertEqual(response.status_code, 400, payload)
            self.assertIn(field, response.data, payload)

    def test_me_get_and_patch(self):
        user = self.make_user("asha")
        client = self.as_user(user)
        self.assertEqual(client.get("/api/v1/auth/me/").data["username"], "asha")
        response = client.patch("/api/v1/auth/me/", {"bio": "Teaches finance", "avatar_url": "https://a.example.com/x.png"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["bio"], "Teaches finance")

    def test_unauthenticated_requests_are_rejected(self):
        self.assertEqual(self.client.get("/api/v1/feed/").status_code, 401)


class SocialGraphTests(InfogramAPITestCase):
    def setUp(self):
        super().setUp()
        self.me = self.make_user("me.user")
        self.creator = self.make_user("startup.school")
        self.client = self.as_user(self.me)

    def test_follow_unfollow_removes_notification(self):
        response = self.client.post("/api/v1/users/startup.school/follow/")
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Notification.objects.filter(recipient=self.creator, notification_type="follow").exists())
        self.assertEqual(self.client.post("/api/v1/users/startup.school/follow/").status_code, 200)

        self.client.delete("/api/v1/users/startup.school/follow/")
        self.assertFalse(Follow.objects.exists())
        self.assertFalse(Notification.objects.exists())

    def test_cannot_follow_self(self):
        self.assertEqual(self.client.post("/api/v1/users/me.user/follow/").status_code, 400)

    def test_profile_counts_and_tabs(self):
        Follow.objects.create(follower=self.me, following=self.creator)
        self.make_post(self.creator)
        video = self.make_post(self.creator, media_type="video", media_url="https://cdn.example.com/v.mp4")
        self.make_post(self.creator, is_published=False)

        response = self.client.get("/api/v1/users/Startup.School/profile/?tab=posts")
        self.assertEqual(response.status_code, 200)
        profile = response.data["profile"]
        self.assertEqual((profile["posts_count"], profile["followers_count"], profile["is_following"]), (2, 1, True))
        self.assertEqual(len(response.data["results"]), 2)

        reels = self.client.get("/api/v1/users/startup.school/profile/?tab=reels").data["results"]
        self.assertEqual([item["id"] for item in reels], [video.id])

        self.assertEqual(self.client.get("/api/v1/users/startup.school/profile/?tab=saved").status_code, 403)

    def test_saved_tab_shows_my_saved_posts_from_anyone(self):
        post = self.make_post(self.creator)
        self.client.post(f"/api/v1/posts/{post.id}/save/")
        saved = self.client.get("/api/v1/users/me.user/profile/?tab=saved").data["results"]
        self.assertEqual([item["id"] for item in saved], [post.id])

    def test_followers_and_following_lists(self):
        Follow.objects.create(follower=self.me, following=self.creator)
        followers = self.client.get("/api/v1/users/startup.school/followers/")
        self.assertEqual(followers.status_code, 200)
        self.assertEqual([u["username"] for u in followers.data["results"]], ["me.user"])
        following = self.client.get("/api/v1/users/me.user/following/")
        self.assertEqual(following.status_code, 200)
        self.assertEqual([u["username"] for u in following.data["results"]], ["startup.school"])


class SuggestionTests(InfogramAPITestCase):
    def test_suggestions_rank_mutuals_and_skip_followed(self):
        me = self.make_user("me.user")
        friend = self.make_user("friend")
        mutual_pick = self.make_user("friend.of.friend")
        popular = self.make_user("popular")
        requested = self.make_user("locked", is_private=True)
        Follow.objects.create(follower=me, following=friend)
        Follow.objects.create(follower=friend, following=mutual_pick)
        for i in range(3):
            Follow.objects.create(follower=self.make_user(f"fan{i}"), following=popular)
        Follow.objects.create(follower=me, following=requested, status="pending")

        results = self.as_user(me).get("/api/v1/users/suggested/?limit=3").data["results"]
        names = [r["username"] for r in results]
        self.assertEqual(names[:2], ["friend.of.friend", "popular"])
        self.assertEqual(results[0]["followed_by"], "friend")
        self.assertNotIn("friend", names)
        self.assertNotIn("locked", names)
        self.assertNotIn("me.user", names)
        self.assertEqual(self.as_user(me).get("/api/v1/users/suggested/?limit=abc").status_code, 200)

    def test_profile_top_topics(self):
        me = self.make_user("me.user")
        for topic in ("Finance", "Finance", "Coding", ""):
            self.make_post(me, topic=topic)
        profile = self.as_user(me).get("/api/v1/users/me.user/profile/").data["profile"]
        self.assertEqual(profile["top_topics"], ["Finance", "Coding"])
