from accounts.models import Follow
from config.testutils import InfogramAPITestCase
from notifications.models import Notification
from posts.hashtags import sync_hashtags


class DiscoveryTests(InfogramAPITestCase):
    def setUp(self):
        super().setUp()
        self.me = self.make_user("me.user")
        self.followed = self.make_user("followed")
        self.creator = self.make_user("startup.school", bio="Startup basics")
        self.make_user("my.startup.notes")
        Follow.objects.create(follower=self.me, following=self.followed)
        self.client = self.as_user(self.me)

    def test_search_users_ranks_prefix_first(self):
        response = self.client.get("/api/v1/search/?q=startup&type=all")
        self.assertEqual(response.status_code, 200)
        usernames = [u["username"] for u in response.data["users"]]
        self.assertEqual(usernames[0], "startup.school")
        self.assertIn("my.startup.notes", usernames)
        for key in ("followers_count", "bio", "avatar_url", "id"):
            self.assertIn(key, response.data["users"][0])

    def test_search_hashtags_and_posts(self):
        post = self.make_post(self.creator, caption="Register first #startuplaw")
        sync_hashtags(post)
        response = self.client.get("/api/v1/search/", {"q": "#startup"})
        self.assertEqual(response.data["hashtags"], [{"name": "startuplaw", "post_count": 1}])
        self.assertEqual(response.data["users"], [])
        posts = self.client.get("/api/v1/search/", {"q": "#startuplaw", "type": "posts"}).data["posts"]
        self.assertEqual([p["id"] for p in posts], [post.id])

    def test_search_validation(self):
        self.assertEqual(self.client.get("/api/v1/search/?q=a").status_code, 400)
        self.assertEqual(self.client.get("/api/v1/search/?q=abc&type=nope").status_code, 400)

    def test_explore_excludes_me_and_followed(self):
        self.make_post(self.me)
        self.make_post(self.followed)
        discover = self.make_post(self.creator)
        response = self.client.get("/api/v1/explore/")
        self.assertEqual([p["id"] for p in response.data["results"]], [discover.id])

    def test_topics(self):
        self.make_post(self.creator, topic="Finance")
        self.make_post(self.creator, topic="Finance")
        self.make_post(self.creator, topic="Coding")
        self.assertEqual(self.client.get("/api/v1/topics/").data["topics"], ["Finance", "Coding"])


class NotificationTests(InfogramAPITestCase):
    def test_list_read_and_counts(self):
        me = self.make_user("me.user")
        fan = self.make_user("fan")
        post = self.make_post(me)
        fan_client = self.as_user(fan)
        fan_client.post(f"/api/v1/posts/{post.id}/like/")
        fan_client.post(f"/api/v1/posts/{post.id}/comments/", {"text": "This is a great breakdown!"}, format="json")

        client = self.as_user(me)
        items = client.get("/api/v1/notifications/").data
        self.assertEqual([i["notification_type"] for i in items], ["comment", "like"])
        self.assertEqual(items[0]["text"], "commented: This is a great breakdown!")
        self.assertEqual(items[0]["actor"]["username"], "fan")
        self.assertEqual(client.get("/api/v1/notifications/unread-count/").data["notifications"], 2)

        client.post(f"/api/v1/notifications/{items[0]['id']}/read/")
        self.assertEqual(client.get("/api/v1/notifications/unread-count/").data["notifications"], 1)
        self.assertEqual(client.post("/api/v1/notifications/read-all/").data["updated"], 1)

        # Deleting the post removes its activity.
        client.delete(f"/api/v1/posts/{post.id}/")
        self.assertFalse(Notification.objects.exists())
