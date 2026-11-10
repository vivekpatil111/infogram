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


class ProfileLinksTests(InfogramAPITestCase):
    def test_links_are_normalised_validated_and_public(self):
        me = self.make_user("linker")
        response = self.as_user(me).patch("/api/v1/auth/me/", {"links": [{"title": " My   blog ", "url": "example.com/blog"}, {"url": "https://github.com/linker"}]}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["links"], [{"title": "My blog", "url": "https://example.com/blog"}, {"title": "", "url": "https://github.com/linker"}])
        for bad in ([{"url": "javascript:alert(1)"}], [{"url": "notalink"}], [{"url": f"https://e{i}.com"} for i in range(6)]):
            self.assertEqual(self.as_user(me).patch("/api/v1/auth/me/", {"links": bad}, format="json").status_code, 400, bad)
        other = self.make_user("visitor")
        profile = self.as_user(other).get("/api/v1/users/linker/profile/").data["profile"]
        self.assertEqual(len(profile["links"]), 2)


class ExpertVerificationTests(InfogramAPITestCase):
    def test_apply_once_then_staff_approval_shows_the_badge(self):
        from accounts.models import ExpertApplication

        me = self.make_user("ca.priya")
        url = "/api/v1/auth/expert-application/"
        self.assertIsNone(self.as_user(me).get(url).data["application"])
        bad = self.as_user(me).post(url, {"vertical": "astrology", "title": "x", "evidence_url": "https://e.com"}, format="json")
        self.assertEqual(bad.status_code, 400)
        body = {"vertical": "finance", "title": "Chartered Accountant", "evidence_url": "https://icai.example/priya"}
        self.assertEqual(self.as_user(me).post(url, body, format="json").status_code, 201)
        self.assertEqual(self.as_user(me).post(url, body, format="json").status_code, 409)
        # Users can't verify themselves through /auth/me/.
        self.as_user(me).patch("/api/v1/auth/me/", {"is_verified": True, "expert_title": "Hacker"}, format="json")
        me.refresh_from_db()
        self.assertFalse(me.is_verified)

        ExpertApplication.objects.get(user=me).approve()
        me.refresh_from_db()  # force_authenticate keeps the object we pass in
        status = self.as_user(me).get(url).data
        self.assertEqual((status["is_verified"], status["expert_vertical"], status["application"]["status"]), (True, "finance", "approved"))
        viewer = self.make_user("reader")
        post = self.make_post(me)
        author = self.as_user(viewer).get(f"/api/v1/posts/{post.id}/").data["author"]
        self.assertEqual((author["is_verified"], author["expert_title"]), (True, "Chartered Accountant"))
        profile = self.as_user(viewer).get("/api/v1/users/ca.priya/profile/").data["profile"]
        self.assertTrue(profile["is_verified"])


class TwoFactorTests(InfogramAPITestCase):
    def test_totp_matches_rfc6238_vector(self):
        import base64

        from accounts import totp

        secret = base64.b32encode(b"12345678901234567890").decode()
        # RFC 6238 Appendix B, SHA-1, T=59 -> 94287082 (8 digits); 6-digit tail is 287082.
        self.assertEqual(totp.code_for(secret, now=59), "287082")

    def test_setup_enable_login_with_code_recovery_and_disable(self):
        from accounts import totp

        me = self.make_user("secure.sam")
        setup = self.as_user(me).post("/api/v1/auth/2fa/setup/").data
        self.assertTrue(setup["otpauth_uri"].startswith("otpauth://totp/Infogram%3Asecure.sam?secret="))
        self.assertEqual(self.as_user(me).post("/api/v1/auth/2fa/enable/", {"code": "000000"}, format="json").status_code, 400)
        me.refresh_from_db()
        enabled = self.as_user(me).post("/api/v1/auth/2fa/enable/", {"code": totp.code_for(setup["secret"], now=__import__("time").time() - 30)}, format="json")
        self.assertEqual(enabled.status_code, 200, enabled.data)
        recovery = enabled.data["recovery_codes"]
        self.assertEqual(len(recovery), 8)

        self.client.force_authenticate(None)
        first = self.client.post("/api/v1/auth/login/", {"username": "secure.sam", "password": PASSWORD}, format="json").data
        self.assertTrue(first["two_factor_required"])
        self.assertNotIn("access", first)
        # The code used to enable can't be replayed; the current one works.
        code = totp.code_for(setup["secret"])
        tokens = self.client.post("/api/v1/auth/2fa/verify/", {"challenge": first["challenge"], "code": code}, format="json")
        self.assertEqual(tokens.status_code, 200, tokens.data)
        self.assertIn("access", tokens.data)
        replay = self.client.post("/api/v1/auth/2fa/verify/", {"challenge": first["challenge"], "code": code}, format="json")
        self.assertEqual(replay.status_code, 400)

        # A recovery code works once.
        second = self.client.post("/api/v1/auth/login/", {"username": "secure.sam", "password": PASSWORD}, format="json").data
        ok = self.client.post("/api/v1/auth/2fa/verify/", {"challenge": second["challenge"], "code": recovery[0].upper()}, format="json")
        self.assertEqual(ok.status_code, 200)
        again = self.client.post("/api/v1/auth/2fa/verify/", {"challenge": second["challenge"], "code": recovery[0]}, format="json")
        self.assertEqual(again.status_code, 400)
        bad = self.client.post("/api/v1/auth/2fa/verify/", {"challenge": "forged", "code": recovery[1]}, format="json")
        self.assertEqual(bad.status_code, 400)

        me.refresh_from_db()
        off = self.as_user(me).post("/api/v1/auth/2fa/disable/", {"password": PASSWORD, "code": recovery[1]}, format="json")
        self.assertEqual(off.data, {"enabled": False})
        self.client.force_authenticate(None)
        plain = self.client.post("/api/v1/auth/login/", {"username": "secure.sam", "password": PASSWORD}, format="json").data
        self.assertIn("access", plain)
