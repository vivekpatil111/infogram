from config.testutils import InfogramAPITestCase


class PushNotificationTests(InfogramAPITestCase):
    def setUp(self):
        super().setUp()
        self.me = self.make_user("pushy")
        self.friend = self.make_user("friend2")

    def subscribe(self, user, endpoint="https://push.example.com/sub/1"):
        return self.as_user(user).post("/api/v1/notifications/push/", {"endpoint": endpoint, "keys": {"p256dh": "BPk", "auth": "xyz"}}, format="json")

    def test_subscribe_requires_server_keys(self):
        from django.test import override_settings

        with override_settings(VAPID_PUBLIC_KEY="", VAPID_PRIVATE_KEY=""):
            self.assertFalse(self.as_user(self.me).get("/api/v1/notifications/push/").data["enabled"])
            self.assertEqual(self.subscribe(self.me).status_code, 503)

    def test_activity_and_messages_are_pushed_and_dead_subscriptions_dropped(self):
        from unittest import mock

        from django.test import override_settings

        from notifications.models import PushSubscription
        from notifications.push import _deliver

        with override_settings(VAPID_PUBLIC_KEY="pub", VAPID_PRIVATE_KEY="priv"):
            info = self.as_user(self.me).get("/api/v1/notifications/push/").data
            self.assertEqual((info["enabled"], info["public_key"]), (True, "pub"))
            self.assertEqual(self.subscribe(self.me).status_code, 201)
            self.assertEqual(self.subscribe(self.me).status_code, 201)  # same device: no duplicate
            self.assertEqual(PushSubscription.objects.count(), 1)
            self.assertEqual(self.as_user(self.me).post("/api/v1/notifications/push/", {"endpoint": "http://insecure", "keys": {"p256dh": "a", "auth": "b"}}, format="json").status_code, 400)

            with mock.patch("notifications.push.send_to_user") as send, self.captureOnCommitCallbacks(execute=True):
                post = self.make_post(self.me)
                self.as_user(self.friend).post(f"/api/v1/posts/{post.id}/like/")
            send.assert_called_once()
            self.assertEqual(send.call_args.kwargs["body"], "friend2 liked your post.")
            self.assertEqual(send.call_args.kwargs["url"], f"/post/{post.id}")

            conversation = self.as_user(self.friend).post("/api/v1/conversations/", {"participant_ids": [self.me.id]}, format="json").data
            with mock.patch("notifications.push.send_to_user") as send:
                self.as_user(self.friend).post(f"/api/v1/conversations/{conversation['id']}/messages/", {"body": "hi there"}, format="json")
            send.assert_called_once_with(self.me.id, title="friend2", body="hi there", url="/messages", tag=f"c{conversation['id']}")

            # A 410 from the push service removes the subscription.
            from pywebpush import WebPushException

            gone = WebPushException("gone", response=mock.Mock(status_code=410))
            with mock.patch("pywebpush.webpush", side_effect=gone):
                _deliver(self.me.id, {"title": "x"})
            self.assertFalse(PushSubscription.objects.exists())
