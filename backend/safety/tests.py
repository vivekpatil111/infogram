import re
from datetime import timedelta

from django.contrib.admin.sites import AdminSite
from django.core import mail
from django.test import RequestFactory, override_settings
from django.utils import timezone

from accounts.models import Follow
from config.testutils import PASSWORD, InfogramAPITestCase
from messaging.models import Conversation, ConversationMember
from notifications.models import Notification
from posts.models import Comment
from safety.admin import ReportAdmin, dismiss, remove_content
from safety.models import Block, Report
from stories.models import Story


class BlockTests(InfogramAPITestCase):
    def setUp(self):
        super().setUp()
        self.me = self.make_user("me.user")
        self.troll = self.make_user("troll")
        Follow.objects.create(follower=self.me, following=self.troll)
        Follow.objects.create(follower=self.troll, following=self.me)
        self.my_post = self.make_post(self.me, caption="my tip")
        self.troll_post = self.make_post(self.troll, caption="troll tip")
        Story.objects.create(author=self.troll, media_type="image", media_url="https://cdn.example.com/s.jpg",
                             expires_at=timezone.now() + timedelta(hours=1))
        Comment.objects.create(post=self.my_post, author=self.troll, text="mean")
        Notification.objects.create(recipient=self.me, actor=self.troll, notification_type="follow")

    def client_for(self, user):
        self.client.force_authenticate(user)
        return self.client

    def test_block_cuts_graph_hides_content_both_ways(self):
        response = self.client_for(self.me).post("/api/v1/users/troll/block/")
        self.assertEqual(response.status_code, 201)
        self.assertFalse(Follow.objects.exists())
        self.assertFalse(Notification.objects.exists())

        me = self.client_for(self.me)
        self.assertEqual(me.get(f"/api/v1/posts/{self.troll_post.id}/").status_code, 404)
        self.assertEqual([p["id"] for p in me.get("/api/v1/feed/").data["results"]], [self.my_post.id])
        self.assertEqual(me.get("/api/v1/stories/").data["results"], [])
        self.assertEqual(me.get(f"/api/v1/posts/{self.my_post.id}/comments/").data["results"], [])
        self.assertEqual(me.get("/api/v1/search/?q=troll&type=users").data["users"], [])
        profile = me.get("/api/v1/users/troll/profile/").data
        self.assertTrue(profile["profile"]["is_blocked"])
        self.assertFalse(profile["profile"]["can_view_content"])
        self.assertEqual(profile["results"], [])
        self.assertEqual([b["username"] for b in me.get("/api/v1/blocks/").data["results"]], ["troll"])

        troll = self.client_for(self.troll)
        self.assertEqual(troll.get("/api/v1/users/me.user/").status_code, 404)  # "User not found"
        self.assertEqual(troll.get(f"/api/v1/posts/{self.my_post.id}/").status_code, 404)
        self.assertEqual(troll.post(f"/api/v1/posts/{self.my_post.id}/like/").status_code, 404)
        self.assertEqual(troll.post(f"/api/v1/posts/{self.my_post.id}/comments/", {"text": "x"}, format="json").status_code, 404)
        self.assertEqual(troll.post("/api/v1/conversations/", {"participant_ids": [self.me.id]}, format="json").status_code, 403)

    def test_blocked_user_cannot_follow_and_unblock_does_not_refollow(self):
        Block.objects.create(blocker=self.me, blocked=self.troll)
        Follow.objects.all().delete()
        # The troll can't even resolve the profile; I can't follow while blocking.
        self.assertEqual(self.client_for(self.troll).post("/api/v1/users/me.user/follow/").status_code, 404)
        self.assertEqual(self.client_for(self.me).post("/api/v1/users/troll/follow/").status_code, 403)
        self.client_for(self.me).delete("/api/v1/users/troll/block/")
        self.assertFalse(Block.objects.exists())
        self.assertFalse(Follow.objects.exists())

    def test_existing_dm_is_frozen(self):
        conversation = Conversation.objects.create()
        ConversationMember.objects.bulk_create(
            [ConversationMember(conversation=conversation, user=u) for u in (self.me, self.troll)]
        )
        self.client_for(self.me).post("/api/v1/users/troll/block/")
        response = self.client_for(self.troll).post(
            f"/api/v1/conversations/{conversation.id}/messages/", {"body": "hey"}, format="json"
        )
        self.assertEqual(response.status_code, 403)

    def test_no_new_notifications_across_a_block(self):
        Block.objects.create(blocker=self.troll, blocked=self.me)
        Notification.objects.all().delete()
        # Troll's post is invisible to me, so I can't like it; and my own
        # actions on others don't notify the troll.
        self.assertEqual(self.client_for(self.me).post(f"/api/v1/posts/{self.troll_post.id}/like/").status_code, 404)
        self.assertFalse(Notification.objects.exists())


class MuteTests(InfogramAPITestCase):
    def test_mute_posts_and_stories_separately(self):
        me, loud = self.make_user("me.user"), self.make_user("loud")
        Follow.objects.create(follower=me, following=loud)
        post = self.make_post(loud)
        Story.objects.create(author=loud, media_type="image", media_url="https://cdn.example.com/s.jpg",
                             expires_at=timezone.now() + timedelta(hours=1))
        client = self.as_user(me)

        client.post("/api/v1/users/loud/mute/", {"posts": True, "stories": False}, format="json")
        self.assertEqual(client.get("/api/v1/feed/").data["results"], [])
        self.assertEqual(len(client.get("/api/v1/stories/").data["results"]), 1)
        # Muting is silent: still following, profile and post still reachable.
        profile = client.get("/api/v1/users/loud/profile/").data
        self.assertEqual((profile["profile"]["follow_status"], profile["profile"]["posts_muted"]), ("following", True))
        self.assertEqual(len(profile["results"]), 1)
        self.assertEqual(client.get(f"/api/v1/posts/{post.id}/").status_code, 200)

        client.post("/api/v1/users/loud/mute/", {"stories": True}, format="json")  # partial: posts stay muted
        self.assertEqual(client.get("/api/v1/stories/").data["results"], [])
        self.assertEqual(client.get("/api/v1/feed/").data["results"], [])
        client.delete("/api/v1/users/loud/mute/")
        self.assertEqual(len(client.get("/api/v1/feed/").data["results"]), 1)


class ReportTests(InfogramAPITestCase):
    def setUp(self):
        super().setUp()
        self.reporter = self.make_user("reporter")
        self.author = self.make_user("author")
        self.post = self.make_post(self.author, caption="buy followers now")
        self.client = self.as_user(self.reporter)

    def test_report_post_is_idempotent_while_open(self):
        payload = {"target_type": "post", "target_id": str(self.post.id), "reason": "spam", "details": "link farm"}
        first = self.client.post("/api/v1/reports/", payload, format="json")
        self.assertEqual(first.status_code, 201, first.data)
        again = self.client.post("/api/v1/reports/", payload, format="json")
        self.assertEqual((again.status_code, again.data["id"]), (200, first.data["id"]))
        report = Report.objects.get()
        self.assertEqual((report.target_owner, report.post, report.status), (self.author, self.post, "open"))

    def test_report_targets_and_validation(self):
        comment = Comment.objects.create(post=self.post, author=self.author, text="rude")
        ok = [
            {"target_type": "comment", "target_id": str(comment.id), "reason": "harassment"},
            {"target_type": "user", "target_id": "AUTHOR", "reason": "impersonation"},
        ]
        for payload in ok:
            self.assertEqual(self.client.post("/api/v1/reports/", payload, format="json").status_code, 201, payload)
        bad = [
            ({"target_type": "post", "target_id": "999999", "reason": "spam"}, 404),
            ({"target_type": "post", "target_id": str(self.post.id), "reason": "made-up"}, 400),
            ({"target_type": "user", "target_id": "reporter", "reason": "spam"}, 400),  # yourself
        ]
        for payload, code in bad:
            self.assertEqual(self.client.post("/api/v1/reports/", payload, format="json").status_code, code, payload)
        private = self.make_user("hidden", is_private=True)
        hidden_post = self.make_post(private)
        self.assertEqual(
            self.client.post("/api/v1/reports/", {"target_type": "post", "target_id": str(hidden_post.id), "reason": "spam"}, format="json").status_code,
            404,
        )
        self.assertTrue(any(r["value"] == "spam" for r in self.client.get("/api/v1/reports/reasons/").data))

    def test_moderation_actions_close_all_reports_on_target(self):
        second = self.make_user("second")
        for user in (self.reporter, second):
            Report.objects.create(reporter=user, target_type="post", post=self.post, target_owner=self.author, reason="spam")
        moderator = self.make_user("mod", is_staff=True, is_superuser=True)
        request = RequestFactory().post("/admin/")
        request.user = moderator
        model_admin = ReportAdmin(Report, AdminSite())
        model_admin.message_user = lambda *args, **kwargs: None
        listing = model_admin.get_queryset(request)
        self.assertEqual(model_admin.open_on_target(listing.first()), 2)

        remove_content(model_admin, request, Report.objects.filter(reporter=self.reporter))
        self.post.refresh_from_db()
        self.assertFalse(self.post.is_published)
        self.assertEqual(set(Report.objects.values_list("status", flat=True)), {"actioned"})

        other = self.make_post(self.author)
        Report.objects.create(reporter=self.reporter, target_type="post", post=other, target_owner=self.author, reason="spam")
        dismiss(model_admin, request, Report.objects.filter(post=other))
        self.assertEqual(Report.objects.get(post=other).status, "dismissed")


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", FRONTEND_URL="http://app.test")
class PasswordResetTests(InfogramAPITestCase):
    def reset_link_parts(self):
        body = mail.outbox[-1].body
        match = re.search(r"http://app\.test/reset-password\?uid=([\w-]+)&token=([\w-]+)", body)
        self.assertIsNotNone(match, body)
        return match.group(1), match.group(2)

    def test_full_reset_flow_logs_out_other_sessions(self):
        user = self.make_user("forgetful")
        login = self.client.post("/api/v1/auth/login/", {"username": "forgetful", "password": PASSWORD}, format="json").data

        response = self.client.post("/api/v1/auth/password-reset/", {"email": "FORGETFUL@example.com"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        uid, token = self.reset_link_parts()

        weak = self.client.post("/api/v1/auth/password-reset/confirm/", {"uid": uid, "token": token, "new_password": "password"}, format="json")
        self.assertEqual(weak.status_code, 400)
        done = self.client.post("/api/v1/auth/password-reset/confirm/", {"uid": uid, "token": token, "new_password": "Brand-New-Pass-42"}, format="json")
        self.assertEqual(done.status_code, 200, done.data)
        user.refresh_from_db()
        self.assertTrue(user.check_password("Brand-New-Pass-42"))

        reused = self.client.post("/api/v1/auth/password-reset/confirm/", {"uid": uid, "token": token, "new_password": "Another-Pass-77"}, format="json")
        self.assertEqual(reused.status_code, 400)  # single use
        self.assertEqual(self.client.post("/api/v1/auth/refresh/", {"refresh": login["refresh"]}, format="json").status_code, 401)

    def test_unknown_email_gets_same_answer_and_no_mail(self):
        response = self.client.post("/api/v1/auth/password-reset/", {"email": "nobody@example.com"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)
        bad = self.client.post("/api/v1/auth/password-reset/confirm/", {"uid": "xx", "token": "yy", "new_password": "Brand-New-Pass-42"}, format="json")
        self.assertEqual(bad.status_code, 400)

    def test_change_password_keeps_this_device(self):
        user = self.make_user("changer")
        client = self.as_user(user)
        wrong = client.post("/api/v1/auth/password/change/", {"current_password": "nope", "new_password": "Brand-New-Pass-42"}, format="json")
        self.assertEqual(wrong.status_code, 400)
        ok = client.post("/api/v1/auth/password/change/", {"current_password": PASSWORD, "new_password": "Brand-New-Pass-42"}, format="json")
        self.assertEqual(ok.status_code, 200)
        self.assertIn("refresh", ok.data)
        user.refresh_from_db()
        self.assertTrue(user.check_password("Brand-New-Pass-42"))
