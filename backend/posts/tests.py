from datetime import timedelta
from urllib.parse import parse_qs, urlparse

from django.utils import timezone

from accounts.models import Follow
from config.testutils import InfogramAPITestCase
from notifications.models import Notification
from posts.models import Comment, Post, PostLike


class PostCrudTests(InfogramAPITestCase):
    def setUp(self):
        super().setUp()
        self.me = self.make_user("me.user")
        self.other = self.make_user("other")
        self.client = self.as_user(self.me)

    def test_create_single_post_extracts_hashtags(self):
        response = self.client.post(
            "/api/v1/posts/",
            {"media_type": "image", "media_url": "https://cdn.example.com/x.jpg", "topic": "Startup", "caption": "Register first #Startup #legal #startup"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(sorted(response.data["hashtags"]), ["legal", "startup"])
        self.assertEqual(response.data["author"]["username"], "me.user")
        for field in ("like_count", "comment_count", "save_count", "liked_by_me", "saved_by_me"):
            self.assertIn(field, response.data)

    def test_create_carousel(self):
        slides = [
            {"media_type": "image", "media_url": "https://cdn.example.com/1.jpg"},
            {"media_type": "video", "media_url": "https://cdn.example.com/2.mp4", "thumbnail_url": "https://cdn.example.com/2.jpg"},
        ]
        response = self.client.post("/api/v1/posts/", {"media": slides, "caption": "Two slides"}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["media_type"], "carousel")
        self.assertEqual(response.data["media_url"], "https://cdn.example.com/1.jpg")  # cover for old clients
        self.assertEqual([s["position"] for s in response.data["media"]], [0, 1])

        one = self.client.post("/api/v1/posts/", {"media": slides[:1]}, format="json")
        self.assertEqual(one.status_code, 400)

    def test_create_requires_media(self):
        self.assertEqual(self.client.post("/api/v1/posts/", {"caption": "x"}, format="json").status_code, 400)
        bad = {"media_type": "carousel", "media_url": "https://cdn.example.com/x.jpg"}
        self.assertEqual(self.client.post("/api/v1/posts/", bad, format="json").status_code, 400)

    def test_only_owner_can_edit_or_delete(self):
        post = self.make_post(self.other)
        self.assertEqual(self.client.patch(f"/api/v1/posts/{post.id}/", {"caption": "hack"}, format="json").status_code, 403)
        self.assertEqual(self.client.delete(f"/api/v1/posts/{post.id}/").status_code, 403)
        mine = self.make_post(self.me)
        response = self.client.patch(f"/api/v1/posts/{mine.id}/", {"caption": "now #tagged"}, format="json")
        self.assertEqual(response.data["hashtags"], ["tagged"])
        self.assertEqual(self.client.delete(f"/api/v1/posts/{mine.id}/").status_code, 204)

    def test_unpublished_posts_hidden_from_others(self):
        draft = self.make_post(self.other, is_published=False)
        self.assertEqual(self.client.get(f"/api/v1/posts/{draft.id}/").status_code, 404)
        self.assertEqual(self.client.post(f"/api/v1/posts/{draft.id}/like/").status_code, 404)


class EngagementTests(InfogramAPITestCase):
    def setUp(self):
        super().setUp()
        self.me = self.make_user("me.user")
        self.author = self.make_user("author")
        self.post = self.make_post(self.author)
        self.client = self.as_user(self.me)

    def test_like_toggle_and_counts(self):
        self.assertEqual(self.client.post(f"/api/v1/posts/{self.post.id}/like/").status_code, 201)
        self.assertEqual(self.client.post(f"/api/v1/posts/{self.post.id}/like/").status_code, 200)  # idempotent
        data = self.client.get(f"/api/v1/posts/{self.post.id}/").data
        self.assertEqual((data["like_count"], data["liked_by_me"]), (1, True))
        self.assertEqual(Notification.objects.filter(notification_type="like").count(), 1)

        self.client.delete(f"/api/v1/posts/{self.post.id}/like/")
        data = self.client.get(f"/api/v1/posts/{self.post.id}/").data
        self.assertEqual((data["like_count"], data["liked_by_me"]), (0, False))
        self.assertFalse(Notification.objects.exists())  # unlike removes the activity item

    def test_counts_do_not_multiply_across_relations(self):
        fans = [self.make_user(f"fan{i}") for i in range(3)]
        for fan in fans:
            PostLike.objects.create(post=self.post, user=fan)
            Comment.objects.create(post=self.post, author=fan, text="useful")
            Comment.objects.create(post=self.post, author=fan, text="thanks")
        data = self.client.get(f"/api/v1/posts/{self.post.id}/").data
        self.assertEqual((data["like_count"], data["comment_count"]), (3, 6))

    def test_save_toggle(self):
        self.assertEqual(self.client.post(f"/api/v1/posts/{self.post.id}/save/").data, {"saved": True, "created": True})
        self.assertEqual(self.client.delete(f"/api/v1/posts/{self.post.id}/save/").data, {"saved": False})

    def test_comments_create_list_delete(self):
        response = self.client.post(f"/api/v1/posts/{self.post.id}/comments/", {"text": "  Great breakdown  "}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["text"], "Great breakdown")
        comment_id = response.data["id"]
        notification = Notification.objects.get(notification_type="comment")
        self.assertEqual(notification.recipient, self.author)

        listing = self.client.get(f"/api/v1/posts/{self.post.id}/comments/").data
        self.assertEqual([c["id"] for c in listing["results"]], [comment_id])

        self.assertEqual(self.client.post(f"/api/v1/posts/{self.post.id}/comments/", {"text": "   "}, format="json").status_code, 400)

        stranger = self.make_user("stranger")
        self.assertEqual(
            self.as_user(stranger).delete(f"/api/v1/posts/{self.post.id}/comments/{comment_id}/").status_code, 403
        )
        # The post owner can moderate comments on their post.
        self.assertEqual(
            self.as_user(self.author).delete(f"/api/v1/posts/{self.post.id}/comments/{comment_id}/").status_code, 204
        )
        self.assertFalse(Notification.objects.exists())

    def test_self_actions_do_not_notify(self):
        mine = self.make_post(self.me)
        self.client.post(f"/api/v1/posts/{mine.id}/like/")
        self.assertFalse(Notification.objects.exists())


class FeedTests(InfogramAPITestCase):
    def setUp(self):
        super().setUp()
        self.me = self.make_user("me.user")
        self.friend = self.make_user("friend")
        self.stranger = self.make_user("stranger")
        Follow.objects.create(follower=self.me, following=self.friend)
        self.client = self.as_user(self.me)

    def ids(self, response):
        return [item["id"] for item in response.data["results"]]

    def test_for_you_shows_network_first_then_suggested(self):
        popular = self.make_post(self.stranger, caption="viral")
        for i in range(5):
            PostLike.objects.create(post=popular, user=self.make_user(f"liker{i}"))
        friend_post = self.make_post(self.friend)
        own_post = self.make_post(self.me)

        response = self.client.get("/api/v1/feed/")
        self.assertEqual(response.status_code, 200)
        ids = self.ids(response)
        self.assertEqual(set(ids[:2]), {friend_post.id, own_post.id})
        self.assertEqual(ids[2], popular.id)
        flags = {item["id"]: item["is_suggested"] for item in response.data["results"]}
        self.assertEqual(flags, {friend_post.id: False, own_post.id: False, popular.id: True})

    def test_new_account_still_gets_suggested_posts(self):
        lonely = self.make_user("lonely")
        post = self.make_post(self.stranger)
        response = self.as_user(lonely).get("/api/v1/feed/")
        self.assertEqual(self.ids(response), [post.id])

    def test_following_mode_excludes_strangers(self):
        friend_post = self.make_post(self.friend)
        self.make_post(self.stranger)
        self.assertEqual(self.ids(self.client.get("/api/v1/feed/?mode=following")), [friend_post.id])
        self.assertEqual(self.client.get("/api/v1/feed/?mode=bogus").status_code, 400)

    def test_cursor_pages_are_stable_while_scores_change(self):
        posts = [self.make_post(self.stranger, caption=f"p{i}") for i in range(5)]
        first = self.client.get("/api/v1/feed/?limit=2")
        seen = self.ids(first)
        # Engagement changes between page loads must not reshuffle later pages.
        last = Post.objects.exclude(id__in=seen).order_by("id").last()
        for i in range(10):
            PostLike.objects.create(post=last, user=self.make_user(f"late{i}"))
        response, next_url = first, first.data["next"]
        while next_url:
            query = parse_qs(urlparse(next_url).query)
            response = self.client.get("/api/v1/feed/", {"limit": 2, "cursor": query["cursor"][0]})
            seen += self.ids(response)
            next_url = response.data["next"]
        self.assertEqual(sorted(seen), sorted(p.id for p in posts))
        self.assertEqual(len(seen), len(set(seen)))
        self.assertIsNotNone(response.data["previous"])

    def test_invalid_and_expired_cursors(self):
        self.assertEqual(self.client.get("/api/v1/feed/?cursor=not-base64!").status_code, 400)
        from posts.feed_snapshot import _encode_cursor

        expired = self.client.get("/api/v1/feed/", {"cursor": _encode_cursor("missing", 20)})
        self.assertEqual(expired.status_code, 400)
        self.assertEqual(expired.data["code"], "cursor_expired")

    def test_topic_filter_matches_topic_caption_and_hashtag(self):
        tagged = self.client.post(
            "/api/v1/posts/",
            {"media_type": "image", "media_url": "https://cdn.example.com/t.jpg", "caption": "Read this #finance"},
            format="json",
        ).data["id"]
        self.make_post(self.friend, topic="Coding")
        ids = self.ids(self.client.get("/api/v1/feed/?topic=%23finance"))
        self.assertEqual(ids, [tagged])

    def test_fresher_posts_rank_higher_at_equal_engagement(self):
        old = self.make_post(self.friend)
        Post.objects.filter(id=old.id).update(created_at=timezone.now() - timedelta(days=10))
        new = self.make_post(self.friend)
        self.assertEqual(self.ids(self.client.get("/api/v1/feed/?mode=following")), [new.id, old.id])

    def test_reels_feed_videos_only(self):
        friend_video = self.make_post(self.friend, media_type="video", media_url="https://cdn.example.com/a.mp4")
        stranger_video = self.make_post(self.stranger, media_type="video", media_url="https://cdn.example.com/b.mp4")
        self.make_post(self.friend)
        ids = self.ids(self.client.get("/api/v1/reels/?feed=for_you"))
        self.assertEqual(set(ids), {friend_video.id, stranger_video.id})
        self.assertEqual(self.ids(self.client.get("/api/v1/reels/?feed=following")), [friend_video.id])


class AuthorFollowStatusTests(InfogramAPITestCase):
    def test_post_author_follow_status(self):
        me, friend, stranger = self.make_user("me.user"), self.make_user("friend"), self.make_user("stranger")
        Follow.objects.create(follower=me, following=friend)
        posts = {self.make_post(u).id: u.username for u in (me, friend, stranger)}
        results = self.as_user(me).get("/api/v1/feed/").data["results"]
        status = {posts[p["id"]]: p["author"]["follow_status"] for p in results}
        self.assertEqual(status, {"me.user": "self", "friend": "following", "stranger": "none"})
