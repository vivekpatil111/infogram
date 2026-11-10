from config.testutils import InfogramAPITestCase
from posts.models import PostView


class LearningPathTests(InfogramAPITestCase):
    def setUp(self):
        super().setUp()
        self.creator = self.make_user("lawyer")
        self.learner = self.make_user("student")
        self.lessons = [self.make_post(self.creator, caption=f"Lesson {i}") for i in range(3)]

    def create_path(self, ids=None, **extra):
        body = {"title": "  Mastering   Startup Law ", "vertical": "law", "post_ids": ids or [p.id for p in self.lessons], **extra}
        return self.as_user(self.creator).post("/api/v1/paths/", body, format="json")

    def test_create_lists_and_reads_with_progress(self):
        created = self.create_path()
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual((created.data["title"], created.data["lesson_count"]), ("Mastering Startup Law", 3))
        path_id = created.data["id"]

        listing = self.as_user(self.learner).get("/api/v1/paths/", {"creator": "lawyer"}).data
        self.assertEqual([p["id"] for p in listing], [path_id])

        PostView.objects.create(post=self.lessons[0], user=self.learner)
        detail = self.as_user(self.learner).get(f"/api/v1/paths/{path_id}/").data
        self.assertEqual([p["caption"] for p in detail["lessons"]], ["Lesson 0", "Lesson 1", "Lesson 2"])
        self.assertEqual(detail["progress"], {"seen": 1, "total": 3})
        self.assertEqual(detail["next_post_id"], self.lessons[1].id)

        # Posts know which path they belong to.
        post = self.as_user(self.learner).get(f"/api/v1/posts/{self.lessons[1].id}/").data
        self.assertEqual(post["paths"], [{"id": path_id, "title": "Mastering Startup Law", "position": 2, "total": 3}])

    def test_only_own_posts_and_only_the_creator_can_edit(self):
        foreign = self.make_post(self.learner)
        self.assertEqual(self.create_path([self.lessons[0].id, foreign.id]).status_code, 400)
        self.assertEqual(self.create_path([self.lessons[0].id, self.lessons[0].id]).status_code, 400)
        path_id = self.create_path().data["id"]
        self.assertEqual(self.as_user(self.learner).patch(f"/api/v1/paths/{path_id}/", {"title": "Mine"}, format="json").status_code, 403)
        reordered = self.as_user(self.creator).patch(f"/api/v1/paths/{path_id}/", {"post_ids": [self.lessons[2].id, self.lessons[0].id]}, format="json")
        self.assertEqual(reordered.data["lesson_count"], 2)
        detail = self.as_user(self.creator).get(f"/api/v1/paths/{path_id}/").data
        self.assertEqual([p["id"] for p in detail["lessons"]], [self.lessons[2].id, self.lessons[0].id])

    def test_private_creator_locks_lessons_for_non_followers(self):
        path_id = self.create_path().data["id"]
        self.creator.is_private = True
        self.creator.save()
        detail = self.as_user(self.learner).get(f"/api/v1/paths/{path_id}/").data
        self.assertTrue(detail["locked"])
        self.assertEqual(detail["lessons"], [])


class ResourceDrawerTests(InfogramAPITestCase):
    def test_resources_are_validated_saved_in_order_and_counted(self):
        author, reader = self.make_user("guide"), self.make_user("reader")
        body = {
            "media_type": "image", "media_url": "https://cdn.example.com/a.jpg",
            "resources": [
                {"kind": "link", "title": "Official site", "url": "https://gov.example/register"},
                {"kind": "checklist", "title": "Documents", "items": ["PAN card", "  ", "Address proof"]},
                {"kind": "pdf", "title": "Guide", "url": "https://cdn.example.com/guide.pdf"},
            ],
        }
        created = self.as_user(author).post("/api/v1/posts/", body, format="json")
        self.assertEqual(created.status_code, 201, created.data)
        post_id = created.data["id"]
        seen = self.as_user(reader).get(f"/api/v1/posts/{post_id}/").data["resources"]
        self.assertEqual([r["kind"] for r in seen], ["link", "checklist", "pdf"])
        self.assertEqual(seen[1]["items"], ["PAN card", "Address proof"])
        self.assertNotIn("open_count", seen[0])  # stats are for the creator only

        self.as_user(reader).post(f"/api/v1/posts/{post_id}/resources/{seen[0]['id']}/open/")
        mine = self.as_user(author).get(f"/api/v1/posts/{post_id}/").data["resources"]
        self.assertEqual(mine[0]["open_count"], 1)

        bad_cases = [
            [{"kind": "link", "title": "x", "url": "javascript:alert(1)"}],
            [{"kind": "checklist", "title": "Empty", "items": []}],
            [{"kind": "link", "title": "  ", "url": "https://e.com"}],
            [{"kind": "link", "title": f"t{i}", "url": "https://e.com"} for i in range(6)],
        ]
        for resources in bad_cases:
            response = self.as_user(author).post("/api/v1/posts/", {**body, "resources": resources}, format="json")
            self.assertEqual(response.status_code, 400, resources)
